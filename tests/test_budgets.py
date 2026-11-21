"""Core budgets (docs/decisions/0002-stack.md): parse speed, tailer idle CPU,
bounded memory. Timing budgets widen with fleet_test_guard.budget() while
other suites share the box. Under AL_CI=1 (CI only) a timing assert skips
with the measured value printed, after the structural checks (decision
0080); the memory bound always holds."""

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


@pytest.mark.slow
def test_tailer_idle_cpu_under_2_percent(tmp_path):
    p = tmp_path / "Client.txt"
    p.write_bytes(b"x\n" * 1000)
    t = Tailer(p, lambda line: None, poll_s=0.25)
    t.start()
    try:
        time.sleep(0.3)
        c0, w0 = time.process_time(), time.perf_counter()
        time.sleep(3.0)
        cpu, wall = time.process_time() - c0, time.perf_counter() - w0
    finally:
        t.stop()
    share = cpu / wall
    skip_if_ci_timing("tailer idle CPU", f"{share * 100:.2f} percent")
    assert share < 0.02 * fleet_test_guard.load_factor(), f"{share * 100:.2f} percent"


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
