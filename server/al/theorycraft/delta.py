"""TC-DELTA: PoB-backed item deltas and per-mod weights (decision 0022).

The calc component (TC-BRIDGE: the pinned, unmodified PoB-PoE2 checkout run
by the pinned LuaJIT, decision 0018) is seen here only as a callable

    calc(build, swaps) -> {"dps": number, "ehp": number}

where `swaps` maps a PoB gear slot name to item text that replaces the
build's item in that slot for this one calculation ({} = the build as
loaded). The bridge client maps PoB's own outputs to these two keys. This
module never starts a process, reads the clipboard or touches the network;
it only asks the calc and does arithmetic.

- `item_delta`: DPS and EHP of the build with the checked item swapped into
  a slot vs the build as it is.
- `mod_weights`: per-mod weights from PoB deltas. Each stat key is probed
  by appending one line ("+10 to maximum Life") to a carrier item in the
  slot (the equipped item, else the checked item) and measuring the change;
  the weight is the blended percent change per point of the stat. These
  replace the hand weights for the item check and the TC-UPGRADE doc.

A calc that raises, times out or answers junk surfaces as CalcError; the
caller (theorycraft.evaluate) then falls back to the stat weights and the
card says so.
"""

import math

from . import weights as weights_mod

OUTPUTS = ("dps", "ehp")
SOURCE_POB, SOURCE_WEIGHTS = "pob", "weights"
NOTICE_OFF, NOTICE_FAILED = "off", "failed"
DEFAULT_BLEND = {"dps": 0.5, "ehp": 0.5}
PROBE_VALUE = 10
MAX_PROBES = 24
SIDEGRADE_PCT = 1.0
UPGRADE, SIDEGRADE, DOWNGRADE = "upgrade", "sidegrade", "downgrade"


class CalcError(RuntimeError):
    """The calc component did not give a usable answer."""


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value):
        raise CalcError(f"calc output {name} is not a finite number")
    return float(value)


def outputs(calc, build, swaps=None):
    """{"dps", "ehp"} floats for the build with `swaps` applied."""
    try:
        raw = calc(build, dict(swaps or {}))
    except CalcError:
        raise
    except Exception as e:  # the bridge is an external process: any failure
        raise CalcError(f"calc raised {type(e).__name__}") from e
    if not isinstance(raw, dict):
        raise CalcError("calc answer is not an object")
    return {k: _number(raw.get(k), k) for k in OUTPUTS}


def _clean(n):
    n = round(n, 4)
    return int(n) if float(n).is_integer() else n


def _pct(old, new):
    if old == 0:
        return 0.0 if new == 0 else None
    return (new - old) / abs(old) * 100.0


def pct(old, new):
    """Percent change (4 decimals), 0.0 for 0 -> 0, None when the base is 0."""
    p = _pct(old, new)
    return None if p is None else round(p, 4)


def change(old, new):
    return {"old": _clean(old), "new": _clean(new), "delta": _clean(new - old),
            "pct": pct(old, new)}


def _blend(blend):
    b = dict(DEFAULT_BLEND)
    b.update(blend or {})
    return b


def combined(pcts, blend=None):
    """The blended percent change: sum(blend[k] * pct[k]); None reads 0."""
    b = _blend(blend)
    return sum(float(b.get(k, 0)) * (pcts.get(k) or 0.0) for k in OUTPUTS)


def verdict(score_delta):
    if score_delta > SIDEGRADE_PCT:
        return UPGRADE
    if score_delta < -SIDEGRADE_PCT:
        return DOWNGRADE
    return SIDEGRADE


def item_delta(calc, build, slot, item_text, blend=None, base=None):
    """{"dps": change, "ehp": change, "score_delta": blended pct} of the
    build with `item_text` in `slot`. `base`: the build's outputs if the
    caller already has them."""
    if base is None:
        base = outputs(calc, build)
    new = outputs(calc, build, {slot: item_text})
    out = {k: change(base[k], new[k]) for k in OUTPUTS}
    out["score_delta"] = round(combined({k: out[k]["pct"] for k in OUTPUTS}, blend), 4)
    return out


def probe_line(key, value=PROBE_VALUE):
    """One mod line for a stat key with every `#` set to `value`; None for a
    flag mod (no number to scale by)."""
    if not isinstance(key, str) or "#" not in key:
        return None
    v = str(value)
    return key.replace("+#", "+" + v).replace("#", v)


def with_line(text, line):
    return (text or "").rstrip("\r\n") + "\n" + line


def mod_weights(calc, build, slot, carrier, keys, blend=None):
    """{"weights": {key: blended pct per point}, "detail": {key: {"dps",
    "ehp"} pct per point}} for up to MAX_PROBES numeric stat keys, probed on
    the carrier item text in `slot`."""
    base = outputs(calc, build, {slot: carrier})
    weights, detail, probed = {}, {}, 0
    for key in keys:
        line = probe_line(key)
        if line is None:
            continue
        _, value = weights_mod.stat_key(line)
        if not value:
            continue
        if probed >= MAX_PROBES:
            break
        probed += 1
        got = outputs(calc, build, {slot: with_line(carrier, line)})
        per = {k: (_pct(base[k], got[k]) or 0.0) / value for k in OUTPUTS}
        weights[key] = round(combined(per, blend), 6)
        detail[key] = {k: round(per[k], 6) for k in OUTPUTS}
    return {"weights": weights, "detail": detail}
