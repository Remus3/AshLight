"""TC-UNCUT-GEM (research 0064 G2, decision 0094): uncut gem advice on the
item-check press, from the build's gems (PoB build or Kindler stage) and
the cached gems snapshot. The item texts in tests/fixtures/uncut_gems are
SYNTHETIC (see its README): the snapshot's own base names and lines in the
item-text structure the item parser handles."""

import json
from pathlib import Path

import pytest

from server.al.core import Core
from server.al.state import eval_card_text
from server.al.plug import gemadvice as gemplug
from server.al.text import gemadvice as gemwords
from server.al.theorycraft import cardparts, codec, evaluate, gemadvice, item, live, model
from server.al.theorycraft.cardparts import uncut

FIX = Path(__file__).parent / "fixtures" / "uncut_gems"
SKILL_10 = (FIX / "uncut_skill_10.txt").read_text(encoding="ascii")
SUPPORT_3 = (FIX / "uncut_support_3.txt").read_text(encoding="ascii")
SPIRIT_14 = (FIX / "uncut_spirit_14.txt").read_text(encoding="ascii")
SKILL_PROP_5 = (FIX / "uncut_skill_prop_5.txt").read_text(encoding="ascii")
ROOT = Path(__file__).resolve().parents[1]

PLAIN_GEM = """Item Class: Skill Gems
Rarity: Gem
Example Strike
--------
Level: 5
--------
Requires: Level 15
"""


def _levels(n):
    return {str(i): {"requirements": {"level": i * 3}} for i in range(1, n + 1)}


# A repoe-fork shaped gems snapshot (DATA-GEMS-SNAP); names invented.
GEMS_DOC = {
    "Metadata/Items/Gems/SkillGemEmberBolt": {
        "base_item": {"display_name": "Ember Bolt", "id": "Metadata/Items/Gems/SkillGemEmberBolt",
                      "release_state": "released"},
        "is_support": False, "tags": ["spell", "fire"], "gem_tier": 1, "per_level": _levels(20)},
    "Metadata/Items/Gems/SkillGemFrostLance": {
        "base_item": {"display_name": "Frost Lance", "id": "x", "release_state": "released"},
        "is_support": False, "tags": ["spell"], "gem_tier": 5, "per_level": _levels(20)},
    "Metadata/Items/Gems/SkillGemStormCall": {
        "base_item": {"display_name": "Storm Call", "id": "x", "release_state": "released"},
        "is_support": False, "tags": ["spell"], "gem_tier": 13, "per_level": _levels(20)},
    "Metadata/Items/Gems/SkillGemAshWard": {
        "base_item": {"display_name": "Ash Ward", "id": "x", "release_state": "released"},
        "is_support": False, "tags": ["buff", "persistent"], "gem_tier": 4,
        "per_level": _levels(20)},
    "Metadata/Items/Gems/SkillGemHiddenOne": {
        "base_item": {"display_name": "Hidden One", "id": "x", "release_state": "unreleased"},
        "is_support": False, "tags": ["spell"], "gem_tier": 1, "per_level": _levels(20)},
    "Metadata/Items/Gems/SupportGemSharpEdge": {
        "base_item": {"display_name": "Sharp Edge", "id": "Metadata/Items/Gems/SupportGemSharpEdge",
                      "release_state": "released"},
        "is_support": True, "tags": ["support"], "gem_tier": 2, "per_level": _levels(1)},
    "Metadata/Items/Gems/SupportGemSwiftCast": {
        "base_item": {"display_name": "Swift Cast", "id": "Metadata/Items/Gems/SupportGemSwiftCast",
                      "release_state": "released"},
        "is_support": True, "tags": ["support"], "gem_tier": 3, "per_level": _levels(1)},
    "Metadata/Items/Gems/SupportGemHeavyHand": {
        "base_item": {"display_name": "Heavy Hand", "id": "Metadata/Items/Gems/SupportGemHeavyHand",
                      "release_state": "released"},
        "is_support": True, "tags": ["support"], "gem_tier": 4, "per_level": _levels(1)},
    # no gem_tier: the snapshot gives no tier, so it is never claimed makeable
    "Metadata/Items/Gems/SkillGemQuietSpark": {
        "base_item": {"display_name": "Quiet Spark", "id": "x", "release_state": "released"},
        "is_support": False, "tags": ["spell"], "per_level": _levels(20)},
}
GEMS = gemadvice.table(GEMS_DOC)


def gem(name, level, enabled=True):
    return model.Gem(name=name, level=level, enabled=enabled)


BUILD = model.Build(raw_xml="", skills=(
    model.SkillGroup(gems=(gem("Ember Bolt", 7), gem("Sharp Edge", 1),
                           gem("Swift Cast", 1, enabled=False))),
    model.SkillGroup(gems=(gem("Frost Lance", 12), gem("Heavy Hand", 1))),
    model.SkillGroup(gems=(gem("Storm Call", 1),)),
    model.SkillGroup(gems=(gem("Quiet Spark", 2),)),
    model.SkillGroup(gems=(gem("Ash Ward", 3), gem("Unknown Gem", 1)), enabled=False),
))


@pytest.fixture(autouse=True)
def fresh_parts():
    cardparts.reset()
    yield
    cardparts.reset()



# -- the uncut gem text --------------------------------------------------------

def test_fixture_shapes_parse_kind_and_level():
    assert gemadvice.parse_uncut(SKILL_10) == {"kind": "skill", "level": 10}
    assert gemadvice.parse_uncut(SUPPORT_3) == {"kind": "support", "level": 3}
    assert gemadvice.parse_uncut(SPIRIT_14) == {"kind": "spirit", "level": 14}
    assert gemadvice.parse_uncut(SKILL_PROP_5) == {"kind": "skill", "level": 5}
    crlf = SKILL_10.replace("\n", "\r\n")
    assert gemadvice.parse_uncut(crlf) == {"kind": "skill", "level": 10}


def test_fixtures_are_marked_synthetic():
    readme = (FIX / "README.md").read_text(encoding="ascii")
    assert readme.splitlines()[2].startswith("SYNTHETIC")


def test_other_items_are_not_uncut_gems():
    assert gemadvice.parse_uncut(PLAIN_GEM) is None
    assert gemadvice.parse_uncut("") is None
    assert gemadvice.parse_uncut(None) is None
    assert gemadvice.parse_uncut("x" * 9000) is None
    # a kind with no level is no answer (the item level is not the cut level)
    assert gemadvice.parse_uncut("Item Class: Uncut Skill Gems\nRarity: Currency\n"
                                 "Uncut Skill Gem\n--------\nItem Level: 12\n") is None


def test_item_parser_still_reads_the_uncut_text():
    parsed = item.parse(SKILL_10)
    assert parsed.item_class == "Uncut Skill Gems"
    assert parsed.base == "Uncut Skill Gem (Level 10)"


# -- the snapshot table ----------------------------------------------------------

def test_snapshot_kinds_tiers_needs_and_releases():
    assert GEMS["ember bolt"]["kind"] == "skill"
    assert GEMS["ash ward"]["kind"] == "spirit"
    assert GEMS["sharp edge"]["kind"] == "support"
    assert GEMS["frost lance"]["tier"] == 5
    assert GEMS["quiet spark"]["tier"] is None
    assert GEMS["ember bolt"]["max_level"] == 20
    assert GEMS["ember bolt"]["need"] == 3
    assert "hidden one" not in GEMS


def test_support_names_match_with_or_without_the_word():
    assert gemadvice.norm("Support: Sharp Edge") == "sharp edge"
    assert gemadvice.norm("Sharp Edge Support") == "sharp edge"
    assert gemadvice.lookup(GEMS, {"name": "Sharp Edge Support"})["name"] == "Sharp Edge"
    assert gemadvice.lookup(GEMS, {"name": "Unknown Gem"}) is None


# -- the advice ------------------------------------------------------------------

def advise(text, build, tab=GEMS):
    return gemadvice.cut_options(text, gemadvice.pob_gems(build), tab)


def names(answer):
    return [g["name"] for g in answer["gems"]]


def test_skill_10_names_gems_it_can_make_and_raise():
    answer = advise(SKILL_10, BUILD)
    # Ember Bolt (tier 1, shown at 7) gains; Frost Lance already 12; Storm
    # Call is tier 13; Ash Ward is a spirit gem; Unknown Gem is not in the
    # snapshot and is never guessed; Quiet Spark has no tier: unchecked
    assert answer["kind"] == "skill" and answer["level"] == 10
    assert names(answer) == ["Ember Bolt"]
    assert answer["gems"][0] == {"name": "Ember Bolt", "level": 10, "have": 7}
    assert answer["unchecked"] == ["Quiet Spark"]


def test_support_3_names_disabled_supports_within_its_tier():
    answer = advise(SUPPORT_3, BUILD)
    # Sharp Edge is socketed and enabled at its one level; Swift Cast is
    # disabled in PoB, so not shown as socketed; Heavy Hand is tier 4
    assert names(answer) == ["Swift Cast"]
    assert answer["gems"][0]["level"] == 1


def test_spirit_14_counts_a_disabled_group_as_not_socketed():
    answer = advise(SPIRIT_14, BUILD)
    assert names(answer) == ["Ash Ward"]
    assert answer["gems"][0] == {"name": "Ash Ward", "level": 14, "have": 0}


def test_no_build_or_no_snapshot_shows_nothing():
    assert advise(SKILL_10, None) is None
    assert advise(SKILL_10, BUILD, None) is None
    assert advise(SKILL_10, BUILD, {}) is None
    assert advise(PLAIN_GEM, BUILD) is None


def test_nothing_to_gain_is_an_empty_list():
    built = model.Build(raw_xml="", skills=(
        model.SkillGroup(gems=(gem("Ember Bolt", 20),)),))
    answer = advise(SKILL_10, built)
    assert answer["gems"] == [] and answer["unchecked"] == [] and answer["more"] == 0


def test_kindler_stage_gems_are_read_with_no_level():
    rows = [{"name": "Ember Bolt", "supports": [{"name": "Swift Cast"}]},
            {"name": "Storm Call", "supports": []}]
    gems = gemadvice.stage_gems(rows)
    assert [g["name"] for g in gems] == ["Ember Bolt", "Swift Cast", "Storm Call"]
    assert all(g["level"] is None and g["on"] for g in gems)
    answer = gemadvice.cut_options(SKILL_10, gems, GEMS)
    assert answer["gems"] == [{"name": "Ember Bolt", "level": 10, "have": 0}]
    plan = {"stages": [{"skills": rows[1:]}, {"skills": rows[:1]}]}
    assert [g["name"] for g in gemadvice.plan_stage_gems(plan, 1)] == ["Ember Bolt",
                                                                      "Swift Cast"]
    assert [g["name"] for g in gemadvice.plan_stage_gems(plan, None)] == ["Storm Call"]
    assert gemadvice.plan_stage_gems(None, 0) == []


# -- the words -------------------------------------------------------------------

def test_notes_are_pinned_exactly():
    assert gemwords.CUT_MAKES == "A level {level} {kind} cut can make your build's {names}."
    assert gemwords.CUT_MAKES_MORE == ("A level {level} {kind} cut can make your build's "
                                       "{names} and {n} more.")
    assert gemwords.CUT_MAKES_COUNT == ("A level {level} {kind} cut can make {n} {gems} of "
                                        "your build.")
    assert gemwords.CUT_NONE == "No {kind} gem of your build needs a level {level} cut."
    assert gemwords.CUT_UNCHECKED == ("The skill gem list gives no tier for {names}, so "
                                      "check the cut in game.")
    assert gemwords.CUT_UNCHECKED_COUNT == ("The skill gem list gives no tier for {n} {gems}, "
                                            "so check the cut in game.")
    assert (gemwords.GEM, gemwords.GEMS) == ("gem", "gems")
    assert gemwords.cut_notes(advise(SKILL_10, BUILD)) == [
        "A level 10 skill cut can make your build's Ember Bolt.",
        "The skill gem list gives no tier for Quiet Spark, so check the cut in game."]
    built = model.Build(raw_xml="", skills=(model.SkillGroup(gems=(gem("Ember Bolt", 20),)),))
    assert gemwords.cut_notes(advise(SKILL_10, built)) == [
        "No skill gem of your build needs a level 10 cut."]
    three = {"kind": "skill", "level": 4, "more": 0,
             "gems": [{"name": "A"}, {"name": "B"}, {"name": "C\u00e9"}]}
    assert gemwords.cut_notes(three) == ["A level 4 skill cut can make your build's A, B and C."]
    one = {"kind": "skill", "level": 4, "gems": [{"name": " ".join(["Long"] * 30)}],
           "unchecked": [" ".join(["Odd"] * 30)]}
    assert gemwords.cut_notes(one) == [
        "A level 4 skill cut can make 1 gem of your build.",
        "The skill gem list gives no tier for 1 gem, so check the cut in game."]
    assert gemwords.cut_notes(None) == [] and gemwords.cut_notes({"kind": "x"}) == []


def test_notes_fit_20_words_with_many_names():
    value = {"kind": "skill", "level": 20, "more": 3,
             "unchecked": [f"Odd {i}" for i in range(12)],
             "gems": [{"name": f"Long Gem Name {i}", "level": 20, "have": 1}
                      for i in range(10)]}
    made, unsure = gemwords.cut_notes(value)
    assert len(made.split()) <= 20 and made.endswith("more.")
    assert made.startswith("A level 20 skill cut can make your build's Long Gem Name 0")
    assert unsure == "The skill gem list gives no tier for 12 gems, so check the cut in game."
    capped = dict(value, unchecked=["Odd"], unchecked_more=30)
    assert gemwords.cut_notes(capped)[1] == ("The skill gem list gives no tier for 31 gems, "
                                             "so check the cut in game.")
    for line in (made, unsure):
        assert line.isascii() and "!" not in line
        for word in ("owned", "have", "socketed", "you own"):
            assert word not in line


def test_the_copy_sheet_lists_every_template():
    sheet = (ROOT / "docs" / "design" / "copy" / "gemadvice.md").read_text(encoding="ascii")
    for name in dir(gemwords):
        v = getattr(gemwords, name)
        if isinstance(v, str) and name.isupper():
            assert f"`{v}`" in sheet, name


# -- the card part ---------------------------------------------------------------

def ctx_for(text, build, plan_gems=None):
    ctx = {"text": text, "parsed": item.parse(text),
           "result": evaluate.evaluate(text, build, None), "build": build,
           "character": "Tester", "level": 30, "area_id": None, "config": dict}
    if plan_gems is not None:
        ctx["plan_gems"] = plan_gems
    return ctx


def card_for(text, build, plan_gems=None):
    ctx = ctx_for(text, build, plan_gems)
    card = live.compact(ctx["result"])
    card["parts"] = cardparts.compute(ctx)
    return card, eval_card_text(card)


def test_card_names_the_gems(monkeypatch):
    monkeypatch.setattr(uncut, "_table", lambda ctx: GEMS)
    card, out = card_for(SKILL_10, BUILD)
    assert card["parts"]["uncut"]["gems"][0]["name"] == "Ember Bolt"
    assert "A level 10 skill cut can make your build's Ember Bolt." in out["notes"]
    # the verdict word and head stay the item check's own
    plain = live.compact(evaluate.evaluate(SKILL_10, BUILD, None))
    plain["parts"] = {}
    assert out["head"] == eval_card_text(plain)["head"]


def test_card_reads_the_kindler_stage_without_a_build(monkeypatch):
    monkeypatch.setattr(uncut, "_table", lambda ctx: GEMS)
    stage = gemadvice.stage_gems([{"name": "Frost Lance", "supports": []}])
    card, _ = card_for(SKILL_10, None, plan_gems=lambda: stage)
    assert card["parts"]["uncut"]["gems"] == [{"name": "Frost Lance", "level": 10, "have": 0}]
    card, _ = card_for(SKILL_10, None, plan_gems=lambda: 1 / 0)
    assert "uncut" not in card["parts"]


def test_card_part_absent_without_build_or_snapshot(monkeypatch):
    monkeypatch.setattr(uncut, "_table", lambda ctx: GEMS)
    card, _ = card_for(SKILL_10, None)
    assert "uncut" not in card["parts"]
    card, _ = card_for(SKILL_10, None, plan_gems=lambda: [])
    assert "uncut" not in card["parts"]
    monkeypatch.setattr(uncut, "_table", lambda ctx: None)
    card, _ = card_for(SKILL_10, BUILD)
    assert "uncut" not in card["parts"]


def test_other_items_never_read_the_snapshot(monkeypatch):
    def boom(ctx):
        raise AssertionError("snapshot read for a non-uncut press")
    monkeypatch.setattr(uncut, "_table", boom)
    card, _ = card_for(PLAIN_GEM, BUILD)
    assert "uncut" not in card["parts"]


def test_snapshot_index_reads_the_cached_file(tmp_path):
    path = tmp_path / "gems.json"
    path.write_text(json.dumps(GEMS_DOC), encoding="ascii")
    assert gemadvice.index(path)["ember bolt"]["tier"] == 1
    assert gemadvice.index(tmp_path / "missing.json") is None


def test_plug_plan_gems_reads_only_a_kindler_model():
    class Holder:
        def __init__(self, model):
            self.model = model

        def get(self):
            return self.model

    class FakeCore:
        pass

    core = FakeCore()
    assert gemplug.plan_gems(core) == []
    core.progression = Holder({"source": "pob", "skills": [{"name": "Ember Bolt"}]})
    assert gemplug.plan_gems(core) == []
    core.progression = Holder({"source": "kindler",
                               "skills": [{"name": "Ember Bolt", "supports": []}]})
    assert [g["name"] for g in gemplug.plan_gems(core)] == ["Ember Bolt"]


BUILD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding2>
  <Build level="30" className="Sorceress" ascendClassName="None" mainSocketGroup="1">
  </Build>
  <Tree activeSpec="1"></Tree>
  <Items activeItemSet="1"><ItemSet id="1"/></Items>
  <Skills activeSkillSet="1">
    <SkillSet id="1">
      <Skill enabled="true"><Gem nameSpec="Ember Bolt" level="6" enabled="true"/></Skill>
    </SkillSet>
  </Skills>
  <Config></Config>
</PathOfBuilding2>
"""


def test_press_through_the_core(tmp_path, monkeypatch):
    monkeypatch.setattr(uncut, "_table", lambda ctx: GEMS)
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    try:
        assert callable(core.last_eval.ctx_extra.get("plan_gems"))
        assert callable(core.last_eval.ctx_extra.get("gem_table"))
        core.last_eval.run(SKILL_10)
        assert "uncut" not in core.state.snapshot()["eval"]["parts"]  # no build, no plan
        core.builds.load_code(codec.encode(BUILD_XML))
        core.last_eval.run(SKILL_10)
        ev = core.state.snapshot()["eval"]
        assert ev["parts"]["uncut"]["gems"] == [{"name": "Ember Bolt", "level": 10, "have": 6}]
        assert "A level 10 skill cut can make your build's Ember Bolt." in ev["text"]["notes"]
    finally:
        core.close()


def test_the_core_reads_its_own_cached_snapshot(tmp_path):
    rt = tmp_path / "rt"
    (rt / "gamedata").mkdir(parents=True)
    (rt / "gamedata" / "gems.json").write_text(json.dumps(GEMS_DOC), encoding="ascii")
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=rt, log_path=str(log), poll_s=0.05)
    try:
        core.builds.load_code(codec.encode(BUILD_XML))
        core.last_eval.run(SKILL_10)
        ev = core.state.snapshot()["eval"]
        assert ev["parts"]["uncut"]["gems"] == [{"name": "Ember Bolt", "level": 10, "have": 6}]
    finally:
        core.close()
