"""TC-AUGMENT-WHATIF (research 0064 G4, decision 0093): augment what-if on
the item-check press.

The augment rows come from a synthetic ModRunes.lua of PoB's line shape
(own words and numbers, not PoB's text), parsed by the real
pobtext.parse_augments. A fake calc stands in for Path of Building: DPS and
EHP are linear in the gear's summed stats.
Item texts are invented. tmp runtime only; nothing reads the clipboard.
"""

import hashlib
import json
import threading
import time

import pytest

from server.al.core import Core
from server.al.state import eval_card_text
from server.al.text import augment as words
from server.al.theorycraft import augment
from server.al.theorycraft import codec
from server.al.theorycraft import delta as delta_mod
from server.al.theorycraft import evaluate as tc_evaluate
from server.al.theorycraft import item as item_parser
from server.al.theorycraft import live
from server.al.theorycraft import model
from server.al.theorycraft import pobtext
from server.al.theorycraft.cardparts import augment as part
from server.al.theorycraft.cardparts import stage as stage_part
from tc_eval_fixtures import ADVANCED_RING, EVAL_BUILD_XML, RARE_GLOVES

WAIT_S = 30.0
T = "\t"


def _rune(name, slots):
    """One augment block; slots: [(key, type, [lines], rank)]."""
    out = [T + '["%s"] = {' % name]
    for key, kind, lines, rank in slots:
        out += [T * 2 + '["%s"] = {' % key, T * 3 + 'type = "%s",' % kind]
        out += [T * 3 + '"%s",' % line for line in lines]
        out += [T * 3 + "statOrder = { %s }," % ", ".join(str(10 + i)
                                                         for i in range(len(lines))),
                T * 3 + 'tradeHashes = { [77] = { "%s" },  },' % lines[0],
                T * 3 + "isSocketBound = false,",
                T * 3 + "rank = { %d }," % rank,
                T * 2 + "},"]
    return out + [T + "},"]


def runes_text(extra=()):
    lines = ["-- synthetic test augments", "return {"]
    lines += _rune("Lesser Ember Rune", [
        ("weapon", "Rune", ["Adds 2 to 4 Fire Damage", "Bonded: 9% increased Test"], 0),
        ("armour", "Rune", ["+8% to Fire Resistance"], 0)])
    lines += _rune("Greater Ember Rune", [
        ("weapon", "Rune", ["Adds 6 to 10 Fire Damage", "Bonded: 9% increased Test"], 30),
        ("armour", "Rune", ["+16% to Fire Resistance"], 30)])
    lines += _rune("Swift Rune", [
        ("weapon", "Rune", ["6% increased Attack Speed"], 15)])
    lines += _rune("Bowyer Rune", [
        ("bow", "Rune", ["+40 to Accuracy Rating"], 15)])
    lines += _rune("Heart Core", [
        ("armour", "SoulCore", ["+30 to maximum Life"], 50)])
    lines += _rune("Wand Spark", [
        ("wand", "Rune", ["Adds 1 to 30 Lightning Damage"], 15)])
    for line in extra:
        lines += line
    return "\n".join(lines + ["}"])


INDEX = pobtext.parse_augments(runes_text())

# fake calc: per point of each stat key
DPS_PER = {"adds # to # fire damage": 3.0, "#% increased attack speed": 3.0,
           "+# to accuracy rating": 0.1, "adds # to # lightning damage": 1.0}
EHP_PER = {"+# to maximum life": 10.0, "+#% to fire resistance": 20.0,
           "+#% to cold resistance": 20.0}


class FakeCalc:
    def __init__(self, gate_after=None, fail_after=None):
        self.calls = []
        self.lock = threading.Lock()
        self.gate = threading.Event()
        self.gate_after = gate_after
        self.fail_after = fail_after
        self.reached = threading.Event()

    def __call__(self, build, swaps):
        with self.lock:
            self.calls.append(dict(swaps))
            n = len(self.calls)
        if self.gate_after is not None and n > self.gate_after:
            self.reached.set()
            assert self.gate.wait(WAIT_S), "the test never opened the gate"
        if self.fail_after is not None and n > self.fail_after:
            raise OSError("calc process killed")
        gear = {slot: it.text for slot, it in build.gear.items()}
        gear.update(swaps)
        dps, ehp = 100.0, 1000.0
        for slot, text in gear.items():
            parsed = item_parser.parse(text)
            for key, value in tc_evaluate.stats_of(parsed).items():
                dps += DPS_PER.get(key.lower(), 0) * value
                ehp += EHP_PER.get(key.lower(), 0) * value
        return {"dps": dps, "ehp": ehp}


# -- fixture items (invented) -------------------------------------------------

def _bow(sockets="S S", runes=(), quality=10, corrupted=False, name="Ash Arc"):
    q = "Quality: +%d%% (augmented)\n" % quality if quality is not None else ""
    text = ("Item Class: Bows\nRarity: Rare\n%s\nExample Bow\n--------\n%s"
            "Physical Damage: 20-40\n--------\n" % (name, q))
    if sockets:
        text += "Sockets: %s\n--------\n" % sockets
    text += "Item Level: 40\n--------\n"
    if runes:
        text += "".join(r + " (rune)\n" for r in runes) + "--------\n"
    text += "+20 to Dexterity\n"
    if corrupted:
        text += "--------\nCorrupted\n"
    return text


SOCKETED_BOW = _bow()                                    # 2 free sockets, quality 10
FULL_BOW = _bow(runes=("6% increased Attack Speed", "+40 to Accuracy Rating"),
                quality=20)                              # sockets full
FULL_LOW_QUALITY = _bow(runes=("6% increased Attack Speed", "+40 to Accuracy Rating"),
                        quality=5)                       # sockets full, quality low
ONE_RUNE_BOW = _bow(runes=("6% increased Attack Speed",), quality=20)
NO_SOCKET_LOW_QUALITY = _bow(sockets=None, quality=0)
CORRUPTED_BOW = _bow(corrupted=True)
HELMET = ("Item Class: Helmets\nRarity: Rare\nDusk Crown\nExample Helmet\n--------\n"
          "Armour: 50\n--------\nSockets: S\n--------\nItem Level: 40\n--------\n"
          "+30 to maximum Life\n")


@pytest.fixture
def build():
    return model.parse(EVAL_BUILD_XML)


def _stages(text, build, calc, index=INDEX, cancelled=None):
    return list(tc_evaluate.stages(text, build, None, calc=calc, augments=lambda: index,
                                   cancelled=cancelled))


# -- room: sockets free, full, quality ----------------------------------------

def test_room_of_fixture_items():
    p = item_parser.parse
    assert augment.room(p(SOCKETED_BOW)) is True
    assert augment.room(p(FULL_BOW)) is False
    # one rune line in two sockets: a free socket is possible
    assert augment.room(p(ONE_RUNE_BOW)) is True
    # quality is no room: PoB scores every modifiable item at its default
    # quality already (bridge set_item, Item:NormaliseQuality; decision 0093)
    assert augment.room(p(FULL_LOW_QUALITY)) is False
    assert augment.room(p(NO_SOCKET_LOW_QUALITY)) is False
    # a corrupted item cannot be changed; a ring has no augment keys
    assert augment.room(p(CORRUPTED_BOW)) is False
    assert augment.room(p(RARE_GLOVES)) is False
    assert augment.room(p(ADVANCED_RING)) is False
    assert augment.room(None) is False


def test_keys_follow_pob_augment_types():
    p = item_parser.parse
    assert augment.keys_for(p(SOCKETED_BOW)) == ("weapon", "bow")
    assert augment.keys_for(p(HELMET)) == ("armour", "helmet")
    assert augment.keys_for(p(ADVANCED_RING)) is None


def test_candidates_one_per_family_bonded_left_out():
    cands = augment.candidates(item_parser.parse(SOCKETED_BOW), INDEX)
    names = [c["name"] for c in cands]
    # the Ember family keeps its highest rank; the bow row joins the weapon rows
    assert names == ["Greater Ember Rune", "Swift Rune", "Bowyer Rune"]
    ember = cands[0]
    assert ember["lines"] == ["Adds 6 to 10 Fire Damage"]
    assert all(not line.startswith("Bonded") for c in cands for line in c["lines"])
    helm = [c["name"] for c in augment.candidates(item_parser.parse(HELMET), INDEX)]
    assert helm == ["Greater Ember Rune", "Heart Core"]


# -- the stage ----------------------------------------------------------------

def test_socketed_weapon_ranks_the_augments_by_pob(build):
    calc = FakeCalc()
    got = _stages(SOCKETED_BOW, build, calc)
    names = [n for n, _r in got]
    assert names == ["weights", "pob", "mods", "augment"]
    mods = got[2][1]
    assert mods["augment"] == {"state": "pending"}
    assert tc_evaluate.pending_after("mods", mods) is True
    aug = got[-1][1]["augment"]
    assert aug["state"] == "ready" and aug["slot"] == "Weapon 1"
    assert aug["tried"] == 3
    # Greater Ember: +24 DPS (8 avg x 3) on the item's own base
    best = aug["best"]
    assert best["name"] == "Greater Ember Rune" and best["type"] == "Rune"
    assert [r["name"] for r in aug["top"]] == ["Greater Ember Rune", "Swift Rune",
                                               "Bowyer Rune"]
    assert best["dps"] == round(24.0 / 100.0 * 100, 4)
    assert best["ehp"] == 0.0 and aug["calls"] == 3
    assert aug["source"] == pobtext.SOURCE_ID
    assert tc_evaluate.pending_after("augment", got[-1][1]) is False
    # the rest of the last result is the mods stage's
    assert got[-1][1]["verdict"] == mods["verdict"]


def test_no_room_has_no_augment_stage(build):
    for text in (FULL_BOW, CORRUPTED_BOW, FULL_LOW_QUALITY, NO_SOCKET_LOW_QUALITY):
        got = _stages(text, build, FakeCalc())
        assert [n for n, _r in got] == ["weights", "pob", "mods"]
        assert "augment" not in got[-1][1]


def test_calc_off_has_no_stage_and_one_sentence():
    got = list(tc_evaluate.stages(SOCKETED_BOW, None, None, calc=None,
                                  augments=lambda: INDEX))
    assert [n for n, _r in got] == ["weights"]
    # with a build and the calc off: the card part names the missing calc
    ctx = {"result": {"ok": True, "calc": {"source": "weights", "notice": "off"}},
           "parsed": item_parser.parse(SOCKETED_BOW)}
    value = part.compute(ctx)
    assert value == {"state": "needs_calc"}
    assert part.notes(value) == ["Augment ranking for this item needs the Path of "
                                 "Building calc."]
    for text in (FULL_BOW, FULL_LOW_QUALITY):
        ctx["parsed"] = item_parser.parse(text)
        assert part.compute(ctx) is None


def test_pin_absent_gives_no_rows_and_no_stage(tmp_path, build):
    # no ModRunes.lua entry in the pins: load_augments reads nothing
    pins = {"pob2": {"top_dir": "x", "archive_sha256": "a" * 64},
            "pob2_files": {"_doc": "x"}}
    assert pobtext.load_augments(tmp_path, pins) == {}
    # a pins file that is missing: the reader gives {}
    reader = pobtext.Augments(pins_path=tmp_path / "missing.json", root=tmp_path)
    assert reader.get() == {}
    got = _stages(SOCKETED_BOW, build, FakeCalc(), index=reader.get())
    assert [n for n, _r in got] == ["weights", "pob", "mods"]
    assert "augment" not in got[-1][1]
    # a wrong sha256: no rows either
    text = runes_text()
    root = tmp_path / "co"
    (root / "src" / "Data").mkdir(parents=True)
    (root / "src" / "Data" / "ModRunes.lua").write_bytes(text.encode("ascii"))
    (root / pobtext.MARKER).write_text(json.dumps({"archive_sha256": "a" * 64}),
                                       encoding="ascii")
    pins["pob2_files"][pobtext.AUGMENTS] = {"sha256": "f" * 64}
    assert pobtext.load_augments(root, pins) == {}
    pins["pob2_files"][pobtext.AUGMENTS] = {
        "sha256": hashlib.sha256(text.encode("ascii")).hexdigest()}
    assert set(pobtext.load_augments(root, pins)) == set(INDEX)


def test_a_calc_failure_in_the_stage_says_so(build):
    # weights 0, pob 1 base + 1 swap, mods: probes; fail on the first augment call
    probe = FakeCalc()
    list(tc_evaluate.stages(SOCKETED_BOW, build, None, calc=probe))
    calc = FakeCalc(fail_after=len(probe.calls))
    got = _stages(SOCKETED_BOW, build, calc)
    assert got[-1][0] == "augment"
    aug = got[-1][1]["augment"]
    assert aug == {"state": "failed", "slot": "Weapon 1"}
    value = part.compute({"result": got[-1][1]})
    assert part.notes(value) == ["Path of Building could not rank augments for this item."]


# -- the budget ---------------------------------------------------------------

def _many(n):
    tag = "abcdefghijklmnopqrstuvwxyz"
    return [_rune("Test Rune %02d" % i, [("weapon", "Rune", ["+5 to Test Stat %s%s" % (
        tag[i % 26], tag[i // 26])], 15)]) for i in range(n)]


def test_at_most_max_probes_calc_calls(build):
    index = pobtext.parse_augments(runes_text(_many(40)))
    probe = FakeCalc()
    list(tc_evaluate.stages(SOCKETED_BOW, build, None, calc=probe))
    calc = FakeCalc()
    got = _stages(SOCKETED_BOW, build, calc, index=index)
    aug = got[-1][1]["augment"]
    stage_calls = len(calc.calls) - len(probe.calls)
    assert stage_calls == aug["calls"] == aug["tried"] == delta_mod.MAX_PROBES
    # the weighted candidates are measured first
    assert aug["best"]["name"] == "Greater Ember Rune"


def test_the_time_budget_stops_the_stage(build):
    the_plan = augment.plan(item_parser.parse(SOCKETED_BOW), INDEX, {})
    ticks = iter([0.0, 0.0, 1.0, augment.TIME_S + 1, 99, 99])
    calc = FakeCalc()
    out = augment.run(calc, build, "Weapon 1", SOCKETED_BOW, {"dps": 100.0, "ehp": 1000.0},
                      the_plan, clock=lambda: next(ticks))
    # two augments fit in the time; the third is left out
    assert out["calls"] == 2 and out["tried"] == 2 and len(calc.calls) == 2


# -- cancellation by a newer press --------------------------------------------

@pytest.fixture
def core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    c.builds.load_code(codec.encode(EVAL_BUILD_XML))
    c.last_eval.augments = lambda: INDEX
    yield c
    c.close()


class Recorder:
    def __init__(self, state):
        self.cards = []
        self._set = state.set_eval
        state.set_eval = self

    def __call__(self, card, keep_time=False, at=None):
        self._set(card, keep_time=keep_time, at=at)
        self.cards.append(dict(card))


def test_core_publishes_the_augment_notes(core):
    rec = Recorder(core.state)
    core.tc_calc = FakeCalc()
    core.eval_press(SOCKETED_BOW)
    assert core.last_eval.wait(WAIT_S)
    stages = [((c.get("parts") or {}).get(stage_part.NAME) or {}).get("stage")
              for c in rec.cards]
    # weights, pob and mods pending; the augment card last, not pending
    assert stages == ["weights", "pob", "mods", None]
    snap = core.state.snapshot()["eval"]
    value = snap["parts"][part.NAME]
    assert value["state"] == "ready" and value["best"]["name"] == "Greater Ember Rune"
    notes = snap["text"]["notes"]
    assert notes[:2] == [
        "Best augment for a free socket: Greater Ember Rune, DPS +24%, EHP 0% "
        "(Path of Building).",
        words.CREDIT_TEXT]
    assert stage_part.PENDING_NOTE not in notes
    assert len(json.dumps(value)) <= 2000


def test_a_newer_press_cancels_the_augment_stage(core):
    probe = FakeCalc()
    list(tc_evaluate.stages(SOCKETED_BOW, core.builds.build, None, calc=probe))
    before = len(probe.calls)
    index = pobtext.parse_augments(runes_text(_many(30)))
    core.last_eval.augments = lambda: index
    calc = FakeCalc(gate_after=before + 2)  # blocks inside the augment stage
    core.tc_calc = calc
    rec = Recorder(core.state)
    core.eval_press(SOCKETED_BOW)
    assert calc.reached.wait(WAIT_S), "the augment stage never started"
    core.last_eval.augments = None
    core.eval_press(HELMET)
    calc.gate.set()
    assert core.last_eval.wait(WAIT_S)
    bows = [c for c in rec.cards if c["item"]["name"] == "Ash Arc"]
    # the bow's augment stage never published, and stopped at the next call
    assert all((c.get("parts") or {}).get(part.NAME) is None for c in bows)
    bow_calls = [c for c in calc.calls if "Weapon 1" in c]
    assert len(bow_calls) < 1 + delta_mod.MAX_PROBES
    last = core.state.snapshot()["eval"]
    assert last["item"]["name"] == "Dusk Crown"


def test_a_rescore_cancels_the_augment_stage_between_calls(build):
    gen = {"n": 0}
    calls = {"n": 0}

    def calc(b, swaps):
        calls["n"] += 1
        if calls["n"] == 2:
            gen["n"] = 1  # a newer press arrives during the stage
        return {"dps": 100.0, "ehp": 1000.0}

    the_plan = augment.plan(item_parser.parse(SOCKETED_BOW), INDEX, {})
    with pytest.raises(augment.Cancelled):
        augment.run(calc, build, "Weapon 1", SOCKETED_BOW, {"dps": 100.0, "ehp": 1000.0},
                    the_plan, cancelled=lambda: gen["n"] != 0)
    assert calls["n"] == 2


# -- words --------------------------------------------------------------------

def test_words_exact():
    assert words.best_text("Iron Rune", 4.23, 0) == (
        "Best augment for a free socket: Iron Rune, DPS +4.2%, EHP 0% (Path of Building).")
    assert words.best_text("Iron Rune", -1, None) == (
        "Best augment for a free socket: Iron Rune, DPS -1%, EHP unknown (Path of Building).")
    assert words.best_text("", 1, 1) is None
    assert words.none_text(1) == ("Path of Building tried 1 augment for a free socket; "
                                  "none raises DPS or EHP.")
    assert words.none_text(12) == ("Path of Building tried 12 augments for a free socket; "
                                   "none raises DPS or EHP.")
    assert words.FAILED_TEXT == "Path of Building could not rank augments for this item."
    assert words.NEEDS_CALC_TEXT == ("Augment ranking for this item needs the Path of "
                                     "Building calc.")
    assert words.CREDIT_TEXT == ("Augment data: Path of Building (MIT), community-written, "
                                 "may be out of date.")
    long_name = words.best_text("A B C D E F G H I J K L M N O P Q R S T", 10.5, -2.5)
    assert long_name == ("Best augment for a free socket: A B C D E F G..., DPS +10.5%, "
                         "EHP -2.5% (Path of Building).")
    for line in (long_name, words.best_text("Hayoxi's Soul Core of Heatproofing", 1, 1),
                 words.none_text(23), words.FAILED_TEXT,
                 words.NEEDS_CALC_TEXT, words.CREDIT_TEXT):
        assert len(line.split()) <= 20 and line.isascii() and "!" not in line


def test_no_augment_helps_note():
    value = {"state": "ready", "best": None, "tried": 3}
    assert part.notes(value) == [words.none_text(3), words.CREDIT_TEXT]
    assert part.notes({"state": "ready", "best": None, "tried": 0}) == []


def test_card_text_keeps_the_part_contract():
    card = {"ok": True, "verdict": "upgrade", "slot": "Weapon 1", "score_delta": 5,
            "item": {"name": "Ash Arc"}, "calc": {"source": "pob", "notice": None},
            "comparisons": [],
            "parts": {part.NAME: {"state": "ready", "tried": 2,
                                  "best": {"name": "Swift Rune", "dps": 2.5, "ehp": 0}}}}
    out = eval_card_text(card)
    assert out["notes"][:2] == [words.best_text("Swift Rune", 2.5, 0), words.CREDIT_TEXT]
    assert out["word"] == eval_card_text(dict(card, parts={}))["word"]


def test_live_lasteval_without_augments_is_unchanged(build):
    class Builds:
        pass

    Builds.build = build

    class Weights:
        def get(self):
            return None

    class St:
        def __init__(self):
            self.cards = []

        def set_eval(self, card, keep_time=False, at=None):
            self.cards.append(card)

    st = St()
    last = live.LastEval(Builds(), Weights(), st, calc=lambda: FakeCalc())
    last.run(SOCKETED_BOW)
    assert part.NAME not in st.cards[-1]["parts"]
    last.augments = lambda: INDEX
    last.run(SOCKETED_BOW)
    assert st.cards[-1]["parts"][part.NAME]["state"] == "ready"
    assert last.close() is True


def test_time_budget_constant_matches_r7():
    # decision 0024 R7 amendment 2026-11-18: a warm check's probes 12 s for
    # every stage; pob + mods take up to 5.5 s warm, so the augment stage
    # gets 5 s (decision 0093 amendment 2026-11-28)
    assert augment.TIME_S == 5.0
    assert 5.5 + augment.TIME_S + 0.5 <= 12.0
    assert time.monotonic() >= 0
