"""TC-BUILDFILE (decision 0034): the loaded build as the game's `.build`
JSON, offered only as a download (research 0026)."""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al.theorycraft import buildfile, treedata
from server.al.theorycraft.model import Build, Gem, Item, SkillGroup, TreeSpec, parse

ROOT = Path(__file__).resolve().parent.parent
TREE = treedata.load(ROOT / "tests" / "fixtures" / "skilltree_synthetic.json")

SKILLS = (
    SkillGroup(gems=(
        Gem("Earthquake", "EarthquakePlayer", gem_id="Metadata/Items/Gems/SkillGemEarthquake"),
        Gem("Fast Forward", "SupportFastForwardPlayer",
            gem_id="Metadata/Items/Gems/SupportGemFastForward"),
        Gem("Off Support", "SupportOffPlayer", enabled=False,
            gem_id="Metadata/Items/Gems/SupportGemOff"),
        # PoB's gameId typo form (singular Gem/) is not a documented id
        Gem("Typo Support", "SupportTypoPlayer", gem_id="Metadata/Items/Gem/SupportGemTypo"))),
    SkillGroup(gems=(Gem("Disabled", "X", gem_id="Metadata/Items/Gems/SkillGemX"),),
               enabled=False),
    SkillGroup(gems=(Gem("No Id", "NoIdPlayer"),)),
)
GEAR = {"Weapon 1": Item(1, "", "RARE", "Grim {Bite}", "Expert <Bow>"),
        "Helmet": Item(2, "", "UNIQUE", "Example Hood", "Hood"),
        "Weapon 2": Item(3, "", "RARE", "Left", "Buckler"),
        "Flask 1": Item(4, "", "NORMAL", None, "Life Flask")}


def make(nodes=(10, 20, 30, 50), asc="First Ascent", **kw):
    return Build(raw_xml="", class_name="Alpha Class", ascendancy=asc, level=42,
                 specs=(TreeSpec(nodes=tuple(nodes)),), active_spec_index=0,
                 skills=SKILLS, gear=GEAR, **kw)


def test_export_matches_the_documented_schema_and_maps_ids():
    out = buildfile.export(make(), TREE)
    doc = out["doc"]
    assert buildfile.validate(doc) == []
    assert json.loads(out["text"]) == doc and out["text"].isascii()
    assert doc["name"] == "First Ascent, level 42"
    assert doc["ascendancy"] == "Alpha1"
    # node 20 has a null slug, 30 / 50 have no id key: dropped, never guessed
    assert doc["passives"] == ["synthetic_start_a"]
    assert out["passives"] == {"mapped": 1, "total": 4, "ok": True}
    assert doc["skills"] == [{"id": "Metadata/Items/Gems/SkillGemEarthquake",
                              "support_skills": ["Metadata/Items/Gems/SupportGemFastForward"]}]
    assert doc["inventory_slots"] == [
        {"inventory_id": "Weapon1", "additional_text": "Grim Bite, Expert Bow"},
        {"inventory_id": "Helm1", "unique_name": "Example Hood"}]
    notes = " ".join(out["notes"])
    assert "3 of 4 passives left out" in notes
    assert "2 gems left out" in notes  # the typo support and the id-less skill
    assert "1 gear slot left out" in notes
    assert out["filename"] == "ashlight-First-Ascent-level-42.build"


def test_no_tree_data_or_mismatch_writes_no_passives_and_says_so():
    out = buildfile.export(make(), None)
    assert "passives" not in out["doc"] and "ascendancy" not in out["doc"]
    assert any("isn't downloaded" in n for n in out["notes"])
    assert any("Ascendancy left out" in n for n in out["notes"])
    out = buildfile.export(make(nodes=(9001, 9002, 9003, 10)), TREE)
    assert "passives" not in out["doc"] and out["passives"]["ok"] is False
    assert any("doesn't match" in n for n in out["notes"])
    assert buildfile.validate(out["doc"]) == []


def test_validate_flags_off_schema_documents():
    assert buildfile.validate([]) == ["the build must be one object"]
    bad = {"description": "", "version": 1, "passives": ["strength89", {"id": "a b"},
                                                         {"id": "x", "weapon_set": 3}],
           "skills": [{"id": "Metadata/Items/Gem/SkillGemX",
                       "support_skills": [{"id": "Metadata/Items/Gems/SupportGemY",
                                           "level_interval": [0, -1]}]}],
           "inventory_slots": [{"unique_name": "U"}, "Weapon1"]}
    errs = buildfile.validate(bad)
    for want in ("name is required text", "unknown field version", "description must be text",
                 "passives[1] bad id 'a b'", "passives[2].weapon_set must be 0, 1 or 2",
                 "skills[0] bad id", "support_skills[0].level_interval",
                 "inventory_slots[0].inventory_id is required text",
                 "inventory_slots[1] must be an object"):
        assert any(want in e for e in errs), (want, errs)


def test_ggg_example_shapes_validate():
    # The shapes of the example on GGG's File Formats page (research 0026)
    doc = {"name": "Titan Warrior", "author": "Example", "ascendancy": "Warrior1",
           "passives": ["melee17", "strength89", "AscendancyWarrior1Small3",
                        {"id": "jewel_slot1956", "additional_text": "<b>{Jewel}"}],
           "skills": ["Metadata/Items/Gems/SkillGemEarthquake",
                      {"id": "Metadata/Items/Gems/SkillGemEarthquake", "level_interval": [0, 100],
                       "support_skills": ["Metadata/Items/Gems/SupportGemFastForward"]}],
           "inventory_slots": [{"inventory_id": "Weapon1", "unique_name": "Kalandra's Touch",
                                "slot_x": 0, "slot_y": 0, "level_interval": 10}]}
    assert buildfile.validate(doc) == []


def test_pob_gem_id_is_parsed():
    xml = ('<PathOfBuilding2><Build level="1" className="Warrior"/><Skills><SkillSet id="1">'
           '<Skill enabled="true"><Gem nameSpec="Earthquake" skillId="EarthquakePlayer" '
           'gemId="Metadata/Items/Gems/SkillGemEarthquake" enabled="true"/></Skill>'
           '</SkillSet></Skills></PathOfBuilding2>')
    b = parse(xml)
    assert b.skills[0].gems[0].gem_id == "Metadata/Items/Gems/SkillGemEarthquake"
    assert buildfile.export(b)["doc"]["skills"] == [
        {"id": "Metadata/Items/Gems/SkillGemEarthquake"}]


def test_filename_never_carries_a_path():
    for name in ("..\\..\\x", "a/b:c*?", "", "   "):
        f = buildfile.filename(name)
        assert f.startswith("ashlight-") and f.endswith(".build")
        assert not any(c in f for c in "\\/:*?\"<>|") and ".." not in f


def test_generator_has_no_file_or_path_code():
    src = (ROOT / "server" / "al" / "theorycraft" / "buildfile.py").read_text(encoding="ascii")
    for bad in ("open(", "write_text", "write_bytes", ".write(", "os.", "shutil",
                "import os", "pathlib", "subprocess"):
        assert bad not in src, bad
    http_src = (ROOT / "server" / "al" / "http.py").read_text(encoding="ascii")
    block = http_src.split('if path == "/api/buildfile":', 1)[1].split("if path ==", 1)[0]
    assert "_send(" in block and ".write" not in block and "open(" not in block
    assert "query" not in block and "q.get" not in block  # no name from the request


@pytest.mark.server
def test_buildfile_endpoint_is_a_token_guarded_download(tmp_path):
    from server.al.core import Core
    from server.al.http import serve
    from server.al.theorycraft import codec
    from tc_eval_fixtures import EVAL_BUILD_XML
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, "f" * 48, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        def get(token):
            conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
            h = {"Host": f"127.0.0.1:{server.port}"}
            if token:
                h["X-AL-Token"] = token
            conn.request("GET", "/api/buildfile", headers=h)
            r = conn.getresponse()
            out = (r.status, r.getheader("Content-Disposition"), r.read().decode("ascii"))
            conn.close()
            return out
        assert get(None)[0] in (401, 403)
        assert get("f" * 48)[0] == 404  # no build yet
        core.builds.load_code(codec.encode(EVAL_BUILD_XML))
        status, disp, text = get("f" * 48)
        assert status == 200 and disp.startswith('attachment; filename="ashlight-')
        assert disp.endswith('.build"')
        assert buildfile.validate(json.loads(text)) == []
        summary = core.builds.snapshot()["build_file"]
        assert summary["filename"] in disp and isinstance(summary["notes"], list)
    finally:
        server.stop()
        core.close()
    assert not any(p.suffix == ".build" for p in tmp_path.rglob("*"))
