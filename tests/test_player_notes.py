"""PLAY-F-186A (decision 0074): the player's own notes.

One plain-text note per zone and character in one bounded runtime file
(server/al/playernotes.py), written only by the token route POST
/api/player-note on the player's Save, published as snapshot
`player_note` for the zone being played and shown as the last row of the
Play view's guide mode ('Your note: ...', server/al/playcards.py).

Every runtime file goes to tmp_path; no running AshLight is touched.
"""

import http.client
import json
import os
import threading
from pathlib import Path

import pytest

from server.al import hotreload, jsonfile
from server.al import http as al_http
from server.al import playcards as pc
from server.al import playernotes as pn
from server.al import playview as pv
from server.al import zoneguide
from server.al.text import playernotes as words
from server.al.core import Core
from server.al.state import SessionState

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "n" * 48
NOW = 1_800_000_000.0


def _enter(st, area_id="G1_2", scene="Clearfell", character="Ash", level=4):
    if character:
        st.apply({"type": "level_up", "character": character, "class": "Monk",
                  "level": level})
    st.apply({"type": "area_generated", "area_id": area_id, "area_level": 2})
    st.apply({"type": "scene_changed", "scene": scene, "is_hideout": False})


def _store(tmp_path, **kw):
    return pn.PlayerNotes(tmp_path / pn.FILE_NAME, registry=hotreload.Registry(), **kw)


# -- cleaning ------------------------------------------------------------------

def test_text_is_plain_and_never_cut():
    assert pn.clean_text("  Take the\nleft   path\t first ") == "Take the left path first"
    assert pn.clean_text("") == "" and pn.clean_text("   ") == ""
    assert pn.clean_text("x" * pn.MAX_NOTE) == "x" * pn.MAX_NOTE
    assert pn.clean_text("Boss hits hard \u00e9") == "Boss hits hard \u00e9"
    for bad in ("x" * (pn.MAX_NOTE + 1), "bell\x07", "zero\u200bwidth", None, 3, b"x"):
        with pytest.raises(pn.NoteError):
            pn.clean_text(bad)
    for bad in ("", "../x", "G1 2", "a" * 65, None):
        with pytest.raises(pn.NoteError):
            pn.clean_area(bad)
    for bad in ("", " Ash", "A" * 65, "A\x00", None):
        with pytest.raises(pn.NoteError):
            pn.clean_name(bad)


# -- the store -----------------------------------------------------------------

def test_save_reads_back_per_zone_and_character(tmp_path):
    s = _store(tmp_path, clock=lambda: NOW)
    assert s.note("Ash", "G1_2") is None
    assert s.save("Ash", "G1_2", "Grelwood exit is north") == {
        "area_id": "G1_2", "text": "Grelwood exit is north", "at": int(NOW)}
    assert s.note("Ash", "G1_2")["text"] == "Grelwood exit is north"
    assert s.note("Bee", "G1_2") is None and s.note("Ash", "G1_3") is None
    doc = json.loads((tmp_path / pn.FILE_NAME).read_bytes())
    assert doc == {"schema": 1, "notes": [{"character": "Ash", "area_id": "G1_2",
                                           "text": "Grelwood exit is north",
                                           "at": int(NOW)}]}
    assert jsonfile.bak_path(tmp_path / pn.FILE_NAME).is_file()
    # a new store reads it back; an empty Save removes it
    s2 = _store(tmp_path)
    assert s2.note("Ash", "G1_2")["text"] == "Grelwood exit is north"
    assert s2.save("Ash", "G1_2", "  ") is None
    assert s2.note("Ash", "G1_2") is None
    assert json.loads((tmp_path / pn.FILE_NAME).read_bytes())["notes"] == []


def test_the_file_never_exceeds_its_bounds(tmp_path, monkeypatch):
    # 339 saves are two durable writes each (file and .bak); the fsync is
    # disk-bound (about half the call time when quiet, and well past the
    # 1.5 s slow limit under parallel disk load). This test checks bounds,
    # not durability (tests/test_jsonfile.py has that), so the fsync is
    # counted, not run.
    synced = []
    monkeypatch.setattr(jsonfile.os, "fsync", lambda fd: synced.append(fd))
    s = _store(tmp_path)
    long = "y" * pn.MAX_NOTE
    for i in range(pn.MAX_ZONES + 25):
        s.save(f"Char{i % 3}", f"Z{i}", long, now=1000 + i)
    path = tmp_path / pn.FILE_NAME
    doc = json.loads(path.read_bytes())
    assert len(doc["notes"]) == pn.MAX_ZONES
    assert all(len(r["text"]) <= pn.MAX_NOTE for r in doc["notes"])
    # the oldest notes left; the newest stays
    assert {r["area_id"] for r in doc["notes"]} == {f"Z{i}" for i in range(25, pn.MAX_ZONES + 25)}
    assert pn.count(s.get()) == pn.MAX_ZONES
    assert len(synced) == 2 * (pn.MAX_ZONES + 25)  # still the durable path
    # characters: at most 12; the one whose newest note is oldest leaves
    for i in range(pn.MAX_CHARACTERS + 2):
        s.save(f"Other{i}", "G1_1", "n", now=5000 + i)
    assert len(s.get()) == pn.MAX_CHARACTERS
    assert "Other13" in s.get() and "Char0" not in s.get()
    # a full worst-case file stays inside the read cap
    worst = {"schema": 1, "notes": [
        {"character": "\U0001f600" * 16 + f"{i:04d}", "area_id": "A" * 60 + f"{i:04d}",
         "text": "\U0001f600" * pn.MAX_NOTE, "at": 2 ** 40} for i in range(pn.MAX_ZONES)]}
    assert len(jsonfile.dumps(worst).encode("ascii")) <= pn.MAX_BYTES


def test_malformed_file_keeps_the_last_good_copy_with_a_note(tmp_path):
    reg = hotreload.Registry()
    path = tmp_path / pn.FILE_NAME
    s = pn.PlayerNotes(path, registry=reg)
    s.save("Ash", "G1_2", "first", now=10)
    assert s.error is None
    for bad in ("{not json", json.dumps({"schema": 2, "notes": []}),
                json.dumps({"schema": 1, "notes": [{"character": "Ash", "area_id": "G1_2",
                                                     "text": "x" * 201, "at": 1}]}),
                json.dumps({"schema": 1, "notes": [
                    {"character": "Ash", "area_id": f"Z{i}", "text": "x", "at": 1}
                    for i in range(pn.MAX_ZONES + 1)]})):
        path.write_text(bad, encoding="utf-8")
        st = os.stat(path)
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
        assert s.note("Ash", "G1_2")["text"] == "first"
        assert s.error and pn.NAME in s.error and "last good copy" in s.error
        assert s.error.endswith(pn.FIX_TAIL)
        assert [n for n in reg.notes() if pn.NAME in n]
    # a good hand edit is taken on its next change and the note clears
    path.write_text(json.dumps({"schema": 1, "notes": [
        {"character": "Ash", "area_id": "G1_2", "text": "edited", "at": 11}]}),
        encoding="utf-8")
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 20_000_000))
    assert s.note("Ash", "G1_2")["text"] == "edited" and s.error is None


def test_malformed_at_start_falls_back_to_the_bak(tmp_path):
    path = tmp_path / pn.FILE_NAME
    _store(tmp_path).save("Ash", "G1_2", "kept", now=10)
    path.write_text("{broken", encoding="utf-8")
    s = _store(tmp_path)
    assert s.error and s.note("Ash", "G1_2")["text"] == "kept"
    assert path.read_text(encoding="utf-8") == "{broken"  # left alone until a Save
    s.save("Ash", "G1_3", "more", now=11)
    assert {r["area_id"] for r in json.loads(path.read_bytes())["notes"]} == {"G1_2", "G1_3"}


def test_a_failed_write_changes_nothing(tmp_path, monkeypatch):
    s = _store(tmp_path)
    s.save("Ash", "G1_2", "first", now=10)

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(pn.jsonfile, "write_json", boom)
    with pytest.raises(OSError):
        s.save("Ash", "G1_2", "second", now=11)
    assert s.note("Ash", "G1_2")["text"] == "first"


# -- the published key and the row ---------------------------------------------

def test_state_publishes_the_note_for_this_zone_and_character_only():
    st = SessionState(clock=lambda: NOW)
    st.set_player_notes({"Ash": {"G1_2": {"text": "Go north", "at": 5}}})
    assert st.snapshot()["player_note"] is None  # no zone yet
    _enter(st)
    assert st.snapshot()["player_note"] == {"area_id": "G1_2", "text": "Go north", "at": 5}
    _enter(st, area_id="G1_3", scene="Mud Burrow")
    assert st.snapshot()["player_note"] is None
    v = st.version
    assert st.set_player_notes({"Ash": {"G1_2": {"text": "Go north", "at": 5}}}) is False
    assert st.version == v
    # another character in the same zone (decision 0038 key)
    bee = SessionState(character="Bee", clock=lambda: NOW)
    bee.set_player_notes({"Ash": {"G1_2": {"text": "Go north", "at": 5}}})
    _enter(bee, character=None)
    assert bee.area_id == "G1_2" and bee.snapshot()["player_note"] is None


def _guide_snap(note=None, area_id="G1_2"):
    doc = zoneguide.load()
    graph = {area_id: {"name": "Clearfell", "waypoint": True, "town": False, "links": []}}
    zg = zoneguide.view(doc, graph, area_id, "Clearfell", False, 4, 2, None)
    snap = {"zone_guide": zg, "area_id": area_id}
    if note is not None:
        snap["player_note"] = {"area_id": area_id, "text": note, "at": 1}
    return snap


def test_guide_mode_shows_the_note_as_the_last_row():
    plain = pc.guide_block(_guide_snap())
    b = pc.guide_block(_guide_snap("Grelwood exit north of the camp"))
    assert b["rows"][-1] == {"kind": "note", "text": "Your note: Grelwood exit north of the camp",
                             "full": "Grelwood exit north of the camp"}
    assert len(b["rows"]) <= pc.CONTEXT_ROWS
    assert b["rows"][:-1] == plain["rows"][:len(b["rows"]) - 1]
    # a long note: one row of at most 52 characters, the whole text in full
    long = "word " * 39 + "end"
    b = pc.guide_block(_guide_snap(long))
    row = b["rows"][-1]
    assert row["kind"] == "note" and len(row["text"]) <= pc.CAP_ROW
    assert row["text"].startswith(pc.NOTE_LEAD) and row["text"].endswith(pv.ELLIPSIS)
    assert row["full"] == pn.clean_text(long)
    one = pc.guide_block(_guide_snap("x" * 200))["rows"][-1]
    assert one["text"].startswith(pc.NOTE_LEAD) and len(one["text"]) <= pc.CAP_ROW
    # composed words stay under the G5 cap (the note is data)
    words = sum(pv.words(t) for t in [b["title"], b["facts"]]
                + [r["text"] for r in b["rows"][:-1]]) + pv.words(pc.NOTE_LEAD)
    assert words - pv.words("Mud Burrow") <= pc.WORDS_CONTEXT
    # a note of another zone (a stale key) shows nothing
    stale = _guide_snap("old")
    stale["area_id"] = "G1_3"
    assert all(r["kind"] != "note" for r in (pc.guide_block(stale) or {"rows": []})["rows"])
    # junk never raises
    for junk in (3, "x", {"text": 5}, {"text": "", "area_id": "G1_2"}):
        snap = _guide_snap()
        snap["player_note"] = junk
        assert all(r["kind"] != "note" for r in pc.guide_block(snap)["rows"])


# -- the core and the route ----------------------------------------------------

@pytest.fixture
def srv(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = al_http.serve(core, TOKEN, port=0, web_root=ROOT / "web",
                           tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def _post(server, body, ctype="text/plain; charset=utf-8", token=TOKEN, path="/api/player-note"):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    h = {"Host": f"127.0.0.1:{server.port}", "Content-Type": ctype}
    if token:
        h["X-AL-Token"] = token
    conn.request("POST", path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, json.loads(data or b"null")


def test_route_needs_the_token_and_plain_text(srv):
    core = srv.core
    assert _post(srv, b"x", token=None)[0] == 401
    assert _post(srv, b"x", token="wrong")[0] == 401
    # nothing known yet: refused, nothing written
    code, doc = _post(srv, b"x")
    assert code == 400 and doc["error"] == pn.NO_CHARACTER
    _enter(core.state)
    for ctype in ("application/json", "text/html", "text/plain; charset=latin-1",
                  "multipart/form-data", ""):
        assert _post(srv, b'"x"', ctype=ctype)[0] == 415, ctype
    assert _post(srv, b"\xff\xfe")[0] == 400
    assert _post(srv, ("x" * 201).encode())[0] == 400
    assert _post(srv, "bell\x07".encode())[0] == 400
    assert _post(srv, b"x" * (al_http.MAX_BODY + 1)) == (413, {"error": words.TOO_BIG})
    assert not (core.runtime / pn.FILE_NAME).exists()
    code, doc = _post(srv, "Grelwood exit north \u00e9".encode("utf-8"))
    assert code == 200 and doc["note"]["text"] == "Grelwood exit north \u00e9"
    assert doc["note"]["area_id"] == "G1_2"
    assert core.state.snapshot()["player_note"]["text"] == "Grelwood exit north \u00e9"
    # ?area= names another zone; a bad one is refused
    code, doc = _post(srv, b"later", path="/api/player-note?area=G1_3")
    assert code == 200 and doc["note"]["area_id"] == "G1_3"
    assert _post(srv, b"x", path="/api/player-note?area=..%2Fx")[0] == 400
    assert _post(srv, b"x", path="/api/player-note?area=A&area=B") == (
        400, {"error": words.ONE_ZONE})
    # an empty Save removes the note
    code, doc = _post(srv, b"", path="/api/player-note?area=G1_3")
    assert code == 200 and doc["note"] is None


def test_note_shows_on_the_next_entry_for_that_character_only(tmp_path):
    core = Core(runtime=tmp_path, tail=False)
    try:
        st = core.state
        _enter(st)
        assert core.save_player_note("Mud Burrow cave first")["area_id"] == "G1_2"
        _enter(st, area_id="G1_3", scene="Mud Burrow")
        assert st.snapshot()["player_note"] is None
        _enter(st)  # the next entry of that zone
        snap = st.snapshot()
        assert snap["player_note"]["text"] == "Mud Burrow cave first"
        rows = (snap["play"]["context"] or {}).get("guide", {}).get("rows", [])
        assert rows and rows[-1]["kind"] == "note"
        assert rows[-1]["text"] == "Your note: Mud Burrow cave first"
        with st._lock:
            st.character = "Bee"  # another character in the same zone
        assert st.snapshot()["player_note"] is None
        # a fresh core reads the file back and publishes it by itself
        core.close()
        core = Core(runtime=tmp_path, tail=False)
        _enter(core.state)
        assert core.state.snapshot()["player_note"]["text"] == "Mud Burrow cave first"
        # a hand edit reaches the snapshot from the tick (hot reload)
        path = tmp_path / pn.FILE_NAME
        path.write_text(json.dumps({"schema": 1, "notes": [
            {"character": "Ash", "area_id": "G1_2", "text": "edited", "at": 3}]}),
            encoding="utf-8")
        st_ = os.stat(path)
        os.utime(path, ns=(st_.st_atime_ns, st_.st_mtime_ns + 10_000_000))
        core.player_notes.watch.get(force=True)  # the registry poll, a minute on
        assert core.state.snapshot()["player_note"]["text"] == "edited"
    finally:
        core.close()


def test_registry_poll_stats_the_file_at_most_once_a_minute(tmp_path, monkeypatch):
    """B3 (tests/test_budget_tick.py): the core tick's registry poll does
    not stat the notes file again inside CHECK_S; a Save is seen at once
    (save() keeps the book), an outside edit after the minute."""
    clock = [100.0]
    reg = hotreload.Registry()
    path = tmp_path / pn.FILE_NAME
    seen = []
    s = pn.PlayerNotes(path, registry=reg, mono=lambda: clock[0], on_change=seen.append)
    s.save("Ash", "G1_2", "mine", now=1)
    assert s.book()["Ash"]["G1_2"]["text"] == "mine"
    stats = []
    real = os.stat

    def counting(p, *a, **k):
        if Path(p) == path:
            stats.append(p)
        return real(p, *a, **k)
    monkeypatch.setattr(hotreload.os, "stat", counting)
    path.write_text(json.dumps({"schema": 1, "notes": [
        {"character": "Ash", "area_id": "G1_2", "text": "outside", "at": 2}]}),
        encoding="utf-8")
    st = real(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    clock[0] += pn.CHECK_S - 1
    reg.poll()
    assert stats == [] and s.book()["Ash"]["G1_2"]["text"] == "mine"
    clock[0] += 1
    reg.poll()
    n = len(stats)  # the due stat, plus the re-read's size check on a change
    assert 1 <= n <= 2 and s.book()["Ash"]["G1_2"]["text"] == "outside"
    assert seen and seen[-1]["Ash"]["G1_2"]["text"] == "outside"
    clock[0] += pn.CHECK_S - 1
    reg.poll()
    assert len(stats) == n


# -- PN-5 / PN-6 (PLAY-F-186B): every sentence pinned exactly -------------------

def test_every_sentence_is_pinned_exactly():
    """The exact-output test the copy sheet docs/design/copy/playernotes.md
    names: every sentence of server/al/text/playernotes.py, word for word,
    and the sheet quotes each one. The sheet and the module are edited in
    both places together."""
    want = {
        "NAME": "Your notes",
        "TEXT_BAD": ("Your note has a character AshLight can't keep. "
                     "Use plain letters, digits and punctuation."),
        "NO_CHARACTER": "AshLight doesn't know your character yet. Enter a zone, then save again.",
        "NO_ZONE": "AshLight doesn't know this zone yet. Enter a zone, then save again.",
        "ONE_ZONE": "Save one zone at a time.",
        "TOO_BIG": "Your note is too long. Shorten it and save again.",
        "BAD_TYPE": "AshLight can't read that note. Try again.",
        "NOTE_SAVE_FAILED": "AshLight couldn't save your note. Try again.",
        "FILE_FORMAT": "the file is not in AshLight's notes format",
        "FILE_ROW": "a note is not in the right form",
        "FILE_TWO": "two notes share one zone",
        "FILE_BIG": "the file is too large",
        "HELD_TAIL": "The last good copy stays in use.",
        "FIX_TAIL": "Fix the file, or save a note to replace it.",
    }
    consts = {k: v for k, v in vars(words).items() if k.isupper() and isinstance(v, str)}
    assert consts == want
    assert words.text_long(200) == "Your note is over 200 characters. Shorten it and save again."
    assert words.file_long(200) == "a note is over 200 characters"
    assert words.file_many(300) == "the file holds more than 300 notes"
    assert words.file_chars(12) == "the file holds notes of more than 12 characters"
    # the store re-exports the same objects
    for k in ("TEXT_BAD", "NO_CHARACTER", "NO_ZONE", "FILE_FORMAT", "FIX_TAIL"):
        assert getattr(pn, k) is getattr(words, k)
    # the copy sheet quotes every sentence (its own line wraps folded)
    sheet = " ".join((ROOT / "docs" / "design" / "copy" / "playernotes.md")
                     .read_text(encoding="ascii").split())
    for text in list(want.values()) + ["Your note is over <n> characters. Shorten it and save again.",
                                       "a note is over <n> characters",
                                       "the file holds more than <n> notes",
                                       "the file holds notes of more than <n> characters"]:
        assert text in sheet, text
    assert "edited in both places together" in sheet
    assert "test_every_sentence_is_pinned_exactly" in sheet
    # PN-5: the route answers in the module's words, none of its own
    src = (ROOT / "server" / "al" / "http.py").read_text(encoding="ascii")
    assert "Save one zone at a time." not in src
    assert "couldn't save your note" not in src and "text/plain (UTF-8) required" not in src
    assert "words.BAD_TYPE" in src and al_http.NOTE_SAVE_FAILED is words.NOTE_SAVE_FAILED
    assert "words.ONE_ZONE" in src and "words.TOO_BIG" in src
