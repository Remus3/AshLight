"""TC-WEIGHTS-DELTA-STORE (F-134): weights.json holds the player's changes.

The file keeps only rows that differ from the defaults (and the band parts
that differ); the full document is merged at load. A version 1 full file
migrates with no score change and one backup. A damaged file is never
overwritten. Temp dirs only; no running AshLight is touched.
"""

import json

import pytest

from server.al.theorycraft import evaluate
from server.al.theorycraft import weights as wm
from tc_eval_fixtures import RARE_GLOVES

LIFE = "+# to maximum Life"
FIRE = "+#% to Fire Resistance"
MANA = "+# to maximum Mana"


def _file(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _score(doc):
    return evaluate.evaluate(RARE_GLOVES, None, doc)["score"]


def test_first_use_writes_an_empty_change_file(tmp_path):
    path = wm.default_path(tmp_path / "rt")
    store = wm.WeightsStore(path)
    assert store.get() == wm.defaults()
    assert _file(path) == {"version": 2, "weights": {}, "sidegrade": {}}


def test_only_changed_rows_are_stored(tmp_path):
    path = tmp_path / "weights.json"
    store = wm.WeightsStore(path)
    doc = wm.defaults()
    doc["weights"][LIFE] = 4
    del doc["weights"][MANA]
    doc["weights"]["+# to Spirit Shards"] = 2
    doc["sidegrade"]["pct"] = 9
    store.put(doc)
    assert _file(path) == {"version": 2, "sidegrade": {"pct": 9},
                           "weights": {LIFE: 4, MANA: None, "+# to Spirit Shards": 2}}
    assert wm.WeightsStore(path).get() == wm.validate(doc)


def test_patched_default_reaches_untouched_rows_only(tmp_path, monkeypatch):
    path = tmp_path / "weights.json"
    store = wm.WeightsStore(path)
    doc = store.get()
    doc["weights"][LIFE] = 7
    store.put(doc)
    patched = dict(wm.DEFAULT_WEIGHTS, **{FIRE: 2.5, LIFE: 3.0})
    monkeypatch.setattr(wm, "DEFAULT_WEIGHTS", patched)
    again = wm.WeightsStore(path)
    rows = again.get()["weights"]
    assert rows[FIRE] == 2.5          # untouched row picks up the new default
    assert rows[LIFE] == 7            # the player's change stays


def test_reset_row_and_reset_all(tmp_path):
    path = tmp_path / "weights.json"
    store = wm.WeightsStore(path)
    doc = store.get()
    doc["weights"][LIFE] = 9
    doc["weights"][FIRE] = 0
    del doc["weights"][MANA]
    doc["weights"]["my stat"] = 1
    doc["sidegrade"]["abs"] = 0
    store.put(doc)
    store.reset(LIFE.upper())
    assert store.get()["weights"][LIFE] == wm.DEFAULT_WEIGHTS[LIFE]
    assert LIFE not in _file(path)["weights"]
    store.reset(MANA)
    assert store.get()["weights"][MANA] == wm.DEFAULT_WEIGHTS[MANA]
    store.reset("my stat")
    assert "my stat" not in store.get()["weights"]
    assert _file(path)["weights"] == {FIRE: 0}
    store.reset()
    assert store.get() == wm.defaults()
    assert _file(path) == {"version": 2, "weights": {}, "sidegrade": {}}
    assert wm.WeightsStore(path).get() == wm.defaults()


def test_case_changed_key_replaces_its_default(tmp_path):
    path = tmp_path / "weights.json"
    store = wm.WeightsStore(path)
    doc = store.get()
    del doc["weights"][LIFE]
    doc["weights"][LIFE.lower()] = 2
    store.put(doc)
    rows = wm.WeightsStore(path).get()["weights"]
    assert rows[LIFE.lower()] == 2 and LIFE not in rows
    assert len(rows) == len(wm.DEFAULT_WEIGHTS)


def test_schema1_file_migrates_with_same_scores_and_one_backup(tmp_path):
    path = tmp_path / "weights.json"
    v1 = {"version": 1, "weights": dict(wm.DEFAULT_WEIGHTS),
          "sidegrade": {"abs": 3, "pct": 5}}
    v1["weights"][LIFE] = 5
    del v1["weights"][FIRE]
    v1["weights"]["custom # stat"] = 1
    text = json.dumps(v1, indent=1, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    before = _score(wm.validate(v1))
    store = wm.WeightsStore(path)
    assert store.load_error is None
    assert store.get()["weights"] == v1["weights"]
    assert _score(store.get()) == before
    backup = tmp_path / wm.V1_BACKUP
    assert backup.read_text(encoding="utf-8") == text
    assert _file(path) == {"version": 2, "sidegrade": {"abs": 3},
                           "weights": {LIFE: 5, FIRE: None, "custom # stat": 1}}
    # reloading the migrated file gives the same document and score
    again = wm.WeightsStore(path)
    assert again.get() == store.get() and _score(again.get()) == before
    # one backup only: a later version 1 file never replaces it
    path.write_text(json.dumps({"weights": {LIFE: 1}}), encoding="utf-8")
    wm.WeightsStore(path)
    assert backup.read_text(encoding="utf-8") == text
    assert sorted(p.name for p in tmp_path.iterdir()) == ["weights.json", wm.V1_BACKUP]


def test_unversioned_full_file_reads_as_schema1(tmp_path):
    path = tmp_path / "weights.json"
    path.write_text(json.dumps({"weights": {LIFE: 3}}), encoding="utf-8")
    store = wm.WeightsStore(path)
    assert store.get()["weights"] == {LIFE: 3}
    assert _file(path)["version"] == 2


@pytest.mark.parametrize("text", [
    "{not json",
    json.dumps({"version": 1, "weights": {"a": "x"}}),
    json.dumps({"version": 2, "weights": {"not a default": None}}),
    json.dumps({"version": 2, "weights": {LIFE: True}}),
    json.dumps({"version": 2, "weights": {}, "sidegrade": {"abs": -1}}),
    json.dumps({"version": 2, "weights": {}, "sidegrade": {"band": 1}}),
    json.dumps({"version": 9, "weights": {}}),
    json.dumps([1, 2]),
])
def test_damaged_file_is_never_overwritten(tmp_path, text):
    path = tmp_path / "weights.json"
    path.write_text(text, encoding="utf-8")
    store = wm.WeightsStore(path)
    assert store.load_error and store.get() == wm.defaults()
    assert path.read_text(encoding="utf-8") == text
    assert not (tmp_path / wm.V1_BACKUP).exists()


def test_snapshot_reports_defaults_and_changed(tmp_path):
    store = wm.WeightsStore(tmp_path / "weights.json")
    snap = store.snapshot()
    assert snap["defaults"] == wm.defaults()
    assert snap["changed"] == {"weights": {}, "sidegrade": {}}
    doc = store.get()
    doc["weights"][LIFE] = 2
    del doc["weights"][MANA]
    doc["sidegrade"]["abs"] = 1
    store.put(doc)
    snap = store.snapshot()
    assert snap["changed"] == {"weights": {LIFE: 2, MANA: None}, "sidegrade": {"abs": 1}}
    assert snap["weights"][LIFE] == 2 and MANA not in snap["weights"]
    assert snap["load_error"] is None and snap["version"] == 2
