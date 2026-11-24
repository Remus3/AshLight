"""Core budgets (docs/decisions/0002-stack.md): parse speed, idle CPU (B1
runs the tailer thread inside the real loop body), bounded memory. Timing
budgets widen with fleet_test_guard.budget() while other suites share the
box. Under AL_CI=1 (CI only) a timing assert skips
with the measured value printed, after the structural checks (decision
0080); the memory bounds always hold.

RUN-BUDGET-TESTS-DET (F-108, research 0048 R6) adds B1 (the real loop body
for 5 s on the worst-case fixture) and B5 (the absolute working set of a
core in a child process); B2, B3 and B7 are the deterministic files
tests/test_budget_tick.py and tests/test_budget_snapshot.py."""

import gc
import os
import sys
import time
from pathlib import Path

import pytest

import fleet_test_guard
from ci_timing import skip_if_ci_timing
from server.al import parser, resume
from server.al.bus import EventBus
from server.al.logfile import Tailer
from server.al.state import SessionState

FIXTURE = Path(__file__).parent / "fixtures" / "client_sample.txt"
# TEST-MARKS: every budget here is wall-clock sensitive.
pytestmark = pytest.mark.timing


def _lines(n):
    base = FIXTURE.read_text(encoding="ascii").splitlines()
    return (base * (n // len(base) + 1))[:n]


def test_parse_10k_lines_under_250ms():
    lines = _lines(10_000)
    parser.parse_lines(lines[:100])  # warm the regex cache
    t0 = time.perf_counter()
    events = parser.parse_lines(lines)
    elapsed = time.perf_counter() - t0
    assert len(events) > 8_000
    skip_if_ci_timing("parse of 10k lines", f"{elapsed * 1000:.1f} ms")
    assert elapsed < fleet_test_guard.budget(0.25), f"{elapsed * 1000:.1f} ms"


def test_tail_1000_line_burst_under_50ms(tmp_path):
    p = tmp_path / "Client.txt"
    p.write_bytes(b"")
    got = []
    t = Tailer(p, lambda line: got.append(parser.parse_line(line)))
    t.poll_once()
    with open(p, "ab") as fh:
        fh.write(("\n".join(_lines(1000)) + "\n").encode("ascii"))
    t0 = time.perf_counter()
    n = t.poll_once()
    elapsed = time.perf_counter() - t0
    assert n == 1000
    skip_if_ci_timing("tail of a 1000-line burst", f"{elapsed * 1000:.1f} ms")
    assert elapsed < fleet_test_guard.budget(0.05), f"{elapsed * 1000:.1f} ms"


def test_resume_scan_of_full_32mb_cap_under_500ms(tmp_path):
    # LIVE-RESUME worst realistic case: no LOG FILE OPENING marker, so the
    # scan runs to the full byte cap. One fixture block per 200 engine lines.
    block = FIXTURE.read_bytes().replace(b"LOG FILE OPENING", b"LOG FILE X")
    noise = (b"2026/11/16 20:00:01 1100 1a2b3c4d [INFO Client 4242] "
             b"[ENGINE] synthetic engine noise line\r\n") * 200
    p = tmp_path / "Client.txt"
    with open(p, "wb") as fh:
        while fh.tell() < resume.DEFAULT_MAX_BYTES + 1024 * 1024:
            fh.write(block + noise)
    resume.scan(p, max_bytes=1024 * 1024)  # warm the file cache
    t0 = time.perf_counter()
    r = resume.scan(p)
    elapsed = time.perf_counter() - t0
    assert r["bytes_scanned"] > resume.DEFAULT_MAX_BYTES - 1024
    assert r["level"] is not None and r["zone"] is not None
    skip_if_ci_timing("resume scan of the 32 MB cap", f"{elapsed * 1000:.1f} ms")
    assert elapsed < fleet_test_guard.budget(0.5), f"{elapsed * 1000:.1f} ms"


def _rss_bytes():
    try:
        import psutil  # optional
        return psutil.Process().memory_info().rss
    except ImportError:
        pass
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32")
        psapi = ctypes.WinDLL("psapi")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC),
                                               wintypes.DWORD]
        if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize
    return None


@pytest.mark.skipif(_rss_bytes() is None, reason="no psutil and not Windows: no RSS probe")
def test_rss_growth_under_20mb_after_50k_events():
    bus = EventBus()
    state = SessionState()
    bus.add_listener(state.apply)
    sub = bus.subscribe()  # a subscriber that never drains: must stay bounded
    events = parser.parse_lines(_lines(500))
    gc.collect()
    before = _rss_bytes()
    for i in range(50_000):
        bus.publish(dict(events[i % len(events)]))
    gc.collect()
    after = _rss_bytes()
    growth = (after - before) / (1024 * 1024)
    assert len(bus.recent()) <= 500 and len(sub.get(timeout=0)) <= 256
    assert growth < 20, f"{growth:.1f} MB"
    sub.close()
    print(f"rss growth {growth:.2f} MB on {sys.platform}")


@pytest.mark.slow
@pytest.mark.server
def test_core_idle_cpu_under_1_percent_with_dashboard_and_overlay_streams(tmp_path):
    """TEST-OVL: decision 0002 "Core idle: under 1 percent of one core" for the
    whole core, not just the tailer: consented tailer at the 250 ms poll, the
    HTTP server and two open SSE streams (dashboard + overlay), no events."""
    import socket
    import threading

    from server.al.core import Core
    from server.al.http import serve

    token = "b" * 48
    log = tmp_path / "Client.txt"
    log.write_bytes(b"x\n" * 1000)
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "consent.json").write_text('{"consented": true}\n', encoding="ascii")
    core = Core(runtime=rt, log_path=str(log), poll_s=0.25)
    srv = serve(core, token, port=0)
    t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.5},
                         daemon=True)
    t.start()
    socks = []
    try:
        assert core.start_tailing()
        for _ in range(2):
            s = socket.create_connection(("127.0.0.1", srv.port), timeout=5)
            s.sendall((f"GET /events?token={token} HTTP/1.1\r\nHost: 127.0.0.1:"
                       f"{srv.port}\r\n\r\n").encode())
            buf = b""
            while b"event: state" not in buf:
                buf += s.recv(65536)
            socks.append(s)
        time.sleep(0.5)
        c0, w0 = time.process_time(), time.perf_counter()
        time.sleep(3.0)
        cpu, wall = time.process_time() - c0, time.perf_counter() - w0
    finally:
        for s in socks:
            s.close()
        srv.stop()
        core.close()
    share = cpu / wall
    print(f"core idle {share * 100:.3f} percent of one core")
    skip_if_ci_timing("core idle CPU", f"{share * 100:.3f} percent")
    assert share < 0.01 * fleet_test_guard.load_factor(), f"{share * 100:.2f} percent"


def test_ladder_tick_200_plus_500_under_2_ms(tmp_path):
    """RUN-LADDER-TICK (AUDIT-P8-LOW P8-5, B2): with 500 saved maps and 200
    session maps plus an open one, a 0.5 s core tick in which only the open
    map's clock moved costs under 2 ms (no matching, no view rebuild)."""
    from server.al import runs
    from server.al.core import Core

    core = Core(runtime=tmp_path / "rt", config_path=tmp_path / "local.json", tail=False)
    clock = [1000.0]
    core.state._clock = lambda: clock[0]

    def feed(ev):
        clock[0] = ev["recv_ts"]
        core.state.apply(ev)

    feed({"type": "level_up", "character": "Quill", "level": 80, "class": "Witch",
          "recv_ts": 1000.0})
    old = [{"area_id": f"MapOld{i % 40}", "seed": i, "opened_at": float(i),
            "area_level": 60 + i % 20, "time_s": 300.0, "deaths": i % 3,
            "level_ups": 0} for i in range(500)]
    core.ladder.record("Quill", old)
    at = 2000.0
    for i in range(runs.MAX_MAPS + 1):  # the last one stays open
        feed({"type": "area_generated", "area_id": f"MapNew{i % 30}",
              "area_level": 65 + i % 15, "seed": 10_000 + i, "recv_ts": at})
        feed({"type": "scene_changed", "scene": f"New{i % 30}", "is_hideout": False,
              "recv_ts": at + 1})
        at += 400.0
    core.tick_ladder(on=True)  # records the 200 finished maps, builds the view
    view = core.state.snapshot()["maps"]["ladder_all"]
    assert view["maps"] == len(core.ladder.by["Quill"]) + 1
    assert len(core.ladder.by["Quill"]) == 500
    times = []
    for _ in range(50):
        clock[0] += 0.5
        t0 = time.perf_counter()
        core.tick_ladder(on=True)
        times.append(time.perf_counter() - t0)
    times.sort()
    med = times[len(times) // 2]
    assert core.state.snapshot()["maps"]["ladder_all"] == view
    skip_if_ci_timing("ladder tick at 200 + 500 maps", f"{med * 1000:.3f} ms")
    assert med < fleet_test_guard.budget(0.002), f"{med * 1000:.3f} ms"


def _worst_case_core(tmp_path, tail=True):
    """RUN-BUDGET-TESTS-DET (B1): the RUN-LADDER-TICK worst case (500 saved
    maps, 200 session maps and an open one) on a core tailing a consented
    1000-line Client.txt at the 250 ms poll; the open map's clock follows
    the real one."""
    from server.al import runs
    from server.al.core import Core

    log = tmp_path / "Client.txt"
    log.write_bytes(b"x\n" * 1000)
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "consent.json").write_text('{"consented": true}\n', encoding="ascii")
    core = Core(runtime=rt, log_path=str(log), poll_s=0.25,
                config_path=tmp_path / "local.json", tail=tail)
    if tail:
        assert core.start_tailing()
        time.sleep(0.3)  # the start-up resume scan
    clock = [1000.0]
    core.state._clock = lambda: clock[0]

    def feed(ev):
        clock[0] = ev["recv_ts"]
        core.state.apply(ev)

    feed({"type": "level_up", "character": "Quill", "level": 80, "class": "Witch",
          "recv_ts": 1000.0})
    old = [{"area_id": f"MapOld{i % 40}", "seed": i, "opened_at": float(i),
            "area_level": 60 + i % 20, "time_s": 300.0, "deaths": i % 3,
            "level_ups": 0} for i in range(500)]
    core.ladder.record("Quill", old)
    at = 2000.0
    for i in range(runs.MAX_MAPS + 1):  # the last one stays open
        feed({"type": "area_generated", "area_id": f"MapNew{i % 30}",
              "area_level": 65 + i % 15, "seed": 10_000 + i, "recv_ts": at})
        feed({"type": "scene_changed", "scene": f"New{i % 30}", "is_hideout": False,
              "recv_ts": at + 1})
        at += 400.0
    base, m0 = clock[0], time.monotonic()
    core.state._clock = lambda: base + (time.monotonic() - m0)
    return core


def _cpu_clock_unit(samples=3):
    """The step of time.process_time() as measured: the largest of a few
    observed changes, capped at 20 ms (TEST-BUDGET-LOOPBODY-NOISE). On
    Windows it is the 15.6 ms clock tick (get_clock_info's 1e-07 is not the
    real step); on Linux it is about a microsecond."""
    step = 0.0
    for _ in range(samples):
        t0 = time.process_time()
        t1 = t0
        while t1 == t0:
            t1 = time.process_time()
        step = max(step, t1 - t0)
    return min(step, 0.02)  # never more than about one Windows tick


@pytest.mark.slow
def test_real_loop_body_10_s_worst_case_under_half_percent(tmp_path):
    """RUN-BUDGET-TESTS-DET (F-108, research 0048 B1): the core's real loop
    body (server/al/__main__: the stop and restart file checks,
    Core.tick_all, the price refresh tick, the heartbeat) every 0.5 s for
    5.0 s (TEST-LOOP-WINDOW-5S; research 0048 B1 named 10 s, the bound is a
    share, not a total, so the same 0.5 percent holds over the shorter window)
    on the worst-case fixture, with the tailer thread polling, costs under
    0.5 percent of one core.

    TEST-BUDGET-LOOPBODY-NOISE (decision 0002 amendment 2026-11-24): the
    process CPU clock only moves in whole steps (15.6 ms on Windows), so a
    5 s window reads 0, 1 or 2 steps (0, 0.31 or 0.62 percent) and the
    0.5 percent line falls between two of them. The CPU used may exceed the
    budget by at most one measured clock step; the budget stays 0.5
    percent."""
    import threading

    from server.al import __main__ as entry
    from server.al import hotreload

    unit = _cpu_clock_unit()
    core = _worst_case_core(tmp_path)
    rt = core.runtime
    stop = threading.Event()
    passes = 0
    try:
        core.tick_all()  # the first pass records the 200 maps and builds the view
        assert core.state.snapshot()["maps"]["ladder_all"]["maps"] > 500
        assert core.tailer is not None
        c0, w0 = time.process_time(), time.perf_counter()
        while time.perf_counter() - w0 < 5.0 and not stop.wait(0.5):
            if entry.stop_requested(rt / entry.STOP_FILE):
                break
            if entry.stop_requested(rt / hotreload.RESTART_FILE):
                break
            core.tick_all()
            core.tick_prices()
            entry.write_heartbeat(rt / "core.alive", os.getpid(), 8961)
            passes += 1
        cpu, wall = time.process_time() - c0, time.perf_counter() - w0
    finally:
        core.close()
    assert passes >= 9, passes
    assert set(core.tick_ms) == {n for n, _ in core.ticks}
    share = cpu / wall
    print(f"loop body {share * 100:.3f} percent of one core over {wall:.1f} s, "
          f"{passes} passes, CPU clock step {unit * 1000:.3f} ms")
    skip_if_ci_timing("core loop body on the worst case", f"{share * 100:.3f} percent")
    # One clock step of rounding (unit / wall) on top of the 0.5 percent share.
    assert share < 0.005 * fleet_test_guard.load_factor() + unit / wall, (
        f"{share * 100:.3f} percent ({cpu * 1000:.1f} ms CPU over {wall:.2f} s, "
        f"clock step {unit * 1000:.3f} ms)")


# B5 child: a test core on 10 MB of cached data files plays a four-hour
# session, ticks, and reports its own working set (steady after a
# collection) and peak, in bytes.
_WS_CHILD = r"""
import gc, json, os, sys
from pathlib import Path
root, rt = Path(sys.argv[1]), Path(sys.argv[2])
sys.path[:0] = [str(root), str(root / "tools")]


def working_set():
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t)] + [
                (n, ctypes.c_size_t) for n in (
                    "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                    "PagefileUsage", "PeakPagefileUsage")]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32")
        psapi = ctypes.WinDLL("psapi")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC),
                                               wintypes.DWORD]
        assert psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.WorkingSetSize, pmc.PeakWorkingSetSize
    import resource
    page = os.sysconf("SC_PAGE_SIZE")
    with open("/proc/self/statm", encoding="ascii") as fh:
        steady = int(fh.read().split()[1]) * page
    return steady, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


import synth_client
from server.al.core import Core

core = Core(runtime=rt, config_path=rt / "local.json", tail=False)
s = synth_client.standard_session(seed=3)
synth_client.play(s, 240)
for line in s.lines:
    core.feed_line(line)
for _ in range(20):
    core.tick_all()
loaded = {"bases": len(core.base_names.get() or {}), "acts": len(core.zone_table.get() or {})}
gc.collect()
steady, peak = working_set()
core.close()
print(json.dumps({"steady": steady, "peak": peak, "loaded": loaded}))
"""


def _write_data_files(gd):
    """About 10 MB of cached snapshots in the shapes the core reads and with
    the density of the real repoe-fork files (about 30 bytes per JSON
    value): world_areas.json (450 areas, the campaign ones first, 1.9 MB)
    and base_items.json (5,500 released bases, 8.2 MB)."""
    import json

    gd.mkdir(parents=True)
    areas = {}
    for i in range(450):
        act, n = divmod(i, 30)
        aid = f"G{act % 4 + 1}_{n + 1}" if i < 120 else f"MapSynthetic{i}"
        areas[aid] = {"name": f"Synthetic Area {i}", "area_level": 1 + i % 80,
                      "is_town": n == 0, "has_waypoint": n % 3 == 0,
                      "connections": [f"MapSynthetic{(i + k) % 450}" for k in range(1, 9)],
                      "tags": [f"area_tag_{k}" for k in range(12)],
                      "monsters": [f"Metadata/Monsters/Synthetic/Monster{i}_{k}"
                                   for k in range(85)],
                      "bosses": [f"Metadata/Monsters/Synthetic/Boss{i}"]}
    (gd / "world_areas.json").write_text(json.dumps(areas), encoding="ascii")
    bases = {}
    for i in range(5500):
        klass = ("Life Flask", "Mana Flask", "Ring", "Body Armour")[i % 4]
        bases[f"Metadata/Items/Synthetic/Base{i}"] = {
            "name": f"Synthetic Base {i}", "item_class": klass, "domain": "item",
            "drop_level": 1 + i % 80, "release_state": "released",
            "tags": [f"base_tag_{k}" for k in range(8)],
            "implicits": [f"SyntheticImplicit{i % 50}_{k}" for k in range(3)],
            "requirements": {"level": 1 + i % 80, "strength": i % 100,
                             "dexterity": i % 90, "intelligence": i % 70},
            "properties": {f"prop_{k}": {"min": k, "max": k + i % 30} for k in range(5)},
            "visual_identity": {"id": f"SyntheticArt{i}",
                                "dds_file": "Art/2DItems/Synthetic/" + "x" * 760 + ".dds"},
            "inventory_width": 2, "inventory_height": 3}
    (gd / "base_items.json").write_text(json.dumps(bases), encoding="ascii")


@pytest.mark.slow
def test_core_working_set_in_a_child(tmp_path):
    """RUN-BUDGET-TESTS-DET (F-108, research 0048 B5): the absolute working
    set of a core in a fresh process, with 10 MB of cached data files and
    a four-hour session played: steady under 60 MB, peak under 80 MB."""
    import json
    import subprocess

    root = Path(__file__).resolve().parents[1]
    rt = tmp_path / "rt"
    _write_data_files(rt / "gamedata")
    size = sum(p.stat().st_size for p in (rt / "gamedata").iterdir())
    assert size >= 10_000_000  # the real pair: 10.1 MB (research 0048 M2)
    proc = subprocess.run([sys.executable, "-c", _WS_CHILD, str(root), str(rt)],
                          cwd=root, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    doc = json.loads(proc.stdout.strip().splitlines()[-1])
    assert doc["loaded"]["bases"] > 1000 and doc["loaded"]["acts"] >= 4, doc["loaded"]
    steady, peak = doc["steady"] / 2 ** 20, doc["peak"] / 2 ** 20
    print(f"core working set {steady:.1f} MB steady, {peak:.1f} MB peak, "
          f"{size / 1e6:.1f} MB of data files")
    assert steady < 60, f"steady {steady:.1f} MB"
    assert peak < 80, f"peak {peak:.1f} MB"
