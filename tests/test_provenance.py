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


# -- DATA-GUIDE-FACTS (F-122, S5-FOLLOWUP c) -----------------------------------
# A new or changed guide entry cites only an allowed source: a cached
# snapshot, a GGG Data Export, the player's own log or operator text, never
# a research note (ruling Q-07: no agent reads a wiki, poe2db or forum page,
# and research 0034 is not a source for new or changed entries).

import hashlib  # noqa: E402

def _entry_hash(entry):
    """sha256 (12 hex) of an entry without its top-level src / checked."""
    e = {k: v for k, v in entry.items() if k not in ("src", "checked")}
    raw = json.dumps(e, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(raw).hexdigest()[:12]


# The point-books reword (S5 f) only narrows a line: no kind of point is
# claimed. Un-narrowed, such an entry is its baseline one again, so it
# keeps its old provenance.
BOOK_NEW, BOOK_OLD = "A book of 2 points - ", "A book of 2 skill points - "
SHORT_NEW, SHORT_OLD = ": book of 2 points", ": 2 skill points"


def _un_narrow(entry):
    e = json.loads(json.dumps(entry))
    for o in e.get("optional", []):
        if isinstance(o, dict) and str(o.get("text", "")).startswith(BOOK_NEW):
            o["text"] = BOOK_OLD + o["text"][len(BOOK_NEW):]
            if o.get("kind") == "other":
                o["kind"] = "passive"
    s = e.get("short")
    if isinstance(s, str) and s.endswith(SHORT_NEW):
        e["short"] = s[:-len(SHORT_NEW)] + SHORT_OLD
    return e


# Every guide entry as it stood before DATA-GUIDE-FACTS (main at f8816cc):
# "<act key>/<zone>" for a zone, "<act key>/" for the act table without its
# zones, "endgame"; the value is _entry_hash of that entry.
BASELINE = {
    "G1/": "2b345eb4fc2d",
    "G1/The Riverbank": "7c67f46d86de",
    "G1/Clearfell Encampment": "5b2270d17e19",
    "G1/Clearfell": "c6177660c9a3",
    "G1/Mud Burrow": "cb591eb1c701",
    "G1/The Grelwood": "c15c40cc7ca5",
    "G1/The Red Vale": "239ec156df3e",
    "G1/The Grim Tangle": "61b549c80918",
    "G1/Cemetery of the Eternals": "9bcb8cac876c",
    "G1/Mausoleum of the Praetor": "913695a12542",
    "G1/Tomb of the Consort": "e49173b83311",
    "G1/Hunting Grounds": "0e675de03a78",
    "G1/Freythorn": "d4dac77458d7",
    "G1/Ogham Farmlands": "2ea9f7f4d2d6",
    "G1/Ogham Village": "c1c069ca48e3",
    "G1/The Manor Ramparts": "6dce343e7aa3",
    "G1/Ogham Manor": "8428d14aaf00",
    "G2/": "ceea52f73be4",
    "G2/Vastiri Outskirts": "5a5633fcc7e9",
    "G2/The Ardura Caravan": "41729273ad89",
    "G2/Mawdun Quarry": "fdd3348025eb",
    "G2/Mawdun Mine": "e6db22561f0b",
    "G2/The Halani Gates": "e6872542a042",
    "G2/Traitor's Passage": "cf7dd273e5db",
    "G2/Trial of the Sekhemas": "92e86f9d3fef",
    "G2/Keth": "3241c62688d1",
    "G2/The Lost City": "4e60bccd22ab",
    "G2/Buried Shrines": "87f960c2c943",
    "G2/Mastodon Badlands": "1b7bfd213b6b",
    "G2/The Bone Pits": "80728f69bab8",
    "G2/Valley of the Titans": "502a9cc62a41",
    "G2/The Titan Grotto": "60196047e7ce",
    "G2/Deshar": "5ff30f454f71",
    "G2/Path of Mourning": "cfdfb68f6576",
    "G2/The Spires of Deshar": "346b1082d484",
    "G2/The Dreadnought's Wake": "455ee259b7ad",
    "G2/Dreadnought": "53359f7bb2d9",
    "G3/": "26bec73dfb7d",
    "G3/Sandswept Marsh": "56db00f811c4",
    "G3/Ziggurat Encampment": "87fd10f720f9",
    "G3/Jungle Ruins": "f6299a1886da",
    "G3/The Venom Crypts": "294f3880d412",
    "G3/Infested Barrens": "6180ddea8300",
    "G3/Chimeral Wetlands": "6867ea54e9b9",
    "G3/Jiquani's Machinarium": "c15f6196cd2d",
    "G3/Jiquani's Sanctum": "b6a9175f752d",
    "G3/The Matlan Waterways": "37d709bde8fe",
    "G3/The Azak Bog": "13f7f3adab2f",
    "G3/The Drowned City": "8453c22573fa",
    "G3/The Molten Vault": "ed53ff7319b4",
    "G3/Apex of Filth": "50717f4b354f",
    "G3/Temple of Kopec": "6e50bc0dbdf0",
    "G3/The Trial of Chaos": "facfd9fbc65d",
    "G3/Utzaal": "6228b72ffc92",
    "G3/Aggorat": "8cab59e1d8e9",
    "G3/The Black Chambers": "173fa4ae86ed",
    "G4/": "5ff9b0cd0e6c",
    "G4/Kingsmarch": "0966032a4732",
    "G4/Isle of Kin": "d18c664114d8",
    "G4/Volcanic Warrens": "578ba51dcea4",
    "G4/Kedge Bay": "7c34cf18c7ea",
    "G4/Journey's End": "7bcf8df26c22",
    "G4/Whakapanu Island": "237dfe759a03",
    "G4/Singing Caverns": "88b4fd21e3a0",
    "G4/Shrike Island": "7d838c0608ef",
    "G4/Abandoned Prison": "50772f32ea63",
    "G4/Solitary Confinement": "0961bcf82519",
    "G4/Eye of Hinekora": "a630b4d6b5a2",
    "G4/Halls of the Dead": "48a77c4b9bb9",
    "G4/Trial of the Ancestors": "d913d2c0e482",
    "G4/Arastas": "408830730117",
    "G4/The Excavation": "e9b8f3bf8e80",
    "G4/Ngakanu": "71c7ca58e9a3",
    "G4/Heart of the Tribe": "d97fc26256c5",
    "G4/Plunder's Point": "21fc1f9e671f",
    "P1/": "233d7546a321",
    "P1/The Refuge": "9e313b454c80",
    "P1/Scorched Farmlands": "407732e17284",
    "P1/Stones of Serle": "83c6a6eb6f21",
    "P1/The Blackwood": "ef693b20b4ad",
    "P1/Holten": "78d8861e8453",
    "P1/Wolvenhold": "906c2999a2ca",
    "P1/Holten Estate": "eb8fdfe73ab7",
    "P2/": "ab9aa1a534bb",
    "P2/The Khari Bazaar": "6a1dd080868b",
    "P2/The Khari Crossing": "2f99989e74af",
    "P2/Pools of Khatal": "fa962d055bca",
    "P2/Sel Khari Sanctuary": "6454abb5cc3d",
    "P2/The Galai Gates": "539ffed48d4b",
    "P2/Qimah": "426693669f2e",
    "P2/Qimah Reservoir": "b1d943e0b0f7",
    "P3/": "7654b3ed35e5",
    "P3/The Glade": "4303c8e765cb",
    "P3/Ashen Forest": "fce5b77f5622",
    "P3/Kriar Village": "37555bfedc22",
    "P3/Glacial Tarn": "1448b327bc04",
    "P3/Howling Caves": "8df99b6282d4",
    "P3/Kriar Peaks": "007cd066194a",
    "P3/Etched Ravine": "30ea401e9400",
    "P3/The Cuachic Vault": "7e5db9985048",
    "endgame": "de87e798acf9",
}


def _guide_items(doc):
    """[(baseline key, entry)] for every act table, zone and the endgame."""
    out = []
    for key, act in doc["acts"].items():
        out.append((key + "/", {k: v for k, v in act.items() if k != "zones"}))
        for zone, z in act.get("zones", {}).items():
            out.append((key + "/" + zone, z))
    out.append(("endgame", doc["endgame"]))
    return out


def _new_or_changed(doc):
    """{key: (entry, how)} for entries that are new or changed against the
    baseline; how is "new", "changed" or "narrowed" (the book reword only)."""
    out = {}
    for key, entry in _guide_items(doc):
        base = BASELINE.get(key)
        if base is not None and _entry_hash(entry) == base:
            continue
        if base is not None and _entry_hash(_un_narrow(entry)) == base:
            out[key] = (entry, "narrowed")
        else:
            out[key] = (entry, "new" if base is None else "changed")
    return out


def test_new_or_changed_guide_entries_carry_their_own_src_and_checked(tmp_path):
    guide = json.loads(provenance.GUIDE.read_text(encoding="ascii"))
    assert len(BASELINE) == 101
    found = _new_or_changed(guide)
    narrowed = sorted(k for k, (_, how) in found.items() if how == "narrowed")
    assert len(narrowed) == 11
    for key, (entry, how) in found.items():
        if how == "narrowed":
            continue        # the old pair stands: nothing new is claimed
        src, checked = entry.get("src"), entry.get("checked")
        assert provenance.valid_src(src) and provenance.valid_checked(checked), key
        assert not src.startswith("research:"), (key, src)
        assert checked >= "2026-11-21", (key, checked)
    assert {k for k, (_, how) in found.items() if how != "narrowed"} >= {
        "G1/Root Hollow", "G3/Library of Kamasa", "G4/Isle of Decay",
        "G4/Brinerot Cove", "G6/", "G6/Interlude"}
    # the rule bites: an edited text, a new zone that inherits its act's
    # pair, or one citing a research note is caught
    bad = json.loads(json.dumps(guide))
    bad["acts"]["G1"]["zones"]["The Riverbank"]["objective"] = "Something new."
    bad["acts"]["G2"]["zones"]["A New Zone"] = {"objective": "Go on."}
    bad["acts"]["G3"]["zones"]["Another Zone"] = {"objective": "Go on.",
                                                  "src": "research:0034",
                                                  "checked": "2026-11-21"}
    hits = _new_or_changed(bad)
    for key in ("G1/The Riverbank", "G2/A New Zone", "G3/Another Zone"):
        entry, how = hits[key]
        assert how in ("new", "changed")
        src = entry.get("src")
        assert src is None or src.startswith("research:"), key
    # a narrowed entry that also slips in a new fact is a changed entry
    bad = json.loads(json.dumps(guide))
    zone = bad["acts"]["G1"]["zones"]["Hunting Grounds"]
    zone["optional"][0]["text"] += " Twice."
    assert _new_or_changed(bad)["G1/Hunting Grounds"][1] == "changed"


def test_src_refuses_wiki_poe2db_and_forum_hosts():
    for bad in ("poe2db.tw", "https://poe2db.tw/us/Root_Hollow", "poe2db",
                "www.poe2wiki.net", "poe2wiki.net", "wiki", "poewiki",
                "https://www.pathofexile.com/forum/view-thread/1",
                "pathofexile.com/forum", "forum", "ggg-forum", "reddit.com",
                "snapshot:poe2db.tw", "ggg-export:forum.thread", "operator poe2db.tw",
                "research:0034 wiki", "log poe2wiki.net"):
        assert not provenance.valid_src(bad), bad
    # no shipped entry names a host, and no new or changed one cites a
    # research note, wiki, poe2db or forum page
    for e in provenance.entries():
        low = str(e["src"]).lower()
        assert "wiki" not in low and "poe2db" not in low and "forum" not in low, e
    guide = json.loads(provenance.GUIDE.read_text(encoding="ascii"))
    for key, (entry, how) in _new_or_changed(guide).items():
        if how != "narrowed":
            assert entry["src"].split(":", 1)[0] in ("snapshot", "ggg-export",
                                                     "log", "operator"), key
