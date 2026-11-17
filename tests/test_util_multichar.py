"""UTIL-MULTICHAR: run history, pace, act splits and deaths keyed by the
character name the player's own Client.txt reports (decision 0037).

Every line and name here is synthetic (invented names); no real log line is
copied. tmp files only."""

import json
import time

from server.al import resume, runhistory
from server.al.core import Core
from server.al.state import MAX_CHARACTERS, SessionState


class Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def gen(area_id, at):
    return {"type": "area_generated", "area_id": area_id, "area_level": 5,
            "seed": "1", "recv_ts": at}


def scene(name, at):
    return {"type": "scene_changed", "scene": name, "recv_ts": at}


def lvl(name, cls, n, at):
    return {"type": "level_up", "character": name, "class": cls, "level": n,
            "recv_ts": at}


def death(name, at):
    return {"type": "death", "character": name, "recv_ts": at}


def interleaved(st):
    """Quill (Monk) plays Acts 1-2, Sable (Witch) starts a new character,
    Quill comes back and opens Act 3, then Sable again."""
    st.apply(gen("G1_1", 1000.0))
    st.apply(lvl("Quill", "Monk", 2, 1010.0))
    st.apply(scene("The Grelwood", 1100.0))
    st.apply(death("Quill", 1110.0))
    st.apply(gen("G2_1", 2000.0))                 # Quill Act 1 = 1000 s
    # character select: Sable, a new level-1 character
    st.apply(lvl("Sable", "Witch", 2, 3000.0))
    st.apply(gen("G1_1", 3010.0))
    st.apply(scene("Clearfell", 3020.0))
    st.apply(death("Sable", 3030.0))
    st.apply(death("Sable", 3040.0))
    st.apply(lvl("Sable", "Witch", 3, 3100.0))
    # back to Quill: his death line switches back (he is a known character)
    st.apply(scene("Ogham Farmlands", 3990.0))
    st.apply(death("Quill", 4000.0))
    st.apply(lvl("Quill", "Monk", 20, 4010.0))
    st.apply(gen("G3_1", 4500.0))                 # Quill Act 2 closes
    # and Sable once more
    st.apply(lvl("Sable", "Witch", 4, 5000.0))
    st.apply(gen("G2_1", 5600.0))                 # Sable Act 1 = 2590 s


def test_two_characters_interleaved_keep_their_own_numbers():
    st = SessionState(clock=Clock(6000.0))
    interleaved(st)
    snap = st.snapshot()
    assert snap["character"] == "Sable" and snap["class"] == "Witch"
    assert snap["level"] == 4 and snap["deaths"] == 2 and snap["level_ups"] == 3
    chars = {c["name"]: c for c in snap["characters"]}
    assert [c["name"] for c in snap["characters"]] == ["Sable", "Quill"]
    assert chars["Sable"]["current"] is True and chars["Quill"]["current"] is False
    assert chars["Quill"]["level"] == 20 and chars["Quill"]["deaths"] == 2
    assert chars["Quill"]["class"] == "Monk" and chars["Quill"]["level_ups"] == 2
    q_rows = chars["Quill"]["acts"]["splits"]
    s_rows = chars["Sable"]["acts"]["splits"]
    assert [r["key"] for r in q_rows] == ["G1", "G2", "G3"]
    assert [r["key"] for r in s_rows] == ["G1", "G2"]
    assert q_rows[0]["time_s"] == 1000.0 and q_rows[1]["time_s"] == 2500.0
    assert s_rows[0]["time_s"] == 2590.0
    # run records stay apart: one per character, own deaths by zone
    rec = st.run_record()
    assert rec["character"] == "Sable" and rec["deaths"] == {"Clearfell": 2}
    q = st.parked_record("Quill")
    assert q["character"] == "Quill" and q["deaths"] == {"The Grelwood": 1, "Ogham Farmlands": 1}
    assert [s["key"] for s in q["splits"]] == ["G1", "G2"]


def test_other_players_never_switch_and_a_configured_character_is_kept():
    st = SessionState(clock=Clock(9000.0))
    st.apply(lvl("Quill", "Monk", 5, 1000.0))
    st.apply({"type": "player_joined_area", "character": "Visitor", "recv_ts": 1100.0})
    st.apply(lvl("Visitor", "Ranger", 40, 1200.0))
    st.apply(death("Visitor", 1300.0))
    snap = st.snapshot()
    assert snap["character"] == "Quill" and len(snap["characters"]) == 1
    # an unknown name's death never switches (a party member)
    st.apply(death("Stranger", 1400.0))
    assert st.snapshot()["character"] == "Quill"
    fixed = SessionState(character="Quill", clock=Clock(9000.0))
    fixed.apply(lvl("Sable", "Witch", 3, 1000.0))
    assert fixed.snapshot()["character"] == "Quill"
    assert len(fixed.snapshot()["characters"]) == 1


def test_character_cap():
    st = SessionState(clock=Clock(99999.0))
    for i in range(MAX_CHARACTERS + 4):
        st.apply(lvl(f"Char{i}", "Monk", 2, 1000.0 + i))
    chars = st.snapshot()["characters"]
    assert len(chars) == MAX_CHARACTERS
    assert chars[0]["name"] == f"Char{MAX_CHARACTERS + 3}"
    assert "Char0" not in [c["name"] for c in chars]


def test_pace_is_per_character():
    st = SessionState(clock=Clock(10000.0))
    st.apply(lvl("Quill", "Monk", 10, 1000.0))
    st.apply(lvl("Quill", "Monk", 11, 1300.0))
    st.apply(lvl("Sable", "Witch", 2, 2000.0))
    snap = st.snapshot()
    sable = snap["characters"][0]
    quill = snap["characters"][1]
    assert sable["pace"]["per_level_s"] is None
    assert quill["pace"]["per_level_s"] == 300.0
    st.apply(lvl("Quill", "Monk", 12, 2600.0))
    assert st.snapshot()["pace"]["per_level_s"] == 800.0


# -- restart resume

_N = [0]


def L(body, ts, tag="INFO"):
    _N[0] += 1
    return f"{ts} {_N[0]} 1a2b3c4d [{tag} Client 4242] {body}"


def G(area_id, ts):
    return L(f'Generating level 5 area "{area_id}" with seed 77', ts=ts, tag="DEBUG")


LOG = ["2026/11/16 20:00:00 ***** LOG FILE OPENING *****",
       G("G1_1", "2026/11/16 20:10:00"),
       L(": Quill (Monk) is now level 2", "2026/11/16 20:11:00"),
       L("[SCENE] Set Source [The Grelwood]", "2026/11/16 20:12:00"),
       L(": Quill has been slain.", "2026/11/16 20:13:00"),
       G("G2_1", "2026/11/16 20:30:00"),
       L(": Visitor has joined the area.", "2026/11/16 20:31:00"),
       L(": Visitor (Ranger) is now level 50", "2026/11/16 20:32:00"),
       L(": Sable (Witch) is now level 2", "2026/11/16 21:00:00"),
       G("G1_1", "2026/11/16 21:01:00"),
       L("[SCENE] Set Source [Clearfell]", "2026/11/16 21:02:00"),
       L(": Sable has been slain.", "2026/11/16 21:03:00"),
       G("G1_2", "2026/11/16 21:04:00"),
       L(": Quill (Monk) is now level 21", "2026/11/16 21:30:00"),
       G("G3_1", "2026/11/16 21:40:00")]


def _write(path, lines):
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    return path


def test_restart_rebuilds_every_character(tmp_path):
    now = time.mktime(time.strptime("2026-11-16T22:00:00", "%Y-%m-%dT%H:%M:%S"))
    r = resume.scan(_write(tmp_path / "Client.txt", LOG))
    st = SessionState(clock=Clock(now))
    st.restore(resume.state_fields(r, now=now))
    snap = st.snapshot()
    assert snap["character"] == "Quill" and snap["level"] == 21
    assert snap["deaths"] == 1
    chars = {c["name"]: c for c in snap["characters"]}
    assert set(chars) == {"Quill", "Sable"}  # the visitor is no character
    assert [x["key"] for x in chars["Quill"]["acts"]["splits"]] == ["G1", "G2", "G3"]
    assert [x["key"] for x in chars["Sable"]["acts"]["splits"]] == ["G1"]
    assert chars["Sable"]["deaths"] == 1 and chars["Sable"]["level"] == 2
    assert st.run_record()["deaths"] == {"The Grelwood": 1}
    assert st.parked_record("Sable")["deaths"] == {"Clearfell": 1}
    # a second restart over the same log gives the same numbers
    st2 = SessionState(clock=Clock(now))
    st2.restore(resume.state_fields(resume.scan(tmp_path / "Client.txt"), now=now))
    assert st2.snapshot()["characters"] == snap["characters"]


def test_restart_saves_each_character_once(tmp_path):
    now = time.mktime(time.strptime("2026-11-16T22:00:00", "%Y-%m-%dT%H:%M:%S"))
    log = _write(tmp_path / "Client.txt", LOG)
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False,
                config_path=tmp_path / "cfg" / "local.json")
    try:
        core.state.restore(resume.state_fields(resume.scan(log), now=now))
        assert core.tick_history() is True
        assert core.tick_history() is False  # nothing new: no write
        doc = json.loads((tmp_path / "rt" / runhistory.FILE_NAME).read_text(encoding="ascii"))
        assert set(doc["characters"]) == {"Quill"}  # Sable has no closed split yet
        view = core.state.snapshot()["run_history"]
        assert view["best"][0]["key"] == "G1" and "Sable" in view["by_character"]
        # clearing keeps the parked character from being saved again at once
        core.set_history(clear=True)
        assert core.history.runs == []
    finally:
        core.close()


# -- migration and per-character storage

def test_schema_1_file_is_migrated(tmp_path):
    p = tmp_path / runhistory.FILE_NAME
    old = {"schema": 1, "runs": [
        {"started_at": 1000.0, "character": "Quill", "class": "Monk", "finished": False,
         "deaths": {"Grelwood": 2},
         "splits": [{"key": "G1", "label": "Act 1", "time_s": 900.0}]},
        {"started_at": 5000.0, "character": "Sable", "class": "Witch", "finished": False,
         "deaths": {"Clearfell": 1},
         "splits": [{"key": "G1", "label": "Act 1", "time_s": 600.0}]},
        {"started_at": 9000.0, "character": None, "deaths": {"Ogham": 1}, "splits": []}]}
    p.write_text(json.dumps(old), encoding="ascii")
    h = runhistory.RunHistory(p)
    doc = json.loads(p.read_text(encoding="ascii"))
    assert doc["schema"] == 2 and set(doc["characters"]) == {"Quill", "Sable", ""}
    assert len(h.runs) == 3
    # bests are per character: Sable's faster Act 1 is not Quill's best
    cur = {"started_at": 20000.0, "character": "Quill", "deaths": {},
           "splits": [{"key": "G1", "label": "Act 1", "time_s": 1000.0}]}
    v = h.view(cur)
    assert v["best"][0]["best_s"] == 900.0 and v["best"][0]["delta_s"] == 100.0
    assert v["deaths_by_zone"] == [{"zone": "Grelwood", "deaths": 2}]
    assert h.view(character="Sable")["best"][0]["best_s"] == 600.0
    # a second load is a no-op
    assert runhistory.migrate(p) is False


def test_storage_caps_characters_and_runs(tmp_path):
    p = tmp_path / runhistory.FILE_NAME
    h = runhistory.RunHistory(p)
    for c in range(runhistory.MAX_CHARACTERS + 3):
        for i in range(3):
            h.record({"character": f"C{c}", "started_at": 100000.0 * c + 1000.0 * i,
                      "deaths": {}, "splits": [{"key": "G1", "label": "Act 1",
                                                "time_s": 100.0}]})
    doc = json.loads(p.read_text(encoding="ascii"))
    assert len(doc["characters"]) == runhistory.MAX_CHARACTERS
    assert "C0" not in doc["characters"]
    assert len(h.characters()) == runhistory.MAX_CHARACTERS
