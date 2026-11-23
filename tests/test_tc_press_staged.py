"""TC-PRESS-STAGED-LIVE: the item check is published in stages.

The core's LastEval publishes the stat-weight card inside the press and the
Path of Building stages (DPS / EHP, then the per-mod rows) from one daemon
worker, each an update that keeps the card's time; a newer press cancels
the older press's pending stages (decision 0024 amendment 2026-11-19).
A fake calc that sleeps or blocks stands in for Path of Building; tmp
runtime and an ephemeral port only; nothing reads the clipboard.
"""

import http.client
import json
import os
import threading
import time
from pathlib import Path

import pytest

from server.al.core import Core
from server.al.http import serve
from server.al.state import CALC_CACHED_TEXT as STATE_CACHED_TEXT
from server.al.state import CALC_NOTICE_TEXT as STATE_NOTICE_TEXT
from server.al.state import eval_card_text
from server.al.theorycraft import cardparts
from server.al.theorycraft import codec
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import item as item_parser
from server.al.theorycraft import live
from server.al.theorycraft.cardparts import stage as stage_part
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, RARE_GLOVES

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "s" * 48
WAIT_S = 30.0
# budget B15: the first card under 0.5 s, the press reply under 1 s
FIRST_CARD_S = 0.5
REPLY_S = 1.0

# private copy of the test_tc_delta fake calc (a test file never imports another)
DPS_PER = {"adds # to # lightning damage to attacks": 2.0, "#% increased attack speed": 3.0}
EHP_PER = {"+# to maximum life": 10.0, "+#% to cold resistance": 20.0,
           "+#% to lightning resistance": 20.0, "+#% to fire resistance": 20.0}


class FakeCalc:
    """dps / ehp as a linear function of the gear's summed stats; each call
    sleeps `sleep_s` and, with `gate`, first waits for it to be set."""

    def __init__(self, sleep_s=0.0, gate=None, fail_after=None):
        self.sleep_s = sleep_s
        self.gate = gate
        self.fail_after = fail_after
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, build, swaps):
        with self.lock:
            self.calls.append(dict(swaps))
            n = len(self.calls)
        if self.gate is not None:
            assert self.gate.wait(WAIT_S), "the test never opened the gate"
        if self.sleep_s:
            time.sleep(self.sleep_s)
        if self.fail_after is not None and n > self.fail_after:
            raise OSError("calc process killed")
        gear = {slot: it.text for slot, it in build.gear.items()}
        gear.update(swaps)
        dps, ehp = 100.0, 1000.0
        for text in gear.values():
            for key, value in tc_evaluate.stats_of(item_parser.parse(text)).items():
                dps += DPS_PER.get(key.lower(), 0) * value
                ehp += EHP_PER.get(key.lower(), 0) * value
        return {"dps": dps, "ehp": ehp}


class Recorder:
    """Wraps state.set_eval: every published card, in order."""

    def __init__(self, state):
        self.cards = []
        self._set = state.set_eval
        state.set_eval = self

    def __call__(self, card, keep_time=False, at=None):
        self._set(card, keep_time=keep_time, at=at)
        self.cards.append(dict(card))


@pytest.fixture
def core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    c.builds.load_code(codec.encode(EVAL_BUILD_XML))
    yield c
    c.close()


def _stage(card):
    return (card.get("parts") or {}).get(stage_part.NAME)


# -- the stage part ----------------------------------------------------------

def _cached_card(notice=None, pending=True):
    return {"ok": True, "verdict": "upgrade", "slot": "Gloves", "score_delta": 5,
            "item": {"name": "Grim Clutch"},
            "calc": {"source": "pob_cached", "notice": notice}, "comparisons": [],
            "parts": {"stage": {"stage": "weights"}} if pending else {}}


def test_warm_cache_first_stage_says_numbers_are_coming(core):
    """TCS-1: a pending card scored with this build's cached PoB weights
    never says the calc is off."""
    core.tc_calc = FakeCalc()
    core.eval_press(RARE_GLOVES)  # measures this build's PoB weights
    assert core.last_eval.wait(WAIT_S)
    gate = threading.Event()
    core.tc_calc = FakeCalc(gate=gate)
    try:
        first = core.eval_press(RARE_GLOVES)
        assert first["calc"] == {"source": "pob_cached", "notice": None}
        text = core.state.snapshot()["eval"]["text"]
        assert "calc is off" not in text["calc"] and "coming" in text["calc"]
        assert text["calc"] == stage_part.PENDING_CALC
        assert stage_part.PENDING_NOTE in text["notes"]
    finally:
        gate.set()
    assert core.last_eval.wait(WAIT_S)
    assert core.state.snapshot()["eval"]["calc"]["source"] == "pob"


def test_last_stage_keeps_the_calc_sentence():
    done = eval_card_text(_cached_card(pending=False))
    assert done["calc"] == STATE_CACHED_TEXT["off"]  # unchanged by the part
    assert stage_part.PENDING_NOTE not in done["notes"]


@pytest.mark.parametrize("notice", ["off", "failed", "implausible"])
def test_a_notice_keeps_its_own_sentence_while_pending(notice):
    t = eval_card_text(_cached_card(notice=notice))
    assert t["calc"] == STATE_CACHED_TEXT[notice]
    assert t["notes"][0] == stage_part.PENDING_NOTE
    w = eval_card_text(dict(_cached_card(notice=notice),
                            calc={"source": "weights", "notice": notice}))
    assert w["calc"] == STATE_NOTICE_TEXT[notice]


@pytest.mark.parametrize("bad", ["", "   ", None, 5, ["x"]])
def test_a_part_cannot_blank_the_calc_sentence(bad):
    class Probe:
        NAME, ORDER = "probe", 1

        @staticmethod
        def compute(ctx):
            return None

        @staticmethod
        def words(value, card, out):
            out["calc"] = bad
    out = {"calc": "Before.", "notes": [], "word": "Upgrade", "tone": "upgrade",
           "head": "Upgrade +5 vs Gloves", "answers": False}
    cardparts.words({"parts": {"probe": 1}}, out, found=[Probe])
    assert out["calc"] == "Before."
    bare = {"notes": [], "word": "Upgrade", "tone": "upgrade", "head": "Upgrade",
            "answers": False}
    cardparts.words({"parts": {"probe": 1}}, bare, found=[Probe])
    assert "calc" not in bare


def test_stage_part_value_and_note():
    assert stage_part.compute({"stage": {"name": "weights", "pending": True}}) == \
        {"stage": "weights"}
    for ctx in ({"stage": {"name": "mods", "pending": False}}, {"stage": None}, {}, None):
        assert stage_part.compute(ctx) is None
    card = {"ok": True, "verdict": "upgrade", "slot": "Gloves", "score_delta": 5,
            "item": {"name": "Grim Clutch"}, "calc": {"source": "weights", "notice": None},
            "comparisons": [], "parts": {"stage": {"stage": "weights"}}}
    t = eval_card_text(card)
    assert t["notes"][0] == "Path of Building numbers are coming."
    assert t["word"] == "Upgrade" and t["head"].startswith("Upgrade")
    done = eval_card_text(dict(card, parts={}))
    assert stage_part.PENDING_NOTE not in done["notes"]


# -- staged publish ----------------------------------------------------------

def test_later_stages_update_the_card_and_keep_its_time(core):
    rec = Recorder(core.state)
    core.tc_calc = FakeCalc()
    result = core.eval_press(RARE_GLOVES)
    # the press answers with the first stage: the weights, no calc number
    assert result["ok"] and result["calc"]["source"] != "pob"
    assert core.last_eval.wait(WAIT_S)
    cards = rec.cards
    assert [c["calc"]["source"] for c in cards] == ["weights", "pob", "pob"]
    assert [bool(_stage(c)) for c in cards] == [True, True, False]
    snap = core.state.snapshot()["eval"]
    assert snap["calc"] == {"source": "pob", "notice": None}
    assert snap["comparisons"][0]["dps"]["pct"] is not None
    assert snap["upgrade"]["weights"]["source"] == "pob"
    assert stage_part.NAME not in snap["parts"]
    assert stage_part.PENDING_NOTE not in snap["text"]["notes"]


def test_stage_updates_keep_the_press_time_not_the_id(core):
    core.tc_calc = FakeCalc()
    seen = []
    orig = core.state.set_eval

    def spy(card, keep_time=False, at=None):
        orig(card, keep_time=keep_time, at=at)
        e = core.state.eval
        seen.append((e["id"], e["at"]))
    core.state.set_eval = spy
    core.eval_press(RARE_GLOVES)
    assert core.last_eval.wait(WAIT_S)
    assert len(seen) == 3
    assert len({at for _id, at in seen}) == 1, seen
    assert [i for i, _at in seen] == sorted({i for i, _at in seen}), seen


def test_calc_off_publishes_once_with_no_pending_note(core):
    rec = Recorder(core.state)
    result = core.eval_press(RARE_GLOVES)
    assert result["calc"] == {"source": "weights", "notice": "off"}
    assert core.last_eval.wait(WAIT_S)
    assert len(rec.cards) == 1 and _stage(rec.cards[0]) is None
    assert core.last_eval._worker is None  # no worker without the calc


def test_not_an_item_has_no_later_stage(core):
    rec = Recorder(core.state)
    core.tc_calc = FakeCalc()
    result = core.eval_press("Just some chat text, not an item.")
    assert result["error"] == "not an item"
    assert core.last_eval.wait(WAIT_S)
    assert len(rec.cards) == 1 and _stage(rec.cards[0]) is None
    assert core.tc_calc.calls == []


def test_blank_press_is_empty_clipboard_with_no_later_stage(core):
    """OVL-COPY-FIRST (F-054): a blank press is the "empty clipboard" card,
    one publish, no stage and no calc call."""
    rec = Recorder(core.state)
    core.tc_calc = FakeCalc()
    result = core.eval_press("")
    assert result["error"] == "empty clipboard"
    assert core.last_eval.wait(WAIT_S)
    assert len(rec.cards) == 1 and _stage(rec.cards[0]) is None
    assert core.tc_calc.calls == []


@pytest.mark.parametrize("fail_after", [0, 3])
def test_a_killed_calc_leaves_the_weights_card(core, fail_after):
    """0: the calc dies on its first call (stage "pob"); 3: after the DPS /
    EHP stage, during the per-mod probes (stage "mods")."""
    rec = Recorder(core.state)
    core.tc_calc = FakeCalc(fail_after=fail_after)
    core.eval_press(RARE_GLOVES)
    assert core.last_eval.wait(WAIT_S)
    last = core.state.snapshot()["eval"]
    assert last["ok"]
    assert last["calc"]["notice"] == "failed"
    assert last["calc"]["source"] in ("weights", "pob_cached")
    assert stage_part.NAME not in last["parts"]
    assert _stage(rec.cards[0])  # the first card said numbers were coming


def test_an_unexpected_stage_error_drops_the_pending_note(core, monkeypatch):
    rec = Recorder(core.state)
    core.tc_calc = FakeCalc()
    real = tc_evaluate.stages

    def broken(*a, **kw):
        gen = real(*a, **kw)
        yield next(gen)
        raise RuntimeError("bug in a later stage")
    monkeypatch.setattr(live.tc_evaluate, "stages", broken)
    core.eval_press(RARE_GLOVES)
    assert core.last_eval.wait(WAIT_S)
    assert len(rec.cards) == 2
    assert _stage(rec.cards[0]) and _stage(rec.cards[1]) is None
    assert rec.cards[1]["calc"]["notice"] == "failed"


# -- one press in flight -----------------------------------------------------

def test_a_second_press_cancels_the_first_press_stages(core):
    gate = threading.Event()
    calc = FakeCalc(gate=gate)
    core.tc_calc = calc
    rec = Recorder(core.state)
    core.eval_press(RARE_GLOVES)  # its stage "pob" now waits on the gate
    deadline = time.monotonic() + WAIT_S
    while not calc.calls and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calc.calls, "the first press's later stage never started"
    second = core.eval_press(ADVANCED_RING)
    assert second["ok"]
    n_first = len(rec.cards)
    gate.set()
    assert core.last_eval.wait(WAIT_S)
    names = [c["item"]["name"] for c in rec.cards]
    # the first press published only its first card; nothing stale after
    assert names[0] == "Grim Clutch" and names.count("Grim Clutch") == 1, names
    assert all(n != "Grim Clutch" for n in names[1:]), names
    assert n_first == 2 and len(rec.cards) > n_first
    last = core.state.snapshot()["eval"]
    assert last["item"]["name"] == rec.cards[-1]["item"]["name"]
    assert last["calc"]["source"] == "pob" and stage_part.NAME not in last["parts"]
    # the first press's generator was closed: only its stage "pob" call ran
    # before the cancel, no per-mod probe of the gloves
    gloves = [c for c in calc.calls if "Gloves" in c]
    assert len(gloves) <= 1, gloves


def test_a_rescore_cancels_the_pending_stages(core):
    gate = threading.Event()
    calc = FakeCalc(gate=gate)
    core.tc_calc = calc
    rec = Recorder(core.state)
    core.eval_press(RARE_GLOVES)
    deadline = time.monotonic() + WAIT_S
    while not calc.calls and time.monotonic() < deadline:
        time.sleep(0.01)
    core.tc_calc = FakeCalc()
    core.last_eval.rerun()  # a weights change: a new generation
    gate.set()
    assert core.last_eval.wait(WAIT_S)
    last = core.state.snapshot()["eval"]
    assert last["calc"]["source"] == "pob" and stage_part.NAME not in last["parts"]
    assert rec.cards[-1]["calc"]["source"] == "pob"


def test_close_joins_the_worker_and_publishes_nothing_after(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    c.builds.load_code(codec.encode(EVAL_BUILD_XML))
    gate = threading.Event()
    c.tc_calc = FakeCalc(gate=gate)
    rec = Recorder(c.state)
    c.eval_press(RARE_GLOVES)
    worker = c.last_eval._worker
    assert worker is not None and worker.is_alive()
    timer = threading.Timer(0.2, gate.set)  # the calc call in flight ends
    timer.start()
    try:
        c.close()
    finally:
        timer.cancel()
        gate.set()
    assert not worker.is_alive()
    assert len(rec.cards) == 1  # no stage after close
    assert c.last_eval.close() is True  # idempotent


def test_a_lasteval_without_staged_runs_inline():
    class Builds:
        build = None

    class Weights:
        def get(self):
            return None

    class St:
        def __init__(self):
            self.cards = []

        def set_eval(self, card, keep_time=False, at=None):
            self.cards.append(card)

    st = St()
    last = live.LastEval(Builds(), Weights(), st, calc=lambda: FakeCalc())
    assert last.staged is False
    last.run(RARE_GLOVES)
    assert len(st.cards) == 1 and last._worker is None
    assert last.close() is True


# -- budget B15 over HTTP ------------------------------------------------------

def _req(port, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=WAIT_S)
    h = {"Host": f"127.0.0.1:{port}", "X-AL-Token": TOKEN}
    data = None
    if body is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(body).encode("ascii")
    conn.request(method, path, body=data, headers=h)
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    return r.status, json.loads(raw)


@pytest.mark.server
@pytest.mark.timing
def test_first_card_and_reply_within_budget_with_a_slow_calc(core):
    core.tc_calc = FakeCalc(sleep_s=0.6)  # every PoB call is slower than B15
    srv = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        _status, before = _req(srv.port, "GET", "/api/state")
        assert before.get("eval") is None
        seen = {}
        stop = threading.Event()
        t0 = time.perf_counter()

        def watch():
            while not stop.is_set():
                _s, snap = _req(srv.port, "GET", "/api/state")
                if snap.get("eval"):
                    seen["t"] = time.perf_counter() - t0
                    seen["card"] = snap["eval"]
                    return
                time.sleep(0.01)
        w = threading.Thread(target=watch, daemon=True)
        w.start()
        status, result = _req(srv.port, "POST", "/api/eval", {"item": RARE_GLOVES})
        took = time.perf_counter() - t0
        w.join(WAIT_S)
        stop.set()
        assert status == 200 and result["ok"]
        assert result["calc"]["source"] != "pob"
        assert seen, "no state frame carried the card"
        assert seen["card"]["item"]["name"] == "Grim Clutch"
        assert _stage(seen["card"]), "the first card does not say numbers are coming"
        print(f"\nTC-PRESS-STAGED-LIVE first card {seen['t']:.3f} s, reply {took:.3f} s")
        if os.environ.get("AL_CI") != "1":  # decision 0080: budgets skip in CI
            assert seen["t"] < FIRST_CARD_S, seen["t"]
            assert took < REPLY_S, took
        # GATE-HOLD: the budgets above are measured; the rest of the slow
        # calc's calls need not sleep (about 4 s of the serial phase) for
        # the stages to prove they arrive by themselves
        core.tc_calc.sleep_s = 0.0
        # the Path of Building stages arrive by themselves, same press time
        assert core.last_eval.wait(WAIT_S * 2)
        _s, snap = _req(srv.port, "GET", "/api/state")
        assert snap["eval"]["calc"]["source"] == "pob"
        assert snap["eval"]["at"] == seen["card"]["at"]
        assert snap["eval"]["id"] > seen["card"]["id"]
    finally:
        srv.stop()
