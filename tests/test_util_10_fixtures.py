"""UTIL-1.0-FIXTURES (area-util batch 8): the whole Client.txt pipeline on a
sanitized, synthetic PoE2 1.0-shaped log (tests/fixtures/client_10_shapes.txt,
research 0021). Act 5 / 6 ids in the G5_ / G6_ style, an unknown-prefix
return-to-Oriath id, an unknown ascendancy, invented league system lines and
endgame maps; every 1.0 id is a GUESS (marked in the fixture). Acts, the
zone guide, maps, deaths, pace, the session summary and the core-start backward
scan must degrade gracefully: no crash, no act given to an id that is not one,
and a sensible message where the data predates 1.0. The price league
rollover is in tests/test_util_10_ready.py. No network, no game."""

import datetime
import json
import time
from pathlib import Path

from server.al import acts, parser, zoneguide
from server.al.core import Core
from server.al.state import SessionState

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "client_10_shapes.txt"
BASE = datetime.datetime(2026, 11, 16, 19)


def log_lines():
    return [ln for ln in FIXTURE.read_text(encoding="ascii").splitlines()
            if ln and not ln.startswith("#")]


def index_of(needle):
    return next(i for i, ln in enumerate(log_lines()) if needle in ln)


def replay(lines, now_s, table=None, guide=None):
    clock = [0.0]
    st = SessionState(clock=lambda: clock[0])
    if table is not None:
        st.set_zone_table(table)
    if guide is not None:
        st.set_zone_guide(guide=guide)
    for ln in lines:
        ev = parser.parse_line(ln)
        if ev is None:
            continue  # unparsed DEBUG noise: dropped, as live
        ts = ev.get("ts_local")
        t = (datetime.datetime.fromisoformat(ts) - BASE).total_seconds()
        clock[0] = t
        st.apply(dict(ev, recv_ts=t))
    clock[0] = now_s
    return st


def test_fixture_is_ascii_sanitized_and_marks_every_guess():
    raw = FIXTURE.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw
    text = raw.decode("ascii")
    comments = "\n".join(ln for ln in text.splitlines() if ln.startswith("#"))
    for guess_id in ("G5_", "G6_", "Oriath_Return_1", "Map", "Assassin",
                     "mercenaries"):
        assert guess_id in text
    assert comments.count("GUESS") >= 6
    # documentation-range IP only, no real host
    assert "192.0.2." in text


def test_whole_run_degrades_gracefully():
    st = replay(log_lines(), 3700.0)
    s = st.snapshot()
    json.dumps(s)  # plain JSON all the way
    a = s["acts"]
    assert [(r["key"], r["time_s"], r["partial"]) for r in a["splits"]] == [
        ("G4", 594.0, True), ("G5", 1200.0, False), ("G6", 1320.0, False)]
    assert a["finished"] is True and a["current"] is None
    m = s["maps"]
    assert m["count"] == 2 and m["done"] == 1
    assert m["recent"] == [{"name": "Stronghold Siege", "area_level": 65,
                            "time_s": 180.0 + 180.0, "deaths": 1}]
    assert m["current"]["name"] == "Ashen Fields"
    assert [r["text"] for r in s["death_recap"]["recent"]] == [
        "Died in Stronghold Siege (area level 65) at level 50, 3:00 into the zone.",
        "Died in Return to Oriath (area level 52) at level 50, 4:00 into the zone.",
        "Died in Ashen Causeway (area level 45) at level 44, 4:00 into the zone.",
    ]
    assert s["deaths"] == 3
    assert s["class"] == "Assassin" and s["level"] == 51
    assert s["pace"]["text"] == ("Pace: about 7:51 a level over the last 7, "
                                 "7.8 levels an hour.")
    assert "zone_note" not in s  # one guide file (DATA-GUIDE-MERGE)


def test_unknown_prefix_after_act_6_opens_no_act():
    """Return to Oriath with a non-G6_ id: no new split, no act label of its
    own; the open Act 6 split keeps counting (acts.py rule for unknown ids)."""
    cut = index_of('"Oriath_Return_1"') + 2
    s = replay(log_lines()[:cut], 2450.0).snapshot()
    a = s["acts"]
    assert [r["key"] for r in a["splits"]] == ["G4", "G5", "G6"]
    assert a["current"] == "G6" and a["splits"][-1]["current"] is True
    assert s["zone"] == "Return to Oriath"
    assert s["zone_guide"] is None
    assert acts.act_of("Oriath_Return_1") is None


def test_zone_notes_fall_back_and_stay_empty_for_new_acts():
    """DATA-GUIDE-MERGE: the one guide file. A zone it does not name gets
    its act default; an act it has no table for (Acts 5-6 before 1.0) gets
    no guide and no crash; the snapshot has no zone_note key."""
    guide = zoneguide.load()
    lines = log_lines()
    s = replay(lines[:index_of('"G4_4"') + 2], 10.0, guide=guide).snapshot()
    g = s["zone_guide"]
    assert "zone_note" not in s
    assert g["kind"] == "campaign" and g["zone"] == "Shore of Echoes"
    assert g["objective"] == guide["acts"]["G4"]["default"]   # Act 4 default
    s = replay(lines[:index_of('"G5_1"') + 2], 610.0, guide=guide).snapshot()
    assert s["zone_guide"] is None             # no Act 5 entries yet: none, no crash
    s = replay(lines[:index_of('"G6_1"') + 2], 1810.0, guide=guide).snapshot()
    assert s["zone_guide"] is None


OLD_AREAS = {  # a pre-1.0 world_areas snapshot: Acts 1-4 only
    "G4_4": {"name": "Shore of Echoes", "area_level": 42, "is_town": False},
    "G1_1": {"name": "The Riverbank", "area_level": 1, "is_town": False},
}


def test_pre_10_zone_table_says_act_5_levels_are_missing(tmp_path):
    p = tmp_path / acts.FILE_NAME
    p.write_text(json.dumps(OLD_AREAS), encoding="utf-8")
    table = acts.load_table(p)
    lines = log_lines()
    a = replay(lines[:index_of('"G4_4"') + 2], 10.0, table).snapshot()["acts"]
    assert a["zones_act"] == "Act 4" and a["act_levels_text"] == ""
    a = replay(lines[:index_of('"G5_1"') + 2], 610.0, table).snapshot()["acts"]
    assert a["current"] == "G5" and a["zones"] == [] and a["zones_act"] is None
    assert a["act_levels_text"] == (
        "Zone levels for Act 5 aren't downloaded yet. They show here once the "
        "game data has them. AshLight fetches newer game data by itself, at "
        "most once a day, while web data is on.")
    # in a map the campaign table is off and nothing is claimed
    a = replay(lines, 3700.0, table).snapshot()["acts"]
    assert a["current"] is None and a["act_levels_text"] == ""


def test_session_summary_closes_on_the_next_launch():
    lines = log_lines() + ["2026/11/16 21:00:00 ***** LOG FILE OPENING *****"]
    s = replay(lines, 3700.0).snapshot()
    card = s["session_summary"]
    assert card["reason"] == "game_closed"
    assert card["maps"] == 2 and card["deaths"] == 3
    assert card["level_to"] == 51
    json.dumps(card)


def _wait(pred, t=5.0):
    end = time.time() + t
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


def _core(tmp_path, lines):
    log = tmp_path / "Client.txt"
    log.write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii"))
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.02,
                character="", config_path=tmp_path / "local.json")
    core.record_consent(True)
    assert _wait(lambda: core.state.snapshot()["tailer"]["reading"])
    return core


def test_core_start_rebuilds_the_10_run_from_the_log(tmp_path):
    core = _core(tmp_path, log_lines())
    try:
        s = core.state.snapshot()
        assert [(r["key"], r["time_s"]) for r in s["acts"]["splits"]] == [
            ("G4", 594.0), ("G5", 1200.0), ("G6", 1320.0)]
        assert s["maps"]["count"] == 2
        assert s["maps"]["recent"][0]["time_s"] == 360.0
        assert len(s["death_recap"]["recent"]) == 3
        assert s["class"] == "Assassin" and s["deaths"] == 3
    finally:
        core.close()


def test_core_start_mid_run_in_an_unknown_zone_claims_no_act(tmp_path):
    lines = log_lines()
    start = index_of('"Oriath_Return_1"')
    cut = lines[:1] + lines[start:start + 3]   # marker, unknown zone, a death
    core = _core(tmp_path, cut)
    try:
        s = core.state.snapshot()
        a = s["acts"]
        assert a["splits"] == [] and a["current"] is None
        assert a["zones"] == [] and a["act_levels_text"] == ""
        assert s["zone"] == "Return to Oriath" and s["zone_guide"] is None
        assert s["death_recap"]["recent"][0]["text"].startswith(
            "Died in Return to Oriath (area level 52)")
        assert s["maps"]["count"] == 0
    finally:
        core.close()
