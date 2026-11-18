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
"""

import threading

from .. import campaign as campaign_mod
from .. import upgrade as upgrade_mod
from . import buildlive
from . import evaluate as tc_evaluate
from . import item as item_parser
from . import pobweights
from . import value as value_mod
from . import waystone as waystone_mod

MAX_COMPARISONS = 3
MAX_STATS = 8
MAX_LIST = 12


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
                 trade_ids=None):
        self.builds = builds
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
        # BUILD-LIVE (decision 0041): the items checked per character, in
        # memory only, re-scored when the build or the weights change
        self.candidates = buildlive.Candidates()

    def _who(self):
        """(character, level) from the state: the player's own log facts."""
        return (getattr(self.state, "character", None),
                getattr(self.state, "level", None))

    def run(self, text, slot=None, keep_time=False, at=None):
        """`at`: the press time (PRICE-1-WIRE shares it with the price
        check of the same press); None stamps now. The card gains
        `upgrade`: the offline upgrade-search link doc, or None (TC-UPGRADE)."""
        calc = self.calc() if callable(self.calc) else None
        result = tc_evaluate.evaluate(text, self.builds.build, self.weights.get(), slot=slot,
                                      calc=calc, cache=self.pob_weights)
        with self._lock:
            self._input = (text, slot)
        league = self.league() if callable(self.league) else self.league
        ids = self.trade_ids() if callable(self.trade_ids) else None
        card = dict(compact(result), upgrade=upgrade_mod.link(result, league, ids),
                    value=self._value(text, result))
        # UTIL-WAYSTONE (decision 0030): the same press on a waystone flags
        # its mods risky for the loaded build; None for any other item
        card["waystone"] = waystone_mod.check(text, self.builds.build)
        self.state.set_eval(card, keep_time=keep_time, at=at)
        if not keep_time and result.get("ok") and card["waystone"] is None:
            # BUILD-LIVE: a press adds the item to this character's list
            with self._lock:
                self.candidates.add(self._who()[0], text, slot, result.get("verdict"),
                                    at if at is not None else _now(self.state))
            self.rescore(fresh=False)
        return result

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
        with self._lock:
            rows = self.candidates.rows(character)
        items = []
        for entry in rows:
            try:
                res = tc_evaluate.evaluate(entry["text"], build, weights, slot=entry["slot"],
                                           calc=None, cache=self.pob_weights)
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

    def _value(self, text, result):
        """MATH-VALUE: the item's own Note price in the primary currency and
        score per primary unit, from cached rates; None without a note
        price. A failing rates source gives a value doc with no rate."""
        note = item_parser.parse(text).note if isinstance(text, str) else None
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
        its time, so the overlay does not show it again."""
        with self._lock:
            last = self._input
        self.rescore()  # BUILD-LIVE: the checked items too
        if last is None:
            return None
        return self.run(last[0], last[1], keep_time=True)


def _now(state):
    clock = getattr(state, "now", None)
    return clock() if callable(clock) else None


def _campaign_facts(state, build):
    """UTIL-CAMPAIGN-CHECKS: the loaded build's gear / resist facts."""
    setter = getattr(state, "set_campaign", None)
    if callable(setter):
        setter(facts=campaign_mod.build_facts(build))


def attach(builds, weights, state, league=None, calc=None, rates=None, trade_ids=None):
    """Wire the live views into a core: build summary now and on every load,
    and a LastEval that re-runs on a build change. Returns the LastEval."""
    last = LastEval(builds, weights, state, league=league, calc=calc, rates=rates,
                    trade_ids=trade_ids)
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
