"""Plan 138: tools/ledger_rotate.py moves old control-ledger rows and finished
progress files to archives. Fixtures live under tmp_path; nothing is deleted."""

import datetime as _dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import eta  # noqa: E402
import ledger_rotate  # noqa: E402
import usage_ledger  # noqa: E402

NOW = 1_790_000_000.0
DAY = 86400.0
CONTROL = Path("ops/loop/control")


def iso(epoch):
    return _dt.datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")


def local(epoch):
    return _dt.datetime.fromtimestamp(epoch).strftime("%Y-%m-%dT%H:%M:%S")


def month(epoch):
    return _dt.datetime.fromtimestamp(epoch).strftime("%Y%m")


def write_lines(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(ln.encode("ascii") + b"\n" for ln in lines))


def jl(rows):
    return [r if isinstance(r, str) else json.dumps(r, sort_keys=True) for r in rows]


def read_rows(path):
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="ascii").split("\n") if ln]


def control(root):
    return root / CONTROL


# ---------------------------------------------------------------- usage

def usage_rows():
    return jl([
        {"ts": iso(NOW - 60 * DAY), "duration_s": 10, "kind": "build"},
        {"ts": iso(NOW - 36 * DAY), "duration_s": 10, "kind": "inbox"},
        "{torn line",
        {"ts": iso(NOW - 20 * DAY), "duration_s": 10, "kind": "build"},
        {"ts": iso(NOW - 3600), "duration_s": 30, "kind": "build"},
        {"ts": iso(NOW - 600), "duration_s": 5, "kind": "triage"},
        {"note": "no timestamp"},
    ])


def test_usage_rows_older_than_35_days_move_to_a_monthly_archive(tmp_path):
    live = control(tmp_path) / "headless_usage.jsonl"
    rows = usage_rows()
    write_lines(live, rows)
    before = usage_ledger.run_starts(live, NOW)
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert res["headless_usage"] == 2
    assert read_rows(live) == rows[2:]  # torn and ts-less lines kept, order kept
    arch = control(tmp_path) / "archive"
    moved = [ln for f in sorted(arch.glob("headless_usage-*.jsonl")) for ln in read_rows(f)]
    assert moved == rows[:2]
    assert (arch / f"headless_usage-{month(NOW - 60 * DAY)}.jsonl").exists()
    assert usage_ledger.run_starts(live, NOW) == before  # 24 h governor unchanged


def test_usage_keeps_at_least_8_days_whatever_the_setting(tmp_path):
    live = control(tmp_path) / "headless_usage.jsonl"
    rows = jl([{"ts": iso(NOW - 7 * DAY), "kind": "build"},
               {"ts": iso(NOW - 9 * DAY), "kind": "build"}])
    write_lines(live, rows)
    plan = ledger_rotate.plan_jsonl(live, ledger_rotate.age_rule(1), NOW,
                                    min_keep_s=ledger_rotate.USAGE_MIN_KEEP_S)
    assert plan["keep"] == [rows[0].encode()]


def test_archive_appends_and_a_second_run_moves_nothing(tmp_path):
    live = control(tmp_path) / "headless_usage.jsonl"
    arch = control(tmp_path) / "archive" / f"headless_usage-{month(NOW - 60 * DAY)}.jsonl"
    write_lines(arch, ['{"old": "archived earlier"}'])
    write_lines(live, usage_rows())
    ledger_rotate.rotate(tmp_path, now=NOW)
    assert read_rows(arch)[0] == '{"old": "archived earlier"}'
    snap = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert ledger_rotate.total(res) == 0
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == snap


def test_a_concurrent_append_skips_the_file_and_loses_nothing(tmp_path):
    live = control(tmp_path) / "headless_usage.jsonl"
    rows = usage_rows()
    write_lines(live, rows)
    extra = json.dumps({"ts": iso(NOW), "kind": "build"})

    def grow():
        with live.open("ab") as fh:
            fh.write(extra.encode() + b"\n")

    n = ledger_rotate.rotate_jsonl(live, ledger_rotate.age_rule(35), NOW,
                                   control(tmp_path) / "archive", _before_replace=grow)
    assert n is None  # skipped: retried next run
    assert read_rows(live) == rows + [extra]
    assert not list((control(tmp_path) / "archive").glob("*.jsonl"))
    assert not list(live.parent.glob("*.tmp"))


def test_missing_files_are_nothing_to_do(tmp_path):
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert ledger_rotate.total(res) == 0 and res["skipped"] == []
    assert not (control(tmp_path) / "archive").exists()


# ---------------------------------------------------------------- timings

def test_timings_keep_newest_200_ok_per_kind_plus_the_last_30_days(tmp_path):
    live = control(tmp_path) / "timings.jsonl"
    rows = []
    for i in range(205):  # 205 old ok rows of kind a: the 5 oldest go
        rows.append({"kind": "a", "seconds": float(i), "ok": True, "ts": NOW - 90 * DAY + i})
    rows.append({"kind": "a", "seconds": 1.0, "ok": False, "ts": NOW - 40 * DAY})  # old fail goes
    rows.append({"kind": "a", "seconds": 2.0, "ok": False, "ts": NOW - 2 * DAY})  # young fail stays
    rows.append({"kind": "b", "seconds": 3.0, "ok": True, "ts": NOW - 400 * DAY})  # few b: stays
    rows = jl(rows) + ["torn{"]
    write_lines(live, rows)
    est = {k: eta.estimate(k, log=live) for k in ("a", "b", "c")}
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert res["timings"] == 6
    kept = read_rows(live)
    assert kept == rows[5:205] + rows[206:]
    assert {k: eta.estimate(k, log=live) for k in ("a", "b", "c")} == est
    moved = [ln for f in (control(tmp_path) / "archive").glob("timings-*.jsonl")
             for ln in read_rows(f)]
    assert sorted(moved) == sorted(rows[:5] + [rows[205]])


# ---------------------------------------------------------------- kit logs

def test_claims_gitlock_identity_keep_30_days(tmp_path):
    for name in ("claims", "gitlock", "identity"):
        rows = jl([{"at": local(NOW - 31 * DAY), "event": "old"},
                   {"at": local(NOW - 29 * DAY), "event": "young"}, "torn"])
        write_lines(control(tmp_path) / f"{name}.jsonl", rows)
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    for name in ("claims", "gitlock", "identity"):
        assert res[name] == 1
        assert [json.loads(r)["event"] for r in read_rows(control(tmp_path) / f"{name}.jsonl")
                if r != "torn"] == ["young"]


# ---------------------------------------------------------------- progress

def put(root, name, doc):
    p = control(root) / "progress" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="ascii")
    return p


def test_finished_progress_files_older_than_7_days_move_to_the_archive(tmp_path):
    old, young = iso(NOW - 8 * DAY), iso(NOW - 6 * DAY)
    put(tmp_path, "a.json", {"status": "done", "updated": old})
    put(tmp_path, "b.json", {"status": "failed", "updated": NOW - 8 * DAY})  # epoch form
    put(tmp_path, "c.json", {"status": "done", "updated": young})
    put(tmp_path, "d.json", {"status": "running", "updated": old})
    put(tmp_path, "e.json", {"status": "blocked", "updated": old})
    put(tmp_path, "loop.json", {"status": "done", "updated": old})
    put(tmp_path, "f.json", "{torn")
    put(tmp_path, "g.json", {"status": "done"})
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert res["progress"] == 2
    prog = control(tmp_path) / "progress"
    assert sorted(p.name for p in (prog / "archive").iterdir()) == ["a.json", "b.json"]
    assert sorted(p.name for p in prog.glob("*.json")) == [
        "c.json", "d.json", "e.json", "f.json", "g.json", "loop.json"]
    assert ledger_rotate.rotate(tmp_path, now=NOW)["progress"] == 0


def test_a_progress_name_already_archived_is_never_overwritten(tmp_path):
    put(tmp_path, "archive/a.json", {"first": 1})
    put(tmp_path, "a.json", {"status": "done", "updated": iso(NOW - 9 * DAY)})
    ledger_rotate.rotate(tmp_path, now=NOW)
    arch = control(tmp_path) / "progress" / "archive"
    assert json.loads((arch / "a.json").read_text()) == {"first": 1}
    assert len(list(arch.glob("a*.json"))) == 2


# ---------------------------------------------------------------- dry run, daily

def test_dry_run_writes_nothing(tmp_path):
    write_lines(control(tmp_path) / "headless_usage.jsonl", usage_rows())
    put(tmp_path, "a.json", {"status": "done", "updated": iso(NOW - 9 * DAY)})
    snap = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    res = ledger_rotate.rotate(tmp_path, now=NOW, dry_run=True)
    assert res["headless_usage"] == 2 and res["progress"] == 1
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == snap


def test_rotate_daily_runs_once_per_local_day(tmp_path):
    write_lines(control(tmp_path) / "headless_usage.jsonl", usage_rows())
    first = ledger_rotate.rotate_daily(tmp_path, now=NOW)
    assert first["headless_usage"] == 2
    write_lines(control(tmp_path) / "headless_usage.jsonl", usage_rows())
    assert ledger_rotate.rotate_daily(tmp_path, now=NOW + 60) is None
    assert ledger_rotate.rotate_daily(tmp_path, now=NOW + DAY)["headless_usage"] == 2


def test_rotate_daily_retries_the_same_day_after_a_skip(tmp_path, monkeypatch):
    write_lines(control(tmp_path) / "headless_usage.jsonl", usage_rows())
    real = ledger_rotate.rotate_jsonl
    monkeypatch.setattr(ledger_rotate, "rotate_jsonl", lambda *a, **k: None)
    res = ledger_rotate.rotate_daily(tmp_path, now=NOW)
    assert "headless_usage" in res["skipped"]
    monkeypatch.setattr(ledger_rotate, "rotate_jsonl", real)
    assert ledger_rotate.rotate_daily(tmp_path, now=NOW + 60)["headless_usage"] == 2


def test_summary_line_and_cli_dry_run(tmp_path, capsys):
    write_lines(control(tmp_path) / "headless_usage.jsonl", usage_rows())
    assert ledger_rotate.main(["--dry-run", "--root", str(tmp_path), "--now", str(NOW)]) == 0
    out = capsys.readouterr().out
    assert "headless_usage: 2" in out and "would move" in out
    assert len(read_rows(control(tmp_path) / "headless_usage.jsonl")) == 7
    assert ledger_rotate.summary({"headless_usage": 2, "timings": 0, "progress": 1,
                                  "skipped": ["claims"]}) == (
        "ledgers rotated: 2 row(s), 1 progress file(s) archived, skipped claims")


# ---------------------------------------------------------------- AUTO-23

def test_subagent_first_ledger_keeps_30_days(tmp_path):
    live = control(tmp_path) / "subagent_first.jsonl"
    rows = jl([{"at": local(NOW - d * DAY - 60), "tool": "Read", "decision": "allow"}
               for d in range(39, -1, -1)] + ["torn"])  # 40 days of rows
    write_lines(live, rows)
    res = ledger_rotate.rotate(tmp_path, now=NOW)
    assert res["subagent_first"] == 10
    kept = [json.loads(r) for r in read_rows(live) if r != "torn"]
    assert len(kept) == 30
    assert all(NOW - ledger_rotate._epoch(r["at"]) <= 30 * DAY for r in kept)
    assert read_rows(live)[-1] == "torn"
    moved = [ln for f in (control(tmp_path) / "archive").glob("subagent_first-*.jsonl")
             for ln in read_rows(f)]
    assert sorted(moved) == sorted(rows[:10])


def _aged(path, epoch, text="x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")
    os.utime(path, (epoch, epoch))
    return path


def test_one_off_suite_logs_move_to_logs_dev(tmp_path):
    side = tmp_path / "sidecar"
    logs = side / "Logs"
    old = NOW - 2 * DAY
    for name in ("suite-run.log", "pytest-full.txt", "AUTO-23-suite.out", "npm-test-1.log"):
        _aged(logs / name, old)
    _aged(logs / "pytest-now.log", NOW - 60)  # may still be written: stays
    for name in ("keepalive.log", "overlay.log", "tc-bridge.log", "events.jsonl"):
        _aged(logs / name, old)  # app logs: never moved
    _aged(logs / "dev" / "suite-run.log", old, "earlier\n")  # never overwritten
    _aged(logs / "ggg_docs" / "suite-x.log", old)  # subfolders untouched
    res = ledger_rotate.rotate(tmp_path, now=NOW, sidecar=side)
    assert res["suite_logs"] == 4
    dev = logs / "dev"
    assert sorted(p.name for p in dev.iterdir()) == sorted([
        "suite-run.log", "suite-run.1.log", "pytest-full.txt", "AUTO-23-suite.out",
        "npm-test-1.log"])
    assert (dev / "suite-run.log").read_text(encoding="ascii") == "earlier\n"
    assert sorted(p.name for p in logs.iterdir() if p.is_file()) == [
        "events.jsonl", "keepalive.log", "overlay.log", "pytest-now.log", "tc-bridge.log"]
    assert (logs / "ggg_docs" / "suite-x.log").exists()
    assert ledger_rotate.rotate(tmp_path, now=NOW, sidecar=side)["suite_logs"] == 0


def test_suite_logs_dry_run_moves_nothing(tmp_path):
    side = tmp_path / "sidecar"
    _aged(side / "Logs" / "suite-run.log", NOW - 2 * DAY)
    res = ledger_rotate.rotate(tmp_path, now=NOW, dry_run=True, sidecar=side)
    assert res["suite_logs"] == 1
    assert (side / "Logs" / "suite-run.log").exists()
    assert not (side / "Logs" / "dev").exists()


def docs_state(root, pages):
    p = root / "sidecar" / "Cache" / "ggg_docs" / "state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"status": "error", "pages": pages}), encoding="ascii")
    return p


def test_docs_watch_read_older_than_3_days_prints_stale(tmp_path, capsys):
    docs_state(tmp_path, {"index": {"read": iso(NOW - 4 * DAY)},
                          "changelog": {"read": iso(NOW - 5 * DAY)}})
    res = ledger_rotate.rotate(tmp_path, now=NOW, sidecar=tmp_path / "sidecar")
    stale = [ln for ln in ledger_rotate.lines(res) if ln.startswith("STALE")]
    assert len(stale) == 1
    assert "docs watch" in stale[0] and "4 day" in stale[0]
    assert ledger_rotate.main(["--dry-run", "--root", str(tmp_path), "--now", str(NOW),
                               "--sidecar", str(tmp_path / "sidecar")]) == 0
    out = capsys.readouterr().out
    assert len([ln for ln in out.splitlines() if ln.startswith("STALE")]) == 1


def test_fresh_docs_watch_read_prints_nothing(tmp_path):
    docs_state(tmp_path, {"index": {"read": iso(NOW - 4 * DAY)},
                          "changelog": {"read": iso(NOW - 2 * DAY)}})
    res = ledger_rotate.rotate(tmp_path, now=NOW, sidecar=tmp_path / "sidecar")
    assert res["stale"] == []
    assert ledger_rotate.lines(res) == [ledger_rotate.summary(res)]


def test_no_docs_watch_state_and_no_sidecar_print_nothing(tmp_path):
    res = ledger_rotate.rotate(tmp_path, now=NOW, sidecar=tmp_path / "sidecar")
    assert res["stale"] == [] and res["suite_logs"] == 0
    res = ledger_rotate.rotate(tmp_path, now=NOW)  # no sidecar given: skipped
    assert res["stale"] == [] and res["suite_logs"] == 0


def test_a_state_with_no_good_read_is_stale_once_3_days_old(tmp_path):
    p = docs_state(tmp_path, {})
    os.utime(p, (NOW - 4 * DAY, NOW - 4 * DAY))
    res = ledger_rotate.rotate(tmp_path, now=NOW, sidecar=tmp_path / "sidecar")
    assert len(res["stale"]) == 1 and "never" in res["stale"][0]
    os.utime(p, (NOW - DAY, NOW - DAY))  # a first read under way: not yet stale
    res = ledger_rotate.rotate(tmp_path, now=NOW, sidecar=tmp_path / "sidecar")
    assert res["stale"] == []


def test_only_the_real_tree_resolves_the_real_sidecar(tmp_path):
    assert ledger_rotate.sidecar_for(tmp_path) is None
    assert ledger_rotate.sidecar_for(ROOT) is not None


def test_rotate_daily_on_a_fixture_root_reports_stale_from_its_sidecar(tmp_path):
    docs_state(tmp_path, {"index": {"read": iso(NOW - 4 * DAY)}})
    res = ledger_rotate.rotate_daily(tmp_path, now=NOW, sidecar=tmp_path / "sidecar")
    assert len(res["stale"]) == 1
