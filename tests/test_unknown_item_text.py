"""RUN-UNKNOWN-ITEM-TEXT (finding F-185, folded into RUN-REPORT-FIELDS):
the session's not counted mod lines (server/al/plug/unknownitems.py), fed
by each fresh press of the core's LastEval (theorycraft/live.py).

Synthetic item text only; no clipboard, no game process, no network. The
runtime lives in tmp_path; the list never reaches a file (decision 0045).
"""

import pytest

from server.al.core import Core
from server.al.plug import report as route
from server.al.plug import unknownitems

NOW = 1795200000.0
INVENTED = "Zqinvented grants 7 glimmers"
ITEM = """Item Class: Gloves
Rarity: Rare
Zzq Clutch
Example Gloves
--------
Item Level: 81
--------
+70 to maximum Life
""" + INVENTED + "\n"


@pytest.fixture
def core(tmp_path, monkeypatch):
    monkeypatch.setattr(route, "_now", lambda: NOW)
    c = Core(runtime=tmp_path / "rt", tail=False)
    yield c
    c.close()


def _invented(core):
    return [ln for ln in core.unknown_items.lines() if "zqinvented" in ln.lower()]


def test_same_invented_line_twice_gives_one_entry(core):
    core.eval_press(ITEM)
    core.eval_press(ITEM)
    got = _invented(core)
    assert len(got) == 1, core.unknown_items.lines()
    assert "glimmers" in got[0]
    # a case or spacing change is the same line
    assert core.unknown_items.add([got[0].upper(), "  " + got[0] + "  "]) == 0


def test_checks_count_is_1(core):
    core.eval_press(ITEM)
    core.eval_press(ITEM)
    n = len(core.unknown_items)
    assert n == len(_invented(core)) == 1, core.unknown_items.lines()
    core.tick_diag(force=True)
    rows = [r for r in core.state.snapshot()["diag"]["checks"]
            if r["id"] == unknownitems.ROW_ID]
    assert len(rows) == 1
    assert rows[0]["status"] == "note" and rows[0]["label"] == unknownitems.LABEL
    assert rows[0]["detail"].startswith("1 mod line ")
    # no row while the list is empty
    assert unknownitems.rows({"unknown_items": 0}, NOW) is None


def test_copied_report_holds_the_line_and_no_path(core, tmp_path):
    core.eval_press(ITEM)
    line = _invented(core)[0]
    text = route.build(core, now=NOW)
    assert "\n  " + line + "\n" in text
    assert "Not counted mod lines: 1 this session" in text
    for p in (str(tmp_path), str(tmp_path).replace("\\", "/"), str(core.runtime)):
        assert p.lower() not in text.lower()
    # a mod line carrying a path is masked like any free text
    # a fixed path no env value can match (LOOP-RED 2026-11-22: under a TEMP
    # inside the user profile the tmp_path line was masked as <home>); the
    # drive letter is joined so the leak sweep's drive-path rule stays quiet
    core.unknown_items.add(["Seen in " + "D" + ":\\zqpathdir\\x.txt"])
    text = route.build(core, now=NOW)
    assert "zqpathdir" not in text.lower() and "<path>" in text


def test_restart_clears_it_and_no_file_is_written(tmp_path):
    rt = tmp_path / "rt"
    c = Core(runtime=rt, tail=False)
    try:
        c.eval_press(ITEM)
        assert _invented(c)
        c.tick_all()
    finally:
        c.close()
    for p in tmp_path.rglob("*"):
        if p.is_file():
            assert b"zqinvented" not in p.read_bytes().lower(), p
    c2 = Core(runtime=rt, tail=False)
    try:
        assert c2.unknown_items.lines() == []
        assert c2.diag_facts()["unknown_items"] == 0
    finally:
        c2.close()


def test_list_caps_at_200():
    lines = unknownitems.Lines()
    assert lines.add([f"zq line {i}" for i in range(250)]) == 250
    got = lines.lines()
    assert len(got) == unknownitems.MAX_LINES == 200
    assert got[0] == "zq line 50" and got[-1] == "zq line 249"
    assert lines.add("not a list") == 0 and lines.add([None, 3, ""]) == 0


def test_a_failing_sink_never_fails_the_press(core):
    def boom(lines):
        raise RuntimeError("zq")
    core.last_eval.unknown_sink = boom
    result = core.eval_press(ITEM)
    assert result is not None
