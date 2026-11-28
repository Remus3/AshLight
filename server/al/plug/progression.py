"""PROGRESSION-VIEW (decision 0092): the Progression view through the plug
seam (decision 0056).

attach(core) makes one Holder per core (core.progression) and adds the
"progression" tick. Each core loop pass the tick compares a few cheap
values (the loaded build object, the published level, area id and zone);
at most every FULL_EVERY_S it also looks at the cached tree export, the
Kindler tabs, the gems snapshot and the guide. Only when one of them
changed is the model rebuilt (theorycraft.progression.build_model) and
its small summary published as the snapshot's "progression" view
(state.publish bumps the version only on a change). So a level-up, a
zone change, a new build, a hot-reloaded build file or a new Kindler
result moves the view on by itself, with no click and no timer on the
page (the page re-reads the whole model only when the published key
changes).

GET /api/progression answers the whole model ({"key": null} before the
first one): token-gated like every plug route, behind the handler's Host
/ Origin / Sec-Fetch-Site guard. It reads nothing and starts nothing:
the model is the one the tick last built.

TC-SPEC-FOLLOW integration point: spec_picker(core) below is the one
place that hands progression.pick_specs its `picker(build, level) -> spec
index or None`: specfollow.pick() over the build's specs with PoB's own
active spec as the fallback (decision 0089), so the shown spec is the one
the level follows and the next band's spec's new nodes are due. Without
theorycraft/specfollow.py it answers None (the active spec, nothing due).

ACTIVE-BUILD-PICK (decision 0096): while the player has put a Kindler
plan in use (plug/buildsource.py), that tab is the source even with a
pasted build loaded (the build store then holds the plan's composed
stage, which is not drawn as a pasted build).

The Kindler source reads the planner with busy=True, so a read never
starts a PoB focus run (decision 0081 point 4: nothing regenerates by
itself). Nothing is sent to the game or anywhere else.
"""

import threading
import time

from ..theorycraft import kindlerplan, progression

ORDER = 120  # after plug/kindler.py (ORDER 110) made core.kindler
FULL_EVERY_S = 2.0


def _specfollow():
    """theorycraft.specfollow (TC-SPEC-FOLLOW, decision 0089), or None while
    the tree holds no such module."""
    try:
        from ..theorycraft import specfollow
    except ImportError:
        return None
    return specfollow if callable(getattr(specfollow, "pick", None)) else None


def spec_picker(core):
    """The TC-SPEC-FOLLOW chooser: a callable(build, level) -> spec index.

    The loaded build already follows the level (specfollow.follow sets its
    active spec, the build view's spec_follow.index), so the chooser asks
    specfollow.pick() with PoB's own active spec (Build.pob_spec_index) as
    the fallback: at the current level it answers the followed spec, and
    pick_specs() asks it for the levels above to find the next band's spec,
    whose new nodes read as due. None (the active spec, nothing due) while
    the module is not there."""
    sf = _specfollow()
    if sf is None:
        return None

    def pick(build, level):
        pob = getattr(build, "pob_spec_index", build.active_spec_index)
        idx, _by_level = sf.pick(build.specs, pob, level)
        return idx
    return pick


class Holder:
    def __init__(self, core, clock=time.monotonic):
        self.core = core
        self.clock = clock
        self.model = None
        self._quick = None
        self._sig = None
        self._next_full = 0.0
        self._published = False
        self._lock = threading.Lock()

    # -- inputs
    def _build(self):
        builds = getattr(self.core, "builds", None)
        return getattr(builds, "build", None) if builds is not None else None

    def _tree(self, build):
        builds = getattr(self.core, "builds", None)
        cache = getattr(builds, "tree", None) if builds is not None else None
        if cache is None:
            return None
        try:
            best_for = getattr(cache, "best_for", None)
            if callable(best_for):
                spec = build.active_spec if build is not None else None
                return best_for(spec.nodes if spec is not None else ())
            return cache.get()
        except Exception:  # noqa: BLE001 - optional data never breaks the view
            return None

    def _gems(self):
        engine = getattr(self.core, "kindler", None)
        sources = getattr(engine, "sources", None)
        fn = getattr(sources, "gems", None)
        try:
            return fn() if callable(fn) else None
        except Exception:  # noqa: BLE001
            return None

    def _kindler_tab(self):
        """(tab id, label, follow, result key) of the first Kindler tab whose
        last result this core holds, or None."""
        store = getattr(self.core, "gen_builds", None)
        engine = getattr(self.core, "kindler", None)
        if store is None or engine is None:
            return None
        try:
            tabs = store.view()["tabs"]
        except Exception:  # noqa: BLE001
            return None
        for t in tabs:
            res = t.get("result") or {}
            if res and engine.last(t["id"]) is not None:
                return (t["id"], t.get("label") or "", bool(t.get("follow", True)),
                        res.get("key"), res.get("at"))
        return None

    def _kindler(self, tab):
        if tab is None:
            return None
        engine = self.core.kindler
        planner = getattr(self.core, "kindler_plan", None)
        doc = engine.last(tab[0])
        if planner is None or doc is None:
            return None
        plan, _focus = planner.plan(doc, busy=True)
        if plan is None:
            return None
        stage = None
        if tab[2]:
            cur = kindlerplan.current_stage(plan, kindlerplan.here_of(self.core.state))
            stage = cur["stage"] if cur else None
        return {"plan": plan, "stage": stage, "label": tab[1]}

    # -- the tick
    def tick(self):
        st = getattr(self.core, "state", None)
        build = self._build()
        quick = (id(build), getattr(st, "level", None), getattr(st, "area_id", None),
                 getattr(st, "zone", None))
        now = self.clock()
        if quick == self._quick and now < self._next_full:
            return False
        self._quick = quick
        self._next_full = now + FULL_EVERY_S
        # ACTIVE-BUILD-PICK (decision 0096): a Kindler plan the player put in
        # use is the source, whatever the pasted build; else, as before, the
        # first Kindler result only while no build is loaded
        picker = getattr(self.core, "build_source", None)
        chosen = picker.kindler_tab() if picker is not None else None
        if chosen is not None:
            build = None
        tree = self._tree(build)
        tab = chosen if chosen is not None else (
            self._kindler_tab() if build is None else None)
        gems = self._gems()
        guide = getattr(st, "zone_guide", None)
        sig = (quick, id(tree), tab, id(gems), id(guide))
        if sig == self._sig:
            return False
        self._sig = sig
        model = progression.build_model(
            build=build, tree=tree, level=quick[1], area_id=quick[2], zone=quick[3],
            guide=guide, kindler=self._kindler(tab), gems=gems,
            picker=spec_picker(self.core), prev=self.model)
        with self._lock:
            self.model = model
        # with nothing to show the snapshot gets no "progression" key at
        # all until a build or plan first appears (then None when it goes)
        view = progression.summary(model) if model["source"] != "none" else None
        if st is not None and hasattr(st, "publish") and (view is not None or self._published):
            st.publish("progression", view)
            self._published = True
        return True

    def get(self):
        with self._lock:
            return self.model


def attach(core):
    holder = Holder(core)
    core.progression = holder
    core.add_tick("progression", holder.tick)


def get_progression(req, query, extra):
    holder = getattr(req.server.core, "progression", None)
    model = holder.get() if holder is not None else None
    return req._json(200, model if model is not None else {"key": None}, extra)


ROUTES = {
    ("GET", "/api/progression"): get_progression,
}
