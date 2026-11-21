"""DATA-PROVENANCE (F-097, OPEN-42): every authored fact resolves to a src
and a checked date; tools/provenance.py lists the re-verify set."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import provenance  # noqa: E402
from server.al import campaign, zoneguide  # noqa: E402
from server.al.theorycraft import waystone  # noqa: E402


def test_every_authored_entry_resolves_src_and_checked():
    items = provenance.entries()
    bad = [e["where"] for e in items if not e["ok"]]
    assert bad == []
    where = {e["where"] for e in items}
    guide = json.loads(provenance.GUIDE.read_text(encoding="ascii"))
    for key, act in guide["acts"].items():
        assert f"zone_guide {key} default" in where
        for zone in act.get("zones", {}):
            assert f"zone_guide {key} {zone}" in where
    assert "zone_guide endgame" in where
    # DATA-GUIDE-MERGE: one authored zone file; no zone_notes entry is left
    assert not any(w.startswith("zone_notes ") for w in where)
    assert not hasattr(provenance, "NOTES")
    # DATA-GUIDE-BOSS: boss entries are read from the guide file, each with
    # its own pair; campaign.py keeps no boss table
    bosses = {f"boss {key} {zone}" for key, act in guide["acts"].items()
              for zone, z in act.get("zones", {}).items() if "boss" in z}
    assert {"boss G1 Ogham Manor", "boss G2 Mawdun Mine"} <= bosses
    assert bosses == {w for w in where if w.startswith("boss ")}
    assert not hasattr(campaign, "BOSS_ZONES") and not hasattr(campaign, "BOSS_PROVENANCE")
    for r in waystone.RULES:
        assert f"waystone rule {r['id']}" in where
    for r in waystone.REWARDS:
        assert f"waystone reward {r['id']}" in where
    # the fields are data only: the reader still loads the guide
    assert zoneguide.load()["acts"]


def test_an_entry_without_a_pair_is_missing(tmp_path):
    guide = json.loads(provenance.GUIDE.read_text(encoding="ascii"))
    act = guide["acts"]["G1"]
    act.pop("src")
    act.pop("checked")
    zone = next(iter(act["zones"]))
    act["zones"][zone].update({"src": "research:0034", "checked": "2026-11-17"})
    g = tmp_path / "g.json"
    g.write_text(json.dumps(guide), encoding="ascii")
    items = provenance.entries(guide=g)
    missing = {e["where"] for e in items if not e["ok"]}
    assert "zone_guide G1 default" in missing
    assert f"zone_guide G1 {zone}" not in missing
    assert any(w.startswith("zone_guide G1 ") for w in missing)
    assert all(w.startswith("zone_guide G1 ") for w in missing)


def test_a_boss_entry_never_inherits_the_zone_pair(tmp_path):
    """DATA-GUIDE-BOSS: a `boss` entry must carry its own src and checked."""
    guide = json.loads(provenance.GUIDE.read_text(encoding="ascii"))
    boss = guide["acts"]["G1"]["zones"]["Ogham Manor"]["boss"]
    boss.pop("src")
    boss.pop("checked")
    g = tmp_path / "g.json"
    g.write_text(json.dumps(guide), encoding="ascii")
    missing = {e["where"] for e in provenance.entries(guide=g) if not e["ok"]}
    assert missing == {"boss G1 Ogham Manor"}


def test_src_is_one_of_the_allowed_forms_and_never_a_host():
    for good in ("research:0034", "snapshot:mods", "snapshot:world_areas",
                 "ggg-export:passive-tree", "log", "operator"):
        assert provenance.valid_src(good), good
    for bad in ("https://poe2db.tw/us/Act_1", "poe2db.tw", "www.example",
                "research:34", "research:0034 poe2db.tw", "snapshot:mods.json",
                "snapshot:", "wiki", "", None, 34, "Log", "operator "):
        assert not provenance.valid_src(bad), bad
    for e in provenance.entries():
        assert provenance.HOST_RE.search(e["src"]) is None, e
        if e["src"].startswith("research:"):
            num = e["src"].split(":", 1)[1]
            assert list((ROOT / "docs" / "research").glob(num + "-*.md")), e
    assert provenance.valid_checked("2026-11-17")
    for bad in ("2026-13-01", "2026-11-31", "17-11-2026", "2026/11/17", "", None):
        assert not provenance.valid_checked(bad), bad


def test_script_lists_entries_checked_before_a_date():
    items = provenance.entries()
    assert provenance.before(items, "2026-11-17") == []
    assert len(provenance.before(items, "2026-12-11")) == len(items)
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "provenance.py"),
                          "--before", "2026-12-11"], capture_output=True, text=True,
                         cwd=str(ROOT), timeout=60)
    assert run.returncode == 0, run.stderr
    lines = run.stdout.splitlines()
    assert lines[-1] == (f"provenance: {len(items)} of {len(items)} entries "
                         "checked before 2026-12-11, 0 missing")
    assert len(lines) == len(items) + 1
    assert "2026-11-17 research:0031 boss G1 Ogham Manor" in lines
    assert "2026-11-17 research:0031 boss G2 Mawdun Mine" in lines
    assert "2026-11-17 snapshot:mods waystone rule ground" in lines
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "provenance.py"),
                          "--before", "2026-11-17"], capture_output=True, text=True,
                         cwd=str(ROOT), timeout=60)
    assert run.returncode == 0
    assert run.stdout.splitlines() == [
        f"provenance: 0 of {len(items)} entries checked before 2026-11-17, 0 missing"]
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "provenance.py"),
                          "--before", "soon"], capture_output=True, text=True,
                         cwd=str(ROOT), timeout=60)
    assert run.returncode == 2
