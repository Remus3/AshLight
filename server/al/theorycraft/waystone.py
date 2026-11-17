"""UTIL-WAYSTONE: flag waystone mods that are risky for the loaded build.

A pure function on the item text of the existing item-check press (the
one per-press clipboard read, decision 0003; nothing here reads the
clipboard or sends anything to the game) and the loaded Path of Building
build's own numbers (`Build.stats`, the PoB PlayerStat values: FireResist,
ColdResist, LightningResist, ChaosResist, Life, EnergyShield).

The rule table `RULES` is AshLight-authored from the mod wording the game
prints (decision 0030); no third-party mod list is copied. Each rule:
- `id`: stable key, also the search-string term key (UTIL-SEARCHSTR);
- `match`: a regex on the lower-cased mod line (roll ranges and tags off);
  a capture group, when present, names the element through `elements`;
- `when`: "always", {"res": <element>|"$1", "below": N} (risky while the
  build's resistance is under N, or unknown), {"defence": "es"|"life"}
  (risky when that pool is at least half of life + energy shield, or
  unknown; no current rule uses it);
- `label`: words for the dashboard sentence ("{el}" is the element,
  "{res}" the build's value); `short`: the overlay card word;
- `avoid`: the search-box term (or tuple of terms) that finds the mod
  (UTIL-SEARCHSTR); a plain lower-case substring of the mod line.
A build stat that is missing reads as unknown, and unknown is risky: the
card would rather say too much than hide a danger.
"""

import re

from . import item as item_parser

RES_CAP = 75
RES_STAT = {"fire": "FireResist", "cold": "ColdResist",
            "lightning": "LightningResist", "chaos": "ChaosResist"}
GROUND = {"ignited": "fire", "chilled": "cold", "shocked": "lightning"}
MAX_MODS = 24
MAX_LINE = 200

# AREA-UTIL b6: every pattern below was checked against the waystone mod
# pool (area-domain prefixes / suffixes with map_key spawn weights) of the
# repoe-fork mods snapshot fetched 2026-11-17 (decision 0009 build-time
# cache, never bundled). Rules whose wording no waystone mod carries (no
# regeneration, curses, reflect, extra projectiles, energy shield
# recharge) were removed; penetration, bleeding, ailments and speed were
# added. tests/test_waystone.py holds one real-shaped line per rule.
RULES = (
    {"id": "extra_element", "short": "Extra {el} dmg",
     "match": r"(?:as extra|extra damage as) (fire|cold|lightning|chaos)\b",
     "when": {"res": "$1", "below": RES_CAP},
     "label": "extra {el} damage ({el} resistance {res})", "avoid": "extra {el}"},
    {"id": "ground", "short": "{El} ground",
     "match": r"patches of (ignited|chilled|shocked) ground",
     "when": {"res": "$1", "below": RES_CAP}, "elements": GROUND,
     "label": "{el} ground ({el} resistance {res})", "avoid": "{word} ground"},
    {"id": "max_res", "short": "Lower max res",
     "match": r"maximum player resistances|-\d+% to (?:all )?maximum resistances",
     "when": "always", "label": "lower maximum resistances", "avoid": "maximum player"},
    {"id": "penetration", "short": "Res penetration",
     "match": r"monsters?\b.*penetrates? .*elemental resistances",
     "when": "always", "label": "monsters penetrate elemental resistances",
     "avoid": "penetrates"},
    {"id": "less_recovery", "short": "Less recovery",
     "match": r"(?:less|reduced) recovery rate of life",
     "when": "always", "label": "less life and energy shield recovery",
     "avoid": "rate of life"},
    {"id": "monster_crit", "short": "Monster crits",
     "match": r"monsters? have .*critical (?:hit chance|damage bonus)",
     "when": "always", "label": "monster critical hits",
     "avoid": ("critical hit chance", "critical damage bonus")},
    {"id": "speed", "short": "Fast monsters",
     "match": r"monsters? have .*increased attack, cast and movement speed",
     "when": "always", "label": "faster monsters", "avoid": "cast and movement"},
    {"id": "poison", "short": "Poison",
     "match": r"monsters? have .*chance to poison",
     "when": {"res": "chaos", "below": 0},
     "label": "monster poison (chaos resistance {res})", "avoid": "to poison"},
    {"id": "bleed", "short": "Bleeding",
     "match": r"monsters? have .*chance to inflict bleeding",
     "when": "always", "label": "monster bleeding", "avoid": "bleeding"},
    {"id": "ailments", "short": "Strong ailments",
     "match": r"monsters? have .*increased elemental ailment application",
     "when": "always", "label": "stronger monster elemental ailments",
     "avoid": "ailment application"},
    {"id": "flasks", "short": "Weak flasks",
     "match": r"(?:less|reduced) flask charges|(?:less|reduced) (?:flask|charm) "
              r"(?:effect|recovery)",
     "when": "always", "label": "fewer flask charges", "avoid": "flask charges"},
)
_COMPILED = tuple((r, re.compile(r["match"])) for r in RULES)
_TAG_RE = re.compile(r"\s*\((?:%s)\)$" % "|".join(item_parser.MOD_TAGS), re.I)


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and v == v and abs(v) != float("inf"):
        return v
    return None


def _stats(build):
    stats = getattr(build, "stats", None)
    return stats if isinstance(stats, dict) else {}


def _res(stats, element):
    return _num(stats.get(RES_STAT.get(element, "")))


def _share(stats, pool):
    life, es = _num(stats.get("Life")), _num(stats.get("EnergyShield"))
    if life is None or es is None or life + es <= 0:
        return None
    return (es if pool == "es" else life) / float(life + es)


def _fmt_res(v):
    if v is None:
        return "unknown"
    v = round(v)
    return f"{v}%"


def is_waystone(parsed):
    c = (parsed.item_class or "").strip().lower()
    return c in ("waystone", "waystones") or "waystone" in (parsed.base or "").lower()


def mod_lines(text):
    """The waystone's mod lines: every line after the header section that is
    not a `Key: value` property, a status word, help text or a separator;
    roll ranges and trailing tags removed."""
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n")]
    out, seen_sep = [], False
    for ln in lines:
        if ln == item_parser.SEPARATOR:
            seen_sep = True
            continue
        if not seen_sep or not ln or len(ln) > MAX_LINE:
            continue
        low = ln.lower()
        if low in item_parser.STATUS_LINES or low.startswith("unidentified"):
            continue
        if ln.endswith(".") or (ln.startswith("(") and ln.endswith(")")):
            continue  # help or reminder text: mods carry no full stop
        if re.match(r"^[A-Z][A-Za-z '()/-]{0,40}:\s", ln) and not _TAG_RE.search(ln):
            continue  # property line (Waystone Tier: 15, Item Level: 79)
        ln = _TAG_RE.sub("", ln).rstrip()
        out.append(item_parser.strip_rolls(ln))
        if len(out) >= MAX_MODS:
            break
    return out


def _check_rule(rule, m, stats):
    """(risky, label, avoid term) for one matched rule."""
    word = m.group(1) if m.groups() else ""
    el = (rule.get("elements") or {}).get(word, word)
    when = rule["when"]
    res = None
    risky = True
    if isinstance(when, dict) and "res" in when:
        element = el if when["res"] == "$1" else when["res"]
        el = element
        res = _res(stats, element)
        risky = res is None or res < when["below"]
    elif isinstance(when, dict) and "defence" in when:
        share = _share(stats, when["defence"])
        risky = share is None or share >= 0.5
    label = rule["label"].format(el=el, res=_fmt_res(res))
    avoid = rule["avoid"]
    avoid = tuple(a.format(el=el, word=word)
                  for a in ((avoid,) if isinstance(avoid, str) else avoid))
    short = rule["short"].format(el=el, El=el.capitalize())
    return risky, label, avoid, short


# UTIL-WAYSTONE-REWARD (research 0031 4.3): the reward kinds a waystone can
# carry. In the repoe-fork mods snapshot (fetched 2026-11-17, decision 0009
# build-time cache) every waystone prefix / suffix carries its reward as a
# hidden "_from_map" stat with no English translation
# (map_map_item_drop_chance, map_item_drop_rarity, map_pack_size,
# map_number_of_magic_and_rare_packs; uniques add map_item_drop_quantity),
# so the game prints them summed as properties under the tier line
# ("Item Rarity: +38% (augmented)"). Keys below match those property
# names; `line` also accepts a plain "N% increased <thing>" mod line. Order
# is the sentence order. Totals are per kind: the property (already the
# game's sum) wins; mod lines add up only for a kind with no property.
REWARDS = (
    {"id": "quantity", "key": r"item quantity",
     "line": r"increased quantity of items found", "label": "item quantity",
     "short": "quantity"},
    {"id": "rarity", "key": r"item rarity",
     "line": r"increased rarity of items found", "label": "item rarity",
     "short": "rarity"},
    {"id": "pack", "key": r"(?:monster )?pack size",
     "line": r"increased (?:monster )?pack size", "label": "pack size",
     "short": "pack"},
    {"id": "magic", "key": r"magic monsters|number of magic monsters",
     "line": r"increased number of magic monsters", "label": "magic monsters",
     "short": "magic"},
    {"id": "rare", "key": r"rare monsters|number of rare monsters",
     "line": r"increased number of rare monsters", "label": "rare monsters",
     "short": "rare"},
    {"id": "waystones", "key": r"waystone drop chance|waystones found",
     "line": r"increased (?:chance|quantity) of waystones", "label": "waystone drops",
     "short": "waystones"},
)
_REW_KEY = tuple((r, re.compile("^(?:" + r["key"] + ")$")) for r in REWARDS)
_REW_LINE = tuple((r, re.compile(r"^([+-]?\d+(?:\.\d+)?)% (?:" + r["line"] + ")"))
                  for r in REWARDS)
_PCT_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)%")
MAX_REWARD = 10000  # a pasted absurd number reads as no reward, not a huge one


def _pct(value):
    m = _PCT_RE.match(str(value or ""))
    if not m:
        return None
    v = float(m.group(1))
    return v if abs(v) <= MAX_REWARD else None


def rewards(parsed, mods):
    """[{"id", "label", "short", "pct"}] in REWARDS order: the waystone's
    reward properties plus any reward mod line, summed per kind; a kind that
    sums to 0 is left out. Pure; never raises on content."""
    total = {}
    for key, value in (getattr(parsed, "properties", None) or {}).items():
        low = str(key).strip().lower()
        for rule, rx in _REW_KEY:
            if rx.match(low):
                v = _pct(value)
                if v is not None:
                    total[rule["id"]] = total.get(rule["id"], 0.0) + v
                break
    # AREA-AUDIT P7-2: an "(augmented)" property is already the game's sum of
    # every source, so a mod line counts only for a kind with no property
    from_props = set(total)
    for line in mods or ():
        low = line.lower()
        for rule, rx in _REW_LINE:
            m = rx.match(low)
            if m:
                v = float(m.group(1))
                if abs(v) <= MAX_REWARD and rule["id"] not in from_props:
                    total[rule["id"]] = total.get(rule["id"], 0.0) + v
                break
    out = []
    for rule in REWARDS:
        v = total.get(rule["id"])
        if v is None or round(v) == 0:
            continue
        out.append({"id": rule["id"], "label": rule["label"], "short": rule["short"],
                    "pct": int(round(v))})
    return out


def check(text, build):
    """None when the text is not a waystone; else {"tier", "item_level",
    "corrupted", "unidentified", "build_loaded", "risky": [{"id", "label",
    "mod"}], "mods": count, "rewards": [{"id", "label", "short", "pct"}]}.
    Never raises on content."""
    if not isinstance(text, str):
        return None
    parsed = item_parser.parse(text)
    if not parsed.is_item or not is_waystone(parsed):
        return None
    tier = None
    for key, value in parsed.properties.items():
        if key.lower() == "waystone tier":
            tier = item_parser._first_int(value)
    if tier is None:
        m = re.search(r"\(Tier (\d+)\)", parsed.base or "")
        tier = int(m.group(1)) if m else None
    stats = _stats(build)
    mods = [] if parsed.flags.get("unidentified") else mod_lines(text)
    risky = []
    for line in mods:
        low = line.lower()
        for rule, rx in _COMPILED:
            m = rx.search(low)
            if not m:
                continue
            hit, label, _avoid, short = _check_rule(rule, m, stats)
            if hit and not any(r["label"] == label for r in risky):
                risky.append({"id": rule["id"], "label": label, "short": short,
                              "mod": line})
            break
    return {"tier": tier, "item_level": parsed.item_level,
            "corrupted": bool(parsed.flags.get("corrupted")),
            "unidentified": bool(parsed.flags.get("unidentified")),
            "build_loaded": build is not None, "risky": risky, "mods": len(mods),
            "rewards": rewards(parsed, mods)}


def avoid_terms(build):
    """UTIL-SEARCHSTR: the search terms of the mods risky for this build
    (every element / ground word tried), in rule order, no repeats."""
    stats = _stats(build)
    terms = []
    for rule in RULES:
        words = [""]
        if rule["id"] == "extra_element":
            words = ["fire", "cold", "lightning", "chaos"]
        elif rule["id"] == "ground":
            words = list(GROUND)
        for w in words:
            hit, _label, avoid, _short = _check_rule(rule, _Fake(w), stats)
            for a in (avoid if hit else ()):
                if a not in terms:
                    terms.append(a)
    return terms


class _Fake:
    """A stand-in match object carrying one capture group."""

    def __init__(self, word):
        self.word = word

    def groups(self):
        return (self.word,) if self.word else ()

    def group(self, _i):
        return self.word
