"""OVL-POS (overlay layout persisted in config/local.json) and HUD-WHISPER
(trade whisper cards, dismissed from the dashboard). Every path is under
tmp_path; the real config/local.json is never read or written."""

import http.client
import json
import re
import threading
from pathlib import Path

import pytest

import srcpaths
from server.al import layout
from server.al.core import Core
from server.al.http import serve
from server.al.state import TRADE_REQUESTS

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "client_sample.txt"
TOKEN = "k" * 48


# ---------------------------------------------------------------- layout model

def test_normalize_fills_defaults():
    assert layout.normalize({}) == layout.DEFAULT
    got = layout.normalize({"corner": "bottom-left", "scale": 1.5, "display": 1})
    assert got["corner"] == "bottom-left" and got["scale"] == 1.5 and got["display"] == 1
    assert got["opacity"] == layout.DEFAULT["opacity"]


@pytest.mark.parametrize("bad", [
    {"corner": "middle"}, {"scale": 5}, {"scale": "big"}, {"scale": True},
    {"opacity": 0.0}, {"margin": -1}, {"display": -1}, {"display": "left"},
    {"display": 1.5}, {"unknown": 1}, {"scale": float("nan")},
])
def test_normalize_strict_rejects(bad):
    with pytest.raises(layout.LayoutError):
        layout.normalize(bad)


def test_normalize_lenient_never_raises():
    got = layout.normalize({"corner": "middle", "scale": "big", "extra": 1}, strict=False)
    assert got == layout.DEFAULT
    assert layout.normalize("garbage", strict=False) == layout.DEFAULT


# OVL-OVERLAY-KEYS (plan 03 section 5.4): parts switches, quiet town and the
# zone-guide choice. Defaults keep today's overlay: every part on, zone line
# shown in town, zone guide on entry.

def test_new_keys_default_to_todays_overlay():
    got = layout.normalize({})
    assert got["parts"] == {name: True for name in layout.PARTS}
    assert layout.PARTS == ("zone", "timer", "level", "deaths", "status",
                            "trade", "item", "moment", "hint")
    assert got["quiet_town"] is False and got["zone_guide"] == "entry"
    assert layout.ZONE_GUIDE == ("entry", "always", "never")


def test_normalize_never_shares_the_default_parts():
    got = layout.normalize({})
    got["parts"]["zone"] = False
    assert layout.DEFAULT["parts"]["zone"] is True
    assert layout.normalize({})["parts"]["zone"] is True


def test_new_keys_strict_accepts_and_fills():
    got = layout.normalize({"parts": {"zone": False, "hint": False},
                            "quiet_town": True, "zone_guide": "never"})
    assert got["parts"]["zone"] is False and got["parts"]["hint"] is False
    assert all(got["parts"][n] for n in layout.PARTS if n not in ("zone", "hint"))
    assert got["quiet_town"] is True and got["zone_guide"] == "never"
    assert layout.normalize({"zone_guide": "always"})["zone_guide"] == "always"


@pytest.mark.parametrize("bad", [
    {"parts": {"offline": False}}, {"parts": {"failure": False}},
    {"parts": {"zone": 0}}, {"parts": {"zone": "off"}}, {"parts": ["zone"]},
    {"parts": None}, {"quiet_town": 1}, {"quiet_town": "yes"},
    {"zone_guide": "sometimes"}, {"zone_guide": None}, {"zone_guide": True},
])
def test_new_keys_strict_rejects(bad):
    with pytest.raises(layout.LayoutError):
        layout.normalize(bad)


def test_failure_words_are_not_parts():
    # A failure word can never be switched off: it is no part at all.
    for word in ("offline", "no_client_txt", "not_reading", "failure", "error"):
        assert word not in layout.PARTS


def test_new_keys_lenient_never_raises():
    got = layout.normalize({"parts": {"zone": False, "bogus": False, "level": 3},
                            "quiet_town": "yes", "zone_guide": "sometimes"},
                           strict=False)
    assert got["parts"] == dict(layout.DEFAULT["parts"], zone=False)
    assert got["quiet_town"] is False and got["zone_guide"] == "entry"
    for junk in (None, 5, "all", ["zone"], {}):
        assert layout.normalize({"parts": junk}, strict=False)["parts"] ==             layout.DEFAULT["parts"]


def test_new_keys_survive_save_and_merge(tmp_path):
    core = Core(runtime=tmp_path / "rt", tail=False)
    try:
        core.set_overlay_layout({"parts": dict(layout.DEFAULT["parts"], trade=False),
                                 "quiet_town": True})
        got = core.set_overlay_layout({"corner": "bottom-left", "zone_guide": "always"})
        assert got["parts"]["trade"] is False and got["quiet_town"] is True
        assert got["zone_guide"] == "always" and got["corner"] == "bottom-left"
        stored = json.loads(core.config_path.read_text(encoding="ascii"))
        assert stored["overlay"] == got
        assert core.state.snapshot()["overlay_layout"] == got
    finally:
        core.close()


def _js_shared_fixture():
    """The fixture in app/test/layout.test.js between the SHARED-FIXTURE
    markers: rows of {"in", "out"} both sides must agree on."""
    src = (ROOT / "app" / "test" / "layout.test.js").read_text(encoding="ascii")
    m = re.search(r"/\* SHARED-FIXTURE \*/(.*?)/\* END-SHARED-FIXTURE \*/", src, re.S)
    assert m, "shared fixture markers in layout.test.js"
    return json.loads(m.group(1))


def test_python_agrees_with_the_js_shared_fixture():
    rows = _js_shared_fixture()
    assert len(rows) >= 4
    for row in rows:
        assert layout.normalize(row["in"], strict=False) == row["out"], row["in"]


def test_overlay_js_keys_match_python():
    js = (ROOT / "app" / "shared" / "layout.js").read_text(encoding="ascii")
    m = re.search(r"var PARTS = \[(.*?)\];", js, re.S)
    assert m and re.findall(r'"([a-z_]+)"', m.group(1)) == list(layout.PARTS)
    m = re.search(r"var ZONE_GUIDE = \[(.*?)\];", js, re.S)
    assert m and re.findall(r'"([a-z_]+)"', m.group(1)) == list(layout.ZONE_GUIDE)
    m = re.search(r"var DEFAULT = \{(.*?)\};", js, re.S)
    keys = re.findall(r"([a-z_]+):", m.group(1))
    assert keys == list(layout.DEFAULT), keys
    assert 'quiet_town: false, zone_guide: "entry"' in js


# DS-OPACITY / DS-SCALE (design 0001 5.2 and O3): opacity floor 0.9 keeps
# every overlay text pair >= 4.5:1 over a white scene; scale floor 0.95
# keeps 13px secondary text >= 12px.

def test_floors():
    assert (layout.OPACITY_MIN, layout.OPACITY_MAX) == (0.9, 1.0)
    assert (layout.SCALE_MIN, layout.SCALE_MAX) == (0.95, 2.0)
    assert 13 * layout.SCALE_MIN >= 12


@pytest.mark.parametrize("bad", [
    {"opacity": 0.85}, {"opacity": 0.3}, {"scale": 0.9}, {"scale": 0.75},
])
def test_strict_rejects_below_floor(bad):
    with pytest.raises(layout.LayoutError):
        layout.normalize(bad)


def test_strict_accepts_floor():
    got = layout.normalize({"opacity": 0.9, "scale": 0.95})
    assert got["opacity"] == 0.9 and got["scale"] == 0.95


def test_lenient_clamps_old_layouts():
    # A layout saved before the floors were raised clamps itself on load.
    got = layout.normalize({"opacity": 0.3, "scale": 0.75, "margin": 999},
                           strict=False)
    assert got["opacity"] == 0.9 and got["scale"] == 0.95 and got["margin"] == 400
    assert layout.normalize({"scale": 99}, strict=False)["scale"] == 2.0


def test_load_clamps_saved_config(tmp_path):
    cfg = tmp_path / "local.json"
    cfg.write_text(json.dumps({"overlay": {"opacity": 0.5, "scale": 0.8,
                                           "corner": "top-left"}}),
                   encoding="ascii")
    got = layout.load(cfg)
    assert got["opacity"] == 0.9 and got["scale"] == 0.95
    assert got["corner"] == "top-left"


def test_dashboard_sliders_match_floors():
    html = srcpaths.index_html()
    assert 'id="layout-scale" name="scale" type="range" min="0.95"' in html
    assert 'id="layout-opacity" name="opacity" type="range" min="0.9"' in html


def test_overlay_js_limits_match_python():
    js = (ROOT / "app" / "shared" / "layout.js").read_text(encoding="ascii")
    assert ("scale: [%s, %s], opacity: [%s, %s]" % (
        layout.SCALE_MIN, layout.SCALE_MAX, layout.OPACITY_MIN,
        layout.OPACITY_MAX)) in js


def test_save_keeps_other_keys_ascii_lf(tmp_path):
    cfg = tmp_path / "local.json"
    cfg.write_text(json.dumps({"client_log": "", "poll_ms": 250, "_doc": "x"}),
                   encoding="ascii")
    saved = layout.save(cfg, {"corner": "bottom-right", "scale": 1.25})
    raw = cfg.read_bytes()
    assert b"\r\n" not in raw and raw.endswith(b"\n")
    raw.decode("ascii")
    doc = json.loads(raw)
    assert doc["poll_ms"] == 250 and doc["_doc"] == "x"
    assert doc["overlay"] == saved and saved["scale"] == 1.25


def test_save_refuses_to_clobber_broken_config(tmp_path):
    cfg = tmp_path / "local.json"
    cfg.write_text("{not json", encoding="ascii")
    with pytest.raises(layout.LayoutError):
        layout.save(cfg, {})
    assert cfg.read_text(encoding="ascii") == "{not json"


def test_layout_survives_restart(tmp_path):
    rt = tmp_path / "rt"
    core = Core(runtime=rt, tail=False)
    core.set_overlay_layout({"corner": "top-left", "opacity": 0.95, "display": 1})
    core.close()
    again = Core(runtime=rt, tail=False)
    try:
        got = again.overlay_layout()
        assert got["corner"] == "top-left" and got["opacity"] == 0.95 and got["display"] == 1
        assert again.state.snapshot()["overlay_layout"] == got
    finally:
        again.close()


def test_merge_keeps_unchanged_fields(tmp_path):
    core = Core(runtime=tmp_path / "rt", tail=False)
    core.set_overlay_layout({"scale": 1.5})
    got = core.set_overlay_layout({"corner": "bottom-center"})
    assert got["scale"] == 1.5 and got["corner"] == "bottom-center"


def test_read_displays(tmp_path):
    assert layout.read_displays(tmp_path) == []
    (tmp_path / "displays.json").write_text(json.dumps({"displays": [
        {"index": 0, "primary": True, "label": "A", "width": 2560, "height": 1440,
         "scale_factor": 1.5},
        {"index": "bad"}, "junk"]}), encoding="ascii")
    got = layout.read_displays(tmp_path)
    assert len(got) == 1 and got[0]["primary"] and got[0]["scale_factor"] == 1.5


# ---------------------------------------------------------------- trade cards

def _replayed(tmp_path, closes=False):
    # The three whisper cards as they arrive. The fixture's "Trade accepted."
    # closes the oldest (decision 0019); closes=True keeps that line.
    core = Core(runtime=tmp_path / "rt", tail=False)
    lines = FIXTURE.read_text(encoding="ascii").splitlines()
    if not closes:
        lines = [ln for ln in lines if not ln.endswith(": Trade accepted.")]
    core.replay(lines)
    return core


def test_fixture_trade_accepted_closes_the_oldest_card(tmp_path):
    core = _replayed(tmp_path, closes=True)
    cards = core.state.snapshot()["trade_requests"]
    assert [c["from"] for c in cards] == ["Quietfox", "Coinmonger"]


def test_fixture_whispers_become_trade_cards(tmp_path):
    core = _replayed(tmp_path)
    cards = core.state.snapshot()["trade_requests"]
    assert [c["from"] for c in cards] == ["Tradewind", "Quietfox", "Coinmonger"]
    first = cards[0]
    assert first["item"] == "Grim Bane Ruby Ring" and first["price_amount"] == 5
    assert first["price_currency"] == "exalted" and first["stash_tab"] == "Sale"
    assert (first["left"], first["top"]) == (3, 7)
    assert cards[1]["price_amount"] is None
    assert cards[2]["kind"] == "exchange" and cards[2]["want_amount"] == 10
    # A plain whisper ("hey there") is not a trade card.
    assert len({c["id"] for c in cards}) == 3


def test_trade_cards_are_bounded(tmp_path):
    core = Core(runtime=tmp_path / "rt", tail=False)
    line = ('2026/11/16 20:02:20 1 4d5e6f70 [INFO Client 4242] @From B{n}: Hi, I would '
            'like to buy your Ring listed for 1 exalted in Standard (stash tab "S"; '
            'position: left 1, top 1)')
    core.replay([line.format(n=i) for i in range(TRADE_REQUESTS + 3)])
    cards = core.state.snapshot()["trade_requests"]
    assert len(cards) == TRADE_REQUESTS
    assert cards[-1]["from"] == f"B{TRADE_REQUESTS + 2}"


def test_dismiss_one_and_all(tmp_path):
    core = _replayed(tmp_path)
    ids = [c["id"] for c in core.state.snapshot()["trade_requests"]]
    v = core.state.snapshot()["version"]
    assert core.state.dismiss_trade(ids[0]) == 1
    assert core.state.snapshot()["version"] > v
    assert core.state.dismiss_trade(ids[0]) == 0
    assert core.state.dismiss_trade(None) == 2
    assert core.state.snapshot()["trade_requests"] == []


# ---------------------------------------------------------------- HTTP

@pytest.fixture
def srv(tmp_path):
    core = _replayed(tmp_path)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def call(server, method, path, body=None, token=TOKEN):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": f"127.0.0.1:{server.port}"}
    if token:
        h["X-AL-Token"] = token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=h)
    r = conn.getresponse()
    out = r.read()
    conn.close()
    return r.status, (json.loads(out) if out[:1] in (b"{", b"[") else out)


@pytest.mark.server
def test_layout_api_needs_token(srv):
    assert call(srv, "GET", "/api/overlay-layout", token=None)[0] == 401
    assert call(srv, "POST", "/api/overlay-layout", {"scale": 1}, token=None)[0] == 401
    assert call(srv, "POST", "/api/trade-dismiss", {"all": True}, token=None)[0] == 401


@pytest.mark.server
def test_layout_api_roundtrip(srv):
    code, doc = call(srv, "GET", "/api/overlay-layout")
    assert code == 200 and doc["layout"] == layout.DEFAULT
    assert doc["corners"] == list(layout.CORNERS)
    code, doc = call(srv, "POST", "/api/overlay-layout", {"corner": "bottom-left",
                                                          "scale": 1.25})
    assert code == 200 and doc["layout"]["corner"] == "bottom-left"
    stored = json.loads(srv.core.config_path.read_text(encoding="ascii"))
    assert stored["overlay"]["scale"] == 1.25
    assert srv.core.state.snapshot()["overlay_layout"]["corner"] == "bottom-left"
    code, doc = call(srv, "POST", "/api/overlay-layout", {"corner": "middle"})
    assert code == 400 and "corner" in doc["error"]
    assert call(srv, "GET", "/api/overlay-layout")[1]["layout"]["corner"] == "bottom-left"


@pytest.mark.server
def test_trade_dismiss_api(srv):
    cards = srv.core.state.snapshot()["trade_requests"]
    code, doc = call(srv, "POST", "/api/trade-dismiss", {"id": cards[0]["id"]})
    assert code == 200 and doc["dismissed"] == 1
    assert len(doc["state"]["trade_requests"]) == 2
    assert call(srv, "POST", "/api/trade-dismiss", {"id": "x"})[0] == 400
    assert call(srv, "POST", "/api/trade-dismiss", {"id": True})[0] == 400
    code, doc = call(srv, "POST", "/api/trade-dismiss", {"all": True})
    assert code == 200 and doc["dismissed"] == 2 and doc["state"]["trade_requests"] == []
