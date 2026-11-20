"""TC-WORN-WIRE (decision 0052): POST /api/wear, the worn_gear switch and
Clear run history; TC-EVAL-CLEAR-API (folded in): LastEval.clear().

Synthetic item texts only; no clipboard, no network, no game process;
every file under tmp_path. The server binds an ephemeral port.
"""

import ast
import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import http as al_http
from server.al.core import WORN_NOTHING, WORN_OFF, Core
from server.al.http import serve
from server.al.theorycraft import cardparts, codec
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import item as item_parser
from server.al.theorycraft import worngear
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, RARE_GLOVES

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "w" * 48
WAIT_S = 10.0


def _ring(name, base, life):
    return ("Item Class: Rings\nRarity: Rare\n%s\n%s\n--------\n"
            "Item Level: 70\n--------\n+%d to maximum Life\n" % (name, base, life))


RING_A = _ring("Alpha Loop", "Ruby Ring", 40)
RING_B = _ring("Beta Loop", "Sapphire Ring", 90)


# private copy of the test_tc_delta fake calc (a test file never imports another)
DPS_PER = {"adds # to # lightning damage to attacks": 2.0, "#% increased attack speed": 3.0}
EHP_PER = {"+# to maximum life": 10.0, "+#% to cold resistance": 20.0,
           "+#% to lightning resistance": 20.0, "+#% to fire resistance": 20.0}


class FakeCalc:
    """dps / ehp linear in the gear's summed stats; with `gate`, every call
    first waits for it to be set. Records each call's swaps."""

    def __init__(self, gate=None):
        self.gate = gate
        self.calls = []
        self.lock = threading.Lock()
        self.entered = threading.Event()

    def __call__(self, build, swaps):
        with self.lock:
            self.calls.append(dict(swaps))
        self.entered.set()
        if self.gate is not None:
            assert self.gate.wait(WAIT_S), "the test never opened the gate"
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


@pytest.fixture(autouse=True)
def fresh_parts():
    cardparts.reset()
    yield
    cardparts.reset()


def _core(tmp_path, config=None):
    log = tmp_path / "Client.txt"
    if not log.exists():
        log.write_bytes(b"")
    cfg = tmp_path / "local.json"
    if config is not None:
        cfg.write_text(json.dumps(config), encoding="ascii")
    return Core(runtime=tmp_path / "rt", log_path=str(log), tail=False, poll_s=0.05,
                config_path=cfg)


class _Server:
    def __init__(self, core):
        self.core = core
        self.srv = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                         tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True).start()

    def post(self, path, body, token=TOKEN):
        conn = http.client.HTTPConnection("127.0.0.1", self.srv.port, timeout=10)
        raw = json.dumps(body).encode("ascii")
        headers = {"Host": f"127.0.0.1:{self.srv.port}", "Content-Type": "application/json",
                   "Content-Length": str(len(raw))}
        if token:
            headers["X-AL-Token"] = token
        conn.request("POST", path, body=raw, headers=headers)
        r = conn.getresponse()
        out = (r.status, json.loads(r.read() or b"null"))
        conn.close()
        return out

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.core.close()


def _bases(card):
    return [(c.get("equipped") or {}).get("base") for c in card.get("comparisons") or []]


def _worn_file(tmp_path):
    return worngear.default_path(tmp_path / "rt")


# -- POST /api/wear ---------------------------------------------------------

def test_wear_then_eval_names_the_worn_ring_without_a_build(tmp_path):
    srv = _Server(_core(tmp_path))
    try:
        assert srv.core.builds.build is None
        status, doc = srv.post("/api/wear", {"item": RING_A})
        assert status == 200 and doc["worn"]["ok"] is True
        assert doc["worn"]["slot"] in ("Ring 1", "Ring 2")
        status, card = srv.post("/api/eval", {"item": RING_B})
        assert status == 200 and card["ok"] is True
        assert "Ruby Ring" in _bases(card)
        assert "Ruby Ring" in _bases(srv.core.state.snapshot()["eval"])
    finally:
        srv.close()


def test_wear_files_the_last_checked_item(tmp_path):
    srv = _Server(_core(tmp_path))
    try:
        status, doc = srv.post("/api/wear", {})
        assert status == 200 and doc["worn"] == {"ok": False, "slot": None,
                                                 "error": WORN_NOTHING}
        srv.post("/api/eval", {"item": RING_A})
        status, doc = srv.post("/api/wear", {"slot": "ring 2"})
        assert status == 200 and doc["worn"] == {"ok": True, "slot": "Ring 2", "error": None}
        assert srv.core.worn.entry(None, "Ring 2")["base"] == "Ruby Ring"
        # not gear / a blank text / a bad slot: nothing filed
        assert srv.post("/api/wear", {"item": "just chat"})[1]["worn"]["ok"] is False
        assert srv.post("/api/wear", {"item": "  "})[1]["worn"]["ok"] is False
        assert srv.post("/api/wear", {"slot": 5})[0] == 400
        assert srv.post("/api/wear", {"item": 5})[0] == 400
        assert list(srv.core.worn.worn(None)) == ["Ring 2"]
    finally:
        srv.close()


def test_wear_needs_the_token_and_reads_no_clipboard(tmp_path):
    srv = _Server(_core(tmp_path))
    try:
        for token in (None, "wrong"):
            status, doc = srv.post("/api/wear", {"item": RING_A}, token=token)
            assert status == 401 and doc == {"error": "token required"}
        assert not _worn_file(tmp_path).exists()
    finally:
        srv.close()
    # nothing on the wear path names the clipboard outside its doc text
    # (decision 0003: the one per-press read stays in app/main.js)
    for path, cls, fn in ((ROOT / "server" / "al" / "http.py", "Handler", "_wear"),
                          (ROOT / "server" / "al" / "core.py", "Core", "wear"),
                          (ROOT / "server" / "al" / "theorycraft" / "live.py", "LastEval",
                           "wear_last")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
        func = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == fn)
        names = [n.id for n in ast.walk(func) if isinstance(n, ast.Name)]
        names += [n.attr for n in ast.walk(func) if isinstance(n, ast.Attribute)]
        names += [a.name for n in ast.walk(func) if isinstance(n, (ast.Import, ast.ImportFrom))
                  for a in n.names]
        assert not [n for n in names if "clip" in n.lower() or "paste" in n.lower()], fn
    assert al_http.POST_ROUTES["/api/wear"] is al_http.Handler._wear


def test_a_restart_keeps_the_worn_set(tmp_path):
    core = _core(tmp_path)
    try:
        assert core.wear(text=RING_A)["ok"]
    finally:
        core.close()
    core = _core(tmp_path)
    try:
        assert core.worn.entry(None, "Ring 1")["base"] == "Ruby Ring"
        card = core.eval_press(RING_B)
        assert card["ok"] and "Ruby Ring" in _bases(card)
    finally:
        core.close()


def test_clear_run_history_empties_the_worn_set(tmp_path):
    core = _core(tmp_path)
    try:
        assert core.wear(text=RING_A)["ok"] and core.wear(text=RING_B)["ok"]
        assert core.worn.characters()
        core.set_history(clear=True)
        assert core.worn.characters() == [] and core.worn.worn(None) == {}
        doc = json.loads(_worn_file(tmp_path).read_text(encoding="utf-8"))
        assert doc["characters"] == {}
        assert not Path(str(_worn_file(tmp_path)) + ".bak").exists()
        card = core.eval_press(RING_B)
        assert "Ruby Ring" not in _bases(card)
    finally:
        core.close()


def test_worn_gear_false_stores_nothing(tmp_path):
    srv = _Server(_core(tmp_path, {"worn_gear": False}))
    try:
        assert srv.core.worn_enabled() is False
        status, doc = srv.post("/api/wear", {"item": RING_A})
        assert status == 200 and doc["worn"] == {"ok": False, "slot": None, "error": WORN_OFF}
        srv.post("/api/eval", {"item": RING_A})
        assert srv.post("/api/wear", {})[1]["worn"]["error"] == WORN_OFF
        assert not _worn_file(tmp_path).exists()
        assert srv.core.worn.characters() == []
    finally:
        srv.close()


def test_switch_off_ignores_a_stored_set_and_on_is_the_default(tmp_path):
    core = _core(tmp_path)
    try:
        assert core.worn_enabled() is True  # no key: on
        assert core.wear(text=RING_A)["ok"]
        assert "Ruby Ring" in _bases(core.eval_press(RING_B))
        core._write_config({"worn_gear": False})
        assert "Ruby Ring" not in _bases(core.eval_press(RING_B))
        assert core.worn.entry(None, "Ring 1") is not None  # kept until Clear
    finally:
        core.close()


# -- TC-EVAL-CLEAR-API -------------------------------------------------------

def test_core_touches_no_last_eval_private_field():
    tree = ast.parse((ROOT / "server" / "al" / "core.py").read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr in ("_gen", "_input"):
            hits.append((node.lineno, node.attr))
        base = node.value
        if (node.attr.startswith("_") and isinstance(base, ast.Attribute)
                and base.attr == "last_eval"):
            hits.append((node.lineno, node.attr))
    assert hits == [], f"core.py reaches into LastEval: {hits}"


@pytest.fixture
def staged(tmp_path):
    core = _core(tmp_path)
    core.builds.load_code(codec.encode(EVAL_BUILD_XML))
    yield core
    core.close()


def test_clear_cancels_a_running_press_and_publishes_no_stale_stage(staged):
    gate = threading.Event()
    staged.tc_calc = FakeCalc(gate=gate)
    rec = Recorder(staged.state)
    try:
        first = staged.eval_press(RARE_GLOVES)
        assert first["ok"]
        assert staged.tc_calc.entered.wait(WAIT_S)  # the worker is mid calc call
        card = {"ok": False, "error": "cleared"}
        old_gen = len(rec.cards)
        gen = staged.last_eval.clear(card=card, result={"ok": False})
        assert staged.last_eval.current(gen)
    finally:
        gate.set()
    assert staged.last_eval.wait(WAIT_S)
    assert rec.cards[old_gen:] == [card]  # nothing after the clear card
    assert staged.state.snapshot()["eval"]["error"] == "cleared"
    assert staged.last_eval.last_result == {"ok": False}
    assert staged.last_eval.rerun() is None  # no item left to re-score


def test_clear_drops_a_queued_press_without_a_calc_call(staged):
    gate = threading.Event()
    staged.tc_calc = FakeCalc(gate=gate)
    rec = Recorder(staged.state)
    try:
        staged.eval_press(RARE_GLOVES)
        assert staged.tc_calc.entered.wait(WAIT_S)
        staged.eval_press(ADVANCED_RING)  # its stages wait in the queue
        n = len(rec.cards)
        staged.last_eval.clear()  # no card: the generation moves on only
    finally:
        gate.set()
    assert staged.last_eval.wait(WAIT_S)
    assert rec.cards[n:] == []
    ring = item_parser.parse(ADVANCED_RING)
    for swaps in staged.tc_calc.calls:
        for text in swaps.values():
            assert item_parser.parse(text).base != ring.base


def test_blank_press_goes_through_clear(staged, monkeypatch):
    seen = []
    real = staged.last_eval.clear
    monkeypatch.setattr(staged.last_eval, "clear",
                        lambda **kw: seen.append(kw) or real(**kw))
    doc = staged.eval_press("")
    assert doc["error"] == "empty clipboard" and len(seen) == 1
    assert seen[0]["card"]["error"] == "empty clipboard"
    assert staged.state.snapshot()["eval"]["error"] == "empty clipboard"
