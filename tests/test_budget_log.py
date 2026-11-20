"""RUN-BUDGET-LOG-CORE (F-032, OPEN-03, OVL-BUDGET; research 0048 R4):
server/al/budgetlog.py and server/al/plug/budget.py.

A test core writes its budget log under its tmp runtime dir, never the
sidecar. No process is started, listed or opened: the own-process read and
the luajit figures are faked; the client's figures come from a tmp
overlay-state.json in app/metrics.js's schema 1 shape.
"""

import datetime
import json
import os
import subprocess
import sys
import time

import pytest

from ci_timing import skip_if_ci_timing
from server.al import budgetlog, diag, metrics
from server.al.core import Core
from server.al.plug import budget
from srcpaths import ROOT

FAKE_PROC = {"working_set_mb": 48.0, "cpu_s": 2.5, "threads": 9}
FAKE_LUAJIT = {"luajit_mb": 300.0, "luajit_peak_mb": 420.0, "luajit_cpu_s": 4.0}


@pytest.fixture(autouse=True)
def _fake_own(monkeypatch):
    monkeypatch.setattr(metrics, "own_process", lambda: dict(FAKE_PROC))
    monkeypatch.setattr(budgetlog, "luajit_footprint", lambda: None)


@pytest.fixture
def core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    yield c
    c.close()


def _utc(ts):
    return (datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.000Z"))


def client_doc(updated, shown=True, companion=False, procs=2, ws_kb=150 * 1024,
               priv_kb=90 * 1024, tab_cpu=0.05):
    tabs = 2 if companion else 1
    return {"schema": 1, "updated": _utc(updated), "period_s": 60,
            "processes": procs, "working_set_kb": ws_kb, "private_kb": priv_kb,
            "cpu_pct": 0.3,
            "by_type": {"browser": {"count": 1, "working_set_kb": 60000,
                                    "private_kb": 30000, "cpu_pct": 0.1},
                        "tab": {"count": tabs, "working_set_kb": 50000,
                                "private_kb": 40000, "cpu_pct": tab_cpu}},
            "overlay_shown": shown, "companion_open": companion}


def write_client(runtime, doc):
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / budgetlog.CLIENT_FILE).write_text(json.dumps(doc), encoding="ascii")


def clean_rows(n=5):
    rows = []
    for i in range(n):
        client = budgetlog.client_figures(client_doc(1000.0 + i), 1000.0 + i)[0]
        rows.append(budgetlog.make_row(1000 + 60 * i, FAKE_PROC, None, client,
                                       ["game_active", "overlay_shown"]))
    return rows


def write_log(path, rows):
    log = budgetlog.BudgetLog(path)
    for r in rows:
        assert log.append(r)
    return log


def test_replayed_log_with_a_breach_fails_and_clean_passes(tmp_path):
    clean = tmp_path / "clean.jsonl"
    write_log(clean, clean_rows())
    lines, rc = budgetlog.report(budgetlog.read_rows(clean))
    assert rc == 0, lines
    assert budgetlog.check(budgetlog.read_rows(clean)) == []

    # one replayed row per budget, each over its limit
    over = clean_rows(1)
    fat = budgetlog.client_figures(client_doc(0.0, ws_kb=230 * 1024), 0.0)[0]
    over.append(budgetlog.make_row(2000, FAKE_PROC, None, fat, ["game_active"]))
    busy = budgetlog.client_figures(client_doc(0.0, tab_cpu=0.5), 0.0)[0]
    over.append(budgetlog.make_row(2060, FAKE_PROC, None, busy, ["game_active"]))
    over.append(budgetlog.make_row(2120, FAKE_PROC,
                                   {"luajit_mb": 700.0, "luajit_peak_mb": 800.0},
                                   None, ["game_active", "calc_on"]))
    open_ok = budgetlog.client_figures(client_doc(0.0, companion=True, procs=3,
                                                  ws_kb=250 * 1024), 0.0)[0]
    over.append(budgetlog.make_row(2150, FAKE_PROC, {"luajit_mb": 100.0}, open_ok,
                                   ["game_active", "companion_open"]))
    many = budgetlog.client_figures(client_doc(0.0, companion=True, procs=4), 0.0)[0]
    over.append(budgetlog.make_row(2180, FAKE_PROC, None, many,
                                   ["game_active", "companion_open"]))
    bad = tmp_path / "breach.jsonl"
    write_log(bad, over)
    rows = budgetlog.read_rows(bad)
    lines, rc = budgetlog.report(rows)
    assert rc == 1, lines
    got = {(b["budget"], b["field"]) for b in budgetlog.check(rows)}
    assert ("B10", "ws_mb") in got
    assert ("B18", "total_mb") in got  # 48 + 250 + 100 with the calc tag off
    assert ("B12", "overlay_cpu_pct") in got
    assert ("B17", "luajit_peak_mb") in got
    assert ("B11", "processes") in got
    assert not any(b["row"] == 0 for b in budgetlog.check(rows))
    # B12 is wider inside a map; B9 only for a row that carries it
    inmap = budgetlog.make_row(1, FAKE_PROC, None, busy, ["game_active", "in_map"])
    assert budgetlog.check([inmap]) == []
    assert budgetlog.check([{"tags": [], "supervisor_mb": 36}])[0]["budget"] == "B9"


def test_rows_are_tagged_from_state_never_a_process_check(core, monkeypatch, tmp_path):
    import subprocess as sp

    def refuse(*a, **k):
        raise AssertionError("the budget log never starts or lists a process")

    monkeypatch.setattr(sp, "Popen", refuse)
    monkeypatch.setattr(sp, "run", refuse)
    monkeypatch.setattr(os, "listdir", refuse)
    monkeypatch.setattr(os, "scandir", refuse)
    sampler = core.budget_sampler

    # no client file, nothing going on
    row = sampler.sample()
    assert row["tags"] == ["game_active"] and row["client"] is None

    # game idle and calc on come from the core's own state and config
    core.state.tailer["consented"] = True
    core.state.tailer["idle"] = True
    monkeypatch.setattr(core, "tc_calc_enabled", lambda: True)
    write_client(core.runtime, client_doc(time.time(), shown=True, companion=True,
                                          procs=3))
    row = sampler.sample()
    assert row["tags"] == ["game_idle", "overlay_shown", "companion_open", "calc_on"]
    assert row["client"]["processes"] == 3
    assert row["client"]["overlay_cpu_pct"] is None  # two renderers: not split

    # in a map: from the map session of the state snapshot
    core.state.tailer["idle"] = False
    real = core.state.snapshot

    def snap():
        s = real()
        s["maps"] = dict(s.get("maps") or {}, current={"inside": True})
        return s

    monkeypatch.setattr(core.state, "snapshot", snap)
    write_client(core.runtime, client_doc(time.time(), shown=False))
    row = sampler.sample()
    assert row["tags"] == ["game_active", "in_map", "calc_on"]
    assert row["client"]["overlay_cpu_pct"] == 0.05

    # a stale or foreign client file is not used
    write_client(core.runtime, client_doc(time.time() - 600))
    assert sampler.sample()["client"] is None
    write_client(core.runtime, dict(client_doc(time.time()), schema=2))
    assert sampler.sample()["client"] is None

    # static: no process scan, list or open in the two modules
    for rel in ("server/al/budgetlog.py", "server/al/plug/budget.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for word in ("OpenProcess", "Toolhelp32", "EnumProcesses", "tasklist",
                     "Get-Process", "wmic", "from . import procs", "import procs",
                     "FindWindow", "EnumWindows"):
            assert word not in text, (rel, word)


def test_luajit_figures_need_no_bridge_import(monkeypatch):
    monkeypatch.undo()  # the real luajit_footprint
    before = set(sys.modules)
    assert budgetlog.luajit_footprint() is None or sys.platform == "win32"
    assert set(sys.modules) - before == set()


def test_file_stops_at_1_mb_oldest_dropped(tmp_path):
    path = tmp_path / "budget.jsonl"
    log = budgetlog.BudgetLog(path)
    client = budgetlog.client_figures(client_doc(0.0), 0.0)[0]
    n = 0
    written = 0
    while written < budgetlog.MAX_BYTES * 1.3:
        row = budgetlog.make_row(10_000 + n, FAKE_PROC, FAKE_LUAJIT, client,
                                 ["game_active", "in_map", "overlay_shown"])
        assert log.append(row)
        written += len(json.dumps(row, separators=(",", ":"))) + 1
        n += 1
        assert path.stat().st_size <= budgetlog.MAX_BYTES
    rows = budgetlog.read_rows(path)
    ats = [r["at"] for r in rows]
    assert ats == sorted(ats) and ats[-1] == 10_000 + n - 1
    assert ats[0] > 10_000  # the oldest went first
    assert path.read_bytes().endswith(b"\n")
    assert not path.with_name(path.name + ".tmp").exists()


def test_no_row_holds_a_path_name_or_pid(core, monkeypatch):
    monkeypatch.setattr(budgetlog, "luajit_footprint", lambda: dict(FAKE_LUAJIT))
    core.state.character = "Zzqcharname"
    write_client(core.runtime, client_doc(time.time()))
    core.budget_sampler.next_at = 0.0
    row = core.budget_sampler.due()
    assert row is not None
    text = core.budget_log.path.read_text(encoding="ascii")
    assert text.count("\n") == 1
    stored = json.loads(text)
    assert set(stored) <= set(budgetlog.ROW_KEYS)

    def leaves(v):
        if isinstance(v, dict):
            for x in v.values():
                yield from leaves(x)
        elif isinstance(v, list):
            for x in v:
                yield from leaves(x)
        else:
            yield v

    pid = os.getpid()
    for v in leaves(stored):
        if isinstance(v, str):
            assert v in budgetlog.TAGS, v
        else:
            assert v is None or isinstance(v, (int, float)), v
            assert v != pid
    for bad in ("Zzqcharname", "\\", "/", "Client.txt", str(core.runtime)):
        assert bad not in text, bad
    # the writer refuses any free text
    with pytest.raises(ValueError):
        budgetlog.clean_row(dict(row, tags=["zzq" + "\\" + "x"]))
    with pytest.raises(ValueError):
        budgetlog.clean_row(dict(row, core_mb="x"))
    with pytest.raises(ValueError):
        budgetlog.clean_row(dict(row, pid=pid))
    # a test core writes under its runtime, never the sidecar
    assert core.budget_log.path.parent == core.runtime


def test_sampler_cost_under_budget(core):
    """research 0048 R4: the sampler adds under 0.01 percent CPU, i.e.
    under 6 ms of CPU per one-minute row; between rows a tick is a compare."""
    write_client(core.runtime, client_doc(time.time()))
    sampler = core.budget_sampler
    sampler.next_at = time.monotonic() + 3600
    t0 = time.process_time()
    for _ in range(2000):
        assert sampler.due() is None
    idle_ms = (time.process_time() - t0) * 1000 / 2000
    n = 100
    t0 = time.process_time()
    for _ in range(n):
        sampler.next_at = 0.0
        assert sampler.due() is not None
    per_row_ms = (time.process_time() - t0) * 1000 / n
    assert len(budgetlog.read_rows(core.budget_log.path)) == n
    skip_if_ci_timing("budget row CPU ms", round(per_row_ms, 3))
    assert per_row_ms < 6.0, per_row_ms
    assert idle_ms < 0.05, idle_ms


def test_check_command_counts_rows_per_tag_and_exits_1_on_breach(tmp_path, capsys):
    clean = tmp_path / "clean.jsonl"
    rows = clean_rows(3)
    rows.append(budgetlog.make_row(5000, FAKE_PROC, None, None, ["game_idle"]))
    write_log(clean, rows)
    assert budgetlog.main(["check", "--file", str(clean)]) == 0
    out = capsys.readouterr().out
    assert "rows: 4" in out
    assert "tag game_active: 3" in out and "tag game_idle: 1" in out
    assert "tag overlay_shown: 3" in out and "tag calc_on: 0" in out

    bad = tmp_path / "bad.jsonl"
    fat = budgetlog.client_figures(client_doc(0.0, ws_kb=260 * 1024), 0.0)[0]
    write_log(bad, [budgetlog.make_row(1, FAKE_PROC, None, fat, ["game_active"])])
    assert budgetlog.main(["check", "--file", str(bad)]) == 1
    out = capsys.readouterr().out
    assert "breach B10 row 0: ws_mb" in out

    # no row: exit 1
    assert budgetlog.main(["check", "--file", str(tmp_path / "none.jsonl")]) == 1
    assert "no row" in capsys.readouterr().out

    # the -m entry point
    proc = subprocess.run([sys.executable, "-m", "server.al.budgetlog", "check",
                           "--file", str(bad)], cwd=ROOT, capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 1 and "breach B10" in proc.stdout


def test_checks_row_says_ashlight_uses_n_mb(core):
    f = core.diag_facts()
    assert f["budget_mb"] is None
    assert not any(r["id"] == budget.ROW_ID for r in diag.checks(f, time.time()))
    write_client(core.runtime, client_doc(time.time()))
    core.budget_sampler.next_at = 0.0
    core.tick_all()
    rows = [r for r in diag.checks(core.diag_facts(), time.time())
            if r["id"] == budget.ROW_ID]
    assert len(rows) == 1
    assert rows[0]["status"] == "pass"
    assert rows[0]["detail"] == "AshLight uses 198 MB."  # 48 core + 150 client
    over = budget.rows({"budget_mb": 400.0, "budget_over": ["B18"]}, 0.0)
    assert over["status"] == "note" and over["detail"].startswith("AshLight uses 400 MB.")
