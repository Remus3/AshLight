"""MATH-PERF: bridge latency and LuaJIT memory budgets (decision 0028).

Measured on the reference build (pobb.in Nqt6FK5lIc6F): cold start, load,
reload, a warm set_item + outputs, and the luajit.exe peak working set
over 12 reloads (one first item check reloads the build about 22 times).
The ceilings in tc_live_util.BUDGET are generous; the memory one also
guards the bridge.lua GC ceiling (without it the working set reached
~900 MB). Skips without the optional calc component and the reference.
"""

import time

import pytest

from tc_live_util import BUDGET, CALC_MARKS, LIVE_REF, process_memory_mb, reference

from server.al.theorycraft import bridge, calcwire

pytestmark = [pytest.mark.slow, pytest.mark.timing, LIVE_REF, *CALC_MARKS]

RING = """Item Class: Rings
Rarity: Rare
Perf Coil
Prismatic Ring
--------
Item Level: 82
--------
+10% to all Elemental Resistances (implicit)
--------
Adds 12 to 22 Physical Damage to Attacks
+150 to maximum Life
+40% to Fire Resistance
"""


@pytest.fixture(scope="module")
def perf():
    ref, xml = reference()
    b = bridge.Bridge.from_component(start_timeout=180.0, timeout=120.0)
    got = {}
    t0 = time.perf_counter()
    b.ping()
    got["cold_start_s"] = time.perf_counter() - t0
    try:
        yield b, xml, got
    finally:
        b.close()
        print("\nMATH-PERF measured:", {k: round(v, 3) for k, v in got.items()})


def test_cold_start_within_budget(perf):
    _, _, got = perf
    assert got["cold_start_s"] <= BUDGET["cold_start_s"], got


def test_load_reload_and_item_within_budget(perf):
    b, xml, got = perf
    t0 = time.perf_counter()
    b.load_build(xml)
    got["load_build_s"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    b.load_build(xml)
    got["reload_s"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    b.set_item(RING, slot="Ring 1")
    out = b.outputs(list(calcwire.OUTPUT_KEYS))
    got["set_item_s"] = time.perf_counter() - t0
    assert calcwire.map_outputs(out)["dps"] > 0
    for key in ("load_build_s", "reload_s", "set_item_s"):
        assert got[key] <= BUDGET[key], (key, got[key])


RELOADS = 12  # the GC ceiling acts per load_build; 12 passes keep the peak guard


def test_luajit_memory_stays_under_ceiling(perf):
    b, xml, got = perf
    times = []
    for _ in range(RELOADS):
        t0 = time.perf_counter()
        b.load_build(xml)
        times.append(time.perf_counter() - t0)
    mem = process_memory_mb(b._proc.pid)
    times.sort()
    got["reload_median_s"] = times[len(times) // 2]
    got["ws_mb"] = mem["ws"]
    got["peak_ws_mb"] = mem["peak_ws"]
    assert got["reload_median_s"] <= BUDGET["reload_s"], got
    assert mem["peak_ws"] <= BUDGET["peak_ws_mb"], (
        f"luajit.exe peak working set {mem['peak_ws']:.0f} MB over the "
        f"{BUDGET['peak_ws_mb']:.0f} MB budget (decision 0028); check the "
        "GC ceiling in bridge.lua load_build")
