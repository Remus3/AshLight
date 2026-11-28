"""Gem advice through the plug seam (decision 0056; TC-UNCUT-GEM, decision
0094).

attach(core) hands the item check's card parts one more ctx key,
"plan_gems": a callable answering the gems of the Kindler stage the
Progression view shows (theorycraft/gemadvice.stage_gems over the model's
skill rows) while no build is pasted, else []. The uncut gem card part
reads it only on an uncut gem press; a pasted build is read from the ctx
"build" as before. It reads the model the progression tick last built and
starts nothing (no Kindler run, no calc). Nothing is sent anywhere.
"""

from ..theorycraft import gemadvice

ORDER = 125  # after plug/progression.py (ORDER 120) made core.progression


def plan_gems(core):
    holder = getattr(core, "progression", None)
    get = getattr(holder, "get", None)
    model = get() if callable(get) else None
    if not isinstance(model, dict) or model.get("source") != "kindler":
        return []
    return gemadvice.stage_gems(model.get("skills"))


def attach(core):
    last_eval = getattr(core, "last_eval", None)
    extra = getattr(last_eval, "ctx_extra", None)
    if isinstance(extra, dict):
        extra["plan_gems"] = lambda: plan_gems(core)
