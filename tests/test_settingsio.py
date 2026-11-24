"""server/al/settingsio.py: the KINDLER-STORE "gen_builds" block of the
settings export (decision 0081 point 7, decision 0036): added only when it
validates and fits MAX_BYTES, checked strictly on import (a bad block
refuses the whole file), merged without overwriting a tab, and never a
way to turn web data on. KINDLER-STORE-EXPORT-WIRE: Core.export_settings
adds the block and Core.import_settings checks it before anything applies,
then merges it (a failed write keeps the tabs and marks the Saver). Pure
functions, tmp files and a non-tailing core only.
"""

import json

import pytest

from pathlib import Path

from server.al import jsonfile, settingsio
from server.al.core import Core
from server.al.plug import genbuilds
from server.al.theorycraft import genstore


def _store(tmp_path, name, n, label="t"):
    s = genstore.GenStore(tmp_path / name)
    for i in range(n):
        s.add(label=f"{label}{i}", cls="Warrior")
    return s


def _base():
    return settingsio.export_doc({"web_data": False, "theme": "dark"}, "0.1.0")


def test_export_adds_the_block_without_ids(tmp_path):
    s = _store(tmp_path, "g.json", 2)
    doc = settingsio.with_gen_builds(_base(), s.export_block())
    block = doc[settingsio.GEN_KEY]
    assert [t["label"] for t in block["tabs"]] == ["t0", "t1"]
    assert all("id" not in t for t in block["tabs"])
    assert settingsio.GEN_KEY not in doc["settings"]
    assert settingsio.GEN_KEY not in settingsio.ALLOWED
    # round trip through the file text
    back = json.loads(json.dumps(doc))
    assert settingsio.gen_builds_of(back) == block["tabs"]


def test_no_tabs_or_a_bad_block_adds_nothing(tmp_path):
    base = _base()
    assert settingsio.with_gen_builds(base, None) == base
    assert settingsio.with_gen_builds(base, {"tabs": [{"id": "k1"}]}) == base
    assert settingsio.gen_builds_of(base) is None


def test_block_left_out_past_the_size_cap(tmp_path, monkeypatch):
    s = _store(tmp_path, "g.json", 6)
    monkeypatch.setattr(settingsio, "MAX_BYTES", 600)
    base = _base()
    assert settingsio.with_gen_builds(base, s.export_block()) == base


def test_bad_block_refuses_the_whole_file():
    doc = dict(_base(), **{settingsio.GEN_KEY: {"tabs": [{"follow": "maybe"}]}})
    with pytest.raises(settingsio.SettingsError) as e:
        settingsio.gen_builds_of(doc)
    assert str(e.value) == "The Kindler tabs in that file are not valid."
    for bad in ({"tabs": [{}] * 7}, {"tabs": [{"id": "k1"}]}, "x"):
        with pytest.raises(settingsio.SettingsError):
            settingsio.gen_builds_of(dict(_base(), **{settingsio.GEN_KEY: bad}))


def test_import_adds_while_room_and_never_overwrites(tmp_path):
    src = _store(tmp_path, "a.json", 3, label="file")
    doc = settingsio.with_gen_builds(_base(), src.export_block())
    tabs = settingsio.gen_builds_of(doc)
    mine = _store(tmp_path, "b.json", 4, label="mine")
    report = settingsio.merge_gen_builds(mine, tabs)
    assert report == {"gen_tabs_added": 2, "gen_tabs_full": 1}
    labels = [t["label"] for t in mine.view()["tabs"]]
    assert labels == ["mine0", "mine1", "mine2", "mine3", "file0", "file1"]


def test_block_never_turns_web_data_on(tmp_path):
    s = _store(tmp_path, "g.json", 1)
    doc = settingsio.with_gen_builds(
        settingsio.export_doc({"web_data": True}, "0.1.0"), s.export_block())
    doc[settingsio.GEN_KEY]["tabs"][0]["web_data"] = True  # a hand-made field
    with pytest.raises(settingsio.SettingsError):
        settingsio.gen_builds_of(doc)
    del doc[settingsio.GEN_KEY]["tabs"][0]["web_data"]
    update, report = settingsio.parse_import(doc, {"web_data": False})
    assert "web_data" not in update and report["web_data_offered"] is True
    assert settingsio.GEN_KEY not in update


# -- KINDLER-STORE-EXPORT-WIRE: the Core wiring ------------------------------

class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def core(tmp_path):
    jsonfile.pop_restored()
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False,
             config_path=tmp_path / "local.json")
    c.store_clock = Clock()
    try:
        yield c
    finally:
        c.close()


def test_core_export_carries_the_kindler_tabs(core):
    assert settingsio.GEN_KEY not in core.export_settings()  # no tab, no block
    core.gen_builds.add(label="slam", cls="Warrior")
    core.gen_builds.add(label="bolt", cls="Sorceress")
    doc = core.export_settings()
    tabs = doc[settingsio.GEN_KEY]["tabs"]
    assert [t["label"] for t in tabs] == ["slam", "bolt"]
    assert all("id" not in t for t in tabs)
    assert settingsio.gen_builds_of(json.loads(json.dumps(doc))) == tabs


def test_core_import_merges_the_tabs_after_the_players_own(core, tmp_path):
    src = _store(tmp_path, "a.json", 3, label="file")
    doc = settingsio.with_gen_builds(_base(), src.export_block())
    for i in range(4):
        core.gen_builds.add(label=f"mine{i}")
    report = core.import_settings(json.loads(json.dumps(doc)))
    assert report["gen_tabs_added"] == 2 and report["gen_tabs_full"] == 1
    labels = [t["label"] for t in core.gen_builds.view()["tabs"]]
    assert labels == ["mine0", "mine1", "mine2", "mine3", "file0", "file1"]
    saved = json.loads((Path(core.runtime) / genstore.FILE_NAME).read_text(encoding="ascii"))
    assert [t["label"] for t in saved["tabs"]][-2:] == ["file0", "file1"]


def test_core_import_without_a_block_leaves_the_tabs_alone(core):
    core.gen_builds.add(label="mine")
    report = core.import_settings(_base())
    assert "gen_tabs_added" not in report
    assert [t["label"] for t in core.gen_builds.view()["tabs"]] == ["mine"]


def test_core_import_bad_block_applies_nothing(core, tmp_path):
    before = core._config().get("theme")
    doc = settingsio.export_doc({"theme": "light"}, "0.1.0")
    doc[settingsio.GEN_KEY] = {"tabs": [{"follow": "maybe"}]}
    with pytest.raises(settingsio.SettingsError):
        core.import_settings(doc)
    assert core._config().get("theme") == before
    assert core.gen_builds.view()["tabs"] == []


def test_core_import_failed_write_keeps_tabs_and_marks_saver(core, tmp_path, monkeypatch):
    src = _store(tmp_path, "a.json", 2, label="file")
    doc = settingsio.with_gen_builds(_base(), src.export_block())
    real = jsonfile.write_json

    def broken(path, data, **kw):
        if Path(path).name.startswith("gen_builds"):
            raise OSError(28, "No space left on device")
        return real(path, data, **kw)

    monkeypatch.setattr(jsonfile, "write_json", broken)
    report = core.import_settings(doc)
    assert report["gen_tabs_added"] == 2 and report["gen_tabs_full"] == 0
    assert [t["label"] for t in core.gen_builds.view()["tabs"]] == ["file0", "file1"]
    monkeypatch.setattr(jsonfile, "write_json", real)
    core.store_clock.t += 2.0
    assert genbuilds.tick(core) is True
    saved = json.loads((Path(core.runtime) / genstore.FILE_NAME).read_text(encoding="ascii"))
    assert [t["label"] for t in saved["tabs"]] == ["file0", "file1"]
