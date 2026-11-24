"""KINDLER-STORE (decision 0081 points 7, 11 and 17): the Kindler tabs
store ops/runtime/gen_builds.json (server/al/theorycraft/genstore.py) and
its token-gated tab route (server/al/plug/genbuilds.py).

Bounded (6 tabs, 32-character labels with control characters stripped),
follow on by default, order = list order, the shown tab kept; durable
like the other stores (one .bak, Saver retry, the Checks row while
unsaved, the restore note); emptied by Clear run history. Tmp files only;
the server binds port 0; a failing disk is a patched write.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import http as al_http
from server.al import jsonfile, plug
from server.al.core import Core
from server.al.plug import genbuilds, stores
from server.al.theorycraft import genstore

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "k" * 48
PATH = "/api/gen-builds"
KEY = "ab" * 32


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _result(**kw):
    out = {"template": "melee-slam", "dps": 1234.5, "ehp": 5678.0, "at": 1795000000,
           "partial": False, "scored": True, "key": KEY}
    out.update(kw)
    return out


# -- the store --------------------------------------------------------------

def test_new_tab_defaults_follow_on_and_unsure_toggles(tmp_path):
    s = genstore.GenStore(tmp_path / genstore.FILE_NAME)
    tid = s.add()
    tab = s.tab(tid)
    assert tab["follow"] is True
    assert tab["toggles"] == {k: "unsure" for k in genstore.TOGGLE_KEYS}
    assert tab["label"] == "" and tab["result"] is None and tab["candidates"] == 0
    view = s.view()
    assert view["shown"] == tid and view["tabs"][0]["label"] == "Kindler 1"
    assert view["tabs"][0]["custom_label"] is False
    doc = json.loads((tmp_path / genstore.FILE_NAME).read_text(encoding="ascii"))
    assert doc["schema"] == 1 and doc["shown"] == tid


def test_seventh_tab_is_refused_with_a_note(tmp_path):
    s = genstore.GenStore(tmp_path / genstore.FILE_NAME)
    for _ in range(6):
        s.add()
    assert s.view()["full"] is True and s.view()["full_text"] == genstore.FULL_TEXT
    with pytest.raises(genstore.GenError) as e:
        s.add()
    assert str(e.value) == genstore.FULL_TEXT
    assert len(s.view()["tabs"]) == 6


def test_label_cut_to_32_and_control_characters_stripped(tmp_path):
    s = genstore.GenStore(tmp_path / genstore.FILE_NAME)
    tid = s.add(label="My\x00 big\tbuild\x7f")
    assert s.tab(tid)["label"] == "My bigbuild"
    s.rename(tid, "x" * 50)
    assert s.tab(tid)["label"] == "x" * 32
    s.rename(tid, "  \x01 ")
    assert s.tab(tid)["label"] == ""  # empty = the default label
    assert s.view()["tabs"][0]["label"] == "Kindler 1"
    with pytest.raises(genstore.GenError):
        s.rename(tid, 5)


def test_move_close_and_shown_survive_a_reload(tmp_path):
    p = tmp_path / genstore.FILE_NAME
    s = genstore.GenStore(p)
    a, b, c = s.add(label="a"), s.add(label="b"), s.add(label="c")
    assert s.move(a, 1) is True
    assert [t["id"] for t in s.view()["tabs"]] == [b, a, c]
    assert s.move(b, -1) is False  # at the left end: nothing moves
    assert s.move(c, 1) is False
    s.show(a)
    s2 = genstore.GenStore(p)
    assert [t["id"] for t in s2.view()["tabs"]] == [b, a, c]
    assert s2.view()["shown"] == a
    # closing the shown tab passes the mark to its right neighbour
    s2.close(a)
    assert s2.view()["shown"] == c
    s2.close(c)
    assert s2.view()["shown"] == b
    s2.close(b)
    assert s2.view()["shown"] == "" and s2.view()["tabs"] == []
    # ids are never reused after a close
    assert s2.add() == "k4"
    with pytest.raises(genstore.GenError) as e:
        s2.close("k99")
    assert str(e.value) == genstore.GONE_TEXT


def test_toggle_or_class_change_marks_the_result_stale(tmp_path):
    s = genstore.GenStore(tmp_path / genstore.FILE_NAME)
    tid = s.add(cls="Warrior", league="Standard")
    s.set_result(tid, _result(), candidates=12)
    tab = s.tab(tid)
    assert tab["result"]["stale"] is False and tab["candidates"] == 12
    s.update(tid, {"league": "Other", "follow": False})  # league never changes scoring
    assert s.tab(tid)["result"]["stale"] is False and s.tab(tid)["follow"] is False
    s.update(tid, {"toggles": {"melee": "yes", "defence": "energy_shield"}})
    tab = s.tab(tid)
    assert tab["result"]["stale"] is True
    assert tab["toggles"]["melee"] == "yes" and tab["toggles"]["spell"] == "unsure"
    s.set_result(tid, _result())
    s.update(tid, {"class": "Monk"})
    assert s.tab(tid)["result"]["stale"] is True
    for bad in ({"toggles": {"melee": "maybe"}}, {"toggles": {"fly": "yes"}},
                {"follow": "yes"}, {"result": {}}, {"template": "Bad Id!"}, {}):
        with pytest.raises(genstore.GenError):
            s.update(tid, bad)
    with pytest.raises(genstore.GenError):
        s.set_result(tid, _result(), candidates=13)


def test_calc_off_result_keeps_no_numbers(tmp_path):
    s = genstore.GenStore(tmp_path / genstore.FILE_NAME)
    tid = s.add()
    s.set_result(tid, _result(scored=False))
    res = s.tab(tid)["result"]
    assert res["dps"] is None and res["ehp"] is None and res["template"] == "melee-slam"


def test_broken_file_reads_from_bak_and_bad_parts_drop(tmp_path):
    p = tmp_path / genstore.FILE_NAME
    s = genstore.GenStore(p)
    tid = s.add(label="keep")
    assert jsonfile.bak_path(p).is_file()
    jsonfile.pop_restored()
    p.write_text("{half", encoding="ascii")
    s2 = genstore.GenStore(p)
    assert s2.tab(tid)["label"] == "keep"
    assert str(p) in jsonfile.pop_restored()
    # hand-edited: too many tabs, a duplicate id, a bad field, item text
    doc = {"schema": 1, "shown": "k9", "next": 0,
           "tabs": ([{"id": f"k{i}", "label": f"t{i}", "item_text": "Rarity: Rare"}
                     for i in range(1, 9)]
                    + [{"id": "k1"}, {"id": "bad"}])}
    doc["tabs"][1]["toggles"] = {"melee": "maybe", "bow": "yes"}
    jsonfile.write_json(p, doc)
    s3 = genstore.GenStore(p)
    view = s3.view()
    assert len(view["tabs"]) == 6 and view["shown"] == "k1"
    assert all("item_text" not in t for t in view["tabs"])
    assert view["tabs"][1]["toggles"]["melee"] == "unsure"
    assert view["tabs"][1]["toggles"]["bow"] == "yes"
    # the next id is past every kept one
    s3.close("k6")
    assert s3.add() == "k7"


def test_file_stays_bounded_and_ascii(tmp_path):
    p = tmp_path / genstore.FILE_NAME
    s = genstore.GenStore(p)
    for i in range(6):
        tid = s.add(label="\u00e9" * 40, cls="c" * 100, league="l" * 100)
        s.set_result(tid, _result(), candidates=12)
    raw = p.read_bytes()
    assert len(raw) < genstore.MAX_BYTES and raw.isascii() and b"\r" not in raw
    tab = s.view()["tabs"][0]
    assert len(tab["label"]) == 32 and len(tab["class"]) == genstore.MAX_FIELD


def test_clear_empties_the_file_and_drops_the_bak(tmp_path):
    p = tmp_path / genstore.FILE_NAME
    s = genstore.GenStore(p)
    s.add()
    s.clear()
    assert json.loads(p.read_text(encoding="ascii"))["tabs"] == []
    assert not jsonfile.bak_path(p).exists()


def test_export_block_has_no_ids_and_imports_never_overwrite(tmp_path):
    s = genstore.GenStore(tmp_path / "a.json")
    assert s.export_block() is None
    a = s.add(label="one")
    s.set_result(a, _result())
    s.add(label="two")
    block = s.export_block()
    assert all("id" not in t for t in block["tabs"])
    tabs = genstore.check_block(block)["tabs"]
    other = genstore.GenStore(tmp_path / "b.json")
    for _ in range(5):
        other.add(label="mine")
    added, full = other.import_tabs(tabs)
    assert (added, full) == (1, 1)
    labels = [t["label"] for t in other.view()["tabs"]]
    assert labels == ["mine"] * 5 + ["one"]
    for bad in ({"tabs": [{"id": "k1"}]}, {"tabs": [{}] * 7}, {"tabs": "x"},
                {"tabs": [], "more": 1}, {"tabs": [{"follow": "yes"}]}, []):
        with pytest.raises(genstore.GenError):
            genstore.check_block(bad)


# -- the core: Saver, Checks row, restore note, Clear run history -------------

@pytest.fixture
def core(tmp_path):
    jsonfile.pop_restored()
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    c.store_clock = Clock()
    try:
        yield c
    finally:
        c.close()


def _checks(core):
    core.tick_all()
    core.tick_diag(force=True)
    return {r["id"]: r for r in core.state.snapshot()["diag"]["checks"]}


def test_attach_wires_store_saver_tick_and_clear_hook(core):
    assert isinstance(core.gen_builds, genstore.GenStore)
    assert core.gen_builds.path == Path(core.runtime) / "gen_builds.json"
    assert genbuilds.SAVER in core.savers
    assert "tick_gen_builds" in [n for n, _ in core.ticks]
    assert core.history.on_clear


def test_failed_save_keeps_the_change_shows_the_row_and_retries(core, monkeypatch):
    store = core.gen_builds
    real = jsonfile.write_json
    tries = []

    def broken(path, doc, **kw):
        if Path(path).name.startswith("gen_builds"):
            tries.append(1)
            raise OSError(28, "No space left on device")
        return real(path, doc, **kw)

    monkeypatch.setattr(jsonfile, "write_json", broken)
    _res, saved = genbuilds._op(core, lambda: store.add(label="kept"))
    assert saved is False and store.view()["tabs"][0]["label"] == "kept"
    row = _checks(core)["stores_unsaved"]
    assert row["detail"] == ("AshLight couldn't save your Kindler tabs yet. "
                             "It keeps trying on its own.")
    n = len(tries)
    for _ in range(10):  # 2 Hz ticks inside the first back-off step
        core.tick_all()
    assert len(tries) == n
    monkeypatch.setattr(jsonfile, "write_json", real)
    core.store_clock.t += 2.0
    assert genbuilds.tick(core) is True
    assert "stores_unsaved" not in _checks(core)
    doc = json.loads((Path(core.runtime) / "gen_builds.json").read_text(encoding="ascii"))
    assert doc["tabs"][0]["label"] == "kept"


def test_restore_note_names_the_kindler_tabs(tmp_path):
    jsonfile.pop_restored()
    rt = tmp_path / "rt"
    s = genstore.GenStore(rt / genstore.FILE_NAME)
    s.add()
    (rt / genstore.FILE_NAME).write_text("{", encoding="ascii")
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=rt, log_path=str(log), tail=False)
    try:
        assert len(c.gen_builds.view()["tabs"]) == 1
        row = _checks(c)["stores_restored"]
        assert row["detail"] == ("Kindler tabs were damaged and restored from the "
                                 "last good copy.")
    finally:
        c.close()
    assert stores.UNSAVED_WORDS["genbuilds"] == "Kindler tabs"


def test_clear_run_history_empties_the_tabs(core):
    store = core.gen_builds
    store.add(label="gone")
    path = Path(core.runtime) / "gen_builds.json"
    assert jsonfile.bak_path(path).is_file()
    core.set_history(clear=True)
    assert store.view()["tabs"] == []
    assert json.loads(path.read_text(encoding="ascii"))["tabs"] == []
    assert not jsonfile.bak_path(path).exists()


def test_a_failing_clear_hook_never_stops_the_clear(tmp_path):
    from server.al import runhistory
    h = runhistory.RunHistory(tmp_path / runhistory.FILE_NAME)
    ran = []

    def bad():
        raise OSError("held")

    h.on_clear.extend([bad, lambda: ran.append(1)])
    h.clear()
    assert ran == [1] and h.runs == []


# -- the route ----------------------------------------------------------------

@pytest.fixture
def srv(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = al_http.serve(c, TOKEN, port=0, web_root=ROOT / "web",
                           tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    c.close()


def req(server, method, path, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    h = {"Host": f"127.0.0.1:{server.port}"}
    h.update(headers or {})
    if isinstance(body, dict):
        body = json.dumps(body)
        h.setdefault("Content-Type", "application/json")
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, (json.loads(data) if data and r.getheader("Content-Type", "")
                      .startswith("application/json") else data)


def auth():
    return {"X-AL-Token": TOKEN}


def test_route_needs_the_token(srv):
    assert ("GET", PATH) in plug.all_routes() and ("POST", PATH) in plug.all_routes()
    body = {"op": "add"}
    for method in ("GET", "POST"):
        for h in ({}, {"X-AL-Token": "wrong"}):
            status, doc = req(srv, method, PATH, h, body if method == "POST" else None)
            assert status == 401 and doc == {"error": "token required"}
    assert req(srv, "POST", PATH, {**auth(), "Sec-Fetch-Site": "cross-site"}, body)[0] == 403
    assert req(srv, "POST", PATH, {**auth(), "Origin": "http://evil.example"}, body)[0] == 403
    assert not (Path(srv.core.runtime) / "gen_builds.json").exists()
    assert req(srv, "PUT", PATH, auth(), body)[0] == 405


def test_route_ops_round_trip(srv):
    status, doc = req(srv, "GET", PATH, auth())
    assert status == 200 and doc["tabs"] == [] and doc["max"] == 6
    status, doc = req(srv, "POST", PATH, auth(), {"op": "add", "label": "Slam"})
    assert status == 200 and doc["saved"] is True
    a = doc["shown"]
    b = req(srv, "POST", PATH, auth(), {"op": "add"})[1]["shown"]
    doc = req(srv, "POST", PATH, auth(), {"op": "move", "id": b, "dir": "left"})[1]
    assert [t["id"] for t in doc["tabs"]] == [b, a]
    doc = req(srv, "POST", PATH, auth(), {"op": "rename", "id": b, "label": "Bow\x07"})[1]
    assert doc["tabs"][0]["label"] == "Bow"
    doc = req(srv, "POST", PATH, auth(), {"op": "set", "id": a, "follow": False,
                                          "toggles": {"bow": "no"}})[1]
    assert doc["tabs"][1]["follow"] is False and doc["tabs"][1]["toggles"]["bow"] == "no"
    doc = req(srv, "POST", PATH, auth(), {"op": "show", "id": a})[1]
    assert doc["shown"] == a
    doc = req(srv, "POST", PATH, auth(), {"op": "close", "id": a})[1]
    assert [t["id"] for t in doc["tabs"]] == [b] and doc["shown"] == b
    # refused changes: a 400 with the player's sentence, nothing changed
    for bad in ({"op": "fly"}, {"op": "close", "id": "k99"},
                {"op": "move", "id": b, "dir": "up"},
                {"op": "set", "id": b, "result": {"template": "x", "at": 1}},
                {"op": "add", "item_text": "Rarity: Rare"}):
        status, doc = req(srv, "POST", PATH, auth(), bad)
        assert status == 400 and isinstance(doc["error"], str), bad
    assert [t["id"] for t in req(srv, "GET", PATH, auth())[1]["tabs"]] == [b]
    for _ in range(5):
        req(srv, "POST", PATH, auth(), {"op": "add"})
    status, doc = req(srv, "POST", PATH, auth(), {"op": "add"})
    assert status == 400 and doc["error"] == genstore.FULL_TEXT
