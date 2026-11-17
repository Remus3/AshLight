"""LANG-GUARD (research 0032 section 4, ruling K, decision 0040): synthetic
log lines only. English -> no notice; localised scene names or non-ASCII
system lines x3 -> notice; English evidence -> clears."""

from server.al import langguard, parser
from server.al.core import Core
from server.al.state import SessionState
from server.al.theorycraft import item

TABLE = {"act1": [{"id": "G1_1", "name": "The Riverbank", "level": 1, "town": False},
                  {"id": "G1_town", "name": "Clearfell Encampment", "level": 15,
                   "town": True},
                  {"id": "G1_2", "name": "Clearfell", "level": 2, "town": False}]}
PRE = "2026/11/17 10:00:00 100 2a3b4c5d [INFO Client 5150] "


def lines(*bodies):
    return [PRE + b for b in bodies]


def load(area, scene):
    return lines(f'Generating level 1 area "{area}" with seed 1', "[SCENE] Set Source [(null)]",
                 f"[SCENE] Set Source [{scene}]")


def state_fed(text_lines):
    st = SessionState(clock=lambda: 1000.0)
    st.set_zone_table(TABLE)
    for ln in text_lines:
        ev = parser.parse_line(ln)
        if ev is not None:
            st.apply(ev)
    return st


def test_english_loads_give_no_notice():
    st = state_fed(load("G1_1", "The Riverbank") + load("G1_town", "Clearfell Encampment")
                   + load("G1_2", "Clearfell"))
    v = st.snapshot()["lang"]
    assert v["verdict"] == langguard.ENGLISH and v["text"] is None


def test_unknown_before_any_evidence():
    st = state_fed(load("G1_1", "The Riverbank")[:1])
    assert st.snapshot()["lang"]["verdict"] == langguard.UNKNOWN


def test_three_localised_loads_show_the_notice():
    two = load("G1_1", "Das Flussufer") + load("G1_town", "Lager von Clearfell")
    st = state_fed(two)
    assert st.snapshot()["lang"]["verdict"] == langguard.UNKNOWN  # 2 strikes only
    st = state_fed(two + load("G1_2", "Clearfell-Wald"))
    v = st.snapshot()["lang"]
    assert v["verdict"] == langguard.NON_ENGLISH
    assert "Level, deaths, whispers, trade requests and the item check stay" in v["text"]
    assert "Zone, act and map times still work" in v["text"]
    assert "broken" not in v["text"].lower()


def test_non_ascii_system_lines_strike():
    st = state_fed(lines(": Cinderwisp (Wiedzma) ma teraz poziom 2 \u0142",
                         ": \u0412\u044b \u0432\u043e\u0448\u043b\u0438",
                         ": \ub808\ubca8 3"))
    assert st.snapshot()["lang"]["verdict"] == langguard.NON_ENGLISH


def test_chat_and_npc_text_never_strike():
    st = state_fed(lines("#Chatterbox: \u043f\u0440\u0438\u0432\u0435\u0442",
                         "#Other: \u043f\u0440\u0438\u0432\u0435\u0442",
                         "Riverside Miller: \u043f\u0440\u0438\u0432\u0435\u0442",
                         "@From Friend: \u043f\u0440\u0438\u0432\u0435\u0442"))
    assert st.snapshot()["lang"]["verdict"] == langguard.UNKNOWN


def test_english_evidence_clears_and_resets():
    bad = (load("G1_1", "Das Flussufer") + load("G1_town", "Lager")
           + load("G1_2", "Wald"))
    st = state_fed(bad + lines(": Cinderwisp (Sorceress) is now level 2"))
    assert st.snapshot()["lang"]["verdict"] == langguard.ENGLISH
    # the count restarts: two strikes after evidence are not enough
    st = state_fed(bad + load("G1_1", "The Riverbank") + load("G1_1", "X") + load("G1_2", "Y"))
    assert st.snapshot()["lang"]["verdict"] == langguard.ENGLISH


def test_ids_without_the_table_and_transient_scenes_never_strike():
    st = SessionState(clock=lambda: 1000.0)  # no snapshot table
    for ln in (load("G1_1", "Das Flussufer") * 3
               + lines("[SCENE] Set Source [(unknown)]", "[SCENE] Set Source [Act 1]")):
        st.apply(parser.parse_line(ln))
    assert st.snapshot()["lang"]["verdict"] == langguard.UNKNOWN


def test_scene_compare_ignores_case_and_space():
    st = state_fed(load("G1_1", "the riverbank "))
    assert st.snapshot()["lang"]["verdict"] == langguard.ENGLISH


def test_item_warning_reuses_the_wording():
    parsed = item.parse("Seltenheit: Selten\nIrgendwas")
    assert any(langguard.ITEM_HINT in w for w in parsed.warnings)


def test_diag_shows_the_same_verdict(tmp_path):
    core = Core(runtime=tmp_path, tail=False)
    core.state.set_zone_table(TABLE)
    for ln in load("G1_1", "A") + load("G1_town", "B") + load("G1_2", "C"):
        core.feed_line(ln)
    core.tick_diag(force=True)
    row = {r["id"]: r for r in core.state.snapshot()["diag"]["checks"]}["language"]
    assert row["status"] == "note" and "still work" in row["detail"]
    core.feed_line(lines(": Cinderwisp (Sorceress) is now level 2")[0])
    core.tick_diag(force=True)
    row = {r["id"]: r for r in core.state.snapshot()["diag"]["checks"]}["language"]
    assert row["status"] == "pass"
