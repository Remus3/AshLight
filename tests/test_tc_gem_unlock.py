"""TC-GEM-UNLOCK (research 0064 G3, decision 0095): the gem unlock card and
next-up steps for a pasted build.

On the player's own level-up line, when a skill or support gem of the
loaded build has a gems snapshot level requirement that the new level now
meets, the core publishes one card naming it (at most one card per
level-up, however many gems unlock), for the decision 0014 card time,
with a row in the recent events list as its dashboard twin.

- no build, or no gems snapshot: no card and no row;
- two gems at one level: one card naming both, one row;
- the card leaves by itself after the card time (20 s, or the layout's
  card_s), a press drops it, parts.moment off hides it;
- another player's level-up, a disabled gem and a gem of another level
  show nothing;
- the plug feeds the build's gems and the cached snapshot index into the
  state, the index read only while a build is loaded;
- the Progression next-up strip gets one step per gem whose snapshot level
  is the player's level (progression.add_next_source), at most 2 steps of
  52 characters, never for a Kindler plan, never claiming the gem is owned.

The log lines, builds and snapshots are invented fixtures; no game file
is read and nothing is sent.
"""

import json

import pytest

from server.al import gemunlock, layout, overlayview, parser
from server.al.plug import gemadvice as advice_plug
from server.al.plug import gemunlock as plug
from server.al.state import SessionState
from server.al.text import gemunlock as words
from server.al.text.common import CARD_LINE
from server.al.theorycraft import gemadvice, model, progression

T0 = 50000.0


def _level(level, who="Emberwright"):
    return (f"2026/11/16 20:00:01 900 1a2b3c4d [INFO Client 4242] : "
            f"{who} (Witch) is now level {level}")


def _xml(*gems, disabled=()):
    rows = "".join(
        f'<Gem nameSpec="{g}" level="1" enabled="{"false" if g in disabled else "true"}"/>'
        for g in gems)
    return ('<PathOfBuilding2><Build level="1" className="Witch"/>'
            '<Tree activeSpec="1"><Spec nodes=""/></Tree>'
            f'<Skills><Skill enabled="true">{rows}</Skill></Skills></PathOfBuilding2>')


def _doc(needs, supports=()):
    """A repoe-fork shaped gems snapshot: {name: level requirement}."""
    return {f"Metadata/Items/Gems/{'Support' if n in supports else 'Skill'}Gem{i}": {
        "base_item": {"display_name": n, "release_state": "released"},
        "is_support": n in supports, "requirements": {"level": lv}}
        for i, (n, lv) in enumerate(needs.items())}


INDEX = gemadvice.table(_doc({"Frost Bomb": 14, "Flame Wall": 14, "Spark": 1,
                              "Arcane Surge": 15, "Ice Nova": 14}))


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


def _state(build_gems=("Spark", "Frost Bomb", "Flame Wall", "Arcane Surge"), index=INDEX):
    clock = Clock()
    st = SessionState(clock=clock)
    if build_gems is not None:
        st.set_gem_unlock(gems=list(build_gems))
    if index is not None:
        st.set_gem_unlock(index=index)
    return st, clock


def _feed(st, clock, *lines, at=None):
    if at is not None:
        clock.t = at
    for line in lines:
        ev = parser.parse_line(line)
        assert ev is not None, line
        ev["recv_ts"] = clock.t
        st.apply(ev)


def _card(st, at):
    st._clock.t = at
    return st.snapshot()["card"]


def _rows(st):
    return [r for r in st.snapshot()["recent_events"] if r.get("type") == "gem_unlock"]


# -- the pure parts --------------------------------------------------------

def test_build_gems_reads_enabled_gems_once_in_build_order():
    build = model.parse(_xml("Spark", "Frost Bomb", "Spark", "Ice Nova",
                             disabled=("Ice Nova",)))
    assert gemunlock.build_gems(build) == ["Spark", "Frost Bomb"]
    assert gemunlock.build_gems(None) == []


def test_unlocked_names_the_gems_the_new_level_now_meets():
    gems = ["Spark", "Frost Bomb", "Flame Wall", "Arcane Surge"]
    assert gemunlock.unlocked(13, 14, gems, INDEX) == ["Frost Bomb", "Flame Wall"]
    assert gemunlock.unlocked(14, 15, gems, INDEX) == ["Arcane Surge"]
    # a skipped level counts every level passed; an unknown one only this one
    assert gemunlock.unlocked(13, 15, gems, INDEX) == ["Frost Bomb", "Flame Wall",
                                                      "Arcane Surge"]
    assert gemunlock.unlocked(None, 14, gems, INDEX) == ["Frost Bomb", "Flame Wall"]
    assert gemunlock.unlocked(15, 16, gems, INDEX) == []
    assert gemunlock.unlocked(13, 14, gems, None) == []
    assert gemunlock.unlocked(13, 14, [], INDEX) == []
    # a support named without its " Support" suffix still matches
    support = gemadvice.table(_doc({"Martial Tempo Support": 5}))
    assert gemunlock.unlocked(4, 5, ["Martial Tempo"], support) == ["Martial Tempo"]
    # a gem the snapshot gives no level never unlocks
    odd = gemadvice.table({"x": {"base_item": {"display_name": "Odd"}}})
    assert odd["odd"]["need"] is None
    assert gemunlock.unlocked(1, 2, ["Odd"], odd) == []


def test_card_and_row_words_fit_and_name_every_gem():
    one = words.card_lines(14, ["Frost Bomb"])
    two = words.card_lines(14, ["Frost Bomb", "Flame Wall"])
    many = words.card_lines(100, ["A Very Long Gem Name Of Many Words", "B", "C"])
    assert words.HEAD_ONE == "Gem usable at level {level}"
    assert words.HEAD_MANY == "{n} gems usable at level {level}"
    assert one == ("Gem usable at level 14", "Frost Bomb", "")
    assert two == ("2 gems usable at level 14", "Frost Bomb", "Flame Wall")
    assert many[0] == "3 gems usable at level 100" and many[2] == "and 2 more"
    assert words.HEAD_MANY_SHORT == "{n} gems usable, Lv {level}"
    assert words.card_lines(100, [f"G{i}" for i in range(12)])[0] == "12 gems usable, Lv 100"
    assert words.card_lines(14, ["Fr\u00f6st Bomb"])[1] == "Frst Bomb"
    for lines in (one, two, many):
        assert all(len(x) <= CARD_LINE and x.isascii() for x in lines), lines
    assert words.ROW_TEXT == "Level {level} makes {names} usable"
    assert words.row_text(14, ["Frost Bomb"]) == "Level 14 makes Frost Bomb usable"
    assert (words.row_text(14, ["Frost Bomb", "Flame Wall"])
            == "Level 14 makes Frost Bomb and Flame Wall usable")
    assert words.row_text(14, ["A", "B", "C"]) == "Level 14 makes A, B and 1 more usable"
    names = [f"Gem {i}" for i in range(9)]
    assert words.row_text(20, names) == "Level 20 makes Gem 0, Gem 1 and 7 more usable"
    assert len(words.row_text(20, ["x" * 60] * 9)) <= 90


# -- the ACCEPT cases --------------------------------------------------------

def test_no_build_shows_no_card_and_no_row():
    st, clock = _state(build_gems=None)
    _feed(st, clock, _level(13), _level(14))
    assert st.snapshot()["card"] is None or st.snapshot()["card"]["kind"] != "gem"
    assert _rows(st) == []
    # a build without gems is the same
    st.set_gem_unlock(gems=[])
    _feed(st, clock, _level(15))
    assert _rows(st) == []


def test_no_snapshot_shows_no_card_and_no_row():
    st, clock = _state(index=None)
    _feed(st, clock, _level(13), _level(14))
    card = st.snapshot()["card"]
    assert card is None or card["kind"] != "gem"
    assert _rows(st) == []


def test_two_gems_at_one_level_make_one_card_naming_both():
    st, clock = _state()
    _feed(st, clock, _level(13), at=T0)
    assert _rows(st) == []
    _feed(st, clock, _level(14), at=T0 + 5)
    card = _card(st, T0 + 5)
    assert card["kind"] == "gem"
    assert (card["head"], card["line2"], card["line3"]) == (
        "2 gems usable at level 14", "Frost Bomb", "Flame Wall")
    assert card["expires_at"] == T0 + 5 + layout.CARD_S[0]
    rows = _rows(st)
    assert len(rows) == 1
    assert rows[0]["text"] == "Level 14 makes Frost Bomb and Flame Wall usable"
    # it expires by itself
    assert _card(st, T0 + 5 + layout.CARD_S[0] - 0.1)["kind"] == "gem"
    assert _card(st, T0 + 5 + layout.CARD_S[0]) is None
    # the next level names only its own gem, in its own card
    _feed(st, clock, _level(15), at=T0 + 100)
    card = _card(st, T0 + 100)
    assert (card["head"], card["line2"]) == ("Gem usable at level 15", "Arcane Surge")
    assert len(_rows(st)) == 2


# -- the edges ---------------------------------------------------------------

def test_the_layout_card_time_and_moment_switch_apply():
    st, clock = _state()
    st.set_overlay_layout(layout.normalize({"card_s": 60}))
    _feed(st, clock, _level(13), _level(14), at=T0)
    assert _card(st, T0)["expires_at"] == T0 + 60
    st.set_overlay_layout(layout.normalize({"parts": {"moment": False}}))
    assert _card(st, T0 + 1) is None
    assert len(_rows(st)) == 1  # the dashboard row stays


def test_another_players_level_up_shows_nothing():
    st, clock = _state()
    _feed(st, clock, _level(13), at=T0)
    _feed(st, clock, _level(14, who="Partyfriend"), at=T0 + 1)
    assert _rows(st) == []
    assert _card(st, T0 + 1) is None


def test_a_press_drops_the_gem_card():
    st, clock = _state()
    _feed(st, clock, _level(13), _level(14), at=T0)
    assert _card(st, T0)["kind"] == "gem"
    st.overlay.on_press(T0 + 1)
    assert _card(st, T0 + 2) is None


def test_the_holder_declares_its_twin_and_card_time():
    holder = next(h for h in overlayview.CARD_HOLDERS if h["kind"] == "gem")
    assert holder["twin"] == ("events",)
    assert holder["life_s"] == layout.CARD_S[0]
    kinds = [h["kind"] for h in overlayview.CARD_HOLDERS]
    assert kinds.index("moment") < kinds.index("gem") < kinds.index("hint")


# -- the plug ----------------------------------------------------------------

class _Builds:
    def __init__(self, build=None):
        self.build = build
        self.listeners = []

    def add_listener(self, fn):
        self.listeners.append(fn)


class _Names:
    def __init__(self, path):
        self.path = path


class _Core:
    def __init__(self, tmp_path, build=None):
        self.state = SessionState(clock=Clock())
        self.builds = _Builds(build)
        self.base_names = _Names(tmp_path / "base_items.json")
        self.ticks = []

    def add_tick(self, name, fn=None):
        self.ticks.append((name, fn))


def _snapshot_file(tmp_path):
    doc = {"Metadata/Items/Gems/SkillGemFrostBomb": {
        "display_name": "Frost Bomb", "requirements": {"level": 14}},
        "Metadata/Items/Gems/SkillGemSpark": {
        "display_name": "Spark", "requirements": {"level": 1}}}
    (tmp_path / "gems.json").write_text(json.dumps(doc), encoding="utf-8")


def test_the_plug_feeds_build_gems_and_the_snapshot(tmp_path, monkeypatch):
    _snapshot_file(tmp_path)
    core = _Core(tmp_path)
    plug.attach(core)
    assert [n for n, _ in core.ticks] == ["gem_unlock"]
    assert core.gem_unlock.path == tmp_path / "gems.json"
    tick = core.ticks[0][1]
    reads = []
    real = gemadvice.index
    monkeypatch.setattr(gemadvice, "index", lambda path=None: reads.append(path) or real(path))
    tick()
    # no build: the snapshot is not read
    assert reads == []
    assert core.state.gem_unlock.gems == []
    core.builds.build = model.parse(_xml("Spark", "Frost Bomb"))
    for fn in core.builds.listeners:
        fn(core.builds.build)
    tick()
    assert core.state.gem_unlock.gems == ["Spark", "Frost Bomb"]
    assert reads == [tmp_path / "gems.json"]
    assert core.state.gem_unlock.index["frost bomb"]["need"] == 14
    st, clock = core.state, core.state._clock
    _feed(st, clock, _level(13), _level(14))
    assert [r["text"] for r in _rows(st)] == ["Level 14 makes Frost Bomb usable"]


@pytest.mark.parametrize("body", ["not json", json.dumps([1, 2])])
def test_the_plug_reads_a_bad_snapshot_as_none(tmp_path, body):
    (tmp_path / "gems.json").write_text(body, encoding="utf-8")
    core = _Core(tmp_path, build=model.parse(_xml("Frost Bomb")))
    plug.attach(core)
    core.ticks[0][1]()
    assert core.state.gem_unlock.index is None
    _feed(core.state, core.state._clock, _level(13), _level(14))
    assert _rows(core.state) == []


def test_the_plug_with_no_snapshot_file(tmp_path):
    core = _Core(tmp_path, build=model.parse(_xml("Frost Bomb")))
    plug.attach(core)
    core.ticks[0][1]()
    assert core.state.gem_unlock.index is None


# -- the next-up steps (decision 0092 hook) -----------------------------------

def _build(*gems, disabled=()):
    return model.parse(_xml(*gems, disabled=disabled))


def _ctx(level, build, source="pob"):
    return {"level": level, "area_id": None, "zone": None, "act": None, "source": source,
            "build": build, "plan": None, "stage": None}


def test_step_words_are_pinned_and_fit_52():
    assert words.STEP_ONE == "{kind} usable now: {name}"
    assert words.STEP_MORE == "{kind} usable now (+{n}): {name}"
    assert (words.GEM_WORD, words.SUPPORT_WORD) == ("Gem", "Support")
    assert words.STEP_CHARS == progression.STEP_CHARS == 52
    assert words.step_lines([{"name": "Frost Bomb", "kind": "skill"}]) == [
        "Gem usable now: Frost Bomb"]
    assert words.step_lines([{"name": "A", "kind": "skill"}, {"name": "B", "kind": "support"},
                             {"name": "C", "kind": "spirit"}, {"name": "D"}]) == [
        "Gem usable now: A", "Support usable now (+2): B"]
    long = words.step_lines([{"name": "Very Long Gem Name " * 5, "kind": "support"}] * 3)
    assert len(long) == 2
    for line in long:
        assert len(line) <= 52 and line.endswith("...") and line.isascii()
    assert words.step_lines([]) == [] and words.step_lines([{"name": " "}]) == []


def test_the_copy_sheet_lists_every_template():
    from pathlib import Path
    sheet = (Path(__file__).resolve().parents[1] / "docs" / "design" / "copy"
             / "gemunlock.md").read_text(encoding="ascii")
    for name in dir(words):
        v = getattr(words, name)
        if isinstance(v, str) and name.isupper():
            assert f"`{v}`" in sheet, name


def test_next_steps_name_each_gem_usable_at_this_level():
    build = _build("Spark", "Frost Bomb", "Flame Wall", "Arcane Surge")
    assert gemunlock.next_steps(_ctx(14, build), INDEX) == [
        {"kind": "gem-unlock", "text": "Gem usable now: Frost Bomb"},
        {"kind": "gem-unlock", "text": "Gem usable now: Flame Wall"}]
    assert gemunlock.next_steps(_ctx(15, build), INDEX) == [
        {"kind": "gem-unlock", "text": "Gem usable now: Arcane Surge"}]
    # a level with nothing new, no build, no snapshot, a Kindler plan: nothing
    assert gemunlock.next_steps(_ctx(16, build), INDEX) == []
    assert gemunlock.next_steps(_ctx(14, None), INDEX) == []
    assert gemunlock.next_steps(_ctx(14, build), None) == []
    assert gemunlock.next_steps(_ctx(None, build), INDEX) == []
    assert gemunlock.next_steps(_ctx(14, build, source="kindler"), INDEX) == []
    # a disabled gem is not in the plan's use
    assert gemunlock.next_steps(_ctx(14, _build("Frost Bomb", disabled=("Frost Bomb",))),
                                INDEX) == []


def test_a_support_step_says_support():
    tab = gemadvice.table(_doc({"Martial Tempo Support": 5}, supports=("Martial Tempo Support",)))
    assert gemunlock.next_steps(_ctx(5, _build("Martial Tempo")), tab) == [
        {"kind": "gem-unlock", "text": "Support usable now: Martial Tempo"}]


def test_steps_never_claim_the_gem_is_owned():
    build = _build("Frost Bomb", "Flame Wall", "Ice Nova")
    for st in gemunlock.next_steps(_ctx(14, build), INDEX):
        low = st["text"].lower()
        for word in ("you have", "owned", "your gem", "socketed", "got", "found"):
            assert word not in low, st


def test_the_progression_strip_carries_the_steps(tmp_path):
    _snapshot_file(tmp_path)
    core = _Core(tmp_path)
    try:
        advice_plug.attach(core)
        build = _build("Spark", "Frost Bomb")
        model_ = progression.build_model(build=build, level=14)
        steps = [s for s in model_["next"] if s["kind"] == "gem-unlock"]
        assert steps == [{"kind": "gem-unlock", "text": "Gem usable now: Frost Bomb"}]
        assert all(len(s["text"]) <= 52 for s in model_["next"])
        model_ = progression.build_model(build=build, level=13)
        assert not [s for s in model_["next"] if s["kind"] == "gem-unlock"]
    finally:
        progression.remove_next_source(advice_plug.SOURCE)
