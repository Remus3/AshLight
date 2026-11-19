"""TC-PRESS-BUILD (F-042, ruling Q-02): the item key loads a copied build.

The text is posted by the test, as the app posts its one clipboard read per
press; the server never reads the clipboard. Ephemeral port and tmp runtime
only; a running AshLight is never touched; the share-link fetch goes to a
fake transport, never the network.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import state as state_mod
from server.al.core import Core
from server.al.http import serve
from server.al.theorycraft import cardparts, codec, press
from server.al.theorycraft import store as store_mod
from server.al.theorycraft.cardparts import buildload
from tc_eval_fixtures import EVAL_BUILD_XML, RARE_GLOVES
from tc_fixtures import CHAR_JSON, FULL_XML, MINIMAL_XML

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "p" * 48
CODE = codec.encode(FULL_XML)  # a level 87 Monk (Invoker)


class FakeNet:
    """Routes by exact URL; every call is recorded; unknown URLs fail."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        if url.startswith("https://poe.ninja/"):
            return 503, {}, b""  # the opt-in also starts a rates refresh
        self.calls.append((method, url))
        if url not in self.routes:
            raise AssertionError(f"unexpected request to {url}")
        return self.routes[url]


@pytest.fixture
def env(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    net = FakeNet({"https://pobb.in/Good1/raw": (200, {}, CODE.encode("ascii"))})
    started = []

    def start():
        core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05, web_fetch=net)
        server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                       tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True).start()
        started.append((core, server))
        return server, core
    yield start, net
    for core, server in started:
        server.stop()
        core.close()


def req(server, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": f"127.0.0.1:{server.port}", "X-AL-Token": TOKEN}
    if body is not None:
        h["Content-Type"] = "application/json"
        body = json.dumps(body).encode("ascii")
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, json.loads(data) if data else None


def _press(srv, text):
    return req(srv, "POST", "/api/eval", {"item": text})


def _card_text(core):
    return core.state.snapshot()["eval"]["text"]


def _spy_price(core):
    calls = []
    real = core.price.request

    def request(text, at=None):
        calls.append(text)
        return real(text, at=at)
    core.price.request = request
    return calls


# -- the press loads a build ---------------------------------------------------

@pytest.mark.server
def test_pressed_code_loads_the_build_and_says_build_loaded(env):
    start, _net = env
    srv, core = start()
    req(srv, "POST", "/api/build-code", {"code": codec.encode(MINIMAL_XML)})
    prices = _spy_price(core)
    watched = []
    real_watch = core._watch_press
    core._watch_press = lambda *a: watched.append(a) or real_watch(*a)
    status, doc = _press(srv, CODE)
    assert status == 200, doc
    assert doc["status"] == "loaded" and doc["kind"] == "code"
    assert (doc["class_name"], doc["ascendancy"], doc["level"]) == ("Monk", "Invoker", 87)
    assert req(srv, "GET", "/api/build")[1]["build"]["class_name"] == "Monk"
    assert core.builds.source == press.SOURCE
    t = _card_text(core)
    assert (t["head"], t["item"], t["line"]) == ("Build loaded", "Invoker, level 87",
                                                 "Item checks use it now")
    assert t["word"] == "Build loaded" and t["tone"] == "note" and t["answers"] is True
    assert t["sentence"] == "Item checks now score against the build you copied."
    # the Warrior build was replaced: the note says it was kept
    assert t["notes"] == ["AshLight loaded a level 87 Invoker build and kept the old "
                          "build as a copy."]
    assert doc["replaced"] is True
    ev = core.state.snapshot()["eval"]
    assert ev["parts"] == {"buildload": {"status": "loaded", "class_name": "Monk",
                                         "ascendancy": "Invoker", "level": 87,
                                         "character": None, "replaced": True}}
    # the one overlay card (design 0001 section 10): a status card
    card = state_mod.overlay_card(ev, core.state.price, ev["at"] + 1)
    assert (card["kind"], card["head"], card["line2"], card["line3"]) == \
        ("eval", "Build loaded", "Invoker, level 87", "Item checks use it now")
    # a build press asks for no price check and adds no price-watch row
    assert prices == [] and core.state.price is None
    assert watched == [] and core.watch.items == [] and not core.watch.path.exists()


@pytest.mark.server
def test_pressed_character_json_loads_too(env):
    start, _net = env
    srv, core = start()
    status, doc = _press(srv, json.dumps(CHAR_JSON))
    assert status == 200 and doc["status"] == "loaded" and doc["kind"] == "json", doc
    assert doc["level"] == 87
    assert req(srv, "GET", "/api/build")[1]["loaded"] is True
    assert _card_text(core)["word"] == "Build loaded"


@pytest.mark.server
def test_item_text_still_gives_a_verdict_and_a_price_check(env):
    start, _net = env
    srv, core = start()
    assert _press(srv, codec.encode(EVAL_BUILD_XML))[1]["status"] == "loaded"
    prices = _spy_price(core)
    status, doc = _press(srv, RARE_GLOVES)
    assert status == 200 and doc["ok"] is True and doc["verdict"], doc
    assert "status" not in doc
    assert prices == [RARE_GLOVES]
    assert _card_text(core)["word"] in ("Upgrade", "Sidegrade", "Downgrade")
    assert "buildload" not in core.state.snapshot()["eval"]["parts"]


@pytest.mark.server
def test_code_shaped_text_that_does_not_decode_is_the_item_check(env):
    start, _net = env
    srv, core = start()
    _press(srv, codec.encode(MINIMAL_XML))
    prices = _spy_price(core)
    text = "Q" * 40
    assert press.classify(text) == "build"
    status, doc = _press(srv, text)
    assert status == 200 and doc["ok"] is False and doc["error"] == "not an item", doc
    assert prices == [text]  # the item check as today, price check included
    assert _card_text(core)["head"] == "Not an item"
    assert core.builds.build.class_name == "Warrior"  # the good build stays


@pytest.mark.server
def test_link_with_web_data_off_gives_the_refusal_words_and_no_request(env):
    start, net = env
    srv, core = start()
    _press(srv, codec.encode(MINIMAL_XML))
    prices = _spy_price(core)
    link = "https://pobb.in/Good1"
    _status, paste_doc = req(srv, "POST", "/api/build-code", {"code": link})
    status, doc = _press(srv, link)
    assert status == 200 and doc["status"] == "refused", doc
    # the existing refusal words of the paste box, word for word
    assert doc["error"] == paste_doc["error"] == press.WEB_DATA_OFF
    assert doc["web_data"] is False and doc["kind"] == "url"
    assert net.calls == [] and prices == []
    t = _card_text(core)
    assert (t["head"], t["item"], t["line"]) == ("Build not loaded", "Share link",
                                                 "See the dashboard")
    assert t["notes"] == [buildload.REASONS["web_data_off"]]
    assert t["word"] == "Not checked" and t["answers"] is True
    assert core.builds.build.class_name == "Warrior"


@pytest.mark.server
def test_link_with_web_data_on_loads_once(env):
    start, net = env
    srv, core = start()
    core.set_web_data(True)
    status, doc = _press(srv, "https://pobb.in/Good1")
    assert status == 200 and doc["status"] == "loaded" and doc["kind"] == "url", doc
    assert [c for c in net.calls if "pobb.in" in c[1]] == [("GET", "https://pobb.in/Good1/raw")]
    assert core.builds.build.class_name == "Monk"
    status, doc = _press(srv, "https://evil.example/Good1")
    assert doc["status"] == "refused" and doc["reason"] == "not_supported"
    assert _card_text(core)["notes"] == [buildload.REASONS["not_supported"]]


def test_press_goes_to_the_character_being_played(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    try:
        core.builds.character_of = lambda: "Quietfox"
        doc = core.eval_press(CODE)
        assert doc["status"] == "loaded" and doc["character"] == "Quietfox"
        assert doc["replaced"] is False  # the first build of this character
        assert core.builds.active_path().parent.name == store_mod.CHARS_DIR
        assert core.builds.active_path().read_text(encoding="ascii").strip() == CODE
        assert _card_text(core)["notes"] == [
            "AshLight loaded a level 87 Invoker build for Quietfox."]
    finally:
        core.close()


# -- one undo copy, bounded ----------------------------------------------------

def test_replaced_build_is_kept_as_one_undo_copy(tmp_path):
    s = store_mod.BuildStore(tmp_path / "build" / "last-code.txt", per_character=True)
    s.character_of = lambda: "Quietfox"
    path_a = codec.encode(MINIMAL_XML)
    s.load_code(path_a)
    target = s.active_path()
    undo = store_mod.BuildStore.undo_path(target)
    assert undo.name == target.stem + ".undo"
    assert not undo.exists()  # nothing was replaced
    s.load_code(CODE, source=press.SOURCE)
    assert undo.read_text(encoding="ascii").strip() == path_a
    s.load_code(CODE)  # the same bytes: the undo copy stays as it was
    assert undo.read_text(encoding="ascii").strip() == path_a
    s.load_code(codec.encode(EVAL_BUILD_XML))
    assert undo.read_text(encoding="ascii").strip() == CODE
    assert sorted(p.name for p in target.parent.iterdir()
                  if p.suffix == store_mod.UNDO_SUFFIX) == [undo.name]
    assert s.characters_with_builds() == ["Quietfox"]  # .undo is not a character
    # bounded: a file over the size cap is never copied
    target.write_bytes(b"A" * (store_mod.MAX_FILE_BYTES + 1))
    s.load_code(path_a)
    assert undo.stat().st_size <= store_mod.MAX_FILE_BYTES


def test_undo_copy_per_character(tmp_path):
    s = store_mod.BuildStore(tmp_path / "build" / "last-code.txt", per_character=True)
    for name in ("Quietfox", "Ember"):
        s.sync(name)
        s.load_code(codec.encode(MINIMAL_XML))
        s.load_code(CODE)
    undos = sorted(p.name for p in s.chars_dir.iterdir() if p.suffix == ".undo")
    assert undos == sorted(store_mod.slug(n) + ".undo" for n in ("Quietfox", "Ember"))


# -- classify and the card part ------------------------------------------------

def test_classify():
    assert press.classify(RARE_GLOVES) == "item"
    assert press.classify("") == "item" and press.classify("   ") == "item"
    assert press.classify(None) == "item"
    assert press.classify(CODE) == "build"
    assert press.classify(json.dumps(CHAR_JSON)) == "build"
    assert press.classify("https://pobb.in/AbCd") == "link"
    assert press.classify("just some text") == "item"


def test_buildload_is_a_discovered_part_and_silent_on_items():
    cardparts.reset()
    assert buildload in cardparts.discover()
    assert buildload.compute({"text": RARE_GLOVES}) is None
    assert buildload.compute({"build_press": {"status": "odd"}}) is None
    assert buildload.compute(None) is None


def test_buildload_words_fit_the_card_contract():
    for reason, note in buildload.REASONS.items():
        assert note.isascii() and "!" not in note and len(note.split()) <= 20, reason
    value = buildload.clean({"status": "loaded", "class_name": "Witch", "ascendancy": None,
                             "level": 3, "character": "A" * 99})
    assert len(value["character"]) == buildload.NAME_MAX
    assert buildload.describe(value) == "Witch, level 3"
    assert buildload.loaded_note({"class_name": "Invoker"}) == \
        "AshLight loaded an Invoker build."
    assert buildload.loaded_note({}) == "AshLight loaded the build you copied."
    assert buildload.describe({}) == "Build from the clipboard"
    assert buildload.describe({"level": 5}) == "Level 5 build"
    card = press.card({"status": "loaded", "class_name": "Witch", "level": 3})
    t = state_mod.eval_card_text(card)
    assert t["head"] == "Build loaded" and len(t["head"]) <= cardparts.HEAD_MAX
    assert t["item"] == "Witch, level 3"
    assert len(json.dumps(card["parts"])) <= cardparts.VALUE_MAX
    for note in t["notes"]:
        assert note.isascii() and "!" not in note and len(note.split()) <= 20
    longest = buildload.loaded_note(buildload.clean({
        "status": "loaded", "class_name": "C" * 99, "ascendancy": "A" * 99, "level": 100,
        "character": "Q" * 99, "replaced": True}))
    assert len(longest.split()) <= 20
