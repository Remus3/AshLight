"""Editable stat weights for TC-EVAL (research 0010 section 4, phase 1).

Mod text is normalised to a stat key: every rolled number becomes `#`, a
signed number becomes `+#` (so "-10% to Fire Resistance" and "+25% to Fire
Resistance" share "+#% to Fire Resistance"), and "reduced" / "less" read as
"increased" / "more" with the value negated. Keys compare case-insensitively.

The weights live in a per-host JSON file under the runtime dir
(`<runtime>/theorycraft/weights.json`, gitignored ops/runtime/ by default;
`paths.weights_file()`). A bad file never crashes the core: the defaults are
used and the file is left alone for the user to fix.

TC-WEIGHTS-DELTA-STORE (F-134): the file (version 2) holds only the player's
changes over the defaults: a row whose weight differs, a row the player
added, a default row the player removed (stored as null), and the band parts
(sidegrade abs / pct) that differ. The full document is merged at load, so a
default AshLight changes reaches every row the player did not touch. A
version 1 file (the old full document) migrates at load with no score
change, after one backup of its bytes beside it (weights.v1.json, never
overwritten). get() still returns the merged full document.
"""

import json
import logging
import math
import re
import threading
from pathlib import Path

from .. import jsonfile
from . import item as item_mod

log = logging.getLogger("al.theorycraft")

VERSION = 2
V1_BACKUP = "weights.v1.json"
MAX_KEYS = 500
MAX_KEY_LEN = 200
MAX_WEIGHT = 1e6
# MATH-NUM: a rolled value past this (or not finite) is no value, so a
# crafted item line can never push a score to inf / NaN (invalid JSON)
MAX_VALUE = 1e9

# Sane phase-1 defaults: a generic life / resist / damage leaning. Values
# are per point of the stat ("Adds # to #" uses the average of the two).
DEFAULT_WEIGHTS = {
    "+# to maximum Life": 1.0,
    "#% increased maximum Life": 6.0,
    "+# to maximum Energy Shield": 1.0,
    "#% increased maximum Energy Shield": 3.0,
    "+# to maximum Mana": 0.3,
    "+# to Spirit": 0.5,
    "+#% to Fire Resistance": 1.0,
    "+#% to Cold Resistance": 1.0,
    "+#% to Lightning Resistance": 1.0,
    "+#% to Chaos Resistance": 1.5,
    "+#% to all Elemental Resistances": 3.0,
    "+# to Strength": 0.4,
    "+# to Dexterity": 0.4,
    "+# to Intelligence": 0.4,
    "+# to all Attributes": 1.2,
    "+# to Armour": 0.1,
    "+# to Evasion Rating": 0.1,
    "#% increased Armour": 0.5,
    "#% increased Evasion Rating": 0.5,
    "#% increased Energy Shield": 0.5,
    "#% increased Physical Damage": 1.0,
    "Adds # to # Physical Damage": 1.5,
    "Adds # to # Fire Damage": 1.0,
    "Adds # to # Cold Damage": 1.0,
    "Adds # to # Lightning Damage": 1.0,
    "#% increased Spell Damage": 1.0,
    "#% increased Elemental Damage": 0.8,
    "#% increased Attack Speed": 2.0,
    "#% increased Cast Speed": 2.0,
    "#% increased Critical Hit Chance": 0.5,
    "#% increased Critical Damage Bonus": 0.5,
    "+# to Accuracy Rating": 0.05,
    "#% increased Movement Speed": 2.0,
    "+# to Level of all Spell Skills": 15.0,
    "+# to Level of all Melee Skills": 15.0,
    "+# to Level of all Projectile Skills": 15.0,
    "#% increased Rarity of Items found": 0.2,
    "#% of Damage taken Recouped as Life": 1.0,
    "Gain # Life per Enemy Killed": 0.5,
}
DEFAULT_SIDEGRADE = {"abs": 2.0, "pct": 5.0}

_NUM_RE = re.compile(r"([+-]?)(\d+(?:\.\d+)?)")
_NEGATE = (("reduced", "increased"), ("less", "more"))
_GOVERN_RE = re.compile(r"\b(increased|reduced|more|less)\b", re.I)


class WeightsError(ValueError):
    """A weights document that does not validate."""


def defaults():
    return {"version": VERSION, "weights": dict(DEFAULT_WEIGHTS),
            "sidegrade": dict(DEFAULT_SIDEGRADE)}


def _num(text):
    v = float(text)
    return int(v) if v.is_integer() else v


def stat_key(text):
    """(key, value) for one mod line; value None when it has no number.

    Two numbers in an "Adds # to #" line read as their average; otherwise
    the first number is the value."""
    if not isinstance(text, str):
        return None, None
    text = item_mod.strip_rolls(text)
    values = []

    def repl(m):
        v = _num(m.group(2))
        start = m.start()
        signed = bool(m.group(1)) and (start == 0 or text[start - 1] in " (")
        if signed:
            values.append(-v if m.group(1) == "-" else v)
            return "+#"
        values.append(v)
        return m.group(1) + "#"

    key = re.sub(r"\s+", " ", _NUM_RE.sub(repl, text)).strip()
    # the sign follows the word that governs the first number only
    # ("10% increased A and 5% reduced B" stays positive); every negative
    # word is still rewritten so the key matches its positive twin
    first = _GOVERN_RE.search(key)
    sign = -1 if first and first.group(1).lower() in ("reduced", "less") else 1
    for word, repl in _NEGATE:
        key = re.sub(r"\b" + word + r"\b", repl, key, flags=re.I)
    if not values:
        return key, None
    if len(values) == 2 and key.lower().startswith("adds # to #"):
        value = (values[0] + values[1]) / 2
    else:
        value = values[0]
    value = value * sign
    if not math.isfinite(value) or abs(value) > MAX_VALUE:
        return key, None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return key, value


def lookup(weights):
    """A case-insensitive view: lower key -> (canonical key, weight)."""
    return {k.lower(): (k, float(v)) for k, v in weights.items()}


def validate(doc):
    """A clean weights document from user input. Raises WeightsError."""
    if not isinstance(doc, dict):
        raise WeightsError("weights document must be an object")
    raw = doc.get("weights")
    if not isinstance(raw, dict):
        raise WeightsError("weights (object of stat key -> number) required")
    if len(raw) > MAX_KEYS:
        raise WeightsError(f"at most {MAX_KEYS} weights")
    clean = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not k.strip() or len(k) > MAX_KEY_LEN:
            raise WeightsError("each stat key must be a non-empty string")
        if not k.isascii():
            raise WeightsError(f"stat key must be ASCII: {k[:40]!r}")
        if isinstance(v, bool) or not isinstance(v, (int, float)) \
                or not math.isfinite(v) or abs(v) > MAX_WEIGHT:
            raise WeightsError(f"weight for {k!r} must be a finite number")
        key = re.sub(r"\s+", " ", k).strip()
        if key.lower() in {c.lower() for c in clean}:
            raise WeightsError(f"duplicate stat key {key!r}")
        clean[key] = v
    side = doc.get("sidegrade", DEFAULT_SIDEGRADE)
    if not isinstance(side, dict):
        raise WeightsError("sidegrade must be an object {abs, pct}")
    sg = {}
    for name in ("abs", "pct"):
        v = side.get(name, DEFAULT_SIDEGRADE[name])
        if isinstance(v, bool) or not isinstance(v, (int, float)) \
                or not math.isfinite(v) or v < 0 or v > MAX_WEIGHT:
            raise WeightsError(f"sidegrade.{name} must be a number >= 0")
        sg[name] = v
    return {"version": VERSION, "weights": clean, "sidegrade": sg}


def _row_default(key):
    """(canonical default key, default weight) for a key, or (None, None)."""
    low = key.lower()
    for k, v in DEFAULT_WEIGHTS.items():
        if k.lower() == low:
            return k, v
    return None, None


def overrides_of(doc):
    """The player's changes in a clean full document, as the version 2 file.

    weights: rows that differ from the defaults (added or changed, under the
    player's key) and default rows the document lacks (null); sidegrade: the
    band parts that differ. Keys compare case-insensitively."""
    rows = {}
    seen = set()
    for k, v in doc["weights"].items():
        dk, dv = _row_default(k)
        if dk is not None:
            seen.add(dk.lower())
            if dk == k and float(dv) == float(v):
                continue
            if dk != k:
                rows[dk] = None
        rows[k] = v
    for dk in DEFAULT_WEIGHTS:
        if dk.lower() not in seen:
            rows[dk] = None
    side = {n: v for n, v in doc["sidegrade"].items()
            if float(v) != float(DEFAULT_SIDEGRADE[n])}
    return {"version": VERSION, "weights": rows, "sidegrade": side}


def merge(over):
    """The full document: the defaults with a version 2 file applied."""
    rows = dict(DEFAULT_WEIGHTS)
    for k, v in over.get("weights", {}).items():
        if v is None:
            rows.pop(k, None)
    for k, v in over.get("weights", {}).items():
        if v is None:
            continue
        dk, _ = _row_default(k)
        if dk is not None and dk != k:
            rows.pop(dk, None)
        rows[k] = v
    side = dict(DEFAULT_SIDEGRADE)
    side.update(over.get("sidegrade", {}))
    return validate({"weights": rows, "sidegrade": side})


def validate_overrides(doc):
    """A clean version 2 file. Raises WeightsError."""
    if not isinstance(doc, dict) or not isinstance(doc.get("weights"), dict):
        raise WeightsError("weights (object of stat key -> number or null) required")
    raw = doc["weights"]
    if len(raw) > MAX_KEYS + len(DEFAULT_WEIGHTS):
        raise WeightsError(f"at most {MAX_KEYS} weights")
    rows = {}
    for k, v in raw.items():
        if v is None:
            dk = _row_default(k)[0] if isinstance(k, str) else None
            if dk is None:
                raise WeightsError(f"null is only for a default row: {str(k)[:40]!r}")
            rows[dk] = None
    kept = validate({"weights": {k: v for k, v in raw.items() if v is not None},
                     "sidegrade": {}})["weights"]
    rows.update(kept)
    side = doc.get("sidegrade", {})
    if not isinstance(side, dict) or set(side) - set(DEFAULT_SIDEGRADE):
        raise WeightsError("sidegrade must be an object {abs, pct}")
    sg = validate({"weights": {}, "sidegrade": dict(DEFAULT_SIDEGRADE, **side)})["sidegrade"]
    return {"version": VERSION, "weights": rows,
            "sidegrade": {n: sg[n] for n in side}}


def default_path(runtime_dir):
    return Path(runtime_dir) / "theorycraft" / "weights.json"


class WeightsStore:
    """The weights file: the player's changes, merged over the defaults at
    load; an empty change file is written when missing."""

    def __init__(self, path):
        self.path = Path(path)
        self.load_error = None
        self._lock = threading.Lock()
        self.doc = self._load()

    def _write(self, over):
        jsonfile.write_json(self.path, over, sort_keys=True)

    def _load(self):
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            doc = defaults()
            try:
                self._write(overrides_of(doc))
            except OSError as e:
                log.warning("default weights not written: %s", e)
            return doc
        except OSError as e:
            self.load_error = f"unreadable: {type(e).__name__}"
            return defaults()
        try:
            raw = json.loads(text)
            version = raw.get("version", 1) if isinstance(raw, dict) else None
            if version == VERSION:
                return merge(validate_overrides(raw))
            if version != 1:
                raise WeightsError(f"unknown weights file version {version!r}")
            doc = validate(raw)
        except (ValueError, WeightsError) as e:
            self.load_error = str(e)
            log.warning("weights file not used, defaults instead: %s", e)
            return defaults()
        self._migrate(text, doc)
        return doc

    def _migrate(self, text, doc):
        """A good version 1 file: back its bytes up once, then rewrite it as
        the player's changes. A failed step leaves the old file as it was;
        the merged document is the same either way."""
        backup = self.path.with_name(V1_BACKUP)
        try:
            if not backup.exists():
                jsonfile.write_text(backup, text)
            self._write(overrides_of(doc))
        except OSError as e:
            log.warning("weights file not migrated: %s", e)

    def get(self):
        with self._lock:
            return json.loads(json.dumps(self.doc))

    def put(self, doc):
        """Validate, persist (as changes) and use a new full document.
        Raises WeightsError."""
        clean = validate(doc)
        with self._lock:
            self._write(overrides_of(clean))
            self.doc = clean
            self.load_error = None
        return self.get()

    def reset(self, key=None):
        """Back to the defaults: one row (key, case-insensitive) or, with no
        key, every row and the band."""
        if key is None:
            return self.put(defaults())
        doc = self.get()
        low = key.lower()
        rows = {k: v for k, v in doc["weights"].items() if k.lower() != low}
        dk, dv = _row_default(key)
        if dk is not None:
            rows[dk] = dv
        doc["weights"] = rows
        return self.put(doc)

    def snapshot(self):
        """The merged document plus load_error, the defaults and the
        player's changes (null = a removed default row)."""
        out = self.get()
        out["load_error"] = self.load_error
        changed = overrides_of(out)
        out["defaults"] = defaults()
        out["changed"] = {"weights": changed["weights"],
                          "sidegrade": changed["sidegrade"]}
        return out
