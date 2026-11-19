"""TC-WORN-STORE (decision 0052, ruling Q-26 (a)): the worn-gear baseline.

The player can file the last checked item as the item they wear in its
slot (the wiring is TC-WORN-WIRE; this module is storage only). The item
text comes from the one per-press read of decision 0003; this module never
reads the clipboard, the screen or the game log, and nothing leaves the
machine.

What is kept, per character and slot: the item class, the rarity, the
base type and the parsed mod lines (stat text with roll ranges removed,
plus its section). Never the item name and never the raw item text; a
magic item whose base the parser could not tell apart from its full name
line keeps no base at all.

Bounded like the run history (decision 0036): at most MAX_SLOTS slots per
character (only model.SLOTS names), MAX_CHARACTERS characters (the one
filed to least recently is dropped first), MAX_MODS mod lines of at most
MAX_TEXT characters each; a file over MAX_BYTES reads as empty. One file,
FILE_NAME under the core's runtime dir (ops/runtime, gitignored), written
atomically with one `.bak` of its last good copy (jsonfile, F-014); clear()
empties it and removes the .bak (Clear run history).

A damaged file (and no good .bak) reads as an empty set and is left as it
is on disk: only the next wear() writes the file again.

Slot choice for items with more than one slot (rings, charms, one-hand
weapons of a dual wielder): an explicit slot wins; else the slot the last
item check of this character compared against, when that check's mod
lines match the item being filed; else a slot that already holds the same
mod lines; else an empty slot; else the one filed to longest ago.

`Baseline` answers equipped(slot) from the worn item first and the PoB
plan second, so the item check can compare without a build.
"""

import hashlib
import threading
from pathlib import Path

from .. import jsonfile, paths
from . import item as item_parser
from . import model

FILE_NAME = "worn_gear.json"
SCHEMA = 1
MAX_SLOTS = 16  # per character; model.SLOTS names 15 today
MAX_CHARACTERS = 12
MAX_MODS = 40
MAX_TEXT = 200  # one mod line
MAX_NAME = 64  # one character name, as run history (decision 0036)
MAX_FIELD = 64  # item class, rarity, base
MAX_BYTES = 1024 * 1024
NO_CHARACTER = ""  # wears made before the log names anyone

SOURCE_WORN = "worn"
SOURCE_PLAN = "plan"

_EXPLICIT = "explicit"
# the parser's sections that come back from a "(<tag>)" suffix
_TAGGED = {t.replace(" ", "_"): t for t in item_parser.MOD_TAGS}
# an advanced-mode header that marks the next line as an explicit mod, so a
# mod with no number or a trailing full stop re-parses as a mod
_EXPLICIT_HEADER = "{ Modifier }"
_SLOT_NAMES = {s.lower(): s for s in model.SLOTS}


def default_path(runtime=None):
    """The store file under `runtime` (default: paths.runtime_dir())."""
    root = Path(runtime) if runtime is not None else paths.runtime_dir()
    return root / FILE_NAME


def _text(value, cap=MAX_FIELD):
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value[:cap] if value else None


def _character(name):
    return _text(name, MAX_NAME) or NO_CHARACTER


def slot_name(slot):
    """The model.SLOTS spelling of `slot` (any case), or None."""
    if not isinstance(slot, str):
        return None
    return _SLOT_NAMES.get(" ".join(slot.split()).lower())


def _count(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return min(value, 2 ** 53)


def clean_mods(mods):
    """Bounded [{"text", "section"}] from parsed Mods or stored dicts."""
    out = []
    for m in mods or ():
        if isinstance(m, dict):
            text, section = m.get("text"), m.get("section")
        elif isinstance(m, item_parser.Mod):
            text, section = m.text, m.section
        else:
            continue
        text = _text(text, MAX_TEXT)
        if not text:
            continue
        section = section if section in _TAGGED else _EXPLICIT
        out.append({"text": text, "section": section})
        if len(out) >= MAX_MODS:
            break
    return out


def mods_key(mods):
    """A stable key of mod lines (order kept), for the same-item checks."""
    blob = "\n".join("%s\t%s" % (m["section"], m["text"]) for m in clean_mods(mods))
    return hashlib.sha1(blob.encode("utf-8", "replace")).hexdigest()


def _parsed(item):
    """A ParsedItem from item text or a ParsedItem; None otherwise."""
    if isinstance(item, str):
        return item_parser.parse(item)
    if isinstance(item, item_parser.ParsedItem):
        return item
    return None


def _base_of(parsed):
    base = _text(parsed.base)
    if parsed.rarity == item_parser.MAGIC and not parsed.name:
        # the parser kept the whole magic name line as the base: that line
        # is the item's name, so no base is stored (never the name)
        return None
    return base


def entry_of(item):
    """The stored form of one item ({class, rarity, base, mods}), or None
    when it is not an item. No name, no raw text."""
    parsed = _parsed(item)
    if parsed is None or not parsed.is_item:
        return None
    return {"class": _text(parsed.item_class), "rarity": _text(parsed.rarity),
            "base": _base_of(parsed), "mods": clean_mods(parsed.mods)}


def _clean_entry(raw):
    if not isinstance(raw, dict):
        return None
    entry = {"class": _text(raw.get("class")), "rarity": _text(raw.get("rarity")),
             "base": _text(raw.get("base")), "mods": clean_mods(raw.get("mods")),
             "n": _count(raw.get("n"))}
    if not entry["class"]:
        return None
    return entry


def item_text(entry):
    """Item text rebuilt from a stored entry; item.parse of it gives the
    same item class, rarity, base and mod lines (so the same stats)."""
    lines = []
    if entry.get("class"):
        lines.append("Item Class: %s" % entry["class"])
    if entry.get("rarity"):
        lines.append("Rarity: %s" % entry["rarity"].title())
    if entry.get("base"):
        lines.append(entry["base"])
    mods = entry.get("mods") or []
    if mods:
        lines.append(item_parser.SEPARATOR)
        for m in mods:
            if m["section"] == _EXPLICIT:
                lines.append(_EXPLICIT_HEADER)
                lines.append(m["text"])
            else:
                lines.append("%s (%s)" % (m["text"], _TAGGED[m["section"]]))
    return "\n".join(lines) + "\n"


def as_item(entry):
    """A model.Item (no name, id 0) for an evaluate()-style caller."""
    if not entry:
        return None
    rarity = entry.get("rarity")
    return model.Item(id=0, text=item_text(entry).strip("\n"),
                      rarity=rarity.upper() if rarity else None, name=None,
                      base=entry.get("base"))


def _one_hand(item_class):
    from . import evaluate  # lazy: evaluate may take a Baseline later
    return evaluate._is_one_hand(item_class)


def _class_slots(item_class):
    from . import evaluate
    return evaluate.slots_for_class(item_class)


def _clean_doc(doc):
    """{character: {"n": int, "slots": {slot: entry}}} in file order,
    bounded; anything bad is dropped."""
    out = {}
    chars = doc.get("characters") if isinstance(doc, dict) else None
    if not isinstance(chars, dict):
        return out
    for name, raw in chars.items():
        if not isinstance(raw, dict) or not isinstance(raw.get("slots"), dict):
            continue
        slots = {}
        for slot, e in raw["slots"].items():
            s = slot_name(slot)
            entry = _clean_entry(e)
            if s and entry and s not in slots:
                slots[s] = entry
            if len(slots) >= MAX_SLOTS:
                break
        if not slots:
            continue
        top = max(e["n"] for e in slots.values())
        out[_character(name)] = {"n": max(_count(raw.get("n")), top), "slots": slots}
    while len(out) > MAX_CHARACTERS:
        out.pop(next(iter(out)))
    return out


class WornGear:
    """The worn set of every character and its file. Thread-safe."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        doc = jsonfile.read_json(self.path, max_bytes=MAX_BYTES, kind=dict, backup=True)
        self._by = _clean_doc(doc)
        self._compared = {}  # memory only: character -> (slot, mods key)

    # -- reads

    def characters(self):
        """The character keys with a worn item, filed-to least recently first."""
        with self._lock:
            return list(self._by)

    def worn(self, character):
        """{slot: {"class", "rarity", "base", "mods"}} of one character."""
        with self._lock:
            rows = self._by.get(_character(character))
            if not rows:
                return {}
            return {s: {k: (list(v) if k == "mods" else v) for k, v in e.items() if k != "n"}
                    for s, e in rows["slots"].items()}

    def entry(self, character, slot):
        s = slot_name(slot)
        if s is None:
            return None
        return self.worn(character).get(s)

    def item(self, character, slot):
        """The worn item of a slot as a model.Item, or None."""
        return as_item(self.entry(character, slot))

    # -- writes

    def note_compared(self, character, slot, item):
        """Remember (memory only) the slot the last item check of this
        character compared `item` against; wear() reuses it."""
        s = slot_name(slot)
        entry = entry_of(item)
        with self._lock:
            if s is None or entry is None:
                self._compared.pop(_character(character), None)
                return
            self._compared[_character(character)] = (s, mods_key(entry["mods"]))

    def candidate_slots(self, character, item_class, build=None):
        """The slots an item of `item_class` can be filed in: its class
        slots, plus Weapon 2 for a one-hand weapon when the worn Weapon 2
        (else the build's) holds a one-hand weapon."""
        slots = tuple(_class_slots(item_class))
        if slots == ("Weapon 1",) and _one_hand(item_class):
            w2 = self.entry(character, "Weapon 2")
            if w2 is not None:
                dual = _one_hand(w2.get("class"))
            else:
                held = build.equipped("Weapon 2") if build is not None else None
                dual = bool(held) and _one_hand(item_parser.parse(held.text or "").item_class)
            if dual:
                slots = ("Weapon 1", "Weapon 2")
        return slots

    def choose_slot(self, character, item, slot=None, build=None):
        """The slot wear() would file `item` in, or None when it has none."""
        entry = entry_of(item)
        if entry is None:
            return None
        cands = self.candidate_slots(character, entry["class"], build)
        if not cands:
            return None
        want = slot_name(slot)
        if want is not None:
            ok = want in cands or (want == "Weapon 2" and _one_hand(entry["class"]))
            return want if ok else None
        if len(cands) == 1:
            return cands[0]
        key = mods_key(entry["mods"])
        name = _character(character)
        with self._lock:
            last = self._compared.get(name)
            if last and last[1] == key and last[0] in cands:
                return last[0]
            have = (self._by.get(name) or {}).get("slots", {})
            for s in cands:
                if s in have and mods_key(have[s]["mods"]) == key:
                    return s
            for s in cands:
                if s not in have:
                    return s
            return min(cands, key=lambda s: have[s]["n"])

    def wear(self, character, item, slot=None, build=None):
        """File `item` (item text or a ParsedItem) as the worn item of its
        slot for `character` and save. Returns the slot, or None when the
        item is not gear (nothing changes then)."""
        entry = entry_of(item)
        s = self.choose_slot(character, item, slot=slot, build=build)
        if entry is None or s is None:
            return None
        name = _character(character)
        with self._lock:
            rows = self._by.pop(name, None) or {"n": 0, "slots": {}}
            rows["n"] = _count(rows.get("n")) + 1
            entry["n"] = rows["n"]
            rows["slots"][s] = entry
            self._by[name] = rows
            while len(self._by) > MAX_CHARACTERS:
                self._by.pop(next(iter(self._by)))
            self._save()
        return s

    def remove(self, character, slot):
        """Forget one worn slot (the player took it off). True when it was
        there."""
        s = slot_name(slot)
        name = _character(character)
        with self._lock:
            rows = self._by.get(name)
            if s is None or not rows or s not in rows["slots"]:
                return False
            del rows["slots"][s]
            if not rows["slots"]:
                del self._by[name]
            self._save()
        return True

    def clear(self):
        """Forget every worn item: the file holds an empty set and its .bak
        is removed (Clear run history)."""
        with self._lock:
            self._by = {}
            self._compared = {}
            self._save()
            try:
                jsonfile.bak_path(self.path).unlink(missing_ok=True)
            except OSError:
                pass  # held open: it holds the empty set written just before

    def _save(self):
        doc = {"schema": SCHEMA,
               "characters": {k: {"n": v["n"], "slots": v["slots"]}
                              for k, v in self._by.items()}}
        jsonfile.write_json(self.path, doc, backup=True)


class Baseline:
    """equipped(slot) from the worn item first and the PoB plan second.

    `store`: a WornGear (or None), `character`: the current character,
    `build`: a model.Build (or None)."""

    def __init__(self, store=None, character=None, build=None):
        self.store = store
        self.character = character
        self.build = build

    def worn(self, slot):
        if self.store is None:
            return None
        return self.store.item(self.character, slot)

    def plan(self, slot):
        return self.build.equipped(slot) if self.build is not None else None

    def equipped(self, slot):
        hit = self.worn(slot)
        return hit if hit is not None else self.plan(slot)

    def source(self, slot):
        """"worn", "plan" or None: where equipped(slot) comes from."""
        if self.worn(slot) is not None:
            return SOURCE_WORN
        if self.plan(slot) is not None:
            return SOURCE_PLAN
        return None

    def has_any(self, slots):
        """True when any of `slots` has a worn or planned item."""
        return any(self.source(s) is not None for s in slots or ())
