"""TC-VIEW / TC-EVAL-UI: the theorycraft bits the live state carries.

- `build_info(build, rev)`: a tiny summary of the loaded build for the state
  snapshot, so the dashboard learns that the build changed (and fetches
  GET /api/build) with no refresh button, and can set the live character's
  level next to the build's.
- `compact(result)`: the last item evaluation, trimmed for the state
  snapshot (pushed to the dashboard and the overlay on every change).
- `LastEval`: runs an evaluation, publishes it, and re-runs the last item
  when the weights or the build change (ZERO-CLICK: deltas recompute on
  change). The item text stays in memory only and comes from the caller
  (the one per-press clipboard read, decision 0003); nothing here reads the
  clipboard or sends anything to the game.
- TC-PRESS-STAGED-LIVE (decision 0024 amendment 2026-11-19): a staged
  LastEval (the core's) publishes the weights card at once, inside the
  press, and the Path of Building stages (DPS / EHP, then the per-mod rows)
  later from one daemon worker, each an update that keeps the card's time.
  A press generation counter keeps one press in flight: a newer press or a
  re-score cancels the pending stages of the older one, and a stale stage
  is never published.
"""

import logging
import threading

from .. import campaign as campaign_mod
from .. import upgrade as upgrade_mod
from . import buildlive
from . import cardparts
from . import delta as delta_mod
from . import evaluate as tc_evaluate
from . import item as item_parser
from . import pobweights
from . import value as value_mod
from . import waystone as waystone_mod
from . import worngear

MAX_COMPARISONS = 3
MAX_STATS = 8
MAX_LIST = 12
JOIN_S = 10.0  # LastEval.close(): how long the stage worker is waited for

LOG = logging.getLogger("al.live")


def build_info(build, rev=0, character=None):
    """`character` (BUILD-LIVE): whose build this is (the store's active
    character), so the stale-build check never compares another's."""
    if build is None:
        return {"loaded": False, "rev": rev, "class_name": None, "ascendancy": None,
                "level": None, "character": character}
    return {"loaded": True, "rev": rev, "class_name": build.class_name,
            "ascendancy": build.ascendancy, "level": build.level,
            "character": character}


def _named(d):
    if not isinstance(d, dict):
        return None
    return {"name": d.get("name"), "base": d.get("base")}


def compact(result):
    """The snapshot form of an evaluate() result: verdict, deltas, the top
    stat rows of each compared slot. Never raises on a partial result."""
    r = result if isinstance(result, dict) else {}
    item = r.get("item") or {}
    comps = []
    for c in (r.get("comparisons") or [])[:MAX_COMPARISONS]:
        stats = [s for s in (c.get("stats") or []) if s.get("delta")]
        extra = {k: c[k] for k in ("dps", "ehp") if isinstance(c.get(k), dict)}
        comps.append({**extra, "slot": c.get("slot"), "empty": bool(c.get("empty")),
                      "equipped": _named(c.get("equipped")),
                      "equipped_score": c.get("equipped_score"),
                      "score_delta": c.get("score_delta"), "verdict": c.get("verdict"),
                      "stats": [{"key": s.get("key"), "new": s.get("new"),
                                 "old": s.get("old"), "delta": s.get("delta"),
                                 "score_delta": s.get("score_delta"),
                                 "weighted": bool(s.get("weighted"))}
                                for s in stats[:MAX_STATS]]})
    flags = item.get("flags") or {}
    calc = r.get("calc") if isinstance(r.get("calc"), dict) else {}
    pot = r.get("potential")
    return {"ok": bool(r.get("ok")), "error": r.get("error"), "verdict": r.get("verdict"),
            "calc": {"source": calc.get("source", "weights"), "notice": calc.get("notice")},
            "slot": r.get("slot"), "score": r.get("score"),
            "score_delta": r.get("score_delta"),
            "build_loaded": bool(r.get("build_loaded")),
            "item": {"name": item.get("name"), "base": item.get("base"),
                     "item_class": item.get("item_class"), "rarity": item.get("rarity")},
            "unidentified": bool(flags.get("unidentified")),
            "unweighted": list(r.get("unweighted") or [])[:MAX_LIST],
            "comparisons": comps,
            # MATH-POTENTIAL: score now vs at the worst / best rolls (shown
            # by web/tc.js rollsText, MATH-POTENTIAL-UI)
            "potential": ({k: pot.get(k) for k in ("score", "worst", "best", "pct")}
                          if isinstance(pot, dict) else None)}


class LastEval:
    """The last evaluated item, kept so a weights or build change re-scores
    it at once. One per core."""

    def __init__(self, builds, weights, state, league=None, calc=None, rates=None,
                 trade_ids=None, staged=False, worn=None):
        self.builds = builds
        # TC-WORN-BASELINE (decision 0052): the worn-gear store (a
        # worngear.WornGear, injected; None: no worn baseline). The item
        # check compares against the worn item first, the PoB plan second
        self.worn = worn
        # TC-WORN-WIRE: a callable read at use time (the core's worn_gear
        # switch); False: no item is filed and no worn item is compared
        # against (the stored set stays as it is). None: always on.
        self.worn_on = None
        self.weights = weights
        self.state = state
        # TC-UPGRADE: a callable read at run time (the configured league or
        # None -> Standard); nothing is fetched
        self.league = league
        # TC-DELTA (decision 0024): a provider read at run time, returning
        # the PoB calc callable (theorycraft.delta) or None while the
        # optional component is off; TC-BRIDGE supplies it
        self.calc = calc
        # TC-UPGRADE-STATS (decision 0037): a callable returning the trade
        # stat id index from the cached snapshot ({} while web data is off)
        self.trade_ids = trade_ids
        # MATH-VALUE: a callable returning the cached poe.ninja rates
        # snapshot (never fetches; empty while web data is off)
        self.rates = rates
        # MATH-WEIGHTS: PoB-measured stat weights per build / slot, so a
        # re-check probes only new stats and a calc outage still scores
        # with this build's PoB weights
        self.pob_weights = pobweights.PobWeightCache()
        self._input = None
        self._lock = threading.Lock()
        # BUILD-LIVE (decision 0045): the items checked per character, in
        # memory only, re-scored when the build or the weights change
        self.candidates = buildlive.Candidates()
        # TC-CARD-PARTS: what the core adds to every part's ctx ("config":
        # the local config callable; "area_id": a callable read per press)
        self.ctx_extra = {}
        # TC-PRESS-STAGED-LIVE: staged True (the core) publishes the weights
        # card inside the press and the PoB stages from one daemon worker;
        # False runs every stage inline and publishes the last one only.
        # `_gen` is the press generation: a stage is published only while
        # its press is still the newest (checked under `_publish`).
        self.staged = bool(staged)
        self._gen = 0
        self._publish = threading.Lock()
        self._cond = threading.Condition()
        self._job = None
        self._worker = None
        self._closed = False
        self._busy = False
        # the result of the last published stage (wait() then read it)
        self.last_result = None

    def _who(self):
        """(character, level) from the state: the player's own log facts."""
        return (getattr(self.state, "character", None),
                getattr(self.state, "level", None))

    def _store(self):
        """TC-WORN-WIRE: the worn-gear store while the switch is on, else
        None (a failing switch reads as on: the default)."""
        if self.worn is None or not callable(self.worn_on):
            return self.worn
        try:
            on = self.worn_on()
        except Exception:  # noqa: BLE001 - the default is on
            on = True
        return self.worn if on is not False else None

    def baseline(self, build=None):
        """TC-WORN-BASELINE: the worngear.Baseline of the current character
        and `build` (default the loaded one), or None without a worn
        store (or with the worn_gear switch off)."""
        store = self._store()
        if store is None:
            return None
        build = self.builds.build if build is None else build
        return worngear.Baseline(store, self._who()[0], build)

    def wear_last(self, slot=None, text=None):
        """TC-WORN-BASELINE: file the last checked item (or `text`) as the
        current character's worn item of its slot (`slot`: an explicit
        slot, else the store's choice). Returns the slot, or None (no worn
        store, nothing checked yet, or not gear). The checked items are
        re-scored against the new baseline."""
        store = self._store()
        if store is None:
            return None
        if text is None:
            with self._lock:
                last = self._input
            text = last[0] if last is not None else None
        if not isinstance(text, str):
            return None
        filed = store.wear(self._who()[0], text, slot=slot, build=self.builds.build)
        if filed is not None:
            self.rescore()
        return filed

    def run(self, text, slot=None, keep_time=False, at=None):
        """`at`: the press time (PRICE-1-WIRE shares it with the price
        check of the same press); None stamps now. The card gains
        `upgrade`: the offline upgrade-search link doc, or None (TC-UPGRADE).

        TC-PRESS-STAGED-LIVE: staged, it returns the first stage's result
        (the weights card; no calc call) and the worker publishes the later
        stages as updates that keep this card's time. Not staged, it
        returns the last stage (evaluate()'s result), as before."""
        calc = self.calc() if callable(self.calc) else None
        with self._publish:
            self._gen += 1
            gen = self._gen
        with self._lock:
            self._input = (text, slot)
        build = self.builds.build
        stages = tc_evaluate.stages(text, build, self.weights.get(), slot=slot,
                                    calc=calc, cache=self.pob_weights,
                                    baseline=self.baseline(build))
        press = _Press(self, text, slot, gen)
        if not self.staged:
            result = None
            for _name, result in stages:
                pass
            press.publish(tc_evaluate.STAGE_MODS, result, False, keep_time, at, force=True)
        else:
            name, result = next(stages)
            # more stages follow only with the calc on, a build and a
            # compared item (a worn item alone is scored by the weights)
            pending = calc is not None and build is not None and bool(result.get("ok"))
            press.publish(name, result, pending, keep_time, at)
            if pending:
                self._queue(press, stages, name)
            else:
                stages.close()
        if not keep_time and result.get("ok") and press.waystone is None:
            # BUILD-LIVE: a press adds the item to this character's list
            with self._lock:
                self.candidates.add(self._who()[0], text, slot, result.get("verdict"),
                                    at if at is not None else _now(self.state))
            store = self._store()
            if store is not None:
                # TC-WORN-BASELINE: wear_last() files it in the slot it was
                # compared against (memory only)
                store.note_compared(self._who()[0], result.get("slot"), text)
            self.rescore(fresh=False)
        return result

    def clear(self, card=None, result=None, at=None):
        """TC-EVAL-CLEAR-API: start a new press that has no item (the blank
        clipboard press of OVL-COPY-FIRST). The press generation moves on
        under the publish lock, so no stage of an older press is published
        after this; a queued stage job is dropped (its generator closed: no
        calc call); rerun() then has no item to re-score. `card`: published
        with set_eval(card, at=at) under the same lock, and `result` kept as
        last_result. Returns the new press generation."""
        with self._lock:
            self._input = None
        with self._publish:
            self._gen += 1
            gen = self._gen
            if card is not None:
                self.state.set_eval(card, at=at)
                self.last_result = result
        with self._cond:
            old, self._job = self._job, None
            self._cond.notify_all()
        if old is not None:
            old[1].close()
        return gen

    # -- TC-PRESS-STAGED-LIVE: the stage worker ------------------------------

    def current(self, gen):
        """True while press generation `gen` is the newest one."""
        return gen == self._gen and not self._closed

    def _queue(self, press, stages, last):
        """Hand a press's remaining stages to the worker; the pending job of
        an older press is dropped (its generator closed: no calc call)."""
        with self._cond:
            old, self._job = self._job, None
            closed = self._closed
            if not closed:
                self._job = (press, stages, last)
                if self._worker is None:
                    self._worker = threading.Thread(target=self._work,
                                                    name="al-eval-stages", daemon=True)
                    self._worker.start()
                self._cond.notify_all()
        if old is not None:
            old[1].close()
        if closed:
            stages.close()

    def _work(self):
        while True:
            with self._cond:
                while self._job is None and not self._closed:
                    self._cond.wait()
                if self._job is None:
                    return
                job, self._job = self._job, None
                self._busy = True
            try:
                self._drain(*job)
            finally:
                with self._cond:
                    self._busy = False
                    self._cond.notify_all()

    def _drain(self, press, stages, last):
        """Run a press's later stages; stop at the first stage boundary
        after a newer press (or close()) and publish nothing stale."""
        try:
            for name, result in stages:
                if not self.current(press.gen):
                    return
                # "pob" has the probes still to come; a "weights" stage
                # after the first is a calc error's fallback, the last one
                pending = name == tc_evaluate.STAGE_POB
                if not press.publish(name, result, pending, True, None) or not pending:
                    return
                last = name
        except Exception as exc:  # noqa: BLE001 - the card must not stay pending
            LOG.warning("item check stage failed (%s)", type(exc).__name__)
            result = dict(press.result or {})
            if last == tc_evaluate.STAGE_WEIGHTS:
                result["calc"] = dict(result.get("calc") or {},
                                      notice=delta_mod.NOTICE_FAILED)
            press.publish(last, result, False, True, None)
        finally:
            stages.close()

    def wait(self, timeout=None):
        """True once no stage is queued or running (tests and the live e2e
        check wait for the last stage); False on timeout."""
        with self._cond:
            return self._cond.wait_for(lambda: self._job is None and not self._busy,
                                       timeout)

    def close(self, timeout=JOIN_S):
        """Stop the stage worker: pending stages are dropped and none is
        published after this; waits up to `timeout` s for a stage that is
        mid calc call (0: do not wait). Returns True when the worker is
        gone. Idempotent."""
        with self._publish:
            self._closed = True
            self._gen += 1
        with self._cond:
            old, self._job = self._job, None
            worker = self._worker
            self._cond.notify_all()
        if old is not None:
            old[1].close()
        if worker is None:
            return True
        if timeout and worker is not threading.current_thread():
            worker.join(timeout)
        return not worker.is_alive()

    def rescore(self, fresh=True):
        """BUILD-LIVE: re-score the current character's checked items with
        the loaded build and weights, and publish the ones that are
        upgrades now (`new`: not an upgrade before this re-score). Uses the
        stat weights, or the weights Path of Building measured for this
        build earlier (MATH-WEIGHTS cache); no new calc run, so a build swap
        stays quick. `fresh` False (a press) keeps every verdict as it was."""
        character, level = self._who()
        build = self.builds.build
        weights = self.weights.get()
        baseline = self.baseline(build)
        with self._lock:
            rows = self.candidates.rows(character)
        items = []
        for entry in rows:
            try:
                res = tc_evaluate.evaluate(entry["text"], build, weights, slot=entry["slot"],
                                           calc=None, cache=self.pob_weights,
                                           baseline=baseline)
            except Exception:  # noqa: BLE001 - one bad row never stops the list
                continue
            with self._lock:
                if fresh:
                    entry["was"] = entry.get("verdict")
                entry["verdict"] = res.get("verdict") if res.get("ok") else None
            n = buildlive.notice(res, entry, level, build)
            if n is not None:
                items.append(n)
        items.sort(key=lambda n: (not n["new"], -(n.get("at") or 0)))
        view = {"character": character, "checked": len(rows),
                "build_loaded": build is not None, "items": items[:buildlive.MAX_ITEMS]}
        setter = getattr(self.state, "set_upgrades", None)
        if callable(setter):
            setter(view)
        return view

    def _part_ctx(self, text, parsed, result, stage=None):
        """TC-CARD-PARTS: the ctx every card part's compute() gets: text,
        parsed, result, build, character, level, area_id and config (a
        callable), plus any other key the core put in ctx_extra.
        TC-PRESS-STAGED-LIVE: `stage` {"name", "pending"}: the evaluate
        stage this card shows and whether later stages are still coming."""
        extra = self.ctx_extra if isinstance(self.ctx_extra, dict) else {}
        ctx = dict(extra)
        area = extra.get("area_id")
        try:
            ctx["area_id"] = area() if callable(area) else area
        except Exception:  # noqa: BLE001 - a part then sees no area
            ctx["area_id"] = None
        config = extra.get("config")
        ctx["config"] = config if callable(config) else dict
        character, level = self._who()
        ctx.update(text=text, parsed=parsed, result=result, build=self.builds.build,
                   character=character, level=level,
                   stage=dict(stage) if isinstance(stage, dict) else None)
        return ctx

    def _value(self, parsed, result):
        """MATH-VALUE: the item's own Note price in the primary currency and
        score per primary unit, from cached rates; None without a note
        price. A failing rates source gives a value doc with no rate.
        `parsed`: the press's item_parser.parse() result (None: no text)."""
        note = parsed.note if parsed is not None else None
        if value_mod.parse_note_price(note) is None:
            return None
        snap = None
        if callable(self.rates):
            try:
                snap = self.rates()
            except Exception:  # noqa: BLE001 - the item check must still publish
                snap = None
        delta = result.get("score_delta") if result.get("ok") else result.get("score")
        return value_mod.value_of(note, delta, snap)

    def rerun(self):
        """Re-score the last item (weights or build changed). The card keeps
        its time, so the overlay does not show it again. Staged, it is a new
        press generation: the older press's pending stages are cancelled."""
        with self._lock:
            last = self._input
        self.rescore()  # BUILD-LIVE: the checked items too
        if last is None:
            return None
        return self.run(last[0], last[1], keep_time=True)


class _Press:
    """TC-PRESS-STAGED-LIVE: one press (or re-score) of a LastEval: the
    per-press inputs every stage's card reuses, and the publish guard."""

    def __init__(self, last, text, slot, gen):
        self.last = last
        self.text = text
        self.slot = slot
        self.gen = gen
        self.parsed = item_parser.parse(text) if isinstance(text, str) else None
        self.league = last.league() if callable(last.league) else last.league
        self.ids = last.trade_ids() if callable(last.trade_ids) else None
        # UTIL-WAYSTONE (decision 0030): the same press on a waystone flags
        # its mods risky for the loaded build; None for any other item
        self.waystone = waystone_mod.check(text, last.builds.build)
        self.result = None

    def card(self, name, result, pending):
        last = self.last
        card = dict(compact(result), upgrade=upgrade_mod.link(result, self.league, self.ids),
                    value=last._value(self.parsed, result))
        card["waystone"] = self.waystone
        # TC-CARD-PARTS: every card part computes its value on this press,
        # on each later stage and on every re-score; the words come later
        # (state.eval_card_text)
        card["parts"] = cardparts.compute(last._part_ctx(
            self.text, self.parsed, result, {"name": name, "pending": bool(pending)}))
        return card

    def publish(self, name, result, pending, keep_time, at, force=False):
        """Publish one stage's card while this press is the newest (force:
        the inline path, not staged). Returns False for a stale press."""
        last = self.last
        card = self.card(name, result, pending)
        with last._publish:
            if not force and not last.current(self.gen):
                return False
            last.state.set_eval(card, keep_time=keep_time, at=at)
            self.result = result
            last.last_result = result
        return True


def _now(state):
    clock = getattr(state, "now", None)
    return clock() if callable(clock) else None


def _campaign_facts(state, build):
    """UTIL-CAMPAIGN-CHECKS: the loaded build's gear / resist facts."""
    setter = getattr(state, "set_campaign", None)
    if callable(setter):
        setter(facts=campaign_mod.build_facts(build))


def attach(builds, weights, state, league=None, calc=None, rates=None, trade_ids=None,
           staged=False, worn=None):
    """Wire the live views into a core: build summary now and on every load,
    and a LastEval that re-runs on a build change. Returns the LastEval.
    `staged` (TC-PRESS-STAGED-LIVE): publish the item check in stages.
    `worn` (TC-WORN-BASELINE): the worn-gear store, or None."""
    last = LastEval(builds, weights, state, league=league, calc=calc, rates=rates,
                    trade_ids=trade_ids, staged=staged, worn=worn)
    rev = [0]

    def on_build(build):
        rev[0] += 1
        state.set_build_info(build_info(build, rev[0], getattr(builds, "character", None)))
        _campaign_facts(state, build)
        last.rerun()

    builds.add_listener(on_build)
    state.set_build_info(build_info(builds.build, 0, getattr(builds, "character", None)))
    _campaign_facts(state, builds.build)
    return last
