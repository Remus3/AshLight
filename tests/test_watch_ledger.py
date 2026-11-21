"""AUTO-18 (W14 of docs/plan/06, LEDGER-SOURCE): the ledger watch source
tools/watch_sources/ledger.py, its templates ops/loop/watch_rows/ledger.json
and the report seed of tools/al_lane.py.

Hermetic: the source file is copied into a tmp folder and run through the
tools/upstream_watch.py frame with a fake clock on a scratch root (no
'live' in ctx, so no subprocess starts and no file outside the root is
read); the filing path (tools/watch_file.py) commits into a scratch git
repository under tmp_path with a real git. No socket is opened, Client.txt
is never read and nothing touches the live tree. Ledger fixtures are built
with logshapes.Ledger itself (the core's own file shape)."""

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import al_lane  # noqa: E402
import live1_report  # noqa: E402
import upstream_watch as uw  # noqa: E402
import watch_file  # noqa: E402
import watch_rows  # noqa: E402
from server.al import logshapes  # noqa: E402

SRC = ROOT / "tools" / "watch_sources" / "ledger.py"
TEMPLATE = ROOT / "ops" / "loop" / "watch_rows" / "ledger.json"
HOUR = "2026-11-21T10"

LIVE_ROWS = """# Roadmap

- [ ] LIVE-1-DEATH (data) Live-verify the death log shape of LIVE-1 from the
  parse ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live.
- [ ] LIVE-1-AFK (data) Live-verify the AFK log shape of LIVE-1 from the parse
  ledger. ACCEPT: python tools/live1_report.py prints VERIFIED live.
- [ ] LIVE-1-ACCEPTED (data) Live-verify the trade accepted / cancelled log
  shape of LIVE-1 from the parse ledger. ACCEPT: python tools/live1_report.py
  prints VERIFIED live.
"""


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
    root = tmp_path / "repo"
    files = {
        "ROADMAP.md": LIVE_ROWS,
        "ops/loop/watch_rows/ledger.json": TEMPLATE.read_text(encoding="ascii"),
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
    shutil.copyfile(SRC, d / "ledger.py")
    return d


def _tick(root, d, now, **ctx):
    def refuse(method, url, headers, body=None):
        raise AssertionError(f"the ledger source made a request: {url}")
    ctx["root"] = root
    return uw.run_due(root, now, fetch=refuse, directory=d, ctx=ctx)


def _kinds(root):
    return [(f["source"], f["kind"], f["key"]) for f in uw.pending(root)]


def _ledger(root, hits=(), shapes=()):
    """Write ops/runtime/logshapes.json; shapes: [(kind, shape, ok)]."""
    led = logshapes.Ledger()
    for pid, n in dict(hits).items():
        led.hits[pid] = [n, HOUR, HOUR]
    for kind, shape, ok in shapes:
        led.shapes[(kind, shape)] = [2 if ok else 1, HOUR, HOUR, ok]
    p = root / "ops/runtime/logshapes.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(led.dumps(), encoding="ascii")
    return p


def _probe(root, entries):
    p = root / "ops/runtime/snapshot/probe.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema": 1, "updated": "2026-11-21T10:00:00Z",
                             "sources": entries}), encoding="ascii")


def _entry(source, verdict, when, missing=2):
    return {"source": source, "verdict": verdict, "missing": missing,
            "missing_keys": ["name", "stats"][:missing], "lost": [], "count": 10,
            "reason": "too few entries" if verdict == "fail" else "", "time": when}


SAFE_SHAPE = "<w> has joined the guild."
SAFE_SHAPE_2 = "<w> is now <w> mode."


# ---------------------------------------------------------------- tests

def test_first_hit_writes_exactly_that_rows_done_file(tmp_path):
    root, d = _root(tmp_path, git=True), _sources(tmp_path)
    _ledger(root, hits={"area.act.G1": 4})
    now = _at(2026, 11, 21, 9)
    _tick(root, d, now)
    assert uw.pending(root) == []

    _ledger(root, hits={"area.act.G1": 4, "death": 1, "trade_accepted": 0})
    _tick(root, d, now + 600)
    _tick(root, d, now + 1200)
    assert _kinds(root) == [("ledger", "live1hit", "live1:DEATH")]

    head = _ok(["rev-parse", "HEAD"], root).strip()
    lines = watch_file.file_pending(root, now + 1800, _git, Budget())
    rel = "docs/roadmap/done/LIVE-1-DEATH.md"
    assert any(f"filed {rel}" in ln for ln in lines), lines
    assert _ok(["rev-parse", "HEAD^"], root).strip() == head
    assert _ok(["show", "--name-only", "--format=", "HEAD"], root).split() == [rel]
    assert (root / rel).read_text(encoding="ascii") == (
        " -- done 2026-11-21 (watch: ledger live1:DEATH)\n")
    assert sorted(p.name for p in (root / "docs/roadmap/done").iterdir()) == [
        "LIVE-1-DEATH.md"]
    assert _ok(["status", "--short"], root).strip() == ""

    # The accepted row has its own kind (no token may carry 'accept'); a row
    # already closed makes nothing more.
    _ledger(root, hits={"death": 3, "trade_accepted": 1})
    _tick(root, d, now + 2400)
    assert _kinds(root) == [("ledger", "live1accepted", "live1:ACCEPTED")]
    lines = watch_file.file_pending(root, now + 3000, _git, Budget())
    assert any("filed docs/roadmap/done/LIVE-1-ACCEPTED.md" in ln for ln in lines), lines
    _tick(root, d, now + 3600)
    assert uw.pending(root) == []
    assert _ok(["rev-list", "--count", "HEAD"], root).strip() == "3"


def test_new_shape_seen_once_files_nothing_twice_files_one_row(tmp_path):
    root, d = _root(tmp_path, git=True), _sources(tmp_path)
    now = _at(2026, 11, 21, 9)
    _ledger(root, shapes=[("sys", SAFE_SHAPE, False)])
    _tick(root, d, now)
    assert uw.pending(root) == []

    _ledger(root, shapes=[("sys", SAFE_SHAPE, True)])
    _tick(root, d, now + 600)
    _tick(root, d, now + 1200)
    assert _kinds(root) == [("ledger", "logshape", "log-shape:20261121")]
    lines = watch_file.file_pending(root, now + 1800, _git, Budget())
    rel = "docs/roadmap/new/LOG-SHAPE-20261121.md"
    assert any(f"filed {rel}" in ln for ln in lines), lines
    text = (root / rel).read_text(encoding="ascii")
    assert text.startswith("- [ ] LOG-SHAPE-20261121 (build) ")
    assert SAFE_SHAPE not in text  # the row names the report, never a shape

    # The same confirmed shape again, even on a later day: nothing.
    _tick(root, d, _at(2026, 11, 22))
    assert uw.pending(root) == []
    # A second new shape the same day waits for the next day.
    _ledger(root, shapes=[("sys", SAFE_SHAPE, True), ("sys", SAFE_SHAPE_2, True)])
    _tick(root, d, _at(2026, 11, 22, 13))
    assert _kinds(root) == [("ledger", "logshape", "log-shape:20261122")]


def test_probe_failure_files_one_row_per_source_and_day(tmp_path):
    root, d = _root(tmp_path, git=True), _sources(tmp_path)
    now = _at(2026, 11, 21, 9)
    _probe(root, [_entry("base_items", "pass", "2026-11-21T08:00:00Z", 0),
                  _entry("not_a_source", "fail", "2026-11-21T08:00:00Z")])
    _tick(root, d, now)
    assert uw.pending(root) == []

    _probe(root, [_entry("base_items", "fail", "2026-11-21T09:00:00Z"),
                  _entry("world_areas", "fail", "2026-11-21T09:00:00Z")])
    _tick(root, d, now + 600)
    # A newer failure the same day files nothing more.
    _probe(root, [_entry("base_items", "fail", "2026-11-21T11:00:00Z"),
                  _entry("world_areas", "fail", "2026-11-21T09:00:00Z")])
    _tick(root, d, now + 7200)
    assert sorted(_kinds(root)) == [
        ("ledger", "snapprobe", "snap:BASE-ITEMS:20261121"),
        ("ledger", "snapprobe", "snap:WORLD-AREAS:20261121")]
    lines = watch_file.file_pending(root, now + 7800, _git, Budget())
    for rid in ("SNAP-BASE-ITEMS-20261121", "SNAP-WORLD-AREAS-20261121"):
        assert any(f"filed docs/roadmap/new/{rid}.md" in ln for ln in lines), lines
        text = (root / f"docs/roadmap/new/{rid}.md").read_text(encoding="ascii")
        assert f"- [ ] {rid} (data) " in text

    # Next day: the unchanged world_areas entry stays quiet; base_items
    # failed again at a new time and files its next day's row.
    _probe(root, [_entry("base_items", "fail", "2026-11-22T09:00:00Z"),
                  _entry("world_areas", "fail", "2026-11-21T09:00:00Z")])
    _tick(root, d, _at(2026, 11, 22))
    assert _kinds(root) == [("ledger", "snapprobe", "snap:BASE-ITEMS:20261122")]


def test_no_ledger_file_means_idle(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    calls = []

    def runner(r, p):
        calls.append(p)
        return "{}"

    lines = _tick(root, d, _at(2026, 11, 21), live1_runner=runner)
    assert not any("failed" in ln for ln in lines), lines
    assert uw.pending(root) == []
    assert calls == []
    assert not (root / "ops/runtime/watch/live1_report.json").exists()
    rec = uw.load_state(root)["sources"]["ledger"]
    assert rec["last_ok"] and rec["fails"] == 0
    # No root and no 'live': the source reads nothing at all.
    mod = uw.discover(d)[0]
    assert mod["check"]({"data": {}}, _at(2026, 11, 21), None, {}) == []
    assert mod["local"]


def test_report_copy_holds_masked_shapes_only(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    led = _ledger(root, hits={"death": 2}, shapes=[("sys", SAFE_SHAPE, True)])
    # A tampered ledger row with raw text: the ledger loader drops it.
    doc = json.loads(led.read_text(encoding="ascii"))
    doc["shapes"].append(["sys", "Zorblax has joined the guild.", 2, HOUR, HOUR, True])
    led.write_text(json.dumps(doc), encoding="ascii")

    def real(r, p):  # F-061's tool, in process
        return json.dumps(live1_report.build(p))

    _tick(root, d, _at(2026, 11, 21), live1_runner=real)
    out = root / "ops/runtime/watch/live1_report.json"
    rep = json.loads(out.read_text(encoding="ascii"))
    assert [s["shape"] for s in rep["new_shapes"]] == [SAFE_SHAPE]
    assert "Zorblax" not in out.read_text(encoding="ascii")
    death = next(i for i in rep["items"] if i["item"] == "DEATH")
    assert death["verdict"] == "VERIFIED live" and death["row"] == "LIVE-1-DEATH"

    # A runner that returns raw text: the source's own re-check drops it.
    def tampered(r, p):
        good = live1_report.build(p)
        good["new_shapes"].append({"kind": "plain", "shape": "Hello from Zorblax",
                                   "n": 3, "first": HOUR, "last": HOUR, "items": []})
        good["waystone"].append({"lines": ["Owner: Zorblax"], "n": 1,
                                 "first": HOUR, "last": HOUR})
        good["items"][0]["row"] = "Zorblax was here"
        good["extra"] = "raw value outside the report"
        return json.dumps(good)

    _ledger(root, hits={"death": 3}, shapes=[("sys", SAFE_SHAPE, True)])
    os.utime(led, ns=(1, 1))  # a changed ledger signature
    _tick(root, d, _at(2026, 11, 21, 13), live1_runner=tampered)
    text = out.read_text(encoding="ascii")
    assert "Zorblax" not in text and "extra" not in text and "raw value" not in text
    rep = json.loads(text)
    assert [s["shape"] for s in rep["new_shapes"]] == [SAFE_SHAPE]
    assert rep["waystone"] == []
    assert rep["items"][0]["row"] is None


def test_lane_worktree_gets_the_fresh_report(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    _ledger(root, shapes=[("sys", SAFE_SHAPE, True)])

    def real(r, p):
        return json.dumps(live1_report.build(p))

    _tick(root, d, _at(2026, 11, 21), live1_runner=real)
    rel = "ops/runtime/watch/live1_report.json"
    src = root / rel
    assert src.is_file()

    wt = tmp_path / "wt"
    old = wt / rel
    old.parent.mkdir(parents=True)
    old.write_text('{"schema": 1, "new_shapes": []}\n', encoding="ascii")
    os.utime(old, ns=(1, 1))
    (wt / "config").mkdir()
    (wt / "config/local.json").write_text("{}\n", encoding="ascii")
    assert al_lane.seed_config(wt, root) == [rel]
    assert old.read_bytes() == src.read_bytes()
    assert al_lane.seed_config(wt, root) == []  # same copy: no-op

    # A fresh report replaces the lane's copy again on the next claim.
    _ledger(root, shapes=[("sys", SAFE_SHAPE, True), ("sys", SAFE_SHAPE_2, True)])
    _tick(root, d, _at(2026, 11, 21, 13), live1_runner=real)
    assert al_lane.seed_config(wt, root) == [rel]
    assert SAFE_SHAPE_2 in old.read_text(encoding="ascii")
    # The gate config seeds still never overwrite.
    (root / "config/local.json").write_text('{"web_data": true}\n', encoding="ascii")
    assert al_lane.seed_config(wt, root) == []
    assert (wt / "config/local.json").read_text(encoding="ascii") == "{}\n"


def test_templates_load_and_cover_every_live1_item():
    table = watch_rows.load(ROOT)
    import re
    pat = table["live1hit"]["tokens"]["ITEM"]
    items = set(logshapes.LIVE1_ITEMS)
    covered = {i for i in items if re.fullmatch(pat, i)}
    assert covered == items - {"ACCEPTED"}
    assert table["live1accepted"]["id"] == "LIVE-1-ACCEPTED"
    for kind in ("logshape", "snapprobe"):
        rid, text = watch_rows.render(table, kind, table[kind]["sample"], "2026-11-21")
        assert rid, text
