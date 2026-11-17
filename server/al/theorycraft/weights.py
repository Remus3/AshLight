"""Editable stat weights for TC-EVAL (research 0010 section 4, phase 1).

Mod text is normalised to a stat key: every rolled number becomes `#`, a
signed number becomes `+#` (so "-10% to Fire Resistance" and "+25% to Fire
Resistance" share "+#% to Fire Resistance"), and "reduced" / "less" read as
"increased" / "more" with the value negated. Keys compare case-insensitively.

The weights live in a per-host JSON file under the runtime dir
(`<runtime>/theorycraft/weights.json`, gitignored ops/runtime/ by default;
`paths.weights_file()`), written with the defaults on first use so the user
can edit it. A bad file never crashes the core: the defaults are used and
the file is left alone for the user to fix.
"""

import json
import logging
import math
import re
import threading
from pathlib import Path

from . import item as item_mod

log = logging.getLogger("al.theorycraft")

VERSION = 1
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


def default_path(runtime_dir):
    return Path(runtime_dir) / "theorycraft" / "weights.json"


def _write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="ascii", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
    tmp.replace(path)


class WeightsStore:
    """The weights file: read on make, defaults written when missing."""

    def __init__(self, path):
        self.path = Path(path)
        self.load_error = None
        self._lock = threading.Lock()
        self.doc = self._load()

    def _load(self):
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            doc = defaults()
            try:
                _write(self.path, doc)
            except OSError as e:
                log.warning("default weights not written: %s", e)
            return doc
        except OSError as e:
            self.load_error = f"unreadable: {type(e).__name__}"
            return defaults()
        try:
            return validate(json.loads(text))
        except (ValueError, WeightsError) as e:
            self.load_error = str(e)
            log.warning("weights file not used, defaults instead: %s", e)
            return defaults()

    def get(self):
        with self._lock:
            return json.loads(json.dumps(self.doc))

    def put(self, doc):
        """Validate, persist and use a new document. Raises WeightsError."""
        clean = validate(doc)
        with self._lock:
            _write(self.path, clean)
            self.doc = clean
            self.load_error = None
        return self.get()

    def snapshot(self):
        out = self.get()
        out["load_error"] = self.load_error
        return out
