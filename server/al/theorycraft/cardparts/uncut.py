"""TC-UNCUT-GEM (research 0064 G2, decision 0094): uncut gem advice.

A card part (TC-CARD-PARTS). On an item-check press of an Uncut Skill,
Support or Spirit Gem of level N it names the loaded build's gems of that
kind that a level N cut can make and that the build does not show as
socketed at that level yet (theorycraft/gemadvice.py: the press's own
text, the build's gems, the cached gems snapshot). The build is the pasted
PoB build, else the Kindler stage the Progression view shows (ctx
"plan_gems", a callable the plug server/al/plug/gemadvice.py adds). No
build or no snapshot adds nothing.

Value: {"kind", "level", "gems": [{"name", "level", "have"}],
"unchecked": [names], "more", "unchecked_more"}.

Words: dashboard notes only (server/al/text/gemadvice.py, copy sheet
docs/design/copy/gemadvice.md); the verdict word, tone and head are left
alone, so no design 0001 section 9 word is added. Nothing here reads the
clipboard or sends anything anywhere.
"""

from ...text import gemadvice as gemwords
from .. import gemadvice

NAME = "uncut"
ORDER = 25  # after keep (20): an item part


def _table():
    return gemadvice.index()


def _gems(ctx):
    build = ctx.get("build")
    if build is not None:
        return gemadvice.pob_gems(build)
    fn = ctx.get("plan_gems")
    try:
        got = fn() if callable(fn) else None
    except Exception:  # noqa: BLE001 - no plan then means no advice
        got = None
    return got if isinstance(got, list) else []


def compute(ctx):
    if not isinstance(ctx, dict) or gemadvice.parse_uncut(ctx.get("text")) is None:
        return None
    gems = _gems(ctx)
    if not gems:
        return None
    tab = _table()
    if not tab:
        return None
    return gemadvice.cut_options(ctx["text"], gems, tab)


def words(value, card, out):
    out["notes"].extend(gemwords.cut_notes(value))
