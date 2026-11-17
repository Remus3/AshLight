"""NEWBIE-HINTS: one-time first-hours hints for a new character (research
0032 section 5.3, ruling L). One test per trigger, a veteran gets none, the
store holds no plain name, reset, per-session fallback, the HTTP route.

Every event and name here is synthetic."""

import http.client
import json
import threading
from pathlib import Path

from server.al import hints
from server.al.core import Core
from server.al.http import serve
from server.al.state import SessionState

ROOT = Path(__file__).resolve().parents[1]
NAME = "Zephyrine"


def _ev(t, at, **kw):
    return dict(kw, type=t, recv_ts=at)


def gen(area_id, at, level=1):
    return _ev("area_generated", at, area_id=area_id, area_level=level, seed=3)


def lvl(at, level, who=NAME):
    return _ev("level_up", at, character=who, level=level, **{"class": "Monk"})


def died(at, who=NAME):
    return _ev("death", at, character=who)


class Run:
    def __init__(self, store=None):
        self.t = [1000.0]
        self.st = SessionState(clock=lambda: self.t[0])
        if store is not None:
            self.st.use_hint_store(store)

    def feed(self, *events):
        for e in events:
            self.t[0] = e["recv_ts"]
            self.st.apply(e)
        return self.st.snapshot()

    def hint_rows(self):
        return [r for r in self.st.snapshot()["recent_events"] if r["type"] == "hint"]


def test_first_level_up_from_one_shows_the_start_hint():
    r = Run()
    snap = r.feed(gen("G1_1", 1000), lvl(1010, 2))
    assert snap["hint"]["id"] == "start"
    assert snap["hint"]["text"] == hints.HINTS["start"]
    assert snap["hint"]["expires_at"] == 1010 + hints.HINT_S
    assert [x["text"] for x in r.hint_rows()] == [hints.HINTS["start"]]


def test_hint_expires_by_itself():
    r = Run()
    r.feed(gen("G1_1", 1000), lvl(1010, 2))
    r.t[0] = 1010 + hints.HINT_S
    assert r.st.snapshot()["hint"] is None


def test_first_town_shows_the_item_check_hint_once():
    r = Run()
    snap = r.feed(gen("G1_1", 1000), lvl(1010, 2), gen("G1_town", 1100, 15))
    assert snap["hint"]["id"] == "town"
    assert "Alt+Shift+E" in snap["hint"]["text"]
    r.feed(gen("G1_2", 1200, 3), gen("G1_town", 1300, 15))
    assert [x["text"] for x in r.hint_rows()].count(hints.HINTS["town"]) == 1


def test_hideout_counts_as_town():
    r = Run()
    snap = r.feed(lvl(1010, 2), gen("HideoutFelled", 1100))
    assert snap["hint"]["id"] == "town"


def test_first_campaign_death_hint():
    r = Run()
    snap = r.feed(lvl(1010, 2), gen("G1_2", 1100, 3), died(1150))
    assert snap["hint"]["id"] == "campaign_death"
    assert "no experience" in snap["hint"]["text"]
    assert not any(ch.isdigit() for ch in snap["hint"]["text"])  # no penalty number


def test_other_players_death_shows_nothing():
    r = Run()
    r.feed(lvl(1010, 2), gen("G1_2", 1100, 3), died(1150, who="Somebody"))
    assert r.st.snapshot()["hint"]["id"] == "start"


def test_first_map_hint():
    r = Run()
    snap = r.feed(lvl(1010, 2), gen("MapCrypt", 1100, 65))
    assert snap["hint"]["id"] == "first_map"
    assert "maps cost experience" in snap["hint"]["text"]


def test_veteran_character_gets_no_hint():
    r = Run()
    r.feed(gen("G1_1", 1000), lvl(1010, 57), gen("G1_town", 1100), died(1150),
           gen("G2_1", 1160, 20), died(1170), gen("MapCrypt", 1200, 65))
    assert r.st.snapshot()["hint"] is None and r.hint_rows() == []


def test_no_hint_before_the_character_is_known():
    r = Run()
    r.feed(gen("G1_town", 1000), gen("MapCrypt", 1100))
    assert r.st.snapshot()["hint"] is None


def test_no_hint_past_max_level():
    r = Run()
    r.feed(lvl(1010, 2), lvl(1020, hints.MAX_LEVEL + 1), gen("MapCrypt", 1100))
    assert r.hint_rows()[-1]["text"] == hints.HINTS["start"]


def test_store_keeps_hash_only_and_survives_restart(tmp_path):
    store = tmp_path / "rt" / hints.FILE_NAME
    r = Run(store)
    r.feed(lvl(1010, 2), gen("G1_town", 1100))
    text = store.read_text(encoding="ascii")
    assert NAME not in text and NAME.lower() not in text
    doc = json.loads(text)
    (key,) = doc["chars"]
    assert key == hints.char_key(NAME) and len(key) == hints.KEY_LEN
    assert doc["chars"][key] == {"fresh": True, "seen": ["start", "town"]}
    # a restart: the same character does not see the town hint again,
    # still gets the ones it has not seen
    r2 = Run(store)
    r2.st.level = 4
    r2.st.character = NAME
    r2.feed(gen("G1_town", 2000))
    assert r2.st.snapshot()["hint"] is None
    snap = r2.feed(gen("G1_3", 2100, 5), died(2150))
    assert snap["hint"]["id"] == "campaign_death"


def test_veteran_is_remembered(tmp_path):
    store = tmp_path / hints.FILE_NAME
    Run(store).feed(lvl(1010, 40))
    doc = json.loads(store.read_text(encoding="ascii"))
    assert list(doc["chars"].values()) == [{"fresh": False, "seen": []}]


def test_reset_shows_hints_again(tmp_path):
    store = tmp_path / hints.FILE_NAME
    r = Run(store)
    r.feed(lvl(1010, 2), gen("G1_town", 1100))
    assert r.st.reset_hints() == hints.RESET_TEXT
    assert r.st.snapshot()["hint"] is None
    snap = r.feed(gen("G1_town", 1200, 15))
    assert snap["hint"]["id"] == "town"


def test_unwritable_store_falls_back_to_this_session(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="ascii")
    r = Run(blocker / "sub" / hints.FILE_NAME)  # parent is a file
    snap = r.feed(lvl(1010, 2), gen("G1_town", 1100))
    assert snap["hint"]["id"] == "town"
    snap = r.feed(gen("G1_town", 1200))
    assert len([x for x in r.hint_rows() if x["text"] == hints.HINTS["town"]]) == 1


def test_bad_store_reads_empty_and_is_bounded(tmp_path):
    store = tmp_path / hints.FILE_NAME
    store.write_text("[1, 2", encoding="ascii")
    h = hints.Hints(store)
    assert h.chars == {}
    store.write_text(json.dumps({"chars": {
        "short": {"fresh": True}, ("a" * hints.KEY_LEN): {"fresh": True,
                                                         "seen": ["start", "bogus"]}}}),
        encoding="ascii")
    h = hints.Hints(store)
    assert dict(h.chars) == {"a" * hints.KEY_LEN: {"fresh": True, "seen": ["start"]}}
    for i in range(hints.MAX_CHARS + 5):
        h.on_level(f"C{i}", 2, 1000.0 + i)
    assert len(json.loads(store.read_text(encoding="ascii"))["chars"]) == hints.MAX_CHARS


def test_hint_texts_are_ascii_and_short():
    for text in hints.HINTS.values():
        assert text.isascii() and len(text) <= 220


def _post(port, path, body, token="f" * 48):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    raw = json.dumps(body).encode("ascii")
    conn.request("POST", path, body=raw, headers={
        "Host": f"127.0.0.1:{port}", "X-AL-Token": token,
        "Content-Type": "application/json", "Content-Length": str(len(raw))})
    r = conn.getresponse()
    out = (r.status, r.read().decode("ascii"))
    conn.close()
    return out


def test_http_reset_route(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False,
                config_path=tmp_path / "local.json")
    assert core.state.hints.path == tmp_path / "rt" / hints.FILE_NAME
    server = serve(core, "f" * 48, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        assert _post(server.port, "/api/hints", {"reset": True}, token="bad")[0] in (401, 403)
        assert _post(server.port, "/api/hints", {})[0] == 400
        status, body = _post(server.port, "/api/hints", {"reset": True})
        assert status == 200 and json.loads(body)["text"] == hints.RESET_TEXT
    finally:
        server.stop()
        core.close()
