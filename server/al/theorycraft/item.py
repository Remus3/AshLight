"""PoE2 item text parser (TC-EVAL, research 0003).

A pure function: text in, a ParsedItem out. It reads the game's Ctrl+C /
Ctrl+Alt+C item text (sections split by an exact `--------` line) and the
Path of Building item text kept in a build (no separators, `Implicits: N`,
`{tag}` prefixes). It never reads the clipboard itself: the caller hands it
text taken from the one per-press read (decision 0003).

English client strings only. Unknown lines and sections are ignored, never
fatal; anything odd goes to `warnings`. A first line that is neither
`Item Class:` nor `Rarity:` sets `wrong_language` / not an item.
"""

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SEPARATOR = "--------"
BOM = chr(0xFEFF)
EM_DASH = chr(0x2014)  # advanced header segment separator
MAX_TEXT = 64 * 1024  # research 0003: size cap on a clipboard item

# Trailing lower-case tags on a mod line (research 0003 "Mod line markers").
MOD_TAGS = ("implicit", "enchant", "rune", "added rune", "desecrated", "fractured",
            "crafted", "scourge", "mutated", "crucible")
STATUS_LINES = {
    "corrupted": "corrupted",
    "twice corrupted": "twice_corrupted",
    "mirrored": "mirrored",
    "unidentified": "unidentified",
    "sanctified": "sanctified",
    "fractured item": "fractured",
    "unmodifiable": "unmodifiable",
    "desecrated prefix": "desecrated_open_prefix",
    "desecrated suffix": "desecrated_open_suffix",
    "split": "split",
}
TWO_NAME_RARITIES = ("RARE", "UNIQUE")
CANNOT_USE = "you cannot use this item"

_NUM = r"[+-]?\d+(?:\.\d+)?"
# MATH-ITEM: a roll range follows its rolled number ("+90(80-99)",
# "-15(-20--10)%"); a bare range stands for the number itself (PoB unique
# text "+(40-60)", read at {range:r}, default the midpoint).
_ROLL_RE = re.compile(r"(?<=\d)\((" + _NUM + r")-(" + _NUM + r")\)")
_BARE_RANGE_RE = re.compile(r"(?<![\d)])\((" + _NUM + r")-(" + _NUM + r")\)")
_POB_RANGE_RE = re.compile(r"\{range:\s*([0-9]*\.?[0-9]+)\s*\}", re.I)
DEFAULT_RANGE = 0.5
# flask / charm property lines that carry numbers but are not mods
_FLASK_PROP_RE = re.compile(r"^(Recovers|Consumes|Currently has|Lasts)\s+(.*\d.*)$")
_NUM_RE = re.compile(_NUM)
_TAG_RE = re.compile(r"\s*\((" + "|".join(re.escape(t) for t in MOD_TAGS) + r")\)\s*$", re.I)
_POB_PREFIX_RE = re.compile(r"^(?:\{[^{}]*\})+")
_ADV_HEADER_RE = re.compile(r"^\{\s(.*)\s\}$")
_PROP_RE = re.compile(r"^([A-Z][A-Za-z0-9 '()/-]{0,40}):\s*(.*)$")
_TIER_RE = re.compile(r"\((?:Tier|Rank):\s*(\d+)\)")
_REQUIRES_RE = re.compile(r"(\d+)\s+(Str|Dex|Int)\b|Level\s+(\d+)", re.I)


def _places(text):
    return len(text.split(".", 1)[1]) if "." in text else 0


def resolve_range(lo, hi, at=DEFAULT_RANGE):
    """The roll at fraction `at` (clamped to 0..1) of the range lo..hi (number
    strings), rounded half away from zero to the endpoints' decimal places,
    as a plain number string ("50", "1.5", "-15")."""
    try:
        a, b = Decimal(lo), Decimal(hi)
        f = min(Decimal(1), max(Decimal(0), Decimal(str(at))))
    except (InvalidOperation, ValueError):
        return lo
    if not (a.is_finite() and b.is_finite() and f.is_finite()):
        return lo
    places = max(_places(lo), _places(hi))
    v = (a + (b - a) * f).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    if v == 0:
        v = abs(v)
    return format(v, "f")


def strip_rolls(text, at=DEFAULT_RANGE):
    """Mod text without roll ranges; bare ranges become their roll at `at`."""
    if "(" not in text:
        return text
    text = _ROLL_RE.sub("", text)
    return _BARE_RANGE_RE.sub(lambda m: resolve_range(m.group(1), m.group(2), at), text)


def _range_of(prefix):
    m = _POB_RANGE_RE.search(prefix or "")
    if not m:
        return DEFAULT_RANGE
    try:
        return float(m.group(1))
    except ValueError:
        return DEFAULT_RANGE


def _number(text):
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return int(v) if v.is_integer() else v


@dataclass
class Mod:
    text: str  # the stat line with tags and roll ranges removed
    section: str = "explicit"  # implicit | explicit | rune | enchant | crafted | ...
    kind: str = None  # prefix | suffix | None (advanced header only)
    name: str = None  # affix name from the advanced header
    tier: int = None
    values: tuple = ()  # rolled numbers, in order

    def to_dict(self):
        return {"text": self.text, "section": self.section, "kind": self.kind,
                "name": self.name, "tier": self.tier, "values": list(self.values)}


@dataclass
class ParsedItem:
    is_item: bool = False
    item_class: str = None
    rarity: str = None
    name: str = None
    base: str = None
    item_level: int = None
    quality: int = None
    requirements: dict = field(default_factory=dict)
    sockets: str = None
    rune_sockets: int = 0
    properties: dict = field(default_factory=dict)
    mods: list = field(default_factory=list)
    flags: dict = field(default_factory=dict)
    note: str = None
    advanced: bool = False
    warnings: list = field(default_factory=list)

    @property
    def display_name(self):
        return " ".join(x for x in (self.name, self.base) if x) or None

    def to_dict(self):
        return {"is_item": self.is_item, "item_class": self.item_class,
                "rarity": self.rarity, "name": self.name, "base": self.base,
                "item_level": self.item_level, "quality": self.quality,
                "requirements": dict(self.requirements), "sockets": self.sockets,
                "rune_sockets": self.rune_sockets, "properties": dict(self.properties),
                "mods": [m.to_dict() for m in self.mods], "flags": dict(self.flags),
                "note": self.note, "advanced": self.advanced,
                "warnings": list(self.warnings)}


def looks_like_item(text):
    """Cheap shape check for a clipboard string (no parse)."""
    if not isinstance(text, str):
        return False
    head = text.lstrip(BOM + " \t\r\n")[:64].lower()
    return head.startswith("item class:") or head.startswith("rarity:")


def _lines(text):
    text = text.replace(BOM, "").replace("\r\n", "\n").replace("\r", "\n")
    return [ln.strip() for ln in text.split("\n")]


def _sections(lines):
    out, cur = [], []
    for ln in lines:
        if ln == SEPARATOR:
            if cur:
                out.append(cur)
            cur = []
        elif ln:
            cur.append(ln)
    if cur:
        out.append(cur)
    return out


def _header(item, section):
    """Item Class / Rarity / name lines. Returns the leftover lines."""
    rest = list(section)
    while rest:
        low = rest[0].lower()
        if low.startswith("item class:"):
            item.item_class = rest.pop(0).split(":", 1)[1].strip() or None
        elif low.startswith("rarity:"):
            item.rarity = rest.pop(0).split(":", 1)[1].strip().upper() or None
        elif low.startswith(CANNOT_USE):
            rest.pop(0)
            item.flags["cannot_use"] = True
        else:
            break
    want = 2 if item.rarity in TWO_NAME_RARITIES else 1
    names = []
    while rest and len(names) < want and not _is_marker(rest[0]):
        names.append(rest.pop(0))
    if len(names) == 2:
        item.name, item.base = names
    elif names:
        item.base = names[0]
    return rest


def _is_marker(line):
    """A line that cannot be a name line (property, tag, status, PoB key)."""
    return bool(_PROP_RE.match(line)) or line.lower() in STATUS_LINES or line.startswith("{")


def _parse_header(text):
    """(type words, name, tier, tags) from an advanced `{ ... }` body."""
    parts = [p.strip() for p in re.split(r"\s+" + EM_DASH + r"\s+|\s+-\s+", text)]
    first = parts[0] if parts else ""
    tier_m = _TIER_RE.search(first)
    name_m = re.search(r'"([^"]*)"', first)
    words = re.sub(r'"[^"]*"|\((?:Tier|Rank):\s*\d+\)', "", first).strip().lower()
    kind = "prefix" if "prefix" in words else "suffix" if "suffix" in words else None
    section = "explicit"
    for word, sec in (("implicit", "implicit"), ("enhancement", "enchant"),
                      ("crafted", "crafted"), ("fractured", "fractured"),
                      ("desecrated", "desecrated"), ("rune", "rune")):
        if word in words:
            section = sec
            break
    return {"kind": kind, "name": name_m.group(1) if name_m else None,
            "tier": int(tier_m.group(1)) if tier_m else None, "section": section}


def _mod(line, header, implicit_left, at=DEFAULT_RANGE):
    """A Mod from a stat line, or None when it is not one."""
    tag_m = _TAG_RE.search(line)
    section = None
    if tag_m:
        section = tag_m.group(1).lower().replace(" ", "_")
        line = line[:tag_m.start()].rstrip()
    rolled = strip_rolls(line, at)
    values = tuple(_number(v) for v in _NUM_RE.findall(rolled))
    text = re.sub(r"\s{2,}", " ", rolled).strip()
    if not text:
        return None
    if section is None:
        if header is not None:
            section = header["section"]
        elif implicit_left:
            section = "implicit"
        else:
            section = "explicit"
    return Mod(text=text, section=section,
               kind=header["kind"] if header else None,
               name=header["name"] if header else None,
               tier=header["tier"] if header else None, values=values)


def _body(item, lines, state):
    """Classify the lines of one non-header section."""
    header = None
    in_reqs = False
    section_has_mods = False
    for raw in lines:
        line = raw
        adv = _ADV_HEADER_RE.match(line)
        if adv:
            item.advanced = True
            header = _parse_header(adv.group(1))
            continue
        pob = _POB_PREFIX_RE.match(line)
        at = _range_of(pob.group(0)) if pob else DEFAULT_RANGE
        line = _POB_PREFIX_RE.sub("", line).strip()
        if not line:
            continue
        low = line.lower()
        if line.startswith("(") and line.endswith(")"):
            continue  # reminder text
        if line.endswith(".") and header is None and not _has_tag(line):
            continue  # flavour, help or description text: mods carry no full stop
        flask = _FLASK_PROP_RE.match(line)
        if flask and any(k in (item.item_class or "").lower() for k in ("flask", "charm")):
            item.properties[flask.group(1)] = flask.group(2).strip()
            continue
        if low in STATUS_LINES:
            item.flags[STATUS_LINES[low]] = True
            continue
        if low.startswith("unidentified"):
            item.flags["unidentified"] = True
            continue
        if low == "requirements:":
            in_reqs = True
            continue
        prop = _PROP_RE.match(line)
        if prop and not _has_tag(line):
            key, value = prop.group(1).strip(), prop.group(2).strip()
            klow = key.lower()
            if in_reqs and klow in ("level", "str", "dex", "int"):
                item.requirements[klow] = _first_int(value)
            elif klow == "requires":
                _requires(item, value)
            elif klow == "item level":
                item.item_level = _first_int(value)
            elif klow == "quality" or klow.startswith("quality ("):
                item.quality = _first_int(value)
            elif klow == "sockets":
                item.sockets = value
                item.rune_sockets = sum(1 for c in value.upper() if c == "S")
            elif klow == "note":
                item.note = value
            elif klow == "implicits":
                state["implicits"] = _first_int(value) or 0
            elif klow == "levelreq":
                item.requirements["level"] = _first_int(value)
            else:
                item.properties[key] = value
            continue
        mod = None
        if header is not None or _NUM_RE.search(line) or section_has_mods \
                or _TAG_RE.search(line) or state.get("implicits"):
            mod = _mod(line, header, state.get("implicits", 0) > 0, at)
        header = None
        if mod is None:
            continue  # flavour or help text
        if state.get("implicits", 0) > 0 and not _TAG_RE.search(raw):
            state["implicits"] -= 1
        section_has_mods = True
        item.mods.append(mod)


def _has_tag(line):
    """A tagged stat line is a mod even when it has a `Key: value` shape."""
    return bool(_TAG_RE.search(line))


def _first_int(text):
    m = re.search(r"\d+", text or "")
    return int(m.group(0)) if m else None


def _requires(item, value):
    for m in _REQUIRES_RE.finditer(value):
        if m.group(3):
            item.requirements["level"] = int(m.group(3))
        else:
            item.requirements[m.group(2).lower()] = int(m.group(1))


def parse(text):
    """A ParsedItem from item text. Never raises on content."""
    item = ParsedItem()
    if not isinstance(text, str) or not text.strip():
        item.warnings.append("empty")
        return item
    if len(text) > MAX_TEXT:
        item.warnings.append("too large")
        return item
    sections = _sections(_lines(text))
    if not sections or not looks_like_item(sections[0][0]):
        item.warnings.append("not an English PoE item text (no Item Class / Rarity line)")
        return item
    item.is_item = True
    leftover = _header(item, sections[0])
    state = {}
    if leftover:
        _body(item, leftover, state)
    for sec in sections[1:]:
        _body(item, sec, state)
    if item.base is None:
        item.warnings.append("no base type line")
    return item
