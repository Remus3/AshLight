"""ITEM-INFO-GEM-DETAIL (decision 0083 amendment 2026-11-28): a gem's
in-game details in the shared item popover, from the cached repoe-fork
skill_gems / skills / gem_tags export only.

Synthetic fixtures in the export's shape (names from the real gem list,
numbers made up). The snapshot tool derives one small file per gem; the
core reads one file per look; nothing goes on the network; unknown
fields stay out.
"""

import json
import socket
import urllib.request

import pytest

from server.al import iteminfo
from server.al.theorycraft import gemdetail, snapprobe, snapshot

from tests.test_iteminfo import auth, call, write_caches

SPARK_ID = "Metadata/Items/Gems/SkillGemSpark"

GEMS = {
    SPARK_ID: {
        "base_item": {"display_name": "Spark", "id": SPARK_ID, "release_state": "released"},
        "gem_type": "active", "grants_skills": ["SparkPlayer"],
        "tags": ["intelligence", "grants_active_skill", "spell", "projectile", "lightning"]},
    "Metadata/Items/Gem/SkillGemUniqueEarthboundTriggeredSpark": {
        "base_item": {"display_name": "Spark", "release_state": "released",
                      "id": "Metadata/Items/Gem/SkillGemUniqueEarthboundTriggeredSpark"},
        "gem_type": "active", "grants_skills": ["UniqueSpark"], "tags": ["spell"]},
    "Metadata/Items/Gems/SkillGemIceStrike": {
        "base_item": {"display_name": "Ice Strike", "release_state": "released"},
        "gem_type": "active", "grants_skills": ["IceStrikePlayer"], "tags": ["attack", "area"]},
    "Metadata/Items/Gems/SupportGemBrutality": {
        "base_item": {"display_name": "Brutality I", "release_state": "released"},
        "gem_type": "support", "grants_skills": ["SupportBrutalityPlayer"],
        "support_text": "Supports any skill that deals [Physical] damage.",
        "tags": ["support", "physical"]},
    "Metadata/Items/Gems/SkillGemHeraldOfIce": {
        "base_item": {"display_name": "Herald of Ice", "release_state": "released"},
        "gem_type": "spirit", "grants_skills": ["HeraldOfIcePlayer"], "tags": []},
    "Metadata/Items/Gems/NoSkill": {
        "base_item": {"display_name": "Lost Gem", "release_state": "released"},
        "gem_type": "active", "grants_skills": ["Missing"]},
    "Metadata/Items/Gems/BadKind": {
        "base_item": {"display_name": "Odd Gem"}, "gem_type": "other",
        "grants_skills": ["SparkPlayer"]},
}

SKILLS = {
    "SparkPlayer": {
        "active_skill": {"description": "Launch [Projectile|Projectiles] of [Lightning].",
                         "types": ["Spell", "Projectile"]},
        "cast_time": 700, "is_support": False, "static": {},
        "per_level": {"1": {"costs": {"Mana": 5}}, "2": {"costs": {"Mana": 6}},
                      "20": {"costs": {"Mana": 56, "Odd Cost!": 3}}},
        "stat_sets": [
            {"id": "SparkPlayer", "label": ["Base", "Base", True],
             "static": {"crit_chance": 900,
                        "stat_text": {"dur": "[Projectile] duration is 2 seconds"},
                        "tooltip_order": ["min\nmax", "count", "dur"]},
             "per_level": {"1": {"stat_text": {"count": "Fires 4 [Projectile|Projectiles]",
                                               "min\nmax": "Deals 1 to 10 [Lightning] Damage"}},
                           "2": {"stat_text": {"count": "Fires 5 [Projectile|Projectiles]",
                                               "min\nmax": "Deals 1 to 13 [Lightning] Damage"}},
                           "20": {"stat_text": {"count": "Fires 9 [Projectile|Projectiles]",
                                                "min\nmax": "Deals 11 to 216 [Lightning] Damage"}}}},
            {"id": "SparkInfused", "label": ["Infused", "Cold-Infused", True],
             "static": {"crit_chance": 200,
                        "stat_text": {"nova": "Fires 12 [Projectile|Projectiles]\nin a circle"}},
             "per_level": {"1": {}, "2": {}, "20": {}}}]},
    "UniqueSpark": {"active_skill": {"description": "Unique copy"}, "cast_time": 1,
                    "per_level": {"1": {}}, "stat_sets": []},
    "IceStrikePlayer": {
        "active_skill": {"description": "Perform an icy [Strike].",
                         "types": ["Attack", "Melee"]},
        "cast_time": 1000, "static": {"attack_speed_multiplier": 40},
        "per_level": {"1": {"costs": {"Mana": 5}}},
        "stat_sets": [{"label": ["N", "Normal Strikes"], "static": {},
                       "per_level": {"1": {"damage_multiplier": 60,
                                           "stat_text": {"conv": "Converts 80% to [Cold]"}}}}]},
    "SupportBrutalityPlayer": {
        "is_support": True, "static": {"cost_multiplier": 120}, "per_level": {"1": {}},
        "stat_sets": [{"label": None, "static": {
            "stat_text": {"a": "Supported Skills deal 25% more [Physical] Damage",
                          "b": "Supported Skills deal no [Chaos] Damage"},
            "tooltip_order": ["a", "b"]}, "per_level": {"1": {}}}]},
    "HeraldOfIcePlayer": {
        "active_skill": {"description": "While active, enemies [Shatter].", "types": ["Buff"]},
        "cast_time": 0, "static": {"reservations": {"spirit": 30}, "cooldown": 1500},
        "per_level": {"1": {}, "5": {}},
        "stat_sets": [{"label": ["Buff", "Buff"],
                       "static": {"stat_text": {"x": "Enemies you [Shatter] explode"}},
                       "per_level": {"1": {}, "5": {}}}]},
}

TAGS = {"spell": "[Spell]", "projectile": "[Projectile]", "lightning": "[Lightning]",
        "intelligence": None, "grants_active_skill": None, "attack": "[Attack]",
        "area": "[AoESkill|AoE]", "support": "Support", "physical": "[Physical]"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network call during a gem detail look")
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(snapshot, "http_fetch", boom)


def manifest(tag="a"):
    return {"files": {n: {"sha256": f"{n}-{tag}"} for n in gemdetail.INPUTS}}


def write_export(gd):
    gd.mkdir(parents=True, exist_ok=True)
    for name, doc in (("gems", GEMS), ("skills", SKILLS), ("gem_tags", TAGS)):
        (gd / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")


def derived(gd):
    write_export(gd)
    assert gemdetail.refresh(gd, manifest()).startswith("written (")
    return gemdetail.GemDetails(gd / gemdetail.DIR_NAME)


# --- derive and the core's read ------------------------------------------

def test_spark_level_one_reads_the_export_words(tmp_path):
    gem = derived(tmp_path).lookup("spark")
    assert gem == {
        "kind": "active", "tags": ["Spell", "Projectile", "Lightning"],
        "description": "Launch Projectiles of Lightning.",
        "cast_time_s": 0.7, "max_level": 20, "level": 1,
        "costs": [{"type": "Mana", "amount": 5}],
        "sets": [{"label": "Base", "crit_pct": 9.0,
                  "lines": ["Deals 1 to 10 Lightning Damage", "Fires 4 Projectiles",
                            "Projectile duration is 2 seconds"]},
                 {"label": "Cold-Infused", "crit_pct": 2.0,
                  "lines": ["Fires 12 Projectiles in a circle"]}]}


def test_level_picks_that_level_else_the_nearest_below(tmp_path):
    look = derived(tmp_path)
    at20 = look.lookup("Spark", 20)
    assert at20["level"] == 20 and at20["sets"][0]["lines"][0] == "Deals 11 to 216 Lightning Damage"
    assert at20["costs"] == [{"type": "Mana", "amount": 56}]   # a bad cost id is left out
    assert look.lookup("Spark", 7)["level"] == 2
    assert look.lookup("Spark", 99)["level"] == 1   # out of range reads the default


def test_normal_gem_wins_over_a_unique_granted_copy(tmp_path):
    assert derived(tmp_path).lookup("Spark")["description"] != "Unique copy"


def test_attack_has_damage_but_no_cast_time_or_speed(tmp_path):
    gem = derived(tmp_path).lookup("Ice Strike")
    assert "cast_time_s" not in gem and "attack_speed" not in json.dumps(gem)
    assert gem["tags"] == ["Attack", "AoE"]
    assert gem["sets"] == [{"damage_pct": 60, "lines": ["Converts 80% to Cold"]}]


def test_support_gives_its_text_lines_and_cost_multiplier(tmp_path):
    gem = derived(tmp_path).lookup("Brutality I")
    assert gem["kind"] == "support" and gem["max_level"] == 1
    assert gem["description"] == "Supports any skill that deals Physical damage."
    assert gem["cost_multiplier"] == 120 and "cast_time_s" not in gem
    assert gem["sets"] == [{"lines": ["Supported Skills deal 25% more Physical Damage",
                                      "Supported Skills deal no Chaos Damage"]}]


def test_spirit_gem_reservation_and_cooldown(tmp_path):
    gem = derived(tmp_path).lookup("Herald of Ice", 5)
    assert gem["kind"] == "spirit" and gem["spirit"] == 30 and gem["cooldown_s"] == 1.5
    assert "tags" not in gem and "cast_time_s" not in gem


def test_unknown_or_unshowable_gems_have_no_file(tmp_path):
    look = derived(tmp_path)
    for name in ("Lost Gem", "Odd Gem", "Chaos Orb"):
        assert look.lookup(name) is None


def test_refresh_writes_once_per_input_hash_and_skips_without_data(tmp_path):
    gd = tmp_path / "gd"
    derived(gd)
    assert gemdetail.refresh(gd, manifest()) == "fresh"
    assert gemdetail.refresh(gd, {"files": {}}) == "skipped: gem data not cached"
    assert gemdetail.refresh(gd, manifest("b")).startswith("written (")
    names = sorted(p.name for p in gd.iterdir())
    assert gemdetail.DIR_NAME + ".old" not in names and gemdetail.DIR_NAME + ".new" not in names
    (gd / "skills.json").write_text("{bad", encoding="utf-8")
    assert gemdetail.refresh(gd, manifest("c")).startswith("error: ")
    assert gemdetail.GemDetails(gd / gemdetail.DIR_NAME).lookup("Spark")   # old copy kept


def test_a_tampered_or_oversized_file_reads_as_nothing(tmp_path):
    look = derived(tmp_path)
    p = look.dir / (gemdetail.file_key("Spark") + ".json")
    doc = json.loads(p.read_text(encoding="ascii"))
    doc["name"] = "Other"
    p.write_text(json.dumps(doc), encoding="ascii")
    assert look.lookup("Spark") is None
    p.write_bytes(b" " * (gemdetail.FILE_MAX_BYTES + 1))
    assert look.lookup("Spark") is None


def test_written_files_are_ascii_and_small(tmp_path):
    look = derived(tmp_path)
    for p in look.dir.iterdir():
        p.read_bytes().decode("ascii")
        assert p.stat().st_size < gemdetail.FILE_MAX_BYTES


# --- the item lookup and the route ----------------------------------------

def test_item_lookup_adds_gem_and_fills_description(tmp_path):
    gd, _ = write_caches(tmp_path)
    derived(gd)
    info = iteminfo.ItemInfo(gd / "base_items.json", gd / "uniques.json", pob=None)
    reply = info.lookup("Spark", 2)
    f = reply["fields"]
    assert f["description"] == "Launch Projectiles of Lightning."
    assert "description" not in f["gem"] and f["gem"]["level"] == 2
    assert reply["sources"] == ["repoe-fork"] and reply["name"] == "Spark"
    assert "gem" not in info.lookup("Chaos Orb")["fields"]


def test_item_lookup_without_derived_files_has_no_gem(tmp_path):
    gd, _ = write_caches(tmp_path)
    info = iteminfo.ItemInfo(gd / "base_items.json", gd / "uniques.json", pob=None)
    assert info.lookup("Spark") == {"name": "Spark", "fields": {}, "sources": []}


@pytest.fixture
def core(tmp_path):
    from server.al.core import Core
    rt = tmp_path / "rt"
    gd, _ = write_caches(rt)
    derived(gd)
    (rt / "local.json").write_text(json.dumps({"web_data": False}), encoding="utf-8")
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=rt, log_path=str(log), tail=False)
    yield c
    c.close()


def test_route_takes_a_gem_level(core):
    status, body = call(core, "/api/iteminfo?name=Spark&level=20", auth())
    assert status == 200
    gem = json.loads(body)["fields"]["gem"]
    assert gem["level"] == 20 and gem["costs"] == [{"type": "Mana", "amount": 56}]
    status, body = call(core, "/api/iteminfo?name=Spark", auth())
    assert json.loads(body)["fields"]["gem"]["level"] == 1


def test_route_refuses_bad_levels(core):
    from server.al.text import iteminfo as text
    want = {"error": text.bad_level(gemdetail.LEVEL_MAX)}
    for q in ("level=0", "level=41", "level=x", "level=-1", "level=1&level=2", "level=007"):
        status, body = call(core, "/api/iteminfo?name=Spark&" + q, auth())
        assert (status, json.loads(body)) == (400, want), q


def test_bad_level_sentence_is_pinned():
    from server.al.text import iteminfo as text
    assert text.bad_level(40) == ("A gem level is a whole number from 1 to 40. "
                                  "Open the gem again.")


# --- the snapshot tool -----------------------------------------------------

def test_snapshot_sources_and_probes_cover_the_gem_files():
    for name in ("gems", "skills", "gem_tags"):
        assert name in snapshot.SOURCES and name in snapprobe.PROBES
        assert name in snapprobe.SOURCE_WORDS and name in snapshot.SOURCE_CAPS
    assert snapshot.SOURCES["gems"].endswith("/poe2/skill_gems.json")
    skills = {f"S{i}": {"stat_sets": []} for i in range(2000)}
    assert snapprobe.probe("skills", skills)["verdict"] == snapprobe.PASS
    assert snapprobe.probe("skills", {"a": {}})["verdict"] == snapprobe.FAIL
    assert snapprobe.probe("gem_tags", {f"t{i}": "[T]" for i in range(30)})["verdict"] == "pass"


def test_snapshot_main_derives_the_gem_files_after_a_run(tmp_path, monkeypatch, capsys):
    write_export(tmp_path)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest()), encoding="ascii")
    monkeypatch.setattr(snapshot, "run", lambda *a, **k: {})
    assert snapshot.main(["--dir", str(tmp_path)], environ={}, contact="", web_data=True) == 0
    assert "snapshot: gem_details: written (" in capsys.readouterr().out
    assert gemdetail.GemDetails(tmp_path / gemdetail.DIR_NAME).lookup("Spark")


def test_gemdetail_imports_no_network_code():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(gemdetail))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
            for a in n.names}
    mods |= {(n.module or "").split(".")[0] for n in ast.walk(tree)
             if isinstance(n, ast.ImportFrom)}
    assert not mods & {"socket", "urllib", "http", "ssl", "subprocess"}
