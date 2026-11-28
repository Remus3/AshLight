"""ITEM-INFO-POB-TEXT (decision 0083 point 3, amends the decision 0037
amendment): "where found" rows for the item info popover, read as TEXT
from the hash-pinned Path of Building PoE2 checkout.

Sources, all inside the pinned checkout that tools/tc_pin.py extracted
into the sidecar Cache (the optional calc component, decision 0018):

- src/Data/Uniques/<slot>.lua: each unique is a Lua long string
  ("[[" ... "]]"), its first line the name. Only its "Source:" lines are
  read: "Source: Drops from unique{<boss>}" with an optional
  " in normal{<zone>}", and "Source: No longer obtainable". Any other
  Source text is skipped, never guessed. Uniques/Special/ is Lua code
  that builds items, not data, and is not read.
- src/Data/WorldAreas.lua: the `name`, `baseName` and `isMap` lines of
  each `worldAreas["<id>"] = {` block. It only tells whether a zone named
  in a Source line is a map area ("map": true / false when every area of
  that name agrees; absent otherwise). Act numbers and levels are not
  passed on (PoB files endgame areas under act 10, which is not a fact a
  player can use).
- src/Data/CurrencyNames.lua (named in decision 0083) is not in the
  pinned checkout; nothing is read for it until a pin move brings it and
  a parser for its real shape lands.

- src/Data/Gems.lua (KINDLER-GEM-VARIANT, for Kindler's composer, not the
  popover): the `name`, `grantedEffectId` and `weaponRequirements` lines
  of each top-level `\t["<id>"] = {` block, so a gem name PoB holds under
  several weapon variants (Mace Strike) can be composed by the one skill id
  the template's weapon class picks (theorycraft.archetypes.skill_id). It is
  read by load_gem_variants / GemVariants only; pinned_files() leaves it out.

- src/Data/ModRunes.lua (DATA-AUGMENT-POB-TEXT, decision 0091, for augment
  effect, value and slot lookup, not the popover): one top-level
  `\t["<augment name>"] = {` block per rune, soul core, idol or other
  augment, holding one `\t\t["<slot key>"] = {` block per slot key with
  its `type`, stat line strings, `statOrder`, `tradeHashes`,
  `isSocketBound` and `rank` lines. A slot block with any other line or a
  missing field is left out, and an augment left with no slot, or named
  twice, is left out: nothing is guessed. Capped at AUGMENTS_MAX_BYTES.
  The tradeHashes numbers are used only as the rune.stat_<n> trade ids of
  decision 0037; no price, no trade2 call (decision 0017). Read by
  load_augments / Augments only; pinned_files() leaves it out. repoe-fork
  wins any conflict (a caller takes names, classes and trade ids from the
  repoe-fork snapshots first and uses these rows only where they agree or
  repoe-fork is silent).

Conditions (decision 0083 point 3): a file is read only when it has a
config/tc_pins.json "pob2_files" entry, the checkout marker names the
pinned archive sha256 and the file's sha256 equals its entry; a file
that fails omits only what it would give. Nothing is ever run as Lua:
these are line scanners. The parse is done once per pin (the pins file
is re-read only when its mtime changes) and kept in memory. The rows feed
only the popover; repoe-fork wins any field both give (the caller,
server/al/iteminfo.py, takes name spelling, class, rarity and release
state from repoe-fork). The popover credits the rows "Path of Building
(MIT), community-written, may be out of date" through the source id
SOURCE_ID. Standard library only; no network code.
"""

import hashlib
import json
import re
import threading
from pathlib import Path

from .. import paths

SOURCE_ID = "path-of-building"
UNIQUES_DIR = "src/Data/Uniques/"
WORLD_AREAS = "src/Data/WorldAreas.lua"
MARKER = ".al-extracted.json"   # tools/tc_pin.py MARKER
MAX_BYTES = 4 * 1024 * 1024     # one data file
MAX_LINES = 200000
NAME_MAX = 120
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOP = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
_UNIQUE_FILE = re.compile(r"^src/Data/Uniques/[a-z0-9_]{1,40}\.lua$")
_BLOCK = re.compile(r"\[\[\n(.*?)\n\]\]", re.S)
_DROPS = re.compile(r"^Source: Drops from unique\{([^{}]+)\}(?: in normal\{([^{}]+)\})?\s*$")
_GONE = "Source: No longer obtainable"
_AREA_OPEN = re.compile(r'^worldAreas\["[^"\\]+"\]\s*=\s*\{\s*$')
_AREA_CLOSE = re.compile(r"^\}\s*,?\s*$")
_AREA_FIELD = re.compile(r'^\t(name|baseName)\s*=\s*"([^"\\]*)",\s*$')
_AREA_MAP = re.compile(r"^\tisMap\s*=\s*(true|false),\s*$")
_SUFFIX = re.compile(r"\s+\((?:Act \d+|Map)\)$")
GEMS = "src/Data/Gems.lua"
_GEM_OPEN = re.compile(r'^\t\["[^"\\]+"\]\s*=\s*\{\s*$')
_GEM_CLOSE = re.compile(r"^\t\}\s*,?\s*$")
_GEM_FIELD = re.compile(r'^\t\t(name|grantedEffectId|weaponRequirements)\s*=\s*"([^"\\]*)",\s*$')
_SKILL_ID = re.compile(r"^[A-Za-z0-9_]{1,80}$")
AUGMENTS = "src/Data/ModRunes.lua"
AUGMENTS_MAX_BYTES = 1024 * 1024    # decision 0091: a 1 MB cap
LINE_MAX = 300                      # one stat line, printable ASCII
_STR = r'"([^"\\]*)"'
_AUG_OPEN = re.compile(r"^\t\[" + _STR + r"\]\s*=\s*\{\s*$")
_AUG_CLOSE = re.compile(r"^\t\}\s*,?\s*$")
_SLOT_OPEN = re.compile(r"^\t\t\[" + _STR + r"\]\s*=\s*\{\s*$")
_SLOT_CLOSE = re.compile(r"^\t\t\}\s*,?\s*$")
_SLOT_KEY = re.compile(r"^[a-z][a-z ]{0,39}$")
_AUG_TYPE = re.compile(r'^\t{3,}type\s*=\s*"([A-Za-z]{1,40})",\s*$')
_AUG_LINE = re.compile(r"^\t{3,}" + _STR + r",\s*$")
# statOrder numbers may carry a line part (6448.1: the second line of stat 6448)
_NUM = r"\d{1,9}(?:\.\d{1,3})?"
_AUG_INTS = re.compile(r"^\t{3,}(statOrder|rank)\s*=\s*\{\s*"
                       r"(" + _NUM + r"(?:\s*,\s*" + _NUM + r")*)\s*,?\s*\},\s*$")
_AUG_BOUND = re.compile(r"^\t{3,}isSocketBound\s*=\s*(true|false),\s*$")
_AUG_HASHES = re.compile(r"^\t{3,}tradeHashes\s*=\s*\{(.*)\},\s*$")
_HASH_ITEM = re.compile(r'\s*\[(\d{1,12})\]\s*=\s*\{\s*'
                        r'("[^"\\]*"(?:\s*,\s*"[^"\\]*")*)\s*,?\s*\}\s*,')
_HASH_STR = re.compile(r'"([^"\\]*)"')


def key(value):
    """The match key of a name: spacing folded, lower case."""
    return " ".join(value.split()).lower() if isinstance(value, str) else ""


def _name(value):
    """A plain one-line name of at most NAME_MAX printable ASCII
    characters, spacing folded; None otherwise."""
    if not isinstance(value, str):
        return None
    v = " ".join(value.split())
    if not v or len(v) > NAME_MAX or not all(" " <= c <= "~" for c in v):
        return None
    return v


def parse_uniques(text):
    """{key: {"name", "drops": [{"boss", "zone"?}], "no_longer_obtainable"?}}
    from the text of one PoB Uniques/<slot>.lua; only uniques with at least
    one readable Source line are kept. Over MAX_LINES lines, or not a
    string, gives {}."""
    out = {}
    if not isinstance(text, str):
        return out
    text = text.replace("\r\n", "\n")
    if text.count("\n") > MAX_LINES:
        return {}
    for block in _BLOCK.findall(text):
        lines = block.split("\n")
        name = _name(lines[0]) if lines else None
        if name is None:
            continue
        drops, gone = [], False
        for line in lines[1:]:
            line = line.strip()
            if line == _GONE:
                gone = True
                continue
            m = _DROPS.match(line)
            if not m:
                continue
            boss, zone = _name(m.group(1)), _name(m.group(2)) if m.group(2) else None
            if boss is None or (m.group(2) and zone is None):
                continue
            row = {"boss": boss}
            if zone:
                row["zone"] = zone
            if row not in drops:
                drops.append(row)
        if not drops and not gone:
            continue
        entry = out.setdefault(key(name), {"name": name, "drops": []})
        for row in drops:
            if row not in entry["drops"]:
                entry["drops"].append(row)
        if gone:
            entry["no_longer_obtainable"] = True
    return out


def parse_world_areas(text):
    """{zone key: bool or None} from the text of PoB's WorldAreas.lua:
    True when every area with that name or baseName (the name without its
    " (Act N)" / " (Map)" suffix) is a map, False when none is, None when
    they disagree or isMap is missing. Over MAX_LINES lines gives {}."""
    seen = {}
    if not isinstance(text, str):
        return {}
    lines = text.replace("\r\n", "\n").split("\n")
    if len(lines) > MAX_LINES:
        return {}
    cur = None
    for line in lines:
        if _AREA_OPEN.match(line):
            cur = {}
            continue
        if cur is None:
            continue
        if _AREA_CLOSE.match(line):
            is_map = cur.get("isMap")
            names = {key(n) for n in (cur.get("name"), cur.get("baseName"),
                                      _SUFFIX.sub("", cur.get("name") or ""))
                     if _name(n)}
            for k in names:
                seen.setdefault(k, set()).add(is_map)
            cur = None
            continue
        m = _AREA_FIELD.match(line)
        if m:
            cur[m.group(1)] = m.group(2)
            continue
        m = _AREA_MAP.match(line)
        if m:
            cur["isMap"] = m.group(1) == "true"
    return {k: (next(iter(v)) if len(v) == 1 else None) for k, v in seen.items()}


def parse_gem_variants(text):
    """{name key: [{"skill_id", "weapons": [weapon class]}]} from the text of
    PoB's Gems.lua, in file order: one row per top-level gem block with a
    readable name and grantedEffectId (a plain id); weapons is the block's
    comma list of weaponRequirements ([] without one). Over MAX_LINES lines,
    or not a string, gives {}."""
    out = {}
    if not isinstance(text, str):
        return out
    lines = text.replace("\r\n", "\n").split("\n")
    if len(lines) > MAX_LINES:
        return {}
    cur = None
    for line in lines:
        if _GEM_OPEN.match(line):
            cur = {}
            continue
        if cur is None:
            continue
        if _GEM_CLOSE.match(line):
            name, sid = _name(cur.get("name")), cur.get("grantedEffectId")
            if name is not None and isinstance(sid, str) and _SKILL_ID.match(sid):
                weapons = [w for w in (_name(p) for p in
                                       (cur.get("weaponRequirements") or "").split(","))
                           if w]
                out.setdefault(key(name), []).append({"skill_id": sid, "weapons": weapons})
            cur = None
            continue
        m = _GEM_FIELD.match(line)
        if m:
            cur.setdefault(m.group(1), m.group(2))
    return out


def _stat_line(value):
    """A one-line stat text of at most LINE_MAX printable ASCII characters,
    kept as written; None otherwise."""
    if not isinstance(value, str) or not value or len(value) > LINE_MAX:
        return None
    return value if all(" " <= c <= "~" for c in value) else None


def _trade_hashes(body):
    """[{"hash": n, "lines": [text]}] from the inside of one tradeHashes
    table, or None when any part of it is not that shape. PoB writes "" for
    a hash it has no text for; that row keeps its hash with no line."""
    out, pos, body = [], 0, body.rstrip()
    while pos < len(body):
        m = _HASH_ITEM.match(body, pos)
        if not m:
            return None
        lines = [_stat_line(s) for s in _HASH_STR.findall(m.group(2)) if s != ""]
        if None in lines:
            return None
        out.append({"hash": int(m.group(1)), "lines": lines})
        pos = m.end()
    return out


def _number(text):
    """An int for a whole number, a float for one with a line part."""
    text = text.strip()
    return float(text) if "." in text else int(text)


_SLOT_FIELDS = ("type", "statOrder", "tradeHashes", "isSocketBound", "rank")


def _slot_line(cur, line):
    """Fold one line into the open slot block; any other shape, a bad
    value, or a field given twice marks the block bad."""
    value = None
    m = _AUG_TYPE.match(line)
    if m:
        name, value = "type", m.group(1)
    elif _AUG_INTS.match(line):
        m = _AUG_INTS.match(line)
        name, value = m.group(1), [_number(x) for x in m.group(2).split(",")]
    elif _AUG_BOUND.match(line):
        name, value = "isSocketBound", _AUG_BOUND.match(line).group(1) == "true"
    elif _AUG_HASHES.match(line):
        name, value = "tradeHashes", _trade_hashes(_AUG_HASHES.match(line).group(1))
    elif _AUG_LINE.match(line):
        text = _stat_line(_AUG_LINE.match(line).group(1))
        if text is None:
            cur["bad"] = True
        else:
            cur["lines"].append(text)
        return
    else:
        cur["bad"] = True
        return
    if value is None or name in cur:
        cur["bad"] = True
        return
    cur[name] = value


def _slot_row(cur):
    """The finished slot dict of a slot block, or None when it is bad, has
    no stat line or misses a field."""
    if cur.get("bad") or not cur["lines"] or any(k not in cur for k in _SLOT_FIELDS):
        return None
    row = {"type": cur["type"], "lines": cur["lines"]}
    row.update((k, cur[k]) for k in _SLOT_FIELDS[1:])
    return row


def parse_augments(text):
    """{name key: {"name", "slots": {slot key: {"type", "lines",
    "statOrder", "tradeHashes": [{"hash", "lines"}], "isSocketBound",
    "rank"}}}} from the text of PoB's ModRunes.lua, slots in file order.
    "lines" are the slot's stat line strings as PoB writes them. A slot
    block that is not exactly the known shape is dropped; an augment with a
    stray line, a block that never closed, no slot left, or a name given
    twice is dropped (a slot key given twice drops that slot). Over
    MAX_LINES lines, or not a string, gives {}. A line scanner: nothing is
    run."""
    out = {}
    if not isinstance(text, str):
        return out
    lines = text.replace("\r\n", "\n").split("\n")
    if len(lines) > MAX_LINES:
        return {}
    twice = set()
    aug = slot = None
    for line in lines:
        if slot is not None:
            if _SLOT_CLOSE.match(line):
                row = _slot_row(slot)
                if row is None or slot["key"] in aug["slots"] or slot["key"] in aug["drop"]:
                    aug["drop"].add(slot["key"])
                else:
                    aug["slots"][slot["key"]] = row
                slot = None
                continue
            if not (_AUG_CLOSE.match(line) or _AUG_OPEN.match(line)
                    or _SLOT_OPEN.match(line)):
                _slot_line(slot, line)
                continue
            aug["bad"], slot = True, None   # the slot block never closed
        if aug is not None and _AUG_OPEN.match(line):
            aug = None                      # the augment block never closed
        if aug is not None:
            m = _SLOT_OPEN.match(line)
            if m:
                slot = {"key": m.group(1), "lines": []}
                if not _SLOT_KEY.match(slot["key"]):
                    slot["bad"] = True
                continue
            if _AUG_CLOSE.match(line):
                for k in aug["drop"]:
                    aug["slots"].pop(k, None)
                name = aug["name"]
                if not aug.get("bad") and name is not None and aug["slots"]:
                    nk = key(name)
                    if nk in out or nk in twice:
                        out.pop(nk, None)
                        twice.add(nk)
                    else:
                        out[nk] = {"name": name, "slots": aug["slots"]}
                aug = None
            elif line.strip():
                aug["bad"] = True
            continue
        m = _AUG_OPEN.match(line)
        if m:
            aug = {"name": _name(m.group(1)), "slots": {}, "drop": set()}
    return out


def pinned_files(pins):
    """[(rel, sha256)] of the pob2_files entries this module reads (the
    Uniques slot files and WorldAreas.lua), sorted; bad entries skipped."""
    out = []
    files = (pins or {}).get("pob2_files") if isinstance(pins, dict) else None
    if not isinstance(files, dict):
        return out
    for rel, row in files.items():
        if not isinstance(rel, str) or not (rel == WORLD_AREAS or _UNIQUE_FILE.match(rel)):
            continue
        sha = row.get("sha256") if isinstance(row, dict) else None
        if isinstance(sha, str) and _HEX64.match(sha):
            out.append((rel, sha))
    return sorted(out)


def checkout_root(pins, environ=None):
    """The pinned checkout folder in the sidecar Cache, or None when the
    pin's top_dir is not a plain folder name."""
    try:
        top = pins["pob2"]["top_dir"]
    except (KeyError, TypeError):
        return None
    if not isinstance(top, str) or not _TOP.match(top) or ".." in top:
        return None
    return paths.all_runtime_paths(environ)["pob2_cache"] / top


def _read_pinned(root, rel, want, cap=MAX_BYTES):
    """The file's text when its size (at most cap) and sha256 hold, else None."""
    try:
        p = Path(root, *rel.split("/"))
        if p.stat().st_size > cap:
            return None
        raw = p.read_bytes()
        if len(raw) > cap or hashlib.sha256(raw).hexdigest() != want:
            return None
        return raw.decode("utf-8")
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def _marker_ok(root, pins):
    """True when the checkout marker at root names the pinned archive sha256."""
    try:
        archive = pins["pob2"]["archive_sha256"]
        marker = json.loads(Path(root, MARKER).read_text(encoding="ascii"))
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return bool(isinstance(archive, str) and _HEX64.match(archive)
                and isinstance(marker, dict) and marker.get("archive_sha256") == archive)


def load_gem_variants(root, pins):
    """parse_gem_variants of the pinned checkout's Gems.lua; {} unless the
    marker names the pinned archive and the file matches its pob2_files
    sha256. Never raises."""
    try:
        want = pins["pob2_files"][GEMS]["sha256"]
    except (KeyError, TypeError):
        return {}
    if not (isinstance(want, str) and _HEX64.match(want)) or not _marker_ok(root, pins):
        return {}
    text = _read_pinned(root, GEMS, want)
    return parse_gem_variants(text) if text is not None else {}


def load_augments(root, pins):
    """parse_augments of the pinned checkout's ModRunes.lua (decision 0091);
    {} unless the marker names the pinned archive and the file, at most
    AUGMENTS_MAX_BYTES, matches its pob2_files sha256. Never raises."""
    try:
        want = pins["pob2_files"][AUGMENTS]["sha256"]
    except (KeyError, TypeError):
        return {}
    if not (isinstance(want, str) and _HEX64.match(want)) or not _marker_ok(root, pins):
        return {}
    text = _read_pinned(root, AUGMENTS, want, AUGMENTS_MAX_BYTES)
    return parse_augments(text) if text is not None else {}


def load(root, pins):
    """{"uniques": {key: entry}, "areas": {zone key: bool or None},
    "files": [rel read]} from the pinned checkout at root; empty unless the
    marker names the pinned archive sha256. Never raises."""
    out = {"uniques": {}, "areas": {}, "files": []}
    if not _marker_ok(root, pins):
        return out
    for rel, want in pinned_files(pins):
        text = _read_pinned(root, rel, want)
        if text is None:
            continue
        out["files"].append(rel)
        if rel == WORLD_AREAS:
            out["areas"] = parse_world_areas(text)
            continue
        for k, entry in parse_uniques(text).items():
            have = out["uniques"].setdefault(k, {"name": entry["name"], "drops": []})
            for row in entry["drops"]:
                if row not in have["drops"]:
                    have["drops"].append(row)
            if entry.get("no_longer_obtainable"):
                have["no_longer_obtainable"] = True
    return out


def field(index, name_key):
    """The popover's "where_found" value for one item key, or None:
    {"drops": [{"boss", "zone"?, "map"?}], "no_longer_obtainable"?}."""
    entry = ((index or {}).get("uniques") or {}).get(name_key)
    if not entry:
        return None
    areas = (index or {}).get("areas") or {}
    drops = []
    for row in entry["drops"]:
        row = dict(row)
        is_map = areas.get(key(row.get("zone"))) if row.get("zone") else None
        if is_map is not None:
            row["map"] = is_map
        drops.append(row)
    out = {"drops": drops}
    if entry.get("no_longer_obtainable"):
        out["no_longer_obtainable"] = True
    return out


class WhereFound:
    """The parsed rows of the pinned checkout, read once per pin. `pins_path`
    is the tracked pin file (paths.tc_pins_file by default); `root` the
    checkout (from the pin's top_dir by default)."""

    def __init__(self, pins_path=None, root=None, environ=None):
        self.pins_path = Path(pins_path) if pins_path else paths.tc_pins_file(environ)
        self.root = Path(root) if root else None
        self.environ = environ
        self._lock = threading.Lock()
        self._stamp = None
        self._pin_key = None
        self._index = {"uniques": {}, "areas": {}, "files": []}

    def get(self):
        with self._lock:
            try:
                stamp = self.pins_path.stat().st_mtime_ns
            except OSError:
                stamp = None
            if stamp == self._stamp:
                return self._index
            self._stamp = stamp
            try:
                pins = json.loads(self.pins_path.read_text(encoding="ascii"))
            except (OSError, ValueError):
                pins = None
            if not isinstance(pins, dict):
                self._pin_key = None
                self._index = {"uniques": {}, "areas": {}, "files": []}
                return self._index
            pin_key = (json.dumps(pins.get("pob2"), sort_keys=True),
                       tuple(pinned_files(pins)))
            if pin_key != self._pin_key:
                root = self.root or checkout_root(pins, self.environ)
                self._index = load(root, pins) if root else \
                    {"uniques": {}, "areas": {}, "files": []}
                self._pin_key = pin_key
            return self._index

    def lookup(self, name_key):
        """field() for one item key (iteminfo.key form)."""
        return field(self.get(), name_key)


class GemVariants:
    """KINDLER-GEM-VARIANT: load_gem_variants of the pinned checkout, read
    once per pin (the pins file re-read only when its mtime changes), {}
    while it cannot be read. Same arguments as WhereFound. REL is the
    pob2_files entry whose pin keys the cache, LOAD its loader."""

    REL = GEMS
    LOAD = staticmethod(load_gem_variants)

    def __init__(self, pins_path=None, root=None, environ=None):
        self.pins_path = Path(pins_path) if pins_path else paths.tc_pins_file(environ)
        self.root = Path(root) if root else None
        self.environ = environ
        self._lock = threading.Lock()
        self._stamp = None
        self._pin_key = None
        self._index = {}

    def get(self):
        with self._lock:
            try:
                stamp = self.pins_path.stat().st_mtime_ns
            except OSError:
                stamp = None
            if stamp == self._stamp:
                return self._index
            self._stamp = stamp
            try:
                pins = json.loads(self.pins_path.read_text(encoding="ascii"))
            except (OSError, ValueError):
                pins = None
            if not isinstance(pins, dict):
                self._pin_key, self._index = None, {}
                return self._index
            files = pins.get("pob2_files")
            pin_key = (json.dumps(pins.get("pob2"), sort_keys=True),
                       json.dumps(files.get(self.REL) if isinstance(files, dict) else None,
                                  sort_keys=True))
            if pin_key != self._pin_key:
                root = self.root or checkout_root(pins, self.environ)
                self._index = self.LOAD(root, pins) if root else {}
                self._pin_key = pin_key
            return self._index


class Augments(GemVariants):
    """DATA-AUGMENT-POB-TEXT (decision 0091): load_augments of the pinned
    checkout, read once per pin the same way, {} while it cannot be read."""

    REL = AUGMENTS
    LOAD = staticmethod(load_augments)
