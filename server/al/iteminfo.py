"""ITEM-INFO-CORE (decision 0083, decision 0082 part 1): the item info
lookup behind the shared item popover.

One exact item name (case and spacing folded, at most NAME_MAX
characters, no control character) is looked up in what is already cached
on this computer; nothing goes on the network:

- the repoe-fork base_items snapshot (decision 0009; the sidecar cache the
  snapshot tool fills): "item_class" (in words, "Stackable Currency"),
  "stack_size" (only above 1), "full_stack_turns_into" (the name of the
  base a full stack becomes), "description" and "directions" (markup like
  "[ItemRarity|Rare]" read as its plain text), "release_state" (only when
  it is not "released");
- the repoe-fork uniques snapshot (in snapshot.SOURCES): "rarity"
  "Unique", its "item_class" and a "release_state" that is not "released".
  Rarity is never given to anything else (currency has none);
- the poe.ninja price book (decision 0026: the Currency rates, then the
  unique and stackable overviews), only while web data is on (decision
  0013) and only for the current league: "market" {value, unit, divine
  (the value in Divine Orbs when the cached rates give that rate),
  change_7d, listings, few, volume, league, age_s, credit "Prices:
  poe.ninja"}, plus the unique's "icon" URL and "flavour" text when the
  cache holds them;
- ITEM-INFO-GEM-DETAIL (decision 0083 amendment 2026-11-28): "gem" for a
  skill, spirit or support gem name, from the per-gem files the snapshot
  tool derives from the cached repoe-fork skill_gems / skills / gem_tags
  export (theorycraft/gemdetail.py, the gem_details folder beside
  base_items): kind, tags, cast time, max_level and, for one gem level
  (lookup's `level`, default 1), costs, spirit, cooldown, cost multiplier
  and each stat set's worded lines; its "description" fills the item's
  description when base_items has none. Source id "repoe-fork";
- ITEM-INFO-POB-TEXT (decision 0083 points 1 and 3): "where_found"
  {drops: [{boss, zone?, map?}], no_longer_obtainable?} from the Source
  lines of the hash-pinned Path of Building PoE2 checkout, text-parsed by
  theorycraft/pobtext.py, only while the optional calc component is
  installed and each file matches its config/tc_pins.json pin; source id
  "path-of-building". It never gives a name spelling, rarity, class or
  release state (repoe-fork wins). Only the core's own lookup (the base
  list at its default sidecar path) reads the checkout; a test runtime
  reads none unless a reader is passed.

A field with no source is absent, never guessed (no drop_level, drop
rates, vendor or disenchant data; decision 0083 points 2 and 5). The
reply is {"name", "fields", "sources"}: the cached spelling of the name
(else the asked one), the fields found, and the source ids that gave them
("repoe-fork", "path-of-building", "poe.ninja"), so the popover credits only what it shows.
An unknown name answers with empty fields.

The tables are hot reloaded (decision 0042) and built on the first look,
not at core start: base_items shares the parse of the core's base list
(RUN-PERF-PARSE-ONCE, hotreload share=True). Standard library only; this
module imports no network code.
"""

import re
import time
from pathlib import Path

from . import hotreload, num
from .text import iteminfo as text
from .theorycraft import gemdetail, pobtext

NAME_MAX = 120          # the price book keeps names to 120 characters too
TEXT_MAX = 600          # description / directions
MAX_BYTES = 64 * 1024 * 1024    # = basetypes.MAX_BYTES (one shared parse)
UNIQUES_MAX_BYTES = 16 * 1024 * 1024
UNIQUES_NAME = "uniques.json"
RELEASED = "released"
CREDIT = text.CREDIT
REPOE, NINJA = "repoe-fork", "poe.ninja"
POB = pobtext.SOURCE_ID
AUTO = object()   # ItemInfo(pob=AUTO): the pinned checkout for the core only
DIVINE_ID, DIVINE_NAME = "divine", "divine orb"
_MARKUP = re.compile(r"\[([^\[\]|]*)\|([^\[\]]*)\]|\[([^\[\]]*)\]")
_CLASS_SPLIT = re.compile(r"(?<=[a-z])(?=[A-Z])")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_STATE = re.compile(r"[a-z_]{1,32}")


def key(value):
    """The match key of a name: spacing folded, lower case."""
    return " ".join(value.split()).lower() if isinstance(value, str) else ""


def clean_name(name):
    """The asked name with its spacing folded; ValueError when it is not a
    string, empty, longer than NAME_MAX or holds a control character."""
    if not isinstance(name, str):
        raise ValueError(text.NO_NAME)
    if len(name) > NAME_MAX:
        raise ValueError(text.name_long(NAME_MAX))
    if _CONTROL.search(name):
        raise ValueError(text.ONE_LINE)
    folded = " ".join(name.split())
    if not folded:
        raise ValueError(text.NO_NAME)
    return folded


def plain(raw):
    """repoe-fork text with its [Id|Shown] / [Shown] markup read as the
    shown words, spacing kept per line, at most TEXT_MAX characters; None
    for no text."""
    if not isinstance(raw, str):
        return None

    def shown(m):
        return m.group(2) if m.group(2) is not None else (m.group(3) or "")
    out = _MARKUP.sub(shown, raw)
    out = "\n".join(" ".join(line.split()) for line in out.splitlines())
    out = out.strip()
    return out[:TEXT_MAX] if out else None


def class_words(item_class):
    """repoe-fork's item class id in words ("StackableCurrency" ->
    "Stackable Currency"); None for none."""
    if not isinstance(item_class, str) or not item_class.strip():
        return None
    return " ".join(_CLASS_SPLIT.sub(" ", item_class.strip()).split())[:60]


def _state(entry):
    s = entry.get("release_state")
    return s if isinstance(s, str) and _STATE.fullmatch(s) and s != RELEASED else None


def _int(v):
    v = num.finite(v)
    return int(v) if v is not None and v == int(v) else None


def bases_from_doc(doc):
    """{"by_key": {key: fields}, "names": {metadata id: name}} from a
    parsed base_items document; a released entry wins a name clash."""
    by_key, names, released = {}, {}, set()
    if not isinstance(doc, dict):
        return {"by_key": by_key, "names": names}
    for mid, entry in doc.items():
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        name = " ".join(name.split())
        if isinstance(mid, str):
            names.setdefault(mid, name)
        k = name.lower()
        state = _state(entry)
        if k in by_key and (k in released or state is not None):
            continue
        props = entry.get("properties") if isinstance(entry.get("properties"), dict) else {}
        fields = {"name": name}
        words = class_words(entry.get("item_class"))
        if words:
            fields["item_class"] = words
        stack = _int(props.get("stack_size"))
        if stack is not None and stack > 1:
            fields["stack_size"] = stack
        turns = props.get("full_stack_turns_into")
        if isinstance(turns, str) and turns:
            fields["_turns"] = turns
        for f in ("description", "directions"):
            words_of = plain(props.get(f))
            if words_of:
                fields[f] = words_of
        if state:
            fields["release_state"] = state
        by_key[k] = fields
        if state is None:
            released.add(k)
    return {"by_key": by_key, "names": names}


def uniques_from_doc(doc):
    """{key: fields} from a parsed uniques document (an object of entries
    or a list of them; an entry needs a name)."""
    out = {}
    entries = doc.values() if isinstance(doc, dict) else doc if isinstance(doc, list) else ()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        name = " ".join(name.split())
        k = name.lower()
        if k in out and entry.get("is_alternate_art") is True:
            continue
        fields = {"name": name, "rarity": text.UNIQUE}
        words = class_words(entry.get("item_class"))
        if words:
            fields["item_class"] = words
        state = _state(entry)
        if state:
            fields["release_state"] = state
        out[k] = fields
    return out


def _empty_bases():
    return {"by_key": {}, "names": {}}


def _default_bases_path():
    from .theorycraft import basetypes  # lazy: only for the AUTO check
    return basetypes.default_path()


def auto_pob(bases_path):
    """A pobtext.WhereFound for the core's own lookup (its base list at the
    default sidecar path), else None (a test or demo runtime)."""
    try:
        if Path(bases_path).resolve() != _default_bases_path().resolve():
            return None
    except (OSError, ValueError, TypeError):
        return None
    return pobtext.WhereFound()


class ItemInfo:
    """The lookup over the cached tables. `rates`: ninja.RatesClient (its
    doc, book and enabled switch) or None. `pob`: a pobtext.WhereFound (or
    any object with lookup(key)), None for none, AUTO (the default) for
    auto_pob(bases_path). `gems`: a gemdetail.GemDetails (or any object
    with lookup(key, level)), None for none, AUTO (the default) for the
    gem_details folder beside bases_path."""

    def __init__(self, bases_path, uniques_path, rates=None, clock=time.time,
                 pob=AUTO, gems=AUTO):
        self.rates = rates
        self.clock = clock
        self.pob = auto_pob(bases_path) if pob is AUTO else pob
        self.gems = (gemdetail.GemDetails(Path(bases_path).with_name(gemdetail.DIR_NAME))
                     if gems is AUTO else gems)
        self.bases = hotreload.Watched(
            bases_path, None, name=text.BASES_NAME, default=_empty_bases,
            check=hotreload.check_json(MAX_BYTES), from_doc=bases_from_doc,
            share=True, registry=False)
        self.uniques = hotreload.Watched(
            uniques_path, None, name=text.UNIQUES_NAME, default=dict,
            check=hotreload.check_json(UNIQUES_MAX_BYTES, kind=(dict, list)),
            from_doc=uniques_from_doc, registry=False)

    # -- poe.ninja (cache only, web data on)
    def _web_on(self):
        r = self.rates
        if r is None:
            return False
        enabled = getattr(r, "enabled", None)
        try:
            return bool(enabled() if callable(enabled) else enabled)
        except Exception:  # noqa: BLE001 - unknown counts as off
            return False

    def _price(self, k):
        """(hit, rates doc) from the Currency rates, then the book; None."""
        doc = getattr(self.rates, "doc", None)
        doc = doc if isinstance(doc, dict) else {}
        league = doc.get("league")
        if not isinstance(league, str) or not league:
            return None, doc
        rates = doc.get("rates") if isinstance(doc.get("rates"), dict) else {}
        for entry in rates.values():
            if isinstance(entry, dict) and key(entry.get("name")) == k:
                primary = doc.get("primary")
                unit = (rates.get(primary) or {}).get("name") or primary
                return ({"name": entry.get("name"), "value": entry.get("value"),
                         "unit": unit, "primary": primary,
                         "volume": entry.get("volume"), "league": league,
                         "checked_at": doc.get("checked_at")}, doc)
        book = getattr(self.rates, "book", None)
        info = getattr(book, "info", None)
        if not callable(info):
            return None, doc
        return info(k, league=league), doc

    def _divine(self, hit, doc):
        value = num.finite(hit.get("value"))
        if value is None:
            return None
        rates = doc.get("rates") if isinstance(doc.get("rates"), dict) else {}
        div_id = None
        for rid, entry in rates.items():
            if rid == DIVINE_ID or (isinstance(entry, dict)
                                    and key(entry.get("name")) == DIVINE_NAME):
                div_id = rid
                break
        if div_id is None:
            return None
        if hit.get("primary") == div_id:
            return value
        dv = num.finite((rates.get(div_id) or {}).get("value"))
        if hit.get("primary") == doc.get("primary") and dv and dv > 0:
            return round(value / dv, 6)
        return None

    def _market(self, hit, doc):
        value = num.finite(hit.get("value"))
        if value is None:
            return None
        m = {"value": value, "credit": CREDIT}
        if isinstance(hit.get("unit"), str):
            m["unit"] = hit["unit"]
        divine = self._divine(hit, doc)
        if divine is not None:
            m["divine"] = divine
        change = num.finite(hit.get("change"))
        if change is not None:
            m["change_7d"] = change
        if isinstance(hit.get("listings"), int):
            m["listings"] = hit["listings"]
            m["few"] = bool(hit.get("few"))
        volume = num.finite(hit.get("volume"))
        if volume is not None:
            m["volume"] = volume
        if isinstance(hit.get("league"), str):
            m["league"] = hit["league"]
        at = num.finite(hit.get("checked_at"))
        if at is not None:
            m["age_s"] = max(0, int(self.clock() - at))
        return m

    # -- Path of Building Source lines (pinned text, calc component installed)
    def _where(self, k):
        lookup = getattr(self.pob, "lookup", None)
        if not callable(lookup):
            return None
        try:
            where = lookup(k)
        except Exception:  # noqa: BLE001 - a bad reader omits the field
            return None
        return where if isinstance(where, dict) and where else None

    # -- gem details (derived repoe-fork files)
    def _gem(self, k, level):
        lookup = getattr(self.gems, "lookup", None)
        if not callable(lookup):
            return None
        try:
            gem = lookup(k, level)
        except Exception:  # noqa: BLE001 - a bad reader omits the field
            return None
        return gem if isinstance(gem, dict) and gem else None

    # -- the lookup
    def lookup(self, name, level=None):
        """{"name", "fields", "sources"} for one item name (see the module
        text); ValueError for a name that is not a short line of text.
        level: the gem level a gem's lines are given for (1 to
        gemdetail.LEVEL_MAX, default 1)."""
        asked = clean_name(name)
        k = asked.lower()
        fields, sources, shown = {}, [], None
        bases = self.bases.get() or _empty_bases()
        base = (bases.get("by_key") or {}).get(k)
        unique = (self.uniques.get() or {}).get(k)
        if unique:
            shown = unique["name"]
            fields.update({f: v for f, v in unique.items() if f != "name"})
        if base:
            shown = shown or base["name"]
            for f, v in base.items():
                if f == "name" or (unique and f in ("item_class", "release_state")):
                    continue
                if f == "_turns":
                    turned = (bases.get("names") or {}).get(v)
                    if turned:
                        fields["full_stack_turns_into"] = turned
                    continue
                fields[f] = v
        gem = self._gem(k, level)
        if gem:
            desc = gem.pop("description", None)
            if desc and "description" not in fields:
                fields["description"] = desc
            fields["gem"] = gem
        if fields:
            sources.append(REPOE)
        where = self._where(k)
        if where:
            fields["where_found"] = where
            sources.append(POB)
        if self._web_on():
            hit, doc = self._price(k)
            if isinstance(hit, dict):
                market = self._market(hit, doc)
                if market:
                    fields["market"] = market
                for f in ("icon", "flavour"):
                    if isinstance(hit.get(f), str) and hit[f]:
                        fields[f] = hit[f]
                if market or "icon" in fields or "flavour" in fields:
                    sources.append(NINJA)
                    if not shown and isinstance(hit.get("name"), str):
                        shown = " ".join(hit["name"].split())
        return {"name": shown or asked, "fields": fields, "sources": sources}
