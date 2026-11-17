"""AUDIT-TC-WIRE: the PoB calc callable the item check uses (decision 0024).

theorycraft.delta asks a callable `calc(build, swaps) -> {"dps", "ehp"}`;
this module makes one from the TC-BRIDGE client (decision 0022): load the
build's own PoB XML, equip each swapped item in its slot, read PoB's main
output table and map PoB's names to the two neutral keys (decision 0024
R2: name drift stays here, TC-DRIFT).

Opt-in and off by default: `Provider` returns None unless the local config
says "tc_calc": true AND the hash-pinned component is installed (setup.ps1
-TcCalc). The bridge module is imported only then, so a core with the
component off never loads it. Any bridge failure surfaces through
delta.outputs as CalcError, and the card falls back with a notice.

Inputs are only the user's pasted build XML and hotkey-read item text;
nothing here touches the game (CLAUDE.md ToS floor).
"""

import math
import threading
import time

# PoB output names, first present wins (research 0010 section 4: FullDPS
# with fallbacks; TotalEHP, else Life + EnergyShield)
DPS_KEYS = ("FullDPS", "CombinedDPS", "TotalDPS", "TotalDotDPS")
EHP_KEYS = ("TotalEHP",)
EHP_PARTS = ("Life", "EnergyShield")
OUTPUT_KEYS = DPS_KEYS + EHP_KEYS + EHP_PARTS
RECHECK_S = 30.0
# MATH-WEAPON-TYPE (decision 0032 amendment): PoB's own disableReason texts
# (pinned checkout, src/Modules/CalcActiveSkill.lua) that mean the main
# skill cannot use the weapon now equipped. Name drift stays here (TC-DRIFT);
# the live test in tests/test_math_weapon_type.py reads the real one.
WEAPON_REASONS = (
    "Main Hand weapon is not usable with this skill",
    "Off Hand weapon is not usable with this skill",
    "No usable weapon equipped",
    "Weapon Types Need to be Different",
)
WEAPON_SLOT_PREFIX = "Weapon "


class OutputError(RuntimeError):
    """PoB's output table had no usable DPS or EHP figure."""


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def map_outputs(out):
    """{"dps", "ehp"} from PoB's output table. Raises OutputError."""
    out = out if isinstance(out, dict) else {}
    dps = next((n for n in (_num(out.get(k)) for k in DPS_KEYS) if n is not None), None)
    ehp = next((n for n in (_num(out.get(k)) for k in EHP_KEYS) if n is not None), None)
    if ehp is None:
        parts = [_num(out.get(k)) for k in EHP_PARTS]
        if any(p is not None for p in parts):
            ehp = sum(p for p in parts if p is not None)
    if dps is None or ehp is None:
        raise OutputError("PoB outputs carry no DPS or EHP figure")
    return {"dps": dps, "ehp": ehp}


def make_calc(get_bridge):
    """A delta calc over a bridge client (`get_bridge()` returns one with
    load_build / set_item / outputs). The build is reloaded before every
    swapped calculation so one item swap never leaks into the next."""
    lock = threading.Lock()
    state = {"xml": None, "dirty": True}

    def calc(build, swaps):
        xml = getattr(build, "raw_xml", None)
        if not isinstance(xml, str) or not xml.strip():
            raise OutputError("no build XML")
        b = get_bridge()
        with lock:
            if swaps or state["dirty"] or state["xml"] != xml:
                b.load_build(xml)
                state["xml"], state["dirty"] = xml, False
            for slot, text in (swaps or {}).items():
                state["dirty"] = True
                b.set_item(text, slot=slot)
            out = map_outputs(b.outputs(keys=list(OUTPUT_KEYS)))
            if any(str(s).startswith(WEAPON_SLOT_PREFIX) for s in (swaps or {})):
                unusable = weapon_unusable(b)
                if unusable:
                    out["weapon_unusable"] = unusable
            return out

    def raw(build, keys):
        """MATH-SKILL-SPLIT / MATH-DEF-BREAKDOWN: PoB's output table for the
        build itself (no swap), only the named keys (pobout.OutputsCache)."""
        xml = getattr(build, "raw_xml", None)
        if not isinstance(xml, str) or not xml.strip():
            raise OutputError("no build XML")
        b = get_bridge()
        with lock:
            if state["dirty"] or state["xml"] != xml:
                b.load_build(xml)
                state["xml"], state["dirty"] = xml, False
            return dict(b.outputs(keys=list(keys)))

    calc.raw = raw
    return calc


def weapon_unusable(bridge):
    """MATH-WEAPON-TYPE: {"skill", "reason"} when PoB says the main skill
    cannot use the equipped weapon, else None. A bridge without the
    "main_skill" command (or an error from it) reads as None, so the
    sanity guard in delta still applies."""
    ask = getattr(bridge, "main_skill", None)
    if not callable(ask):
        return None
    try:
        got = ask()
    except Exception:  # noqa: BLE001 - extra info only; never fail the calc
        return None
    if not isinstance(got, dict) or not got.get("disabled"):
        return None
    reason = got.get("reason")
    if reason not in WEAPON_REASONS:
        return None
    name = got.get("name")
    return {"skill": name if isinstance(name, str) and name else None, "reason": reason}


class Provider:
    """The core's calc provider: None while off, else one shared calc.

    `enabled()`: the user's opt-in (local config "tc_calc": true).
    `available()` / `get_bridge()`: default to the real component (imported
    lazily); tests inject doubles. Availability is re-checked at most every
    RECHECK_S while enabled but not yet available."""

    def __init__(self, enabled, available=None, get_bridge=None, clock=time.monotonic,
                 stop=None):
        self.enabled = enabled
        self._available = available
        self._get_bridge = get_bridge
        self._stop = stop  # tests; default: the real shared bridge's shutdown
        self._clock = clock
        self._calc = None
        self._checked = None
        self._lock = threading.Lock()

    def _real_available(self):
        from . import bridge  # lazy: only with the opt-in on
        return bridge.available()

    def _real_bridge(self):
        from . import bridge
        return bridge.shared()

    def __call__(self):
        try:
            on = bool(self.enabled())
        except Exception:  # noqa: BLE001 - a bad config reads as off
            on = False
        if not on:
            self.close()  # P3-6: turned off while running -> stop the process
            return None
        with self._lock:
            if self._calc is not None:
                return self._calc
            now = self._clock()
            if self._checked is not None and now - self._checked < RECHECK_S:
                return None
            self._checked = now
            try:
                ok = (self._available or self._real_available)()
            except Exception:  # noqa: BLE001 - missing pins etc. read as absent
                ok = False
            if not ok:
                return None
            self._calc = make_calc(self._get_bridge or self._real_bridge)
            return self._calc

    def running(self):
        """True while this provider holds a calc (the process may be up)."""
        return self._calc is not None

    def reap(self):
        """AREA-AUDIT P3-6, from the core's loop tick: stop the calc process
        once the user turned tc_calc off. Reads the opt-in only while a calc
        is running (no config read when idle). True when it stopped one."""
        if self._calc is None:
            return False
        try:
            on = bool(self.enabled())
        except Exception:  # noqa: BLE001 - a bad config reads as off
            on = False
        return False if on else self.close()

    def close(self):
        """Stop the shared bridge process if this provider started one;
        True when it did."""
        with self._lock:
            started, self._calc = self._calc is not None, None
            self._checked = None  # a later opt-in re-checks at once
        if not started:
            return False
        if self._stop is not None:
            self._stop()
        elif self._get_bridge is None:
            from . import bridge
            bridge.shutdown_shared()
        return True
