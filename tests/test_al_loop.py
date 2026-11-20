"""Plan 015: tools/al_loop.py tick. Every side effect is injected: no test
spawns claude, touches a git remote or calls schtasks. Merge tests use a
throwaway local git repo under tmp_path."""

import contextlib
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402

from al_loopkit import (  # noqa: E402 (plan 156: shared with the sibling loop tests)
    HANDOFF, ROADMAP, FakeSpawn, _inbox_root, deps, git, git_world, isolate_git, make_root,
    progress, real_git)

# TEST-LOOP-SPLIT-LANES (F-196): the lane worker, stalls, lane race, resolve
# lanes, refused commits and the detached review worker live in
# tests/test_al_loop_lanes.py.

# Plan 097 / 156 (TESTS-A-18): only the tests that build a real git world under
# tmp_path are marked git, one by one, so the fast tier runs the pure ones; the
# module stays one git unit (--dist loadfile keeps it on one worker). Tests
# over about 1.5 s are also marked slow.


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    isolate_git(monkeypatch)  # TESTS-A-19


# ---------------------------------------------------------------- parsing

def test_title_dedupe_by_token_overlap():
    existing = ["Grind spot recommender by AP/DP/level from a sourced community table",
                "Season pass tracker by objective"]
    assert al_loop.is_duplicate("Grind spot recommender", existing) == existing[0]
    assert al_loop.is_duplicate("Season Pass objective tracker", existing) == existing[1]
    assert al_loop.is_duplicate("Lifeskill node empire planner", existing) is None


def test_ascii_text():
    raw = "a" + chr(0x2014) + "b " + chr(0x201C) + "q" + chr(0x201D) + chr(0xE9)
    assert al_loop.ascii_text(raw) == 'a-b "q"?'


# ---------------------------------------------------------------- tick gates

def test_halt_writes_halted_and_spawns_nothing(tmp_path):
    root = make_root(tmp_path)
    (root / "ops/loop/control").mkdir(parents=True)
    (root / "ops/loop/control/HALT").write_text("")
    d = deps(root)
    doc = al_loop.tick(deps=d)
    assert doc["state"] == "halted" and d.spawn.calls == [] and d.seen["launch"] == []
    st = json.loads((root / "ops/loop/control/inbox_status.json").read_text())
    assert st["state"] == "halted" and st["next_tick"]


def test_busy_lock_exits_quietly(tmp_path):
    root = make_root(tmp_path)

    @contextlib.contextmanager
    def busy(path):
        raise d.watch.LockBusy("held")
        yield

    d = deps(root, lock=busy)
    assert al_loop.tick(deps=d) == {"state": "busy"}
    assert not (root / "ops/loop/control/progress/loop.json").exists()


@pytest.mark.git
def test_inbox_unconfigured_logged(tmp_path):
    root = make_root(tmp_path)
    d = deps(root)
    al_loop.tick(deps=d, no_push=True)
    assert "inbox unconfigured" in progress(root)["log"]


@pytest.mark.git
def test_tick_rotates_control_ledgers_once_a_day_after_reap(tmp_path):
    """Plan 138: one step line when the daily rotation ran, none otherwise;
    a dry-run tick never rotates."""
    root = make_root(tmp_path)
    calls = []
    res = {"headless_usage": 3, "timings": 0, "progress": 1, "skipped": []}
    d = deps(root, rotate=lambda r, now: calls.append((r, now)) or res)
    al_loop.tick(deps=d, no_push=True)
    assert calls == [(root, 1_790_000_000.0)]
    assert "ledgers rotated: 3 row(s), 1 progress file(s) archived" in progress(root)["log"]
    d = deps(root, rotate=lambda r, now: calls.append(r))
    al_loop.tick(deps=d, no_push=True)
    assert not any(s.startswith("ledgers rotated") for s in progress(root)["log"])
    al_loop.tick(dry_run=True, deps=d, no_push=True)
    assert len(calls) == 2


@pytest.mark.git
def test_tick_runs_the_tc_drift_check_and_logs_its_line(tmp_path):
    """TC-DRIFT: the tick calls the drift hook (daily throttle lives in
    tools/tc_drift.py) and logs its one line; a dry run never calls it, and
    a drift fault never stops the tick."""
    root = make_root(tmp_path)
    calls = []
    line = "tc drift: PoB-PoE2 v0.24.0 released (pin v0.23.1), trial launched"
    d = deps(root, drift=lambda r, now: calls.append((r, now)) or line)
    al_loop.tick(deps=d, no_push=True)
    assert calls == [(root, 1_790_000_000.0)]
    assert line in progress(root)["log"]
    al_loop.tick(dry_run=True, deps=d, no_push=True)
    assert len(calls) == 1
    assert al_loop._drift_check(tmp_path / "no-such-tree", 0.0) is None


def test_inbox_defaults_to_fleet_moon_sync_dirs(tmp_path):
    cfg = al_loop.load_config(tmp_path)
    assert Path(cfg["inbox_dir"]) == tmp_path / "moon_sync_inbox"
    assert Path(cfg["outbox_dir"]) == tmp_path / "moon_sync_outbox"


# ---------------------------------------------------------------- inbox

@pytest.mark.git
def test_inbox_baseline_then_one_answer_per_note(tmp_path):
    inbox, outbox = tmp_path / "in", tmp_path / "out"
    inbox.mkdir()
    outbox.mkdir()
    (inbox / "old-from-MAIN-ORDER-x.md").write_text("# From MAIN - ORDER\nold\n")
    root = make_root(tmp_path, roadmap="", handoff="",
                     local={"loop": {"inbox_dir": str(inbox), "outbox_dir": str(outbox)}})
    sp = FakeSpawn([{"rc": 0, "error": None,
                     "result": "VERDICT: ANSWER\nyes " + chr(0x2014) + " ok"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)  # baseline: history is not news
    assert [c for c in sp.calls if c.get("note", "").endswith(".md")] == []
    (inbox / "n1-from-MAIN-QUESTION-y.md").write_text("# From MAIN - QUESTION\nq?\n")
    (inbox / "n2-from-AL-ANSWER-z.md").write_text("# From AL - ANSWER\nmine\n")
    (inbox / "n3-from-MAIN-INFORMATION-w.md").write_text("# From MAIN\nTERMINAL\n")
    al_loop.tick(deps=d, no_push=True)
    inbox_calls = [c for c in sp.calls if c.get("note", "").endswith(".md")]
    assert [c["note"] for c in inbox_calls] == ["n1-from-MAIN-QUESTION-y.md"]
    c = inbox_calls[0]
    # kit v8 item 14 b: one triage spawn, sonnet, effort low, bare, kind triage
    assert c["model"] == "sonnet" and c["effort"] == "low" and c["bare"] is True
    assert c["kind"] == "triage" and c["writes_code"] is False
    assert "governor" not in c and c["stdin"] is True
    replies = list(outbox.glob("*-from-AL-ANSWER-to-MAIN-*.md"))
    assert len(replies) == 1
    text = replies[0].read_bytes().decode("ascii")
    assert "HOP: 2" in text and "yes - ok" in text and "n1-from-MAIN-QUESTION-y.md" in text
    al_loop.tick(deps=d, no_push=True)  # re-run is a no-op
    assert len([c for c in sp.calls if c.get("note", "").endswith(".md")]) == 1
    seen = (root / "ops/loop/control/inbox_seen.jsonl").read_text()
    assert "n1-from-MAIN-QUESTION-y.md" in seen and "n3-from-MAIN-INFORMATION-w.md" in seen


@pytest.mark.git
def test_inbox_failed_answer_is_reoffered(tmp_path):
    inbox, outbox = tmp_path / "in", tmp_path / "out"
    inbox.mkdir()
    outbox.mkdir()
    root = make_root(tmp_path, roadmap="", handoff="",
                     local={"loop": {"inbox_dir": str(inbox), "outbox_dir": str(outbox)}})
    sp = FakeSpawn([{"rc": 1, "error": "boom", "result": None},
                    {"rc": 0, "error": None, "result": "VERDICT: ANSWER\nfine"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    (inbox / "a-from-MAIN-QUESTION-q.md").write_text("# From MAIN - QUESTION\ndo\n")
    al_loop.tick(deps=d, no_push=True)
    assert not list(outbox.iterdir())
    al_loop.tick(deps=d, no_push=True)
    assert len(list(outbox.iterdir())) == 1


@pytest.mark.git
def test_triage_noreply_or_ack_writes_no_note(tmp_path):
    inbox, outbox = tmp_path / "in", tmp_path / "out"
    inbox.mkdir()
    outbox.mkdir()
    root = make_root(tmp_path, roadmap="", handoff="",
                     local={"loop": {"inbox_dir": str(inbox), "outbox_dir": str(outbox)}})
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: NOREPLY"},
                    {"rc": 0, "error": None, "result": "no verdict at all"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    (inbox / "a-from-MAIN-QUESTION-q.md").write_text("# From MAIN - QUESTION\nq\n")
    (inbox / "b-from-SS-PROPOSAL-p.md").write_text("# From SS - PROPOSAL\np\n")
    al_loop.tick(deps=d, no_push=True)
    assert not list(outbox.iterdir()) and len(sp.calls) == 2
    al_loop.tick(deps=d, no_push=True)
    assert len(sp.calls) == 2


@pytest.mark.git
def test_order_note_escalates_to_lane_item_then_answers_after_merge(tmp_path):
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=ROADMAP)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "# From AL - ANSWER\ndone"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)  # baseline
    name = "b-from-MAIN-ORDER-to-AL-harden.md"
    (inbox / name).write_text("# From MAIN - ORDER\nadd dependabot\n")
    al_loop.tick(deps=d, no_push=True)
    oid = al_loop.order_id(name)
    assert [c for c in sp.calls if c.get("note") == name] == []  # no ack spawn
    assert d.seen["launch"][-1] == oid
    assert al_loop.Tick(d).work_list()[1][0]["id"] == oid  # orders first
    rec = al_loop.Items(root).get(oid)
    assert rec["kind"] == "order" and "add dependabot" in rec["prompt"]
    assert not list(outbox.iterdir())
    rec.update(state="merged", commit="abc123", verdict="PASS", rounds=1)
    al_loop.Items(root).put(rec)
    al_loop.tick(deps=d, no_push=True)
    calls = [c for c in sp.calls if c.get("note") == name]
    assert len(calls) == 1 and "abc123" in calls[0]["prompt"]
    assert calls[0]["kind"] == "inbox"
    replies = list(outbox.glob("*-re-b-from-MAIN-ORDER-to-AL-harden.md"))
    assert len(replies) == 1
    lines = replies[0].read_text().splitlines()
    assert lines[0] == "# From AL - ANSWER" and lines[1] == "HOP: 2"
    al_loop.tick(deps=d, no_push=True)
    assert len([c for c in sp.calls if c.get("note") == name]) == 1


@pytest.mark.git
def test_daily_note_cap_defers_answers(tmp_path):
    root, inbox, outbox = _inbox_root(tmp_path, local_extra={"max_notes_per_day": 1})
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: ANSWER\nok"}] * 3)
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    (inbox / "q1-from-MAIN-QUESTION-a.md").write_text("q1\n")
    (inbox / "q2-from-SS-QUESTION-b.md").write_text("q2\n")
    doc = al_loop.tick(deps=d, no_push=True)
    assert len(list(outbox.iterdir())) == 1
    assert any("daily note cap 1" in s for s in doc["log"])
    assert any("1 capped" in s for s in doc["log"])
    assert not any("deliver-failed" in s for s in doc["log"])


@pytest.mark.git
def test_answers_to_one_destination_batch_into_one_note(tmp_path):
    root, inbox, outbox = _inbox_root(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: ANSWER\nfirst"},
                    {"rc": 0, "error": None, "result": "VERDICT: ANSWER\nsecond"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    (inbox / "q1-from-MAIN-QUESTION-a.md").write_text("# From MAIN - QUESTION\nq1\n")
    (inbox / "q2-from-MAIN-QUESTION-b.md").write_text("# From MAIN - QUESTION\nq2\n")
    al_loop.tick(deps=d, no_push=True)
    notes = list(outbox.iterdir())
    assert len(notes) == 1
    body = notes[0].read_text()
    assert "first" in body and "second" in body and "HOP: 2" in body
    ledger = (root / "ops/loop/control/outbound_notes.jsonl").read_text().splitlines()
    assert len(ledger) == 1 and json.loads(ledger[0])["parts"] == 2


# ---------------------------------------------------------------- plan 093 delivery

def _sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _deliveries(root):
    return [json.loads(x) for x in
            (root / "ops/loop/control/delivery.jsonl").read_text().splitlines()]


@pytest.mark.git
def test_batch_reply_lands_in_destination_inbox_with_matching_hash(tmp_path):
    dest = tmp_path / "main_inbox"
    dest.mkdir()
    root, inbox, outbox = _inbox_root(tmp_path, local_extra={
        "dest_inboxes": {"MAIN": str(dest)}})
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: ANSWER\nyes"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    (inbox / "q1-from-MAIN-QUESTION-a.md").write_text("# From MAIN - QUESTION\nq1\n")
    doc = al_loop.tick(deps=d, no_push=True)
    [out] = list(outbox.iterdir())
    [copy] = list(dest.iterdir())
    assert copy.name == out.name
    assert re.match(r"\d{4}-\d{2}-\d{2}-\d{4}-from-AL-ANSWER-", copy.name)
    assert _sha(copy) == _sha(out)
    [rec] = _deliveries(root)
    assert rec["note"] == out.name and rec["to"] == "MAIN" and rec["reached"] is True
    assert rec["sha256"] == _sha(out)
    assert any("1/1 reached" in s for s in doc["log"])
    al_loop.tick(deps=d, no_push=True)  # re-run is a no-op
    assert len(_deliveries(root)) == 1 and len(list(dest.iterdir())) == 1


@pytest.mark.git
def test_order_answer_uses_dashed_stamp_and_lands_in_sender_inbox(tmp_path):
    dest = tmp_path / "main_inbox"
    dest.mkdir()
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=ROADMAP, local_extra={
        "dest_inboxes": {"MAIN": str(dest)}})
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "# From AL - ANSWER\ndone"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    name = "b-from-MAIN-ORDER-to-AL-harden.md"
    (inbox / name).write_text("# From MAIN - ORDER\nadd dependabot\n")
    al_loop.tick(deps=d, no_push=True)
    rec = al_loop.Items(root).get(al_loop.order_id(name))
    rec.update(state="merged", commit="abc123", verdict="PASS", rounds=1)
    al_loop.Items(root).put(rec)
    al_loop.tick(deps=d, no_push=True)
    [out] = list(outbox.iterdir())
    assert re.match(r"\d{4}-\d{2}-\d{2}-\d{4}-from-AL-ANSWER-re-b-from-MAIN", out.name)
    [copy] = list(dest.iterdir())
    assert copy.name == out.name and _sha(copy) == _sha(out)


@pytest.mark.git
def test_roster_resolves_destination_inbox(tmp_path):
    main_root = tmp_path / "mainrepo"
    (main_root / "moon_sync_inbox").mkdir(parents=True)
    roster = tmp_path / "fleet_roster.json"
    roster.write_text(json.dumps({"repos": [{"code": "MAIN", "root": str(main_root)}]}))
    root, inbox, outbox = _inbox_root(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: ANSWER\nyes"}])
    d = deps(root, spawn=sp, roster_path=roster)
    al_loop.tick(deps=d, no_push=True)
    (inbox / "q1-from-MAIN-QUESTION-a.md").write_text("# From MAIN - QUESTION\nq1\n")
    al_loop.tick(deps=d, no_push=True)
    [out] = list(outbox.iterdir())
    [copy] = list((main_root / "moon_sync_inbox").iterdir())
    assert _sha(copy) == _sha(out)


@pytest.mark.git
def test_unresolved_destination_is_recorded_0_of_1_then_retried(tmp_path):
    root, inbox, outbox = _inbox_root(tmp_path)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: ANSWER\nyes"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    (inbox / "q1-from-MAIN-QUESTION-a.md").write_text("# From MAIN - QUESTION\nq1\n")
    doc = al_loop.tick(deps=d, no_push=True)
    assert len(list(outbox.iterdir())) == 1  # the outbox copy is still the record
    assert any("0/1 reached" in s for s in doc["log"])
    assert _deliveries(root)[-1]["reached"] is False
    # the destination becomes known: the next tick delivers the outbox copy
    dest = tmp_path / "main_inbox"
    dest.mkdir()
    cfg = json.loads((root / "config/local.json").read_text())
    cfg["loop"]["dest_inboxes"] = {"MAIN": str(dest)}
    (root / "config/local.json").write_text(json.dumps(cfg))
    doc = al_loop.tick(deps=d, no_push=True)
    [out] = list(outbox.iterdir())
    [copy] = list(dest.iterdir())
    assert _sha(copy) == _sha(out) and _deliveries(root)[-1]["reached"] is True
    assert any("redelivered 1/1 reached" in s for s in doc["log"])
    assert len(sp.calls) == 1  # no second triage spawn


def test_existing_destination_copy_with_other_bytes_is_not_overwritten(tmp_path):
    dest = tmp_path / "main_inbox"
    dest.mkdir()
    root, inbox, outbox = _inbox_root(tmp_path, local_extra={
        "dest_inboxes": {"MAIN": str(dest)}})
    t = al_loop.Tick(deps(root))
    note = outbox / "2026-10-08-2300-from-AL-ANSWER-to-MAIN-x.md"
    note.write_text("# From AL - ANSWER\nHOP: 2\nreal\n", newline="\n")
    (dest / note.name).write_text("other\n", newline="\n")
    assert t.deliver_note(note, "MAIN") is False
    assert (dest / note.name).read_text() == "other\n"
    assert _deliveries(root)[-1]["reached"] is False


def test_max_notes_default_is_kit_cap_and_config_cannot_raise_it(tmp_path):
    assert al_loop.load_config(tmp_path)["max_notes_per_day"] == 12
    root = make_root(tmp_path, local={"loop": {"max_notes_per_day": 24}})
    assert al_loop.load_config(root)["max_notes_per_day"] == 12
    root2 = make_root(tmp_path / "b", local={"loop": {"max_notes_per_day": 2}})
    assert al_loop.load_config(root2)["max_notes_per_day"] == 2


@pytest.mark.git
def test_order_answer_respects_slot_held_by_a_batch(tmp_path):
    # verifier r1 finding 2: the order answer must not take the slot a batch holds
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=ROADMAP,
                                      local_extra={"max_notes_per_day": 1})
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: ANSWER\nq answer"},
                    {"rc": 0, "error": None, "result": "# From AL - ANSWER\ndone"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    order = "o-from-MAIN-ORDER-to-AL-x.md"
    (inbox / "a-from-MAIN-QUESTION-q.md").write_text("# From MAIN - QUESTION\nq\n")
    (inbox / order).write_text("# From MAIN - ORDER\ndo\n")
    rec = {"id": al_loop.order_id(order), "kind": "order", "state": "merged",
           "commit": "c0ffee", "verdict": "PASS", "rounds": 0, "title": order}
    al_loop.Items(root).put(rec)
    doc = al_loop.tick(deps=d, no_push=True)
    assert len(list(outbox.iterdir())) == 1
    line = [s for s in doc["log"] if s.startswith("inbox:")][-1]
    assert "deliver-failed" not in line and "1 capped" in line
    assert [c.get("note") for c in sp.calls] == ["a-from-MAIN-QUESTION-q.md"]


@pytest.mark.git
def test_ack_class_and_hop_limit_are_ledger_lines_not_notes(tmp_path):
    root, inbox, outbox = _inbox_root(tmp_path)
    sp = FakeSpawn()
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    (inbox / "a-from-MAIN-ANSWER-re-x.md").write_text("# From MAIN - ANSWER\nthanks\n")
    (inbox / "b-from-MAIN-ACK-y.md").write_text("# From MAIN - ACK\nok\n")
    (inbox / "c-from-MAIN-QUESTION-z.md").write_text("# From MAIN - QUESTION\nHOP: 2\nq?\n")
    doc = al_loop.tick(deps=d, no_push=True)
    assert sp.calls == [] and not list(outbox.iterdir())
    assert sum(s.startswith("inbox ack") for s in doc["log"]) == 3
    seen = (root / "ops/loop/control/inbox_seen.jsonl").read_text().splitlines()
    assert [json.loads(x)["action"] for x in seen] == ["ack"] * 3


@pytest.mark.git
def test_ack_quoting_an_order_name_is_not_escalated(tmp_path):
    # verifier r2: escalation follows classify(), not an -ORDER- token anywhere
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=ROADMAP)
    sp = FakeSpawn()
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    for name in ("a-from-MAIN-ACK-re-b-from-AL-ANSWER-re-c-from-MAIN-ORDER-to-AL-x.md",
                 "d-from-MAIN-ANSWER-re-e-FIX-plan.md"):
        (inbox / name).write_text("# From MAIN - ACK\nseen\n")
    doc = al_loop.tick(deps=d, no_push=True)
    assert sp.calls == [] and not list(outbox.iterdir())
    assert not (root / "ops/loop/control/loop_orders.json").exists()
    assert sum(s.startswith("inbox ack") for s in doc["log"]) == 2


@pytest.mark.git
def test_note_settled_by_pre_v8_ledger_is_not_retriaged(tmp_path):
    root, inbox, outbox = _inbox_root(tmp_path)
    sp = FakeSpawn()
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    (root / "ops/loop/control/inbox_ledger.jsonl").write_text(
        json.dumps({"note": "q-from-MAIN-QUESTION-a.md", "action": "ack"}) + "\n")
    (inbox / "q-from-MAIN-QUESTION-a.md").write_text("# From MAIN - QUESTION\nq\n")
    al_loop.tick(deps=d, no_push=True)
    assert sp.calls == []


@pytest.mark.git
def test_note_settled_before_the_seen_ledger_is_backfilled_once(tmp_path):
    # 2026-10-09: 10-04/10-05 notes (legacy ledger or an outbox reply) were
    # handled before inbox_seen.jsonl existed and never appeared in it.
    root, inbox, outbox = _inbox_root(tmp_path)
    sp = FakeSpawn()
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    (root / "ops/loop/control/inbox_ledger.jsonl").write_text(
        json.dumps({"note": "q-from-MAIN-QUESTION-a.md", "action": "ack"}) + "\n")
    (inbox / "q-from-MAIN-QUESTION-a.md").write_text("# From MAIN - QUESTION\nq\n")
    (inbox / "o-from-MAIN-ORDER-to-AL-v6.md").write_text("# From MAIN - ORDER\nv6\n")
    (outbox / "2026-10-05-0900-from-AL-ANSWER-re-o-from-MAIN-ORDER-to-AL-v6.md"
     ).write_text("# From AL - ANSWER\ndone\n")
    al_loop.tick(deps=d, no_push=True)
    al_loop.tick(deps=d, no_push=True)
    assert sp.calls == []
    seen = [json.loads(x) for x in
            (root / "ops/loop/control/inbox_seen.jsonl").read_text().splitlines()]
    assert sorted(x["note"] for x in seen) == ["o-from-MAIN-ORDER-to-AL-v6.md",
                                               "q-from-MAIN-QUESTION-a.md"]
    assert {x["verdict"] for x in seen} == {"LEGACY"} and all(x.get("sha256") for x in seen)
    # kit v27: the backfilled ORDER was queued by mark_seen and is closed at once
    work = [json.loads(x) for x in
            (root / "ops/loop/control/inbox_work.jsonl").read_text().splitlines()]
    assert [(x["op"], x["note"]) for x in work] == [
        ("queued", "o-from-MAIN-ORDER-to-AL-v6.md"), ("done", "o-from-MAIN-ORDER-to-AL-v6.md")]
    marker = json.loads((root / "ops/loop/control/inbox_pending_orders.json").read_text())
    assert marker["pending"] == []


def test_default_cap_reaches_the_kit_outbound_cap(tmp_path):
    root, _, _ = _inbox_root(tmp_path, local_extra={"max_notes_per_day": 40})
    assert al_loop.Tick(deps(root)).cap.cap == 12


def test_unlabelled_tick_spawns_are_kind_build(tmp_path):
    sp = FakeSpawn()
    t = al_loop.Tick(deps(make_root(tmp_path), spawn=sp))
    t.spawn("p", note="lane-review-x", writes_code=False)
    assert sp.calls[-1]["kind"] == "build"


@pytest.mark.git
def test_pending_orders_are_not_delivery_failures_and_handled_notes_stay_handled(tmp_path):
    # 2026-10-05: loop.json read "inbox: deliver-failed 2 2 pending" - two ORDERs
    # waiting for their lane items. Pending is by design; the label was wrong,
    # and every other note of the re-offered batch was processed again each tick.
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=ROADMAP)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: ACK"}] * 5)
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)  # baseline
    (inbox / "o-from-MAIN-ORDER-to-AL-x.md").write_text("# From MAIN - ORDER\nwork\n")
    (inbox / "q-from-MAIN-QUESTION-y.md").write_text("# From MAIN - QUESTION\nq\n")
    doc = al_loop.tick(deps=d, no_push=True)
    line = [s for s in doc["log"] if s.startswith("inbox:")][-1]
    assert "deliver-failed" not in line and "1 order(s) awaiting lane" in line
    triage = [c for c in sp.calls if c.get("note") == "q-from-MAIN-QUESTION-y.md"]
    assert len(triage) == 1
    al_loop.tick(deps=d, no_push=True)  # the order is still pending
    triage = [c for c in sp.calls if c.get("note") == "q-from-MAIN-QUESTION-y.md"]
    assert len(triage) == 1  # never re-triaged


@pytest.mark.git
def test_priority_rows_dispatch_first(tmp_path):
    rm = ROADMAP.replace("- [ ] 013 Season pass tracker",
                         "- [ ] 013 Season pass tracker (priority)")
    root = make_root(tmp_path, roadmap=rm, handoff="")
    d = deps(root)
    al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"][:2] == ["013", "012"]


# ---------------------------------------------------------------- dispatch

@pytest.mark.git
def test_dead_lane_process_is_redispatched_once(tmp_path):
    root = make_root(tmp_path, roadmap=ROADMAP.replace("- [ ] 013 Season pass tracker\n", ""),
                     handoff="")
    alive = {"v": False}
    d = deps(root, pid_alive=lambda pid: alive["v"])
    for _ in range(4):
        al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"].count("012") == al_loop.MAX_ATTEMPTS


@pytest.mark.git
def test_runs_cap_headroom_stops_spawning(tmp_path):
    root = make_root(tmp_path)
    d = deps(root)
    now = d.clock()
    p = root / "ops/loop/control/headless_budget.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"starts": [now - 10] * (d.budget.cap - 3)}))
    d.budget.clock = lambda: now
    doc = al_loop.tick(deps=d, no_push=True)
    assert d.seen["launch"] == [] and doc["state"] == "limit"


def test_backoff_doubles_and_caps(tmp_path):
    root, now = tmp_path, 1_790_000_000.0
    a = al_loop.backoff_hit(root, now, "429")
    b = al_loop.backoff_hit(root, now, "429")
    assert (a["delay_s"], b["delay_s"]) == (1800, 3600) and b["until"] == now + 3600
    for _ in range(10):
        c = al_loop.backoff_hit(root, now, "usage limit")
    assert c["delay_s"] == 6 * 3600
    al_loop.backoff_clear(root)
    assert al_loop.backoff_until(root) == 0


@pytest.mark.git
def test_usage_limit_result_sets_backoff_and_pauses(tmp_path):
    inbox, outbox = tmp_path / "in", tmp_path / "out"
    inbox.mkdir()
    outbox.mkdir()
    root = make_root(tmp_path, local={"loop": {"inbox_dir": str(inbox),
                                               "outbox_dir": str(outbox)}})
    sp = FakeSpawn([{"rc": 1, "error": None, "result": "Claude usage limit reached"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)
    (inbox / "a-from-MAIN-QUESTION-q.md").write_text("# From MAIN - QUESTION\ndo\n")
    d.seen["launch"].clear()
    al_loop.Items(root).dir.mkdir(parents=True, exist_ok=True)
    for p in al_loop.Items(root).dir.glob("*.json"):
        p.unlink()
    doc = al_loop.tick(deps=d, no_push=True)
    assert al_loop.backoff_until(root) == d.clock() + 1800
    assert doc["state"] == "backoff" and d.seen["launch"] == []


@pytest.mark.git
def test_dry_run_spawns_and_launches_nothing(tmp_path):
    root = make_root(tmp_path)
    d = deps(root)
    doc = al_loop.tick(dry_run=True, deps=d)
    assert d.spawn.calls == [] and d.seen["launch"] == [] and d.seen["record"] == []
    assert any("would dispatch" in s for s in doc["log"])


# ---------------------------------------------------------------- checklist

@pytest.mark.git
def test_checklist_lines(tmp_path):
    # FLEET item 13 d (kit v7/v8): remaining tasks as {id, task, state, eta_s}
    # LOOP-HANDOFF-PREFIX: only LOOP: bullets are hand-off items
    root = make_root(tmp_path, handoff=HANDOFF.replace("\n- ", "\n- LOOP: "))
    d = deps(root)
    doc = al_loop.tick(deps=d, no_push=True)
    cl = doc["checklist"]
    assert all(set(r) == {"id", "task", "state", "eta_s"} for r in cl)
    assert cl[0] == {"id": "012", "task": "Grind spot recommender", "state": "dispatched",
                     "eta_s": 2700}
    assert any(r["state"] == "operator-only, skipped" for r in cl)
    assert any(r["state"] == "other-tree-only, skipped" for r in cl)
    assert len(cl) <= 20 and doc["fire"] == 1
    assert al_loop.tick(deps=d, no_push=True)["fire"] == 2
    block = al_loop.render_checklist(progress(root))
    lines = block.splitlines()
    assert lines[0] == "Session 2 checklist" and lines[-1] == chr(0x2610) + " /done"
    assert lines[1] == chr(0x2610) + " 012: Grind spot recommender (dispatched, ~45m Remain)"
    raw = (root / "ops/loop/control/progress/loop.json").read_bytes()
    raw.decode("ascii")
    st = json.loads((root / "ops/loop/control/inbox_status.json").read_text())
    assert st["code"] == "AL" and st["state"] == "running" and st["next_tick"]


def test_checklist_cli_heads_with_handoff_session(tmp_path, monkeypatch, capsys):
    # FLEET item 13 a: an interactive `checklist` reads `Session <n>` from the
    # hand-off SESSION line, not the tick's fire count
    assert al_loop.handoff_session("x\nSESSION: 34\ny\n") == 34
    assert al_loop.handoff_session("no counter") is None
    doc = {"fire": 7, "checklist": [{"id": "012", "task": "Grind", "state": None,
                                     "eta_s": None}]}
    assert al_loop.render_checklist(doc).splitlines()[0] == "Session 7 checklist"
    assert al_loop.render_checklist(doc, 34).splitlines()[0] == "Session 34 checklist"
    (tmp_path / "ops/loop/control/progress").mkdir(parents=True)
    (tmp_path / "ops/loop/control/progress/loop.json").write_text(json.dumps(doc))
    monkeypatch.setattr(al_loop, "ROOT", tmp_path)
    assert al_loop.main(["checklist"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "Session 7 checklist"
    (tmp_path / "AL-NEXT-SESSION.txt").write_text("hand-off\nSESSION: 34\n")
    assert al_loop.main(["checklist"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "Session 34 checklist"


# ---------------------------------------------------------------- plan 091

def test_session_paths_names_protected_targets():
    sp = al_loop.session_paths
    assert sp("o-from-MAIN-ORDER-to-AL-x.md", "add dependabot\n") == []
    assert sp("n.md", "vendor into ops/fleet_kit/ and re-pin") == ["ops/fleet_kit/"]
    assert sp("n.md", "edit ops\\fleet_kit\\MANIFEST.json") == ["ops/fleet_kit/"]
    assert sp("2026-FLEET-KIT-v10-ORDER.md", "ship it") == ["ops/fleet_kit/"]
    assert sp("n.md", "wire .claude/settings.json and re-embed CLAUDE.md") == \
        [".claude/", "CLAUDE.md"]
    assert sp("n.md", "the app/.claudex dir and NOTCLAUDE.mdx") == []


KIT_ORDER = "k-from-MAIN-ORDER-to-AL-kit-v10.md"


def _session_order(tmp_path):
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=ROADMAP)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "# From AL - ANSWER\nvendored"}])
    d = deps(root, spawn=sp)
    al_loop.tick(deps=d, no_push=True)  # baseline
    (inbox / KIT_ORDER).write_text("# From MAIN - ORDER\nvendor kit into ops/fleet_kit/\n"
                                   "wire the hook in .claude/settings.json\n")
    return root, outbox, sp, d


@pytest.mark.git
def test_session_order_is_not_dispatched_and_shows_in_checklist(tmp_path):
    root, outbox, sp, d = _session_order(tmp_path)
    doc = al_loop.tick(deps=d, no_push=True)
    oid = al_loop.order_id(KIT_ORDER)
    assert oid not in d.seen["launch"] and al_loop.Items(root).get(oid) is None
    _, work, skipped = al_loop.Tick(d).work_list()
    assert oid not in [w["id"] for w in work]
    hit = [h for h in skipped if h["id"] == oid]
    assert hit and hit[0]["skip"] == "session"
    row = [r for r in doc["checklist"] if r["id"] == oid]
    assert row and row[0]["state"].startswith("session: needs ops/fleet_kit/")
    assert not list(outbox.iterdir())


@pytest.mark.git
def test_session_order_waits_past_adjudicate_then_answers_after_session_done(tmp_path):
    root, outbox, sp, d = _session_order(tmp_path)
    al_loop.tick(deps=d, no_push=True)
    oid = al_loop.order_id(KIT_ORDER)
    al_loop.Items(root).put({"id": oid, "kind": "order", "state": "adjudicate",
                             "commit": "wip0", "rounds": 3, "title": KIT_ORDER})
    al_loop.tick(deps=d, no_push=True)
    assert not list(outbox.iterdir())  # a partial lane run does not close it
    assert [o["id"] for o in al_loop.session_orders(root)] == [oid]
    rec = al_loop.session_done(root, oid, "abc1234", clock=lambda: 1_790_000_000.0)
    assert rec["state"] == "merged" and rec["session_done"] and rec["commit"] == "abc1234"
    assert al_loop.session_orders(root) == []
    again = al_loop.session_done(root, oid, "other", clock=lambda: 1_790_000_100.0)
    assert again["commit"] == "abc1234"  # idempotent: the first record stands
    al_loop.tick(deps=d, no_push=True)
    calls = [c for c in sp.calls if c.get("note") == KIT_ORDER]
    assert len(calls) == 1 and "abc1234" in calls[0]["prompt"]
    assert len(list(outbox.glob("*-re-k-from-MAIN-ORDER-to-AL-kit-v10.md"))) == 1
    al_loop.tick(deps=d, no_push=True)
    assert len([c for c in sp.calls if c.get("note") == KIT_ORDER]) == 1


def _settle_by_hand(d, root, name, verdict="ANSWER"):
    """A session answered the note itself: the kit seen ledger records it, but
    no `session-done` item record was written (2026-10-12: N9138b6 / N97fbd7)."""
    dec = d.inbox.classify(name, "AL", "# From MAIN - ORDER\n")
    d.inbox.mark_seen(root, name, dec, verdict=verdict)


@pytest.mark.git
def test_session_order_settled_in_seen_ledger_leaves_checklist(tmp_path):
    root, outbox, sp, d = _session_order(tmp_path)
    al_loop.tick(deps=d, no_push=True)
    oid = al_loop.order_id(KIT_ORDER)
    assert [o["id"] for o in al_loop.session_orders(root)] == [oid]
    _settle_by_hand(d, root, KIT_ORDER)
    _, work, skipped = al_loop.Tick(d).work_list()
    assert oid not in [w["id"] for w in work] + [h["id"] for h in skipped]
    assert al_loop.session_orders(root) == []
    doc = al_loop.tick(deps=d, no_push=True)
    assert oid not in [r["id"] for r in doc["checklist"]]
    assert not [c for c in sp.calls if c.get("note") == KIT_ORDER]  # never re-answered


def test_lane_order_settled_in_seen_ledger_is_not_dispatched(tmp_path):
    # sibling: a queued (non-session) order answered by hand, no item record,
    # must not be re-run as a lane item
    root, inbox, outbox = _inbox_root(tmp_path, roadmap=ROADMAP)
    d = deps(root)
    name = "o-from-MAIN-ORDER-to-AL-x.md"
    al_loop.Tick(d).queue_order(al_loop.order_id(name), name, "# From MAIN - ORDER\nwork\n")
    oid = al_loop.order_id(name)
    assert oid in [w["id"] for w in al_loop.Tick(d).work_list()[1]]
    _settle_by_hand(d, root, name)
    _, work, skipped = al_loop.Tick(d).work_list()
    assert oid not in [w["id"] for w in work] + [h["id"] for h in skipped]


@pytest.mark.git
def test_session_cli_lists_and_refuses_unknown_id(tmp_path, monkeypatch, capsys):
    root, outbox, sp, d = _session_order(tmp_path)
    al_loop.tick(deps=d, no_push=True)
    monkeypatch.setattr(al_loop, "ROOT", root)
    oid = al_loop.order_id(KIT_ORDER)
    assert al_loop.main(["session"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(oid + " " + KIT_ORDER) and "needs: ops/fleet_kit/, .claude/" in out
    assert al_loop.main(["session-done", "Nffffff"]) == 2
    assert al_loop.Items(root).get("Nffffff") is None
    assert al_loop.main(["session-done", oid, "--commit", "f00d"]) == 0
    assert al_loop.Items(root).get(oid)["commit"] == "f00d"
    capsys.readouterr()
    assert al_loop.main(["session"]) == 0
    assert capsys.readouterr().out.strip() == "none"


# ---------------------------------------------------------------- perf audit 2.10: hooksPath

def _cp(rc, out=""):
    import subprocess
    return subprocess.CompletedProcess(["git"], rc, out, "")


def test_hooks_path_check_ok_when_inside_repo(tmp_path):
    (tmp_path / ".githooks").mkdir()
    git = lambda args, cwd, input=None: _cp(0, ".githooks\n")  # noqa: E731
    assert al_loop.hooks_path_problem(tmp_path, git) is None


def test_hooks_path_check_flags_missing_outside_or_unset(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (tmp_path / "elsewhere").mkdir()
    gone = lambda args, cwd, input=None: _cp(0, ".githooks\n")  # noqa: E731
    assert "does not exist" in al_loop.hooks_path_problem(root, gone)
    outside = lambda args, cwd, input=None: _cp(0, str(tmp_path / "elsewhere") + "\n")  # noqa: E731
    assert "outside" in al_loop.hooks_path_problem(root, outside)
    unset = lambda args, cwd, input=None: _cp(1, "")  # noqa: E731
    assert "unset" in al_loop.hooks_path_problem(root, unset)


def test_tick_logs_a_bad_hooks_path_without_failing(tmp_path):
    root = make_root(tmp_path)

    def git(args, cwd, input=None):
        if args[:2] == ["config", "core.hooksPath"]:
            return _cp(0, "gone-hooks\n")
        return real_git(args, cwd, input)

    doc = al_loop.tick(deps=deps(root, git=git), no_push=True)
    assert doc.get("state") != "busy"
    assert any("hooksPath" in line for line in progress(root)["log"])


@pytest.mark.git
def test_git_worlds_see_no_host_global_or_system_config(tmp_path):
    """Plan 156, TESTS-A-19: a host merge.ff=only / signing / hooksPath cannot
    reach a tmp_path git world; only the repo's own and command-line config."""
    root, wt = git_world(tmp_path)
    origins = {line.split("\t", 1)[0].split(":", 1)[0]
               for line in git(root, "config", "--list", "--show-scope").splitlines()}
    assert origins <= {"local", "worktree", "command"}, origins
    assert real_git(["config", "--global", "--list"], root).stdout == ""
    assert os.environ["GIT_CONFIG_NOSYSTEM"] == "1"
