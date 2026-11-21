"""AUTO-07 (W11 of docs/plan/06, F-052): the launch gate source
tools/watch_sources/launch.py and its templates ops/loop/watch_rows/launch.json.

Hermetic: the source file is copied into a tmp folder and run through the
tools/upstream_watch.py frame with a fake clock on a scratch root; the
filing path (tools/watch_file.py) commits into a scratch git repository
under tmp_path with a real git. No socket is opened and nothing touches
the live tree."""

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import roadmap  # noqa: E402
import upstream_watch as uw  # noqa: E402
import watch_file  # noqa: E402
import watch_rows  # noqa: E402

SRC = ROOT / "tools" / "watch_sources" / "launch.py"
TEMPLATE = ROOT / "ops" / "loop" / "watch_rows" / "launch.json"

GATE_ROWS = """# Roadmap

- [ ] GATE-POE2-10 (data) Gate: PoE2 1.0 is live. BLOCKED: gate,
  flipped by the launch watcher (date and one upstream signal).
- [ ] GATE-ACT5-SEEN (data) Gate: the operator's own log shows Act
  5. BLOCKED: gate, flipped by the launch watcher (run history or
  parse ledger).
- [ ] UTIL-10-DATA (data) (priority) PoE2 1.0 data refresh: runbook
  steps 4, 6, 7 and 8. ACCEPT: the zone table has Act 5 and 6 rows;
  id_match passes; read-back per step. DEPENDS: GATE-POE2-10.
  ZERO-CLICK: the loop works it.
- [ ] UTIL-10-NOTES (review) PoE2 1.0 notes: runbook step 1 from
  the allowed sources only (pasted text, public repositories, the
  API Reference and Data Exports pages). ACCEPT: a dated research
  note. DEPENDS: GATE-POE2-10. ZERO-CLICK: a requested dive.
- [ ] UTIL-10-LOG (build) PoE2 1.0 log shapes: runbook steps 2, 3
  and 5 from tools/live1_report.py output. ACCEPT: every new shape
  has a fixture and a passing test. DEPENDS: GATE-POE2-10,
  GATE-ACT5-SEEN. ZERO-CLICK: opens after the first 1.0 session.
"""
DEPENDENTS = ("UTIL-10-DATA", "UTIL-10-NOTES", "UTIL-10-LOG")


def _at(y, m, d, h=12):
    return dt.datetime(y, m, d, h, 0).timestamp()


# ---------------------------------------------------------------- helpers

def _env():
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return env


def _git(args, cwd, input=None):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          env=_env(), timeout=60)


def _ok(args, cwd):
    r = _git(args, cwd)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


class Budget:
    cap = 100

    def readable(self):
        return True

    def used(self):
        return 0


def _root(tmp_path, git=False):
    """A scratch tree: the gate rows, the real launch template, web data off."""
    root = tmp_path / "repo"
    files = {
        "ROADMAP.md": GATE_ROWS,
        "ops/loop/watch_rows/launch.json": TEMPLATE.read_text(encoding="ascii"),
        "config/local.json": json.dumps({"web_data": False}) + "\n",
        ".gitignore": "ops/runtime/\nconfig/local.json\n",
    }
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("ascii"))
    if git:
        _ok(["init", "-q", "-b", "main"], root)
        for k, v in (("user.name", "Operator"), ("user.email", "operator@example.com"),
                     ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
            _ok(["config", k, v], root)
        _ok(["add", "-A"], root)
        _ok(["commit", "-q", "-m", "base"], root)
    return root


def _sources(tmp_path):
    d = tmp_path / "sources"
    d.mkdir(exist_ok=True)
    shutil.copyfile(SRC, d / "launch.py")
    return d


def _record(root, name, **data):
    st = uw.load_state(root)
    st["sources"].setdefault(name, uw._entry())["data"] = dict(data)
    uw.save_state(root, st)


def _tick(root, d, now, transport=None):
    def refuse(method, url, headers, body=None):
        raise AssertionError(f"the launch source made a request: {url}")
    return uw.run_due(root, now, fetch=transport or refuse, directory=d, ctx={"root": root})


def _kinds(root):
    return [(f["source"], f["kind"], f["key"]) for f in uw.pending(root)]


def _write(root, rel, doc):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _run_history(root, keys):
    run = {"started_at": 1000.0, "character": "Someone", "class": "Monk",
           "splits": [{"key": k, "label": f"Act {k[1:]}", "time_s": 600.0} for k in keys],
           "deaths": {}, "finished": False}
    _write(root, "ops/runtime/run_history.json",
           {"schema": 2, "characters": {"Someone": {"runs": [run]}}})


def _ledger(root, hits):
    _write(root, "ops/runtime/logshapes.json",
           {"schema": 1, "hits": {k: [n, "2026-12-11T10:00Z", "2026-12-11T11:00Z"]
                                  for k, n in hits.items()}, "shapes": {}})


# ---------------------------------------------------------------- tests

def test_clock_2026_12_10_flips_nothing(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    _record(root, "repoe-fork", version="1.0.0.1", title="Version 1.0.0.1",
            preview=False, live_version="1.0.0.1")
    _record(root, "ggg-tree", version="1.0.0", title="1.0.0", preview=False,
            live_version="1.0.0")
    lines = _tick(root, d, _at(2026, 12, 10, 23))
    assert not any("failed" in ln for ln in lines), lines
    assert uw.pending(root) == []
    assert uw.load_state(root)["sources"]["launch"]["last_ok"]


def test_2026_12_11_with_a_1_0_0_record_flips_the_gate_once(tmp_path):
    root, d = _root(tmp_path, git=True), _sources(tmp_path)
    _record(root, "ggg-tree", version="1.0.0", title="tag 1.0.0", preview=False,
            live_version="1.0.0")
    now = _at(2026, 12, 11, 9)
    _tick(root, d, now)
    _tick(root, d, now + 600)
    assert _kinds(root) == [("launch", "gatepoe210", "poe2-10:ggg-tree:1.0.0")]

    # End to end: the queued finding becomes a committed done file.
    head = _ok(["rev-parse", "HEAD"], root).strip()
    lines = watch_file.file_pending(root, now + 900, _git, Budget())
    rel = "docs/roadmap/done/GATE-POE2-10.md"
    assert any(f"filed {rel}" in ln for ln in lines), lines
    assert _ok(["rev-parse", "HEAD^"], root).strip() == head
    assert _ok(["show", "--name-only", "--format=", "HEAD"], root).split() == [rel]
    assert (root / rel).read_text(encoding="ascii") == (
        " -- done 2026-12-11 (watch: launch poe2-10:ggg-tree:1.0.0)\n")
    assert _ok(["log", "-1", "--format=%s"], root).strip() == (
        "chore(roadmap): file GATE-POE2-10 (watch launch)")
    assert _ok(["status", "--short"], root).strip() == ""
    assert uw.pending(root) == []

    # Later ticks, a newer version included, file nothing more.
    _record(root, "repoe-fork", version="1.0.1.0", preview=False, live_version="1.0.1.0")
    _tick(root, d, now + 86400)
    assert uw.pending(root) == []
    assert watch_file.file_pending(root, now + 86400, _git, Budget()) == []
    assert _ok(["rev-list", "--count", "HEAD"], root).strip() == "2"


def test_gate_flip_makes_the_dependents_dispatchable(tmp_path):
    root, d = _root(tmp_path, git=True), _sources(tmp_path)
    before = roadmap.waits(roadmap.load_rows(root))
    assert all(r in before for r in DEPENDENTS), before

    _record(root, "repoe-fork", version="1.0.0.3", title="Version 1.0.0.3",
            preview=False, live_version="1.0.0.3")
    _run_history(root, ["G1", "G2", "G3", "G4", "G5"])
    now = _at(2026, 12, 12)
    _tick(root, d, now)
    assert sorted(k for _s, k, _k in _kinds(root)) == ["gateact5seen", "gatepoe210"]
    lines = watch_file.file_pending(root, now + 60, _git, Budget())
    assert sum("filed docs/roadmap/done/" in ln for ln in lines) == 2, lines

    rows = {r["id"]: r for r in roadmap.load_rows(root)}
    assert not rows["GATE-POE2-10"]["open"] and not rows["GATE-ACT5-SEEN"]["open"]
    after = roadmap.waits(list(rows.values()))
    for rid in DEPENDENTS:
        assert rows[rid]["open"] and rid not in after, (rid, after.get(rid))
        assert not roadmap.is_tagged(rows[rid])


def test_preview_title_flips_nothing(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    _record(root, "ggg-tree", version="1.0.0", title="1.0.0 Preview", preview=True,
            live_version="0.5.5")
    _record(root, "repoe-fork", version="1.0.0.0", title="Version 1.0.0.0 Preview",
            preview=True, live_version="0.5.5.12")
    _tick(root, d, _at(2026, 12, 11))
    _tick(root, d, _at(2026, 12, 13))
    assert uw.pending(root) == []


def test_act_5_split_in_run_history_flips_gate_act5_seen(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    _run_history(root, ["G1", "G2", "G3", "G4"])
    _ledger(root, {"area.act.G4": 3})
    _tick(root, d, _at(2026, 12, 11))
    assert uw.pending(root) == []

    _run_history(root, ["G1", "G2", "G3", "G4", "G5"])
    _tick(root, d, _at(2026, 12, 11, 13))
    _tick(root, d, _at(2026, 12, 11, 14))
    assert _kinds(root) == [("launch", "gateact5seen", "act5-seen:run-history")]


def test_ledger_act_5_hit_flips_it_when_run_history_is_off(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    _ledger(root, {"area.act.G4": 9, "area.act.C5": 0})
    _tick(root, d, _at(2026, 12, 11))
    assert uw.pending(root) == []
    assert not (root / "ops/runtime/run_history.json").exists()

    _ledger(root, {"area.act.G4": 9, "area.act.G5": 1})
    _tick(root, d, _at(2026, 12, 11, 13))
    _tick(root, d, _at(2026, 12, 11, 14))
    assert _kinds(root) == [("launch", "gateact5seen", "act5-seen:ledger")]


def test_three_days_past_with_no_signal_files_launch_check_once(tmp_path):
    root, d = _root(tmp_path, git=True), _sources(tmp_path)
    _record(root, "repoe-fork", version="0.5.5.12", preview=False, live_version="0.5.5.12")
    for day in (11, 12, 13):
        _tick(root, d, _at(2026, 12, day, 23))
    assert uw.pending(root) == []

    now = _at(2026, 12, 14, 8)
    _tick(root, d, now)
    _tick(root, d, now + 3600)
    assert _kinds(root) == [("launch", "launchcheck", "no-signal")]
    lines = watch_file.file_pending(root, now + 3700, _git, Budget())
    rel = "docs/roadmap/new/LAUNCH-CHECK-20261214.md"
    assert any(f"filed {rel}" in ln for ln in lines), lines
    text = (root / rel).read_text(encoding="ascii")
    assert text.startswith("- [ ] LAUNCH-CHECK-20261214 (review) The 1.0 date passed")
    assert "BLOCKED: session. SOURCE: watch launch no-signal, filed 2026-12-14." in text

    for day in (15, 16):
        _tick(root, d, _at(2026, 12, day))
    assert uw.pending(root) == []
    assert watch_file.file_pending(root, _at(2026, 12, 16, 13), _git, Budget()) == []


def test_source_makes_no_request(tmp_path):
    src = uw.normalize(uw.discover(_sources(tmp_path))[0])
    assert src["name"] == "launch" and src["hosts"] == [] and src["urls"] == []
    assert src["local"] and not uw.is_network(src)
    text = SRC.read_text(encoding="ascii")
    for word in ("http://", "https://", "import urllib", "import socket",
                 "import subprocess", "webfetch", "fetch("):
        assert word not in text, word

    # Web data off: the local source still runs every tick, the transport is
    # never called, and a fetch it might try is refused by the frame.
    root, d = _root(tmp_path), _sources(tmp_path)
    calls = []

    def transport(method, url, headers, body=None):
        calls.append(url)
        return 200, {}, b"[]"

    _record(root, "repoe-fork", version="1.0.0.1", preview=False, live_version="1.0.0.1")
    _tick(root, d, _at(2026, 12, 11), transport)
    assert calls == []
    assert [k for _s, k, _k in _kinds(root)] == ["gatepoe210"]

    # Without a root (and not live) it reads nothing and finds nothing.
    mod = __import__("importlib").import_module("watch_sources.launch")
    state = {"data": {}}
    assert mod.check(state, _at(2026, 12, 20), None, {}) == []


def test_launch_templates_render():
    table = watch_rows.load(ROOT)
    for kind in ("gatepoe210", "gateact5seen", "launchcheck"):
        assert table[kind]["source"] == "launch"
    assert watch_rows.render_samples(table)["launchcheck"][0] == "LAUNCH-CHECK-20260101"
    assert table["gatepoe210"]["id"] == "GATE-POE2-10"
    assert table["gateact5seen"]["id"] == "GATE-ACT5-SEEN"
