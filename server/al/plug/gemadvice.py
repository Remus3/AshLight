"""Gem advice through the plug seam (decision 0056; TC-UNCUT-GEM, decision
0094; TC-GEM-UNLOCK, decision 0095).

attach(core):
- hands the item check's card parts two more ctx keys: "plan_gems", a
  callable answering the gems of the Kindler stage the Progression view
  shows (theorycraft/gemadvice.stage_gems over the model's skill rows)
  while no build is pasted, else []; and "gem_table", a callable
  answering the cached gems snapshot table beside this core's base list
  (gemadvice.index). The uncut gem card part reads them only on an uncut
  gem press;
- adds the TC-GEM-UNLOCK next-up source to the Progression view
  (progression.add_next_source, gemunlock.next_steps, order
  gemunlock.ORDER_STEP): the build gems whose snapshot level is the
  player's level.
It reads the model the progression tick last built and the local cache,
and starts nothing (no Kindler run, no calc). Nothing is sent anywhere.
"""

from .. import gemunlock
from ..theorycraft import gemadvice, progression

ORDER = 125  # after plug/progression.py (ORDER 120) made core.progression
SOURCE = "gem-unlock"


def plan_gems(core):
    holder = getattr(core, "progression", None)
    get = getattr(holder, "get", None)
    model = get() if callable(get) else None
    if not isinstance(model, dict) or model.get("source") != "kindler":
        return []
    return gemadvice.stage_gems(model.get("skills"))


def attach(core):
    path = gemadvice.gems_file(core)
    last_eval = getattr(core, "last_eval", None)
    extra = getattr(last_eval, "ctx_extra", None)
    if isinstance(extra, dict):
        extra["plan_gems"] = lambda: plan_gems(core)
        extra["gem_table"] = lambda: gemadvice.index(path)
    progression.add_next_source(SOURCE, lambda ctx: gemunlock.next_steps(
        ctx, gemadvice.index(path)), order=gemunlock.ORDER_STEP)
