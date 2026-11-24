"""KINDLER-ENGINE (decision 0081 points 3 to 5 and 12): the Generate
route, through the plug seam (decision 0056).

attach(core) makes one theorycraft.kindler.Engine per core (core.kindler)
over the Kindler tabs store of plug/genbuilds.py (core.gen_builds), the
core's calc callable (core.tc_calc in tests, else core.tc_provider(): None
while the calc component is off, so the result is one unscored template)
and the character level the state already publishes (decision 0038).

POST /api/kindler-generate takes {"id": <tab id>} plus an optional
"op": "generate" (the default; the player's Generate click) or "read"
(the tab's last result, never a calc). It answers {"state", "result"}:

    started  a run began on the engine's own daemon worker; the store's
             tab summary changes when it ends (GET /api/gen-builds)
    running  a run is in flight (one at a time); nothing new started
    done     a final result of the same key, or the read result
    none     read: no result yet

KINDLER-PLAN (decision 0081 points 14 to 17): "op": "plan" answers
{"state", "plan", "focus", "current"} for the tab's last result, never a
new Generate: the plan of its top-ranked template
(theorycraft.kindlerplan; "none" and null when there is no result), the
focus word ("pob", "pending" while one PoB focus run works on the
planner's own daemon worker, "calc_off", ...) and, while the tab's follow
flag is on, the stage to highlight from the snapshot's published area id,
area level and level (null while it is off or nothing is known). It never
claims a step was done.

Nothing regenerates by itself (point 4): only this route starts a run.
Behind the handler's Host / Origin / Sec-Fetch-Site / token guard; the
body is capped at the handler's MAX_BODY (4096). Nothing is sent to the
game or anywhere else.
"""

from ..theorycraft import genstore, kindler, kindlerplan

ORDER = 110  # after plug/genbuilds.py (ORDER 100) made core.gen_builds
OPS = ("generate", "read", "plan")
BAD = "That Kindler request isn't one AshLight understands."


def _calc(core):
    calc = getattr(core, "tc_calc", None)
    if calc is not None:
        return calc
    provider = getattr(core, "tc_provider", None)
    return provider() if provider is not None else None


def _level(core):
    state = getattr(core, "state", None)
    level = getattr(state, "level", None)
    return level if isinstance(level, int) and not isinstance(level, bool) else None


def attach(core):
    """One engine per core, over the tabs store (made here when the store
    plug did not run first)."""
    if getattr(core, "gen_builds", None) is None:
        from . import genbuilds
        genbuilds.attach(core)
    engine = kindler.Engine(kindler.Sources(), calc=lambda: _calc(core),
                            level=lambda: _level(core), store=core.gen_builds)
    savers = getattr(core, "savers", None) or {}
    saver = savers.get("genbuilds")
    if saver is not None:
        engine.on_save_error = saver.mark
    core.kindler = engine
    core.kindler_plan = kindlerplan.Planner(engine.sources, calc=lambda: _calc(core))


def _engine(req):
    core = req.server.core
    if getattr(core, "kindler", None) is None:  # attach did not run
        attach(core)
    return core.kindler


def _planner(core, engine):
    planner = getattr(core, "kindler_plan", None)
    if planner is None or planner.sources is not engine.sources:
        planner = kindlerplan.Planner(engine.sources, calc=lambda: _calc(core))
        core.kindler_plan = planner
    return planner


def _plan(core, engine, tab_id):
    """The "plan" answer for one tab (its last result; no Generate)."""
    doc = engine.last(tab_id)
    if doc is None:
        return {"state": "none", "plan": None, "focus": "", "current": None}
    busy = engine.running() is not None
    plan, focus = _planner(core, engine).plan(doc, busy=busy)
    if plan is None:
        return {"state": "none", "plan": None, "focus": "", "current": None}
    current = None
    if engine.store.tab(tab_id).get("follow", True):
        current = kindlerplan.current_stage(
            plan, kindlerplan.here_of(getattr(core, "state", None)))
    return {"state": "done", "plan": plan, "focus": focus, "current": current}


def post_generate(req, query, extra):
    body = req._read_json()
    if body is None:
        return None
    op = body.get("op", "generate")
    tab_id = body.get("id")
    if set(body) - {"id", "op"} or op not in OPS or not isinstance(tab_id, str):
        return req._json(400, {"error": BAD}, extra)
    engine = _engine(req)
    try:
        engine.store.tab(tab_id)
        if op == "plan":
            return req._json(200, _plan(req.server.core, engine, tab_id), extra)
        if op == "read":
            doc = engine.last(tab_id)
            state = "running" if engine.running() == tab_id else (
                "done" if doc is not None else "none")
            return req._json(200, {"state": state, "result": doc}, extra)
        state, doc = engine.generate(tab_id)
    except genstore.GenError as exc:
        return req._json(400, {"error": str(exc)}, extra)
    return req._json(200, {"state": state, "result": doc}, extra)


ROUTES = {
    ("POST", "/api/kindler-generate"): post_generate,
}
