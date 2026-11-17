"""UX-ZONE-NOTES (decision 0030): the zone note data file and lookup."""

import json

import pytest

from server.al import acts, zonenotes
from server.al.state import SessionState

DOC = zonenotes.load()


def test_schema_and_copy_rules():
    assert DOC["version"] == 1 and isinstance(DOC["about"], str)
    table = DOC["acts"]
    for key in ("G1", "G2", "G3", "G4", "P1", "P2", "P3", "C"):
        assert isinstance(table[key]["default"], str), key
    for key, entry in table.items():
        assert set(entry) <= {"default", "zones"}, key
        notes = [entry["default"]] + list(entry.get("zones", {}).values())
        for n in notes:
            assert 10 <= len(n) <= zonenotes.MAX_NOTE, n
            assert n.isascii() and "!" not in n and n.endswith("."), n
    for key in ("G1", "G2", "G3", "G4"):
        assert len(table[key]["zones"]) >= 14, key


def test_every_campaign_id_has_a_note_or_the_act_default():
    ids = ["G1_1", "G1_town", "G1_15", "G2_1", "G2_12_2", "G3_1", "G3_16_b", "G4_1_1",
           "G4_town", "P1_1", "P2_3", "P3_9", "C_G1_1", "C_G3_10"]
    for area_id in ids:
        n = zonenotes.note_for(area_id, "A zone with no note")
        assert n is not None and n["source"] == "act", area_id
    for area_id in ("HideoutFelled", "MapCrypt", "", None, "G0_1"):
        assert zonenotes.note_for(area_id, "The Riverbank") is None


def test_zone_name_note_wins():
    n = zonenotes.note_for("G1_1", "The Riverbank")
    assert n["source"] == "zone" and n["text"].startswith("First zone")
    assert zonenotes.note_for("G1_1", " The Riverbank ")["source"] == "zone"
    # a name from another act gets this act's default, not the other note
    assert zonenotes.note_for("G2_1", "The Riverbank")["source"] == "act"


def test_bad_documents_degrade():
    assert zonenotes.note_for("G1_1", "x", doc={}) is None
    assert zonenotes.note_for("G1_1", "x", doc={"acts": {"G1": "junk"}}) is None
    assert zonenotes.load("does/not/exist.json") == {}


def test_snapshot_carries_the_note():
    st = SessionState(clock=lambda: 10.0)
    assert st.snapshot()["zone_note"] is None
    st.apply({"type": "area_generated", "area_id": "G1_1", "area_level": 1})
    st.apply({"type": "scene_changed", "scene": "The Riverbank", "is_hideout": False})
    note = st.snapshot()["zone_note"]
    assert note["source"] == "zone" and note["zone"] == "The Riverbank"


@pytest.mark.skipif(not acts.default_path().is_file(), reason="world_areas snapshot not fetched")
def test_snapshot_ids_all_resolve():
    doc = json.loads(acts.default_path().read_text(encoding="utf-8"))
    for area_id, a in doc.items():
        info = acts.act_of(area_id)
        if info is None or info["key"][0] not in "GPC":
            continue
        if info["key"][0] == "G" and info["n"] > 4:
            continue  # Acts 5-6 after 1.0 (UTIL-1.0-POST)
        name = a.get("name") if isinstance(a, dict) else None
        assert zonenotes.note_for(area_id, name) is not None, area_id
