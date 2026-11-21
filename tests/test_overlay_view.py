"""OVL-CARD-SLOT (F-118): the overlay view seam (server/al/overlayview.py).

- the card-slot holder order: the press card, then the sample, then the
  zone moment card (a live press card always wins; the sample shows only
  while the slot is free; OVL-ZONE-CARD's moment card comes last);
- the 10 s sample card shows, leaves by itself and never enters the recent
  events, the item check, the price check or run history;
- POST /api/overlay-sample needs the token;
- every card line fits the 34-character clip;
- the snapshot card is the old overlay_card() result for every eval /
  price fixture (the press card is unchanged);
- the store round trip drops unknown keys and survives a broken file.

No game file is read and nothing is sent; the server binds port 0.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import jsonfile, overlayview
from server.al.core import Core
from server.al.http import serve
from server.al.overlayview import CARD_HOLDERS, SAMPLE_S, OverlayView
from server.al.state import SessionState, overlay_card
from server.al.text.common import CARD_LINE

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "o" * 48
T0 = 50000.0


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


def _state(t=T0):
    clock = Clock(t)
    return SessionState(clock=clock), clock


# -- fixtures (invented items; the card text comes from server/al/text) -----

def _ev(**kw):
    ev = {"ok": True, "item": {"name": "Grim Grip", "base": "Ringmail Gauntlets"}}
    ev.update(kw)
    return ev


def _comp(verdict, delta, slot="Gloves"):
    return {"slot": slot, "verdict": verdict, "score_delta": delta,
            "equipped": {"name": "Old Grip"},
            "stats": [{"key": "+# to maximum Life", "delta": 30, "weighted": True,
                       "score_delta": delta}]}


EVALS = [
    _ev(verdict="upgrade", slot="Gloves", score_delta=4.5,
        comparisons=[_comp("upgrade", 4.5)]),
    _ev(verdict="sidegrade", slot="Gloves", score_delta=0.2,
        comparisons=[_comp("sidegrade", 0.2)]),
    _ev(verdict="downgrade", slot="Gloves", score_delta=-3,
        comparisons=[_comp("downgrade", -3)]),
    _ev(ok=False, error="no build loaded"),
    _ev(ok=False, error="not an item"),
    _ev(waystone={"tier": 15, "build_loaded": True,
                  "risky": [{"label": "Monsters deal extra Fire damage", "short": "Fire"}]}),
    _ev(waystone={"tier": 3, "unidentified": True}),
]


def _price(**kw):
    p = {"item": {"name": "A Very Long Unique Item Name Of Doom"}}
    p.update(kw)
    return p


PRICES = [
    _price(status="waiting", wait_s=7),
    _price(status="searching"),
    _price(status="done", count=12, listings=[{"amount": 1, "currency": "divine"}]),
    _price(status="done", listings=[]),
    _price(status="link", league="Standard"),
    _price(status="link", league="Standard",
           ninja={"value": 3.5, "unit": "chaos", "league": "Standard", "listings": 40}),
    _price(status="off"),
    _price(status="error", error="no league"),
]


# -- the holder table ---------------------------------------------------------

def test_holder_order_is_press_then_sample_then_moment():
    # press first (design review D-2 of OVL-CARD-SLOT), then the sample;
    # the trade card is built on the overlay page between sample and
    # moment (render_gate.js), then the zone moment card (OVL-ZONE-CARD)
    assert [h["kind"] for h in CARD_HOLDERS] == ["press", "sample", "moment"]
    for h in CARD_HOLDERS:
        assert isinstance(h["life_s"], (int, float)) and h["life_s"] > 0, h
        exempt, twin = h.get("exempt"), h.get("twin")
        assert (isinstance(exempt, str) and exempt.strip()) or twin, h
    assert CARD_HOLDERS[1]["life_s"] == SAMPLE_S == 10
    moment = CARD_HOLDERS[2]
    assert moment["life_s"] == overlayview.MOMENT_CARD_S == 12
    assert moment["cards"] == ("zone",) and moment["twin"] == ("zone-guide",)


def test_a_press_or_the_sample_beats_the_moment_card():
    st, clock = _state()
    st.overlay.moment = {"at": T0, "gen": st._zone_gen, "head": "Zone short",
                         "line2": "Next: Elsewhere", "line3": ""}
    assert st.snapshot()["card"]["kind"] == "zone"
    clock.t = T0 + 1
    assert st.set_overlay_sample()["kind"] == "sample"
    assert st.overlay.moment is None  # dropped, never returns
    clock.t = T0 + SAMPLE_S + 2
    assert st.snapshot()["card"] is None
    st2, clock2 = _state()
    st2.set_eval(EVALS[0], at=T0)
    st2.overlay.moment = {"at": T0 + 1, "gen": st2._zone_gen, "head": "Zone short",
                          "line2": "", "line3": ""}
    clock2.t = T0 + 1
    assert st2.snapshot()["card"]["kind"] == "eval"
    assert st2.overlay.moment is None


def test_a_live_press_card_beats_the_sample():
    st, clock = _state()
    st.set_eval(EVALS[0], at=T0)
    press = st.snapshot()["card"]
    assert press["kind"] == "eval"
    clock.t = T0 + 1
    assert st.set_overlay_sample() == press  # the press card keeps the slot
    clock.t = T0 + 5
    assert st.snapshot()["card"] == press
    # a press during a sample takes the slot at once
    st2, clock2 = _state()
    assert st2.set_overlay_sample()["kind"] == "sample"
    clock2.t = T0 + 3
    st2.set_eval(EVALS[1], at=T0 + 3)
    assert st2.snapshot()["card"]["kind"] == "eval"


def test_the_sample_shows_when_the_slot_is_free():
    st, clock = _state()
    st.set_eval(EVALS[0], at=T0)
    # the press card has left (20 s): the slot is free, the sample shows
    clock.t = T0 + 30
    card = st.set_overlay_sample()
    assert card["kind"] == "sample"
    clock.t = T0 + 30 + SAMPLE_S - 0.01
    assert st.snapshot()["card"] == card
    clock.t = T0 + 30 + SAMPLE_S
    assert st.snapshot()["card"] is None


def test_sample_shows_10_s_and_leaves_by_itself():
    st, clock = _state()
    v0 = st.version
    card = st.set_overlay_sample()
    assert st.version == v0 + 1  # pushed at once
    assert card == {"kind": "sample", "head": "Sample card",
                    "line2": "This is how a card looks", "line3": "It leaves in 10 s",
                    "verdict": "note", "expires_at": T0 + SAMPLE_S}
    clock.t = T0 + SAMPLE_S - 0.01
    assert st.snapshot()["card"] == card
    clock.t = T0 + SAMPLE_S
    assert st.snapshot()["card"] is None
    assert st.overlay.sample_at is None
    # a second click starts the 10 s again
    clock.t = T0 + 100
    assert st.set_overlay_sample()["expires_at"] == T0 + 100 + SAMPLE_S


def test_sample_enters_no_history():
    st, clock = _state()
    before = st.snapshot()
    st.set_overlay_sample()
    after = st.snapshot()
    assert after["card"]["kind"] == "sample"
    for key in ("recent_events", "eval", "price", "run_history", "events_seen",
                "deaths", "level_ups", "session_summary", "price_watch", "upgrades",
                "trade_requests"):
        assert after[key] == before[key], key
    assert st.eval is None and st.price is None and not st.recent_events


def test_core_sample_writes_no_store(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    try:
        card = core.show_overlay_sample()
        assert card["kind"] == "sample"
        core.tick_guide()
        snap = core.state.snapshot()
        assert snap["card"]["kind"] == "sample"
        assert snap["eval"] is None and snap["price"] is None
        assert not snap["recent_events"]
        rt = tmp_path / "rt"
        names = {p.name for p in rt.iterdir()} if rt.is_dir() else set()
        for store in ("run_history.json", "price_watch.json", "zone_visits.json",
                      overlayview.FILE_NAME):
            assert store not in names, store
    finally:
        core.close()


# -- the card text ------------------------------------------------------------

def test_card_lines_fit_the_clip():
    st, _ = _state()
    card = st.set_overlay_sample()
    for key in ("head", "line2", "line3"):
        assert isinstance(card[key], str) and card[key].isascii(), key
        assert 0 < len(card[key]) <= CARD_LINE == 34, (key, card[key])


def test_snapshot_card_unchanged_for_every_fixture():
    cases = [(ev, None) for ev in EVALS] + [(None, pr) for pr in PRICES]
    cases += [(ev, pr) for ev in EVALS for pr in PRICES]
    cases += [(EVALS[0], dict(PRICES[2], at=T0 - 5))]  # different presses
    for ev, pr in cases:
        for dt in (0.0, 10.0, 19.9, 20.0, 40.0):
            st, clock = _state(T0 + dt)
            st.eval = dict(ev, id=1, at=T0) if ev is not None else None
            if pr is not None:
                st.price = dict({"at": T0, "updated_at": T0}, **pr, id=1)
            snap = st.snapshot()
            want = overlay_card(st.eval, st.price, T0 + dt, snap["build_alert"])
            assert snap["card"] == want, (ev, pr, dt)
            assert snap["overlay"] == {"guide_short": "", "calm_at": None}


# -- the feed hooks -----------------------------------------------------------

def test_on_press_only_for_a_real_press(monkeypatch):
    st, _ = _state()
    seen = []
    monkeypatch.setattr(st.overlay, "on_press", lambda now: seen.append(now))
    st.set_eval(EVALS[0], at=T0)
    st.set_eval(EVALS[1], keep_time=True)  # a re-score
    st.set_eval(EVALS[2])
    assert seen == [T0, T0]


def test_on_event_once_per_event(monkeypatch):
    st, _ = _state()
    seen = []
    monkeypatch.setattr(st.overlay, "on_event",
                        lambda ev, state, now: seen.append((ev["type"], state)) or False)
    st.apply({"type": "level_up", "name": "Quietfox", "char_class": "Monk", "level": 2,
              "recv_ts": T0})
    st.apply({"type": "afk_changed", "on": True, "recv_ts": T0})
    assert seen == [("level_up", st), ("afk_changed", st)]


# -- POST /api/overlay-sample --------------------------------------------------

@pytest.fixture
def srv(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def _post(server, headers, body=b"{}"):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": f"127.0.0.1:{server.port}", "Content-Type": "application/json"}
    h.update(headers)
    conn.request("POST", "/api/overlay-sample", body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, data


def test_post_overlay_sample_needs_the_token(srv):
    for h in ({}, {"X-AL-Token": "wrong"}, {"Authorization": "Bearer wrong"}):
        status, data = _post(srv, h)
        assert status == 401 and json.loads(data) == {"error": "token required"}
    assert srv.core.state.snapshot()["card"] is None
    status, data = _post(srv, {"X-AL-Token": TOKEN})
    assert status == 200
    card = json.loads(data)["card"]
    assert card["kind"] == "sample" and card["head"] == "Sample card"
    assert srv.core.state.snapshot()["card"]["kind"] == "sample"
    # an empty body is an empty object; a non-object is refused
    assert _post(srv, {"X-AL-Token": TOKEN}, body=b"")[0] == 200
    assert _post(srv, {"X-AL-Token": TOKEN}, body=b"[]")[0] == 400


# -- the store ------------------------------------------------------------------

def test_store_round_trip_drops_unknown_keys(monkeypatch):
    v = OverlayView()
    assert v.to_doc() == {"schema": overlayview.SCHEMA}
    assert v.load_doc({"schema": overlayview.SCHEMA, "zzq": 1}) is True
    assert v.to_doc() == {"schema": overlayview.SCHEMA}
    # a key a later package declares survives; anything else is dropped
    monkeypatch.setattr(overlayview, "STORE_KEYS", ("seen",))
    w = OverlayView()
    w.load_doc({"schema": overlayview.SCHEMA, "seen": [1, 2], "other": "x"})
    doc = w.to_doc()
    assert doc == {"schema": overlayview.SCHEMA, "seen": [1, 2]}
    again = OverlayView()
    again.load_doc(json.loads(json.dumps(doc)))
    assert again.to_doc() == doc
    for bad in (None, [], "x", 3, {}, {"schema": 99, "seen": [9]}):
        z = OverlayView()
        assert z.load_doc(bad) is False
        assert z.to_doc() == {"schema": overlayview.SCHEMA}


@pytest.mark.parametrize("raw", [b"", b"{not json", b"[1, 2]", b"\xff\xfe",
                                 b"{" + b" " * overlayview.MAX_BYTES + b"}"])
def test_store_survives_a_broken_file(tmp_path, raw):
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / overlayview.FILE_NAME).write_bytes(raw)
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=rt, log_path=str(log), tail=False)
    try:
        assert core.state.overlay.to_doc() == {"schema": overlayview.SCHEMA}
        assert core.state.snapshot()["card"] is None
    finally:
        core.close()


def test_store_saved_from_the_guide_tick_when_dirty(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    rt = tmp_path / "rt"
    core = Core(runtime=rt, log_path=str(log), tail=False)
    path = rt / overlayview.FILE_NAME
    try:
        core.tick_guide()
        assert not path.exists()  # nothing changed, nothing written
        core.state.overlay.dirty = True
        core.tick_guide()
        raw = path.read_bytes()
        assert raw.isascii() and b"\r" not in raw
        assert json.loads(raw) == {"schema": overlayview.SCHEMA}
        assert not core.state.overlay.dirty
        assert jsonfile.read_json(path, kind=dict) == {"schema": overlayview.SCHEMA}
    finally:
        core.close()


def test_store_save_failure_is_retried(tmp_path, monkeypatch):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    rt = tmp_path / "rt"
    core = Core(runtime=rt, log_path=str(log), tail=False)
    clock = Clock(0.0)
    core.store_clock = clock
    real = jsonfile.write_json
    fail = [True]

    def write(path, doc, **kw):
        if fail[0] and Path(path).name == overlayview.FILE_NAME:
            raise OSError(28, "No space left on device")
        return real(path, doc, **kw)

    monkeypatch.setattr(jsonfile, "write_json", write)
    try:
        core.state.overlay.dirty = True
        core.tick_guide()
        assert core.state.overlay.dirty and core._overlay_saver.dirty
        fail[0] = False
        core.tick_guide()  # inside the 1 s back-off: no new attempt
        assert core._overlay_saver.dirty
        clock.t = 2.0
        core.tick_guide()
        assert not core._overlay_saver.dirty and not core.state.overlay.dirty
        assert (rt / overlayview.FILE_NAME).is_file()
    finally:
        core.close()
