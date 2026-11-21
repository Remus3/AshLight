"""AUTO-08 (WATCH-HEALTH, F-125): a broken watcher is itself a finding.

tools/watch_sources/health.py (the source), ops/loop/watch_rows/health.json
(its template) and tools/loop_steps/watch_health.py (the tick line and the
checklist rows).

Hermetic: the health source and scratch test sources are copied into a tmp
folder and run through the tools/upstream_watch.py frame with a fake clock
on a scratch root (ctx root given, no 'live'), every transport refuses; the
filing path commits into a scratch git repository with a real git; the
HALTed tick runs al_loop.tick on a scratch root with the no-spawn git
stand-ins. No socket is opened and nothing touches the live tree."""

import datetime as dt
import importlib
import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import al_loop  # noqa: E402
import upstream_watch as uw  # noqa: E402
import watch_file  # noqa: E402
import watch_rows  # noqa: E402
from al_loopkit import deps, make_root, stub_git  # noqa: E402

step = importlib.import_module("loop_steps.watch_health")
health = importlib.import_module("watch_sources.health")

SRC = ROOT / "tools" / "watch_sources" / "health.py"
TEMPLATE = ROOT / "ops" / "loop" / "watch_rows" / "health.json"
FLAKY = '''
from pathlib import Path


def check(state, now, fetch, ctx):
    if (Path(ctx["root"]) / "flaky_ok").exists():
        return []
    raise OSError("upstream down")


SOURCE = {"name": "flaky", "home": "loop", "cadence_s": 0, "needs_web_data": True,
          "hosts": [], "urls": [], "check": check}
'''

NET = '''
def check(state, now, fetch, ctx):
    fetch("https://example.invalid/x")
    return []


SOURCE = {"name": "netsrc", "home": "loop", "cadence_s": 86400, "needs_web_data": True,
          "hosts": ["example.invalid"], "urls": [], "check": check}
'''


def _at(y, m, d, h=12):
    return dt.datetime(y, m, d, h, 0).timestamp()


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


def _root(tmp_path, git=False, web_data=False):
    root = tmp_path / "repo"
    files = {
        "ROADMAP.md": "# Roadmap\n",
        "ops/loop/watch_rows/health.json": TEMPLATE.read_text(encoding="ascii"),
        "config/local.json": json.dumps({"web_data": web_data}) + "\n",
        ".gitignore": "ops/runtime/\nconfig/local.json\nflaky_ok\n",
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


def _sources(tmp_path, **extra):
    d = tmp_path / "sources"
    d.mkdir(exist_ok=True)
    shutil.copyfile(SRC, d / "health.py")
    for name, text in extra.items():
        (d / f"{name}.py").write_text(text, encoding="ascii", newline="\n")
    return d


def _run(root, d, now):
    def refuse(method, url, headers, body=None):
        raise AssertionError(f"a request was made: {url}")
    ctx = {"root": root, "watch_sources": uw.discover(d)}
    return uw.run_due(root, now, fetch=refuse, directory=d, ctx=ctx)


def _tick(root, now, halted=False):
    kit = al_loop.al_lane._load("fleet_checklist", "ops/fleet_kit/fleet_checklist.py")
    return types.SimpleNamespace(root=root, halted=halted, dry=False,
                                 d=types.SimpleNamespace(clock=lambda: now, checklist=kit))


def _broken(root):
    return [f for f in uw.pending(root) if f["kind"] == health.KIND]


# ---------------------------------------------------------------- contract

def test_source_and_template_fit_the_frame_and_the_table():
    src = uw.normalize(health)
    assert src["name"] == "health" and src["local"] and src["home"] == "loop"
    table = watch_rows.load(ROOT)
    assert table[health.KIND]["source"] == "health"
    rid, text = watch_rows.render(table, health.KIND,
                                  {"NAME": "NINJA-DOCS", "CAUSE": "rate-limit"}, "2026-11-21")
    assert rid == "WATCH-BROKEN-NINJA-DOCS-20261121"
    assert text.startswith(f"- [ ] {rid} (review) ") and "BLOCKED: session." in text
    assert health.token_of("pob_next") == "POB-NEXT" and health.token_of("x" * 40) is None
    # no root and no live: the source reads nothing
    assert health.check({}, 0.0, None, {}) == []


# ---------------------------------------------------------------- package tests

def test_three_failures_in_a_row_add_one_tick_line(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path, flaky=FLAKY)
    now = _at(2026, 11, 21, 9)
    (root / "flaky_ok").write_text("", encoding="ascii")
    _run(root, d, now)
    (root / "flaky_ok").unlink()
    seen = []
    for i in range(1, 6):
        _run(root, d, now + 900 * i)
        seen.append(step.pre_halt(_tick(root, now + 900 * i)))
    assert seen[0] == [] and seen[1] == []
    assert len(seen[2]) == 1 and seen[3:] == [[], []]
    line = seen[2][0]
    assert line.startswith("watch health: flaky failed 3 times in a row (network)")
    assert "last good read" in line
    # a good read ends the streak; three more failures add one more line
    (root / "flaky_ok").write_text("", encoding="ascii")
    _run(root, d, now + 9000)
    assert step.pre_halt(_tick(root, now + 9000)) == []
    (root / "flaky_ok").unlink()
    again = []
    for i in range(1, 5):
        _run(root, d, now + 9000 + 900 * i)
        again += step.pre_halt(_tick(root, now + 9000 + 900 * i))
    assert len(again) == 1 and "flaky failed 3 times" in again[0]
    # under a week: no finding
    assert _broken(root) == []


@pytest.mark.git
def test_source_failing_for_8_days_files_one_row_once(tmp_path):
    root, d = _root(tmp_path, git=True), _sources(tmp_path, flaky=FLAKY)
    day0 = _at(2026, 11, 10, 9)
    (root / "flaky_ok").write_text("", encoding="ascii")
    _run(root, d, day0)
    (root / "flaky_ok").unlink()
    for day in range(1, 7):
        _run(root, d, day0 + day * 86400)
    assert _broken(root) == []  # six days: not yet
    for day in range(7, 10):
        _run(root, d, day0 + day * 86400)
    found = _broken(root)
    assert len(found) == 1
    assert found[0]["source"] == "health"
    assert found[0]["tokens"] == {"NAME": "FLAKY", "CAUSE": "network"}

    when = day0 + 9 * 86400 + 600
    lines = watch_file.file_pending(root, when, _git, Budget())
    stamp = dt.datetime.fromtimestamp(when).strftime("%Y%m%d")
    rel = f"docs/roadmap/new/WATCH-BROKEN-FLAKY-{stamp}.md"
    assert any(f"filed {rel}" in ln for ln in lines), lines
    assert _ok(["show", "--name-only", "--format=", "HEAD"], root).split() == [rel]
    text = (root / rel).read_text(encoding="ascii")
    assert "(review)" in text and "BLOCKED: session." in text
    assert uw.pending(root) == []
    # still broken on later days: queued once for all time, nothing more filed
    for day in range(10, 13):
        _run(root, d, day0 + day * 86400)
    assert uw.pending(root) == []
    later = watch_file.file_pending(root, day0 + 13 * 86400, _git, Budget())
    assert not any("filed" in ln for ln in later), later
    assert _ok(["rev-list", "--count", "HEAD"], root).strip() == "2"


def test_idle_web_data_off_is_a_checklist_line_and_no_row(tmp_path):
    root, d = _root(tmp_path, web_data=False), _sources(tmp_path, netsrc=NET)
    day0 = _at(2026, 11, 10, 9)
    for day in range(0, 10):
        _run(root, d, day0 + day * 86400)
        assert step.pre_halt(_tick(root, day0 + day * 86400)) == []
    rec = uw.load_state(root)["sources"]["netsrc"]
    assert rec["idle"] == uw.IDLE_OFF and rec["fails"] == 0
    assert uw.pending(root) == []
    rows = step.checklist(_tick(root, day0 + 10 * 86400))
    assert rows == [{"id": "watch-idle", "task": "Watchers idle, web data off: netsrc",
                     "state": None, "eta_s": None}]
    # idle on a source that had failed before web data went off: still no row
    st = uw.load_state(root)
    st["sources"]["netsrc"].update(fails=5, cause="network", last_ok=None)
    uw.save_state(root, st)
    for day in range(10, 20):
        _run(root, d, day0 + day * 86400)
        assert step.pre_halt(_tick(root, day0 + day * 86400)) == []
    assert uw.pending(root) == []
    # a bare root with no config/local.json shows no idle row
    (root / "config" / "local.json").unlink()
    assert step.checklist(_tick(root, day0 + 20 * 86400)) == []


def test_halted_tick_checklist_lists_pending_findings(tmp_path, monkeypatch):
    stub_git(monkeypatch)
    root = make_root(tmp_path, handoff="")
    tpl = root / "ops" / "loop" / "watch_rows" / "health.json"
    tpl.parent.mkdir(parents=True)
    shutil.copyfile(TEMPLATE, tpl)
    uw.set_pending(root, [
        {"source": "health", "kind": health.KIND, "key": "broken:ninja-docs:never",
         "tokens": {"NAME": "NINJA-DOCS", "CAUSE": "status"}, "found": "2026-09-20T10:00:00"},
        {"source": "other", "kind": "nokind", "key": "k", "tokens": {}, "found": ""},
    ])
    hp = root / al_loop.HALT_REL
    hp.parent.mkdir(parents=True, exist_ok=True)
    hp.write_text("", encoding="ascii")
    doc = al_loop.tick(deps=deps(root), no_push=True)
    assert doc["state"] == "halted"
    stamp = dt.datetime.fromtimestamp(1_790_000_000.0).strftime("%Y%m%d")
    rows = {r["id"]: r for r in doc["checklist"]}
    rid = f"WATCH-BROKEN-NINJA-DOCS-{stamp}"
    assert rid in rows and rows[rid]["state"] == "queued, HALT"
    assert rows[rid]["task"] == f"File row {rid} from watch health"
    assert rows["watch-other-2"]["state"] == "queued, HALT"
    # HALTed: nothing filed, the findings stay queued
    assert len(uw.pending(root)) == 2
    assert not (root / "docs" / "roadmap" / "new").exists()
