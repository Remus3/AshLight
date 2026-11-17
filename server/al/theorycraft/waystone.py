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
  unknown);
- `label`: words for the dashboard sentence ("{el}" is the element,
  "{res}" the build's value); `short`: the overlay card word;
- `avoid`: the search-box term that finds the mod (UTIL-SEARCHSTR).
A build stat that is missing reads as unknown, and unknown is risky: the
card would rather say too much than hide a danger.
"""

import re

from . import item as item_parser

RES_CAP = 75
RES_STAT = {"fire": "FireResist", "cold": "ColdResist",
            "lightning": "LightningResist", "chaos": "ChaosResist"}
GROUND = {"burning": "fire", "ignited": "fire", "chilled": "cold",
          "shocked": "lightning", "shocking": "lightning"}
MAX_MODS = 24
MAX_LINE = 200

RULES = (
    {"id": "extra_element", "short": "Extra {el} dmg",
     "match": r"(?:as extra|extra damage as) (fire|cold|lightning|chaos)\b",
     "when": {"res": "$1", "below": RES_CAP},
     "label": "extra {el} damage ({el} resistance {res})", "avoid": "extra {el}"},
    {"id": "ground", "short": "{El} ground",
     "match": r"patches of (burning|ignited|chilled|shocked|shocking) ground",
     "when": {"res": "$1", "below": RES_CAP}, "elements": GROUND,
     "label": "{el} ground ({el} resistance {res})", "avoid": "{word} ground"},
    {"id": "no_regen", "short": "No regen",
     "match": r"cannot (?:regenerate|recover)",
     "when": "always", "label": "no regeneration", "avoid": "cannot rege"},
    {"id": "less_recovery", "short": "Less recovery",
     "match": r"(?:less|reduced) recovery|(?:less|reduced) life regeneration",
     "when": {"defence": "life"}, "label": "less life recovery", "avoid": "recovery rate"},
    {"id": "es_recharge", "short": "Slow ES recharge",
     "match": r"(?:less|reduced) energy shield recharge",
     "when": {"defence": "es"}, "label": "slower energy shield recharge",
     "avoid": "shield recharge"},
    {"id": "max_res", "short": "Lower max res",
     "match": r"-\d+% to (?:all )?maximum (?:player |elemental )?resistances?"
              r"|maximum player resistances",
     "when": "always", "label": "lower maximum resistances", "avoid": "maximum player res"},
    {"id": "monster_crit", "short": "Monster crits",
     "match": r"monsters?\b.*critical (?:hit|strike|damage)",
     "when": "always", "label": "monster critical hits", "avoid": "critical"},
    {"id": "curse", "short": "Cursed",
     "match": r"cursed with ([a-z ]+)",
     "when": "always", "label": "cursed with {el}", "avoid": "cursed with"},
    {"id": "reflect", "short": "Reflect",
     "match": r"\breflect",
     "when": "always", "label": "reflected damage", "avoid": "reflect"},
    {"id": "poison", "short": "Poison",
     "match": r"monsters?\b.*poison",
     "when": {"res": "chaos", "below": 0},
     "label": "monster poison (chaos resistance {res})", "avoid": "poison"},
    {"id": "projectiles", "short": "Extra projectiles",
     "match": r"monsters?\b.*additional projectiles?",
     "when": "always", "label": "extra monster projectiles", "avoid": "additional proj"},
    {"id": "flasks", "short": "Weak flasks",
     "match": r"(?:less|reduced) (?:flask|charm) (?:effect|charges|recovery)"
              r"|(?:flask|charm) charges? (?:gained|used)",
     "when": "always", "label": "weaker flasks", "avoid": "flask"},
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
    avoid = rule["avoid"].format(el=el, word=word)
    short = rule["short"].format(el=el, El=el.capitalize())
    return risky, label, avoid, short


def check(text, build):
    """None when the text is not a waystone; else {"tier", "item_level",
    "corrupted", "unidentified", "build_loaded", "risky": [{"id", "label",
    "mod"}], "mods": count}. Never raises on content."""
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
            "build_loaded": build is not None, "risky": risky, "mods": len(mods)}


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
            if hit and avoid not in terms:
                terms.append(avoid)
    return terms


class _Fake:
    """A stand-in match object carrying one capture group."""

    def __init__(self, word):
        self.word = word

    def groups(self):
        return (self.word,) if self.word else ()

    def group(self, _i):
        return self.word
