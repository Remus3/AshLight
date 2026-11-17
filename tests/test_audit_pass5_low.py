"""AREA-AUDIT pass 5 lows P5-2..P5-7 (docs/audit/2026-11-17-audit.md,
"Pass 5"; ROADMAP AUDIT-P5-LOW). Synthetic files under tmp_path; no game,
no network."""

import json
import os
import time
from pathlib import Path

import pytest

from server.al import hotkeys, runhistory, settingsio
from server.al.core import Core
from server.al.theorycraft import lootfilter

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "app" / "test" / "hotkey_cases.json").read_text(encoding="utf-8"))


def _doc(settings):
    return {"kind": settingsio.KIND, "schema": settingsio.SCHEMA, "settings": settings}


# P5-3: an imported hotkey needs Ctrl or Alt (Shift only with an F key) and
# never a game key; the same table drives app/hotkey.js (app/test/hotkey.test.js).
def test_p5_3_hotkey_rule_matches_the_shared_table():
    for value, want in CASES["ok"].items():
        assert hotkeys.safe_accelerator(value) == want, value
    for value in CASES["bad"]:
        assert hotkeys.safe_accelerator(value) is None, repr(value)
    for value in (None, 5, True, ["Alt", "K"]):
        assert hotkeys.safe_accelerator(value) is None


@pytest.mark.parametrize("key", ["overlay_toggle", "eval_hotkey"])
@pytest.mark.parametrize("bad", ["C", "Space", "F5", "Shift+C", "Ctrl+C", "Ctrl+Alt+C"])
def test_p5_3_import_refuses_a_bare_or_game_hotkey(key, bad):
    with pytest.raises(settingsio.SettingsError) as e:
        settingsio.parse_import(_doc({key: bad, "league": "L"}), {})
    assert settingsio.LABELS[key] in str(e.value)


def test_p5_3_import_stores_the_canonical_hotkey():
    update, _ = settingsio.parse_import(_doc({"eval_hotkey": "ctrl+alt+k"}), {})
    assert update == {"eval_hotkey": "Ctrl+Alt+K"}


def test_p5_3_export_drops_a_bare_stored_hotkey():
    doc = settingsio.export_doc({"overlay_toggle": "C", "eval_hotkey": "Alt+Shift+E"}, "v")
    assert doc["settings"] == {"eval_hotkey": "Alt+Shift+E"}


# P5-2: tc_calc follows the web_data rule: an import never switches it on.
def test_p5_2_import_never_switches_tc_calc_on():
    update, report = settingsio.parse_import(_doc({"tc_calc": True, "league": "L"}),
                                             {"tc_calc": False})
    assert "tc_calc" not in update and update == {"league": "L"}
    assert report["tc_calc_offered"] is True and "tc_calc" not in report["applied"]
    # the existing import sentence tells the player it was skipped
    assert "tc_calc" in report["ignored"]


def test_p5_2_import_may_switch_tc_calc_off_or_keep_it_on():
    update, report = settingsio.parse_import(_doc({"tc_calc": False}), {"tc_calc": True})
    assert update == {"tc_calc": False} and report["tc_calc_offered"] is False
    update, report = settingsio.parse_import(_doc({"tc_calc": True}), {"tc_calc": True})
    assert update == {"tc_calc": True} and report["tc_calc_offered"] is False


def test_p5_2_core_import_leaves_tc_calc_off(tmp_path):
    cfg = tmp_path / "local.json"
    cfg.write_text('{"contact": "c"}\n', encoding="ascii")
    core = Core(runtime=tmp_path, tail=False, config_path=cfg)
    report = core.import_settings(_doc({"tc_calc": True, "underlevel_gap": 5}))
    assert report["tc_calc_offered"] is True
    saved = json.loads(cfg.read_text(encoding="ascii"))
    assert "tc_calc" not in saved and saved["underlevel_gap"] == 5
    assert core.tc_calc_enabled() is False


# P5-4: a same-size rewrite inside one coarse timestamp tick (FAT / SMB)
# is still seen.
def test_p5_4_same_size_rewrite_with_the_same_mtime_is_seen(tmp_path):
    cfg = tmp_path / "local.json"
    cfg.write_text('{"league": "AAAA"}\n', encoding="ascii")
    core = Core(runtime=tmp_path, tail=False, config_path=cfg)
    st = cfg.stat()
    assert core._config()["league"] == "AAAA"
    cfg.write_text('{"league": "BBBB"}\n', encoding="ascii")
    os.utime(cfg, ns=(st.st_atime_ns, st.st_mtime_ns))  # coarse tick: same stamp
    assert cfg.stat().st_size == st.st_size and cfg.stat().st_mtime_ns == st.st_mtime_ns
    assert core._config()["league"] == "BBBB"


def test_p5_4_an_old_unchanged_file_is_not_re_read(tmp_path, monkeypatch):
    cfg = tmp_path / "local.json"
    cfg.write_text('{"league": "AAAA"}\n', encoding="ascii")
    old = time.time() - 60
    os.utime(cfg, (old, old))
    core = Core(runtime=tmp_path, tail=False, config_path=cfg)
    assert core._config()["league"] == "AAAA"
    reads = []
    real = Core._read_config_bytes
    monkeypatch.setattr(Core, "_read_config_bytes",
                        lambda self: reads.append(1) or real(self))
    for _ in range(5):
        assert core._config()["league"] == "AAAA"
    assert reads == []


# P5-5: a filter with the AshLight start line but no end line is refused
# (stripping to EOF would delete the player's own filter).
def test_p5_5_unterminated_section_is_refused():
    data = (lootfilter.MERGE_BEGIN + "\nShow\n    BaseType == \"X\"\n").encode("ascii")
    with pytest.raises(lootfilter.MergeRefused) as e:
        lootfilter.merge(data, None)
    assert e.value.reason == "no_end"
    assert "end line" in str(e.value)
    crlf = (lootfilter.MERGE_BEGIN + "\r\nShow\r\n").encode("ascii")
    with pytest.raises(lootfilter.MergeRefused):
        lootfilter.merge(b"\xef\xbb\xbf" + crlf, None)


def test_p5_5_terminated_section_still_re_merges_once():
    first = lootfilter.merge(b"Show\n    Rarity Unique\n", None)
    again = lootfilter.merge(first, None)
    assert again == first
    assert again.count(lootfilter.MERGE_BEGIN.encode("ascii")) == 1


# P5-6: the current run's saved splits count: no "No finished acts saved
# yet" while they exist. With no other run, its own split is the best so far.
def test_p5_6_current_runs_saved_splits_are_not_empty(tmp_path):
    h = runhistory.RunHistory(tmp_path / runhistory.FILE_NAME)
    cur = {"character": "Ash", "class": "Witch", "finished": False, "started_at": 1000.0,
           "deaths": {}, "splits": [{"key": "G1", "label": "Act 1", "time_s": 1500.0}]}
    assert h.record(cur)
    v = h.view(cur)
    assert v["empty_text"] == ""
    assert v["best"] == [{"key": "G1", "label": "Act 1", "best_s": 1500.0,
                          "best_text": "25:00", "delta_s": None, "this_run": True}]


def test_p5_6_no_splits_anywhere_is_still_empty(tmp_path):
    h = runhistory.RunHistory(tmp_path / runhistory.FILE_NAME)
    cur = {"character": "Ash", "started_at": 1000.0, "deaths": {"Clearfell": 1},
           "splits": []}
    v = h.view(cur)
    assert v["empty_text"] == runhistory.EMPTY_TEXT and v["best"] == []


# P5-7: decision 0035 is recorded as intentionally unused.
def test_p5_7_decision_0035_gap_is_recorded():
    dec = ROOT / "docs" / "decisions"
    assert not list(dec.glob("0035-*.md"))
    text = (dec / "README.md").read_text(encoding="ascii")
    assert "0035" in text and "unused" in text


# FOLLOWUP11: Windows system combinations (task switcher, window cycling,
# Task Manager, secure attention, Win key) are refused, and every blocked
# combination is in the shared table so app/hotkey.js is held to it too.
def test_followup11_windows_system_combos_refused():
    for value in ("Alt+Shift+Tab", "Shift+Alt+Tab", "Ctrl+Alt+Tab", "Alt+Shift+Escape",
                  "Ctrl+Shift+Esc", "Ctrl+Alt+Delete", "Ctrl+Alt+End", "Win+Tab", "Win+D"):
        assert hotkeys.safe_accelerator(value) is None, value
        assert value in CASES["bad"], value


def test_followup11_every_blocked_combo_is_in_the_table():
    assert hotkeys.GAME_KEYS <= set(CASES["bad"])
