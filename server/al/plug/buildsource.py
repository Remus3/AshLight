"""ACTIVE-BUILD-PICK (decision 0096): which build Play, the item check and
the Progression view use, per character, through the plug seam (decision
0056).

One active build source per character: the pasted Path of Building build
(decision 0045, the default) or a Kindler tab's plan (decision 0081).
The choice is the player's click only and is kept in
theorycraft.buildsource.SourceStore (ops/runtime/build/source.json), so it
survives a restart. While a Kindler plan is in use the tick composes the
PoB XML of the plan's stage (kindler.compose_xml: the passives up to that
stage, its skills and the checked weapon base, no other item) and puts it
in the build store in place of the pasted build (BuildStore.use_override);
the item check, the Play build line, the build view and the stale-build
check follow through the store's listeners, and the Progression view uses
the chosen tab's Kindler plan (plug/progression.py). The stage is the one
the Play guidance matches while the tab's follow flag is on, else the
result's best stage; a new stage composes again. The pasted build file is
never touched, so "Use pasted build" brings it straight back. A new paste
(the paste box, an item-key press holding a code, or a pasted file newer
than the choice) makes the pasted build the one in use again.

After a restart the Kindler result is restored from the tab's stored
summary (kindler.from_summary, Engine.restore): no calc, no Generate.

GET /api/build-source answers the view. POST /api/build-source takes
{"use": "pasted"} or {"use": "kindler", "id": <tab id>} for the character
being played and answers the view plus "saved" (false while the change
waits for its retry; it is kept in memory). A refused change is a 400
{"error": <the player's sentence>, "reason": <one fixed word of
text/buildsource.py REASONS>} (BUILD-SWITCH-COPY), never a path or free
text. Both run behind the handler's Host / Origin /
Sec-Fetch-Site / token guard; the body is capped at the handler's
MAX_BODY (4096). Nothing is sent to the game or anywhere else, and the
character name stays on this computer.

The snapshot gets "build_source":
    {"use": "pasted" | "kindler", "tab": id | None, "label": str,
     "offer": {"id", "label"} | None, "pasted": bool}
"offer" is the Kindler tab a one-click switch would pick while the pasted
build is in use (the shown tab when it has a result, else the first one
with a result); "pasted" says the character has a pasted build file.
"""

import logging
import threading
import time

from .. import jsonfile
from ..text import buildsource as words
from ..theorycraft import buildsource, genstore, kindler, kindlerplan, model

ORDER = 115  # after plug/kindler.py (110), before plug/progression.py (120)
SAVER = "buildsource"
FULL_EVERY_S = 2.0
USES = ("pasted", "kindler")

SAVE_FAILED = words.SAVE_FAILED
BAD = words.BAD
NO_CHARACTER = words.NO_CHARACTER
NO_RESULT = words.NO_RESULT

log = logging.getLogger("al.buildsource")


class Refused(ValueError):
    """A refused click: reason is one word of words.REASONS and str() its
    player's sentence."""

    def __init__(self, reason):
        super().__init__(words.REASONS[reason])
        self.reason = reason


def refusal(reason):
    """The 400 body of a refused click (BUILD-SWITCH-COPY)."""
    return {"error": words.REASONS[reason], "reason": reason}


class Picker:
    def __init__(self, core, store, clock=time.monotonic, wall=time.time):
        self.core = core
        self.store = store
        self.clock = clock
        self.wall = wall
        self._quick = None
        self._next_full = 0.0
        self._applied = None
        self._view = None
        self._published = False
        # the core loop's tick and a route click may run at once
        self._lock = threading.RLock()

    # -- inputs
    def _builds(self):
        return getattr(self.core, "builds", None)

    def character(self):
        builds = self._builds()
        name = getattr(builds, "character", None) if builds is not None else None
        if not name:
            name = getattr(getattr(self.core, "state", None), "character", None)
        return name if isinstance(name, str) and name else None

    def _tabs(self):
        store = getattr(self.core, "gen_builds", None)
        if store is None:
            return None
        try:
            return store.view()
        except Exception:  # noqa: BLE001 - optional data never breaks the tick
            return None

    def _inputs(self):
        engine = getattr(self.core, "kindler", None)
        sources = getattr(engine, "sources", None)
        try:
            return sources.inputs() if sources is not None else None
        except Exception:  # noqa: BLE001
            return None

    def _doc(self, tab, inputs):
        """The tab's result document: the engine's, else restored from the
        stored summary (no calc, no Generate)."""
        engine = self.core.kindler
        doc = engine.last(tab["id"])
        if doc is None:
            restored = kindler.from_summary(tab.get("result"), inputs["view"]["templates"])
            engine.restore(tab["id"], restored)
            doc = engine.last(tab["id"])
        return doc

    def chosen_tab(self, view=None):
        """The view tab of the character's Kindler choice while it can be
        used (the tab exists and has a result), else None."""
        entry = self.store.get(self.character())
        if entry is None:
            return None
        view = view if view is not None else self._tabs()
        for t in (view or {}).get("tabs") or ():
            if t["id"] == entry["tab"]:
                return t if t.get("result") else None
        return None

    def kindler_tab(self):
        """plug/progression.py's Kindler source tuple (id, label, follow,
        result key, result time) of the chosen tab whose result this core
        holds, or None."""
        tab = self.chosen_tab()
        engine = getattr(self.core, "kindler", None)
        if tab is None or engine is None or engine.last(tab["id"]) is None:
            return None
        res = tab.get("result") or {}
        return (tab["id"], tab.get("label") or "", bool(tab.get("follow", True)),
                res.get("key"), res.get("at"))

    def _compose(self, tab, inputs):
        """(key, build) of the chosen tab's plan stage, or None when it
        cannot be composed yet (no tree data, a template gone)."""
        doc = self._doc(tab, inputs)
        templates = inputs["view"]["templates"]
        hit = kindlerplan.best_of(doc, templates)
        tree = inputs.get("tree")
        if hit is None or tree is None:
            return None
        template, si, variant = hit
        if tab.get("follow", True):
            plan = kindlerplan.build_plan(template, tree=tree)
            cur = kindlerplan.current_stage(
                plan, kindlerplan.here_of(getattr(self.core, "state", None)))
            if cur is not None:
                si = cur["stage"]
        res = tab.get("result") or {}
        key = (tab["id"], template["id"], si, variant, inputs.get("tree_version"),
               res.get("at"), self.character())
        if key == self._applied and self._builds().override is not None:
            return key, None
        try:
            xml = kindler.compose_xml(template, si, variant, kindler.tree_ids(tree, template))
            return key, model.parse(xml)
        except (kindler.TreeIdsMissing, model.BuildError, KeyError, IndexError):
            log.warning("Kindler plan stage not composed")
            return None

    def _offer(self, view):
        tabs = [t for t in (view or {}).get("tabs") or () if t.get("result")]
        if not tabs:
            return None
        shown = (view or {}).get("shown")
        pick = next((t for t in tabs if t["id"] == shown), tabs[0])
        return {"id": pick["id"], "label": pick.get("label") or ""}

    # -- the tick
    def tick(self, force=False):
        with self._lock:
            return self._tick(force)

    def _tick(self, force):
        builds = self._builds()
        engine = getattr(self.core, "kindler", None)
        if builds is None or engine is None:
            return False
        st = getattr(self.core, "state", None)
        name = self.character()
        quick = (name, repr(self.store.get(name)), getattr(st, "level", None),
                 getattr(st, "area_id", None), getattr(st, "area_level", None),
                 id(builds.build), builds._file_key is not None)
        now = self.clock()
        if not force and quick == self._quick and now < self._next_full:
            return False
        self._quick = quick
        self._next_full = now + FULL_EVERY_S
        view = self._tabs()
        tab = self.chosen_tab(view)
        inputs = self._inputs() if tab is not None else None
        changed = False
        if tab is None or inputs is None:
            self._applied = None
            if builds.override is not None:
                builds.clear_override()
                changed = True
        else:
            got = self._compose(tab, inputs)
            if got is not None:
                key, build = got
                if build is not None:
                    builds.use_override(build, tab.get("label") or "")
                    self._applied = key
                    changed = True
        self._publish(view)
        return changed

    def view(self, tabs=None):
        builds = self._builds()
        tabs = tabs if tabs is not None else self._tabs()
        on = builds is not None and builds.override is not None
        tab = self.chosen_tab(tabs) if on else None
        return {"use": "kindler" if tab is not None else "pasted",
                "tab": tab["id"] if tab is not None else None,
                "label": (tab.get("label") or "") if tab is not None else "",
                "offer": None if tab is not None else self._offer(tabs),
                "pasted": bool(builds is not None and builds._file_key is not None
                               and builds._file_key[1] is not None)}

    def _publish(self, tabs):
        view = self.view(tabs)
        st = getattr(self.core, "state", None)
        if view == self._view and self._published:
            return
        self._view = view
        if st is not None and hasattr(st, "publish"):
            st.publish("build_source", view)
            self._published = True

    # -- the build store's hooks
    def paste_wins(self, name, mtime):
        """A pasted file that changed on disk takes over only when it is
        newer than the character's Kindler choice."""
        entry = self.store.get(name)
        return entry is None or mtime is None or mtime > entry["at"]

    def on_paste(self, name):
        """A new paste is the build in use: forget the Kindler choice."""
        try:
            if self.store.drop(name):
                self._applied = None
                self._quick = None
        except OSError as exc:
            log.warning("build choice not saved yet: %s", type(exc).__name__)
            self.core.savers[SAVER].mark()

    # -- the route
    def choose(self, use, tab_id=None):
        """Apply one click. Returns saved (bool). Raises Refused (its
        reason word and the player's sentence) when refused."""
        name = self.character()
        if name is None:
            raise Refused("no_character")
        saved = True
        try:
            if use == "pasted":
                self.store.drop(name)
            else:
                view = self._tabs()
                tab = next((t for t in (view or {}).get("tabs") or ()
                            if t["id"] == tab_id), None)
                if tab is None or not tab.get("result"):
                    raise Refused("no_result")
                try:
                    self.store.set(name, tab_id, self.wall())
                except ValueError:  # a name or tab id the file may not hold
                    raise Refused("bad") from None
        except OSError as exc:
            log.warning("build choice not saved yet: %s", type(exc).__name__)
            self.core.savers[SAVER].mark()
            saved = False
        self._applied = None
        self.tick(force=True)
        return saved


def attach(core):
    """One store and picker per core, its Saver, its tick and the build
    store's hooks (made here when the Kindler plugs did not run first)."""
    if getattr(core, "kindler", None) is None:
        from . import kindler as kindler_plug
        kindler_plug.attach(core)
    store = buildsource.SourceStore(buildsource.default_path(core.runtime))
    picker = Picker(core, store)
    core.build_source = picker
    saver = jsonfile.Saver(store.save, clock=lambda: getattr(
        core, "store_clock", time.monotonic)())
    savers = getattr(core, "savers", None)
    if savers is None:
        savers = core.savers = {}
    savers[SAVER] = saver
    builds = getattr(core, "builds", None)
    if builds is not None:
        builds.paste_wins = picker.paste_wins
        builds.on_paste = picker.on_paste
    core.add_tick("tick_build_source", lambda: tick(core))


def tick(core):
    saver = core.savers.get(SAVER)
    if saver is not None:
        saver.flush()
    picker = getattr(core, "build_source", None)
    return picker.tick() if picker is not None else False


def _picker(req):
    core = req.server.core
    if getattr(core, "build_source", None) is None:  # attach did not run
        attach(core)
    return core.build_source


def get_build_source(req, query, extra):
    return req._json(200, _picker(req).view(), extra)


def post_build_source(req, query, extra):
    body = req._read_json()
    if body is None:
        return None
    use = body.get("use")
    if use not in USES or set(body) - {"use", "id"}:
        return req._json(400, refusal("bad"), extra)
    tab_id = body.get("id")
    if use == "kindler" and not (isinstance(tab_id, str) and buildsource.clean_tab(tab_id)):
        return req._json(400, refusal("bad"), extra)
    if use == "pasted" and tab_id is not None:
        return req._json(400, refusal("bad"), extra)
    picker = _picker(req)
    try:
        saved = picker.choose(use, tab_id)
    except Refused as exc:
        return req._json(400, refusal(exc.reason), extra)
    except (genstore.GenError, ValueError):  # never the store's own text
        return req._json(400, refusal("bad"), extra)
    return req._json(200, dict(picker.view(), saved=saved), extra)


ROUTES = {
    ("GET", "/api/build-source"): get_build_source,
    ("POST", "/api/build-source"): post_build_source,
}
