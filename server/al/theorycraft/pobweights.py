"""MATH-WEIGHTS: stat weights from Path of Building outputs, kept per build.

TC-DELTA (decision 0024) probes each stat key through the PoB calc (one
full PoB calculation per key, up to delta.MAX_PROBES per slot) on every
item check. Those weights depend only on the build, the slot, the carrier
item in that slot and the DPS / EHP blend, so this cache keeps them:

- a re-check (another item, a weights edit, a build re-score) probes only
  the stat keys it has not measured yet for that build and slot;
- when the optional calc component is off or fails, the item check can
  still score with the weights PoB measured earlier for the same build
  (source "pob_cached", with the off / failed notice), never with weights
  of another build.

Every weight is PoB's own number (blended percent change of DPS / EHP per
point of the stat, theorycraft.delta.mod_weights); nothing here computes
damage or EHP (decision 0004). In memory only, bounded, thread-safe.
"""

import hashlib
import json
import threading
from collections import OrderedDict

from . import delta as delta_mod
from . import weights as weights_mod

SOURCE_CACHED = "pob_cached"
MAX_ENTRIES = 64


def _sha(text):
    return hashlib.sha256((text or "").encode("utf-8", "replace")).hexdigest()[:24]


def build_id(build):
    """A short id of a build's PoB XML (None for no build)."""
    raw = getattr(build, "raw_xml", None)
    return None if raw is None else _sha(raw)


def _blend_id(blend):
    b = dict(delta_mod.DEFAULT_BLEND)
    b.update(blend or {})
    return json.dumps({k: float(b.get(k, 0)) for k in delta_mod.OUTPUTS}, sort_keys=True)


def probeable(key):
    """True when delta.mod_weights would probe this key (it has a number)."""
    line = delta_mod.probe_line(key)
    if line is None:
        return False
    _, value = weights_mod.stat_key(line)
    return bool(value)


class PobWeightCache:
    """{(build, slot, carrier, blend): {lower key: (key, weight, detail)}}."""

    def __init__(self, max_entries=MAX_ENTRIES):
        self.max_entries = max(1, int(max_entries))
        self._data = OrderedDict()
        self._lock = threading.Lock()
        self.probes = 0  # stat keys sent to the calc (tests, telemetry)

    def _key(self, build, slot, carrier, blend):
        return (build_id(build), (slot or "").lower(), _sha(carrier), _blend_id(blend))

    def mod_weights(self, calc, build, slot, carrier, keys, blend=None):
        """delta.mod_weights for `keys`, probing only the ones not cached for
        this build / slot / carrier / blend. Raises delta.CalcError."""
        k = self._key(build, slot, carrier, blend)
        with self._lock:
            entry = dict(self._data.get(k) or {})
        missing, seen = [], set()
        for key in keys:
            low = key.lower()
            if low in entry or low in seen or not probeable(key):
                continue
            seen.add(low)
            missing.append(key)
        if missing:
            got = delta_mod.mod_weights(calc, build, slot, carrier, missing, blend=blend)
            for key, w in got["weights"].items():
                entry[key.lower()] = (key, w, dict(got["detail"].get(key) or {}))
            with self._lock:
                self.probes += len(got["weights"])
                self._data[k] = entry
                self._data.move_to_end(k)
                while len(self._data) > self.max_entries:
                    self._data.popitem(last=False)
        elif entry:
            with self._lock:
                if k in self._data:
                    self._data.move_to_end(k)
        weights, detail = {}, {}
        for key in keys:
            hit = entry.get(key.lower())
            if hit:
                weights[hit[0]] = hit[1]
                detail[hit[0]] = dict(hit[2])
        return {"weights": weights, "detail": detail}

    def fallback(self, build, slot, blend=None):
        """{key: weight} PoB measured earlier for this build and slot (any
        carrier, the most recent first wins), {} when none."""
        bid, s, bl = build_id(build), (slot or "").lower(), _blend_id(blend)
        if bid is None:
            return {}
        out = {}
        with self._lock:
            entries = [v for (b, sl, _c, bb), v in reversed(self._data.items())
                       if b == bid and sl == s and bb == bl]
        for entry in entries:
            for low, (key, w, _d) in entry.items():
                if low not in {x.lower() for x in out}:
                    out[key] = w
        return out

    def clear(self):
        with self._lock:
            self._data.clear()
