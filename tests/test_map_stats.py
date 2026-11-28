"""UTIL-MAP-STATS: per-map stats by map area id next to the map ladder
(research 0064 G5): runs, deaths, median time and last run per area id
from the same run records (decision 0036 bounds, cleared by Clear run
history), and the current map's line on the map context card.

Every line here is synthetic (invented names); no real log line is copied."""

import json
import time

from server.al import mapladder, mapstats, playcards, runs
from server.al.core import Core
from server.al.text import mapstats as text

_N = [0]


def L(body, ts, tag="INFO"):
    _N[0] += 1
    return f"{ts} {_N[0]} 1a2b3c4d [{tag} Client 4242] {body}"


def G(area_id, ts, level=65, seed=77):
    return L(f'Generating level {level} area "{area_id}" with seed {seed}',
             ts=ts, tag="DEBUG")


def S(name, ts):
    return L(f"[SCENE] Set Source [{name}]", ts=ts)


def HIDE(ts):
    return [G("HideoutFelled", ts, 1, 1), S("Felled Hideout", ts)]


OPEN = "2026/11/16 20:00:00 ***** LOG FILE OPENING *****"

# Two maps run twice each: Crypt 5:00 (1 death) and 7:00, Bog 4:00 (2
# deaths), then Bog again, open, the player inside it.
FIXTURE = ([OPEN, L(": Quill (Witch) is now level 80", "2026/11/16 20:30:00")]
           + HIDE("2026/11/16 20:59:00")
           + [G("MapCrypt", "2026/11/16 21:00:00", 65, 11),
              S("Crypt", "2026/11/16 21:00:00"),
              L(": Quill has been slain.", "2026/11/16 21:02:00")]
           + HIDE("2026/11/16 21:05:00")
           + [G("MapBog", "2026/11/16 21:10:00", 66, 12),
              S("Bog", "2026/11/16 21:10:00"),
              L(": Quill has been slain.", "2026/11/16 21:11:00"),
              L(": Quill has been slain.", "2026/11/16 21:12:00")]
           + HIDE("2026/11/16 21:14:00")
           + [G("MapCrypt", "2026/11/16 21:20:00", 65, 13),
              S("Crypt", "2026/11/16 21:20:00")]
           + HIDE("2026/11/16 21:27:00")
           + [G("MapBog", "2026/11/16 21:30:00", 66, 14),
              S("Bog", "2026/11/16 21:30:00")])


def _write(path, lines):
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    return path


def _epoch(ts):
    return time.mktime(time.strptime(ts, "%Y/%m/%d %H:%M:%S"))


def _wait(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


def _core(tmp_path):
    log = _write(tmp_path / "Client.txt", FIXTURE)
    core = Core(runtime=tmp_path / "rt", config_path=tmp_path / "local.json",
                log_path=str(log), poll_s=0.02, character="")
    core.record_consent(True)
    assert _wait(lambda: core.state.snapshot()["tailer"]["reading"])
    assert _wait(lambda: core.state.snapshot()["maps"]["count"] == 4)
    return core


def _by(areas):
    return {a["area_id"]: a for a in areas}


# -- the fixture log, through the core ---------------------------------------

def test_fixture_log_of_two_maps_run_twice_each(tmp_path):
    core = _core(tmp_path)
    try:
        snap = core.state.snapshot()
        st = snap["maps"]["ladder"]["by_map"]
        assert [a["area_id"] for a in st["areas"]] == ["MapBog", "MapCrypt"]
        bog, crypt = _by(st["areas"])["MapBog"], _by(st["areas"])["MapCrypt"]
        assert (crypt["runs"], crypt["deaths"], crypt["median_s"]) == (2, 1, 360.0)
        assert crypt["text"] == "Crypt: 2 runs, 1 death, median 6:00"
        assert crypt["last_at"] == _epoch("2026/11/16 21:20:00")
        # the open Bog run counts as a run, not into the median
        assert (bog["runs"], bog["deaths"], bog["median_s"]) == (2, 2, 240.0)
        assert bog["here"] == "2 runs here, median 4:00, 2 deaths"
        assert st["text"] == ("This session: 2 maps. Median time counts "
                              "finished runs.")
        # run history on: the saved sessions carry the same table
        core.tick_history()
        snap = core.state.snapshot()
        all_st = snap["maps"]["ladder_all"]["by_map"]
        assert [(a["area_id"], a["runs"], a["deaths"]) for a in all_st["areas"]] == [
            ("MapBog", 2, 2), ("MapCrypt", 2, 1)]
        assert all_st["text"].startswith("All saved sessions: 2 maps.")
        # one table in the snapshot: the session copy is left out
        # (mapstats.publish_once, the 8 KB maps key budget)
        assert "by_map" not in snap["maps"]["ladder"]
        # the map context card shows this map's line, from the saved table
        block = playcards.context_view(snap)["map"]
        texts = [r["text"] for r in block["rows"]]
        assert "2 runs here, median 4:00, 2 deaths" in texts
        assert texts.index("2 runs here, median 4:00, 2 deaths") == 1
        assert len(block["rows"]) <= playcards.CONTEXT_ROWS
    finally:
        core.close()


def test_saved_table_survives_a_restart_and_clear_empties_it(tmp_path):
    core = _core(tmp_path)
    try:
        core.tick_history()
    finally:
        core.close()
    saved = mapladder.load(tmp_path / "rt" / mapladder.FILE_NAME)
    assert sorted(r["area_id"] for r in saved["Quill"]) == [
        "MapBog", "MapCrypt", "MapCrypt"]
    lad = mapladder.MapLadder(tmp_path / "rt" / mapladder.FILE_NAME)
    view = lad.view("Quill", [])
    assert [(a["area_id"], a["runs"]) for a in view["by_map"]["areas"]] == [
        ("MapCrypt", 2), ("MapBog", 1)]
    lad.clear()
    view = lad.view("Quill", [])
    assert view["by_map"]["areas"] == []
    assert view["by_map"]["empty_text"] == text.EMPTY_TEXT


# -- the view ---------------------------------------------------------------------

def _row(aid, at, t, deaths=0, done=True):
    return {"area_id": aid, "opened_at": at, "time_s": t, "deaths": deaths,
            "done": done, "area_level": 70}


def test_table_counts_runs_deaths_median_last_newest_first():
    st = mapstats.table([_row("MapCrypt", 100.0, 300.0, 1),
                         _row("MapBog", 200.0, 100.0),
                         _row("MapCrypt", 300.0, 500.0, 2),
                         _row("MapCrypt", 400.0, 9999.0, done=False)], "This session")
    crypt, bog = st["areas"]
    assert crypt["area_id"] == "MapCrypt" and crypt["runs"] == 3
    assert crypt["deaths"] == 3 and crypt["median_s"] == 400.0
    assert crypt["last_at"] == 400.0 and crypt["median_text"] == "6:40"
    assert bog["runs"] == 1 and bog["median_text"] == "1:40"


def test_table_skips_bad_rows_and_is_bounded():
    rows = [_row(f"MapZ{i:03d}", float(i), 60.0) for i in range(mapstats.MAX_AREAS + 9)]
    rows += [None, {"area_id": ""}, {"area_id": 5}, _row("MapX", "x", -1, deaths=True)]
    st = mapstats.table(rows, "This session")
    assert len(st["areas"]) == mapstats.MAX_AREAS
    # newest first; a map with no open time sorts after every timed one
    assert st["areas"][0]["area_id"] == f"MapZ{mapstats.MAX_AREAS + 8:03d}"
    assert "MapX" not in {a["area_id"] for a in st["areas"]}
    assert st["text"].startswith(f"This session: {mapstats.MAX_AREAS + 10} maps.")


def test_unfinished_map_has_no_median_and_says_so():
    st = mapstats.table([_row("MapBog", 1.0, 50.0, done=False)], "This session")
    (bog,) = st["areas"]
    assert bog["median_s"] is None
    assert bog["text"] == "Bog: 1 run, 0 deaths, no finished run yet"
    assert bog["here"] == "1 run here, 0 deaths"


def test_empty_table_says_so():
    st = mapstats.table([], "This session")
    assert st == {"areas": [], "text": "", "empty_text": text.EMPTY_TEXT}


def test_area_name_matches_runs_map_name():
    for aid in ("MapSunTemple", "MapBog", "Map_Old_Fort", "Map", "", None):
        assert mapstats.area_name(aid) == runs.map_name(aid, None)


def test_here_prefers_the_saved_table_and_misses_cleanly():
    a = {"area_id": "MapBog", "here": "x"}
    maps = {"ladder": {"by_map": {"areas": [dict(a, here="session")]}},
            "ladder_all": {"by_map": {"areas": [a]}}}
    assert mapstats.here(maps, "MapBog")["here"] == "x"
    assert mapstats.here({"ladder": maps["ladder"], "ladder_all": None},
                         "MapBog")["here"] == "session"
    assert mapstats.here(maps, "MapCrypt") is None
    assert mapstats.here(None, "MapBog") is None and mapstats.here(maps, None) is None


def test_context_card_has_no_line_on_a_first_run():
    snap = {"area_id": "MapBog", "maps": {
        "count": 1, "current": {"name": "Bog", "area_level": 66, "time_s": 10.0,
                                "deaths": 0, "inside": True},
        "ladder": {"by_map": mapstats.table([_row("MapBog", 1.0, 10.0, done=False)],
                                            "This session")}}}
    rows = playcards.context_view(snap)["map"]["rows"]
    assert not any("here" in r["text"] for r in rows)


# -- words: every sentence pinned exactly (copy sheet mapstats.md) -------------

def test_every_sentence_is_pinned_exactly():
    assert text.EMPTY_TEXT == "No maps yet. Each map shows here by itself as you play it."
    assert text.MEDIAN_NOTE == "Median time counts finished runs."
    assert text.head_text(1, "This session") == (
        "This session: 1 map. Median time counts finished runs.")
    assert text.head_text(3, "All saved sessions") == (
        "All saved sessions: 3 maps. Median time counts finished runs.")
    assert text.row_text("Sun Temple", 3, 1, "6:30") == (
        "Sun Temple: 3 runs, 1 death, median 6:30")
    assert text.row_text("Bog", 1, 2, "") == "Bog: 1 run, 2 deaths, no finished run yet"
    assert text.here_text(3, 1, "6:30") == "3 runs here, median 6:30, 1 death"
    assert text.here_text(2, 0, "") == "2 runs here, 0 deaths"


def test_copy_sheet_holds_every_template():
    from pathlib import Path
    sheet = (Path(__file__).resolve().parents[1] / "docs" / "design" / "copy"
             / "mapstats.md").read_text(encoding="ascii")
    flat = " ".join(sheet.split())
    for words in ("No maps yet. Each map shows here by itself as you play it.",
                  "Median time counts finished runs.", "no finished run yet",
                  "runs here, median", ", last run <time>", "By map name"):
        assert words in flat, words


def test_context_line_fits_the_row_cap():
    longest = text.here_text(mapstats.MAX_COUNT, mapstats.MAX_COUNT, "99:59:59")
    assert len(longest) <= playcards.CAP_ROW
    assert json.dumps(longest).isascii()
