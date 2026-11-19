"""TC-CARD-PARTS: the item card parts registry (server/al/theorycraft/
cardparts). Discovery order, a raising part skipped and logged once, a None
value adding nothing, the notes cap, word / tone pass-through, `answers`
keeping the item card on the overlay, and the press wiring (ctx keys)."""

import logging
import sys
import types
import uuid

import pytest

from server.al.core import Core
from server.al.state import EVAL_CARD_S, eval_card_text, overlay_card
from server.al.theorycraft import cardparts
from tc_eval_fixtures import RARE_GLOVES

PART = """NAME = {name!r}
ORDER = {order!r}


def compute(ctx):
    return 1


def words(value, card, out):
    out["notes"].append(NAME)
"""


def part(name, order=10, compute=None, words=None):
    return types.SimpleNamespace(
        NAME=name, ORDER=order,
        compute=compute or (lambda ctx: name),
        words=words or (lambda value, card, out: out["notes"].append(value)))


@pytest.fixture(autouse=True)
def fresh_registry():
    cardparts.reset()
    yield
    cardparts.reset()


@pytest.fixture
def use_parts(monkeypatch):
    def _use(*found):
        monkeypatch.setattr(cardparts, "_PARTS", list(found))
    return _use


def ok_card(**kw):
    base = {"ok": True, "error": None, "verdict": "upgrade", "slot": "Belt",
            "score_delta": 2, "item": {"name": "Cord", "base": "Leather Belt"},
            "comparisons": []}
    base.update(kw)
    return base


def test_discovery_order_by_order_then_name(tmp_path, monkeypatch, caplog):
    pkg = "alparts_" + uuid.uuid4().hex[:8]
    root = tmp_path / pkg
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="ascii")
    (root / "b_mod.py").write_text(PART.format(name="beta", order=1), encoding="ascii")
    (root / "a_mod.py").write_text(PART.format(name="alpha", order=2), encoding="ascii")
    (root / "c_mod.py").write_text(PART.format(name="aardvark", order=1), encoding="ascii")
    (root / "d_mod.py").write_text(PART.format(name="beta", order=5), encoding="ascii")
    (root / "_helper.py").write_text("X = 1\n", encoding="ascii")
    (root / "notapart.py").write_text("NAME = 'np'\n", encoding="ascii")
    (root / "broken.py").write_text("raise RuntimeError('boom')\n", encoding="ascii")
    (root / "sub").mkdir()
    (root / "sub" / "__init__.py").write_text(PART.format(name="sub", order=0),
                                              encoding="ascii")
    monkeypatch.syspath_prepend(str(tmp_path))
    caplog.set_level(logging.WARNING, logger="al.cardparts")
    try:
        found = cardparts.discover(pkg)
        assert [m.NAME for m in found] == ["aardvark", "beta", "alpha"]
        assert found[1].__name__ == pkg + ".b_mod"  # the repeated NAME keeps the first
        again = cardparts.discover(pkg)
        assert [m.NAME for m in again] == ["aardvark", "beta", "alpha"]
        skipped = [r.getMessage() for r in caplog.records]
        assert len(skipped) == 3  # broken, notapart, repeated beta: once each
        assert any("broken" in m and "RuntimeError" in m for m in skipped)
        assert "boom" not in " ".join(skipped)  # the type only, never the text
    finally:
        for name in [n for n in sys.modules if n == pkg or n.startswith(pkg + ".")]:
            del sys.modules[name]


def test_the_real_package_holds_only_parts():
    found = cardparts.discover()
    assert found == sorted(found, key=lambda m: (m.ORDER, m.NAME))
    assert all(cardparts._is_part(m) for m in found)
    assert len({m.NAME for m in found}) == len(found)
    assert cardparts.parts() == found


def test_raising_part_is_skipped_and_logged_once(use_parts, caplog):
    caplog.set_level(logging.WARNING, logger="al.cardparts")

    def bad(ctx):
        raise ValueError("secret item text")

    def bad_words(value, card, out):
        out["notes"].append("half done")
        out["word"] = "Broken"
        raise KeyError("x")
    found = [part("first", 1), part("bad", 2, compute=bad), part("last", 3)]
    for _ in range(3):
        assert cardparts.compute({}, found) == {"first": "first", "last": "last"}
    msgs = [r.getMessage() for r in caplog.records]
    assert len(msgs) == 1 and "bad" in msgs[0] and "ValueError" in msgs[0]
    assert "secret" not in msgs[0]
    use_parts(part("first", 1), part("worse", 2, words=bad_words), part("last", 3))
    card = ok_card(parts={"first": "one", "worse": 1, "last": "three"})
    for _ in range(2):
        t = eval_card_text(card)
        assert t["notes"] == ["one", "three"] and t["word"] == "Upgrade"
    assert len(caplog.records) == 2


def test_none_value_adds_nothing(use_parts):
    calls = []
    quiet = part("quiet", 1, compute=lambda ctx: None,
                 words=lambda v, c, o: calls.append(v))
    assert cardparts.compute({}, [quiet]) == {}
    use_parts(quiet)
    t = eval_card_text(ok_card(parts={}))
    assert t["notes"] == [] and calls == []
    plain = eval_card_text(ok_card())
    assert t == plain


def test_value_must_be_json(caplog):
    caplog.set_level(logging.WARNING, logger="al.cardparts")
    odd = part("odd", 1, compute=lambda ctx: {"s": {1, 2}})
    nan = part("nan", 2, compute=lambda ctx: float("nan"))
    big = part("big", 4, compute=lambda ctx: "x" * cardparts.VALUE_MAX)
    assert cardparts.compute({}, [odd, nan, part("fine", 3), big]) == {"fine": "fine"}
    assert len(caplog.records) == 3


def test_notes_capped_at_four(use_parts):
    many = part("many", 1, words=lambda v, c, o: o["notes"].extend(
        ["Note one", "", None, "Note two", "Note three"]))
    more = part("more", 2, words=lambda v, c, o: o["notes"].extend(
        ["Note four", "Note five"]))
    use_parts(many, more)
    t = eval_card_text(ok_card(parts={"many": 1, "more": 1}))
    assert t["notes"] == ["Note one", "Note two", "Note three", "Note four"]
    assert len(t["notes"]) == cardparts.NOTES_MAX


def test_word_and_tone_pass_through(use_parts):
    def keep(value, card, out):
        out.update(word="Keep", tone="upgrade")
    use_parts(part("keep", 1, words=keep))
    ev = ok_card(verdict="downgrade", parts={"keep": 1}, at=100.0)
    t = eval_card_text(ev)
    assert (t["word"], t["tone"]) == ("Keep", "upgrade")
    assert t["head"] == "Keep - Downgrade +2 vs Belt"  # the word leads the head
    card = overlay_card(ev, None, 101.0)
    assert (card["verdict"], card["head"]) == ("upgrade", "Keep - Downgrade +2 vs Belt")
    plain = dict(ev, parts={})
    assert eval_card_text(plain)["word"] == "Downgrade"
    assert overlay_card(plain, None, 101.0)["verdict"] == "downgrade"

    def blank(value, card, out):
        out.update(word="", tone=None, answers="yes")
    use_parts(part("blank", 1, words=blank))
    t = eval_card_text(dict(ev, parts={"blank": 1}))
    assert (t["word"], t["tone"], t["answers"]) == ("Downgrade", "downgrade", False)


def test_parts_keep_the_card_contract(use_parts):
    """Colour is never alone: a new tone needs a new word; a tone outside
    TONES, a head that does not start with the word and any key outside
    WORD_KEYS are put back; a long head is clipped to HEAD_MAX."""
    base = eval_card_text(ok_card(verdict="downgrade", score_delta=-2))

    def run(fn):
        use_parts(part("p", 1, words=lambda v, c, o: fn(o)))
        return eval_card_text(ok_card(verdict="downgrade", score_delta=-2, parts={"p": 1}))

    t = run(lambda o: o.update(tone="upgrade"))  # tone under the old word
    assert t == base
    t = run(lambda o: o.update(word="Keep", tone="glow"))  # tone outside TONES
    assert (t["word"], t["tone"]) == ("Keep", "downgrade")
    t = run(lambda o: o.update(line="Changed", item="Other", sentence="Other.", extra=1))
    assert t == base
    t = run(lambda o: o.update(head="Upgrade +99 vs Belt"))  # head without the word
    assert t["head"] == base["head"]
    t = run(lambda o: o.update(word="Keep", head="Keep for the next act"))
    assert t["head"] == "Keep for the next act"
    t = run(lambda o: o.update(word="Keep it for a later level, it fits"))
    assert len(t["head"]) == cardparts.HEAD_MAX and t["head"].endswith("...")
    assert base["head"] == "Downgrade -2 vs Belt"


def test_answers_keeps_the_eval_part_on_the_overlay(use_parts):
    def answer(value, card, out):
        out.update(answers=True, word="Keep", tone="upgrade")
        out["notes"].append("Worth keeping for a later level")
    use_parts(part("keep", 1, words=answer))
    ev = {"ok": False, "error": "no build loaded", "item": {"name": "Grim Clutch"},
          "at": 100.0}
    price = {"at": 100.5, "status": "link", "league": "Standard",
             "item": {"name": "Grim Clutch"}}
    assert overlay_card(ev, price, 101.0)["kind"] == "price"  # no part: price only
    card = overlay_card(dict(ev, parts={"keep": 1}), price, 101.0)
    assert card["kind"] == "merged" and card["head"] == "Keep - No build loaded"
    assert card["verdict"] == "upgrade"
    assert card["expires_at"] >= 100.0 + EVAL_CARD_S


@pytest.fixture
def core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    yield c
    c.close()


def test_press_builds_ctx_and_publishes_parts(core, use_parts):
    seen = []

    def grab(ctx):
        seen.append(ctx)
        return {"area": ctx["area_id"], "config": isinstance(ctx["config"](), dict)}

    use_parts(part("probe", 1, compute=grab,
                   words=lambda v, c, o: o["notes"].append("Probe note")))
    assert set(core.last_eval.ctx_extra) == {"config", "area_id"}
    core.state.area_id = "G1_1"
    core.last_eval.run(RARE_GLOVES, "Gloves")
    ctx = seen[-1]
    assert {"text", "parsed", "result", "build", "character", "level", "area_id",
            "config"} <= set(ctx)
    assert ctx["text"] == RARE_GLOVES and ctx["parsed"].base
    assert ctx["build"] is None and ctx["result"]["error"] == "no build loaded"
    snap = core.state.snapshot()["eval"]
    assert snap["parts"] == {"probe": {"area": "G1_1", "config": True}}
    assert snap["text"]["notes"] == ["Probe note"]
    core.last_eval.rerun()  # a re-score runs the parts again
    assert len(seen) == 2


def test_a_bare_last_eval_has_empty_ctx_extra(core, use_parts):
    use_parts()
    core.last_eval.ctx_extra = {}
    core.last_eval.run(RARE_GLOVES)
    assert core.state.snapshot()["eval"]["parts"] == {}
