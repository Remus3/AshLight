"""LOOP-WATCH-WIRE (F-030, AUTO-05; decisions 0069, 0044, 0025 amendment
2026-11-18, rulings Q-12 and Q-13): the upstream watcher in the loop tick.
It replaces AUTO-01's docs_watch and tc_drift steps.

pre_halt(tick): in front of the HALT test, even HALTed, never on a dry run.
  tools/upstream_watch.run_due(root, now, halted=tick.halted, ctx=...) runs
  every due source of tools/watch_sources/. The two settled sources (GGG
  docs, decision 0044; PoB-PoE2 release, decision 0025) reach their reads
  only through the tick's seams, ctx["docs_watch"] = tick.d.docs_watch and
  ctx["drift"] = tick.d.drift; the line a seam returns is one tick line, as
  before. Under HALT the sources read and record and their findings queue;
  nothing is filed, bumped or committed.
post_work(tick, rows, work, skipped): after the work list (never HALTed,
  never dry): tools/watch_file.file_pending files the queued findings as
  add-only row files through tick.d.git (the kit git lock) under
  tick.d.budget.

Hermetic rule (tools/loop_steps): ctx["live"] is true only when tick.root
is this checkout (al_loop's ROOT); on any other root the frame's network
transport refuses every request, so a scratch-root tick starts no process
and makes no request. Only on the live root, while HALTed, and only when
the drift seam takes no `halted` argument, the release check runs as
tc_drift.loop_check(halted=True) so it still reads in front of the HALT
return (Q-13: the read, the record and a static trial only).

A source's one-time "idle: web data off" line stays in the watch state
(`python tools/upstream_watch.py status`), not in the tick log. This module
never imports al_loop. Python stdlib only.
"""

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import upstream_watch as watch  # noqa: E402  tools/upstream_watch.py (the frame)
import watch_file  # noqa: E402

from server.al import webfetch  # noqa: E402


def _same(a, b):
    try:
        return Path(a).resolve() == Path(b).resolve()
    except (OSError, TypeError, ValueError):
        return False


def live(tick):
    """True only when the tick runs on this checkout (al_loop.ROOT)."""
    return _same(tick.root, ROOT)


def _takes_halted(fn):
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return "halted" in params or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def _keep(out, res):
    if isinstance(res, str) and res.strip():
        out.append(res)
    return res


def _docs_seam(fn, out):
    def docs_watch(root, now):
        return _keep(out, fn(root, now))
    return docs_watch


def _live_halted_drift(root, now, halted=False):
    """The release check on the live root while HALTed (Q-13); never raises."""
    try:
        import tc_drift
        return tc_drift.loop_check(root, now, halted=halted)
    except Exception as exc:  # noqa: BLE001 - a drift fault must not stop the tick
        return f"tc drift: {type(exc).__name__}: {exc}"


def _drift_seam(fn, out, is_live):
    """The drift seam for the pob-release source. A seam that takes `halted`
    gets it; one that does not is called only while not HALTed (the source's
    rule), except on the live root, where a HALTed tick runs the release
    check with halted=True."""
    if _takes_halted(fn):
        def drift(root, now, halted=False):
            return _keep(out, fn(root, now, halted=halted))
        return drift
    if not is_live:
        def drift(root, now):
            return _keep(out, fn(root, now))
        return drift

    def drift(root, now, halted=False):
        if halted:
            return _keep(out, _live_halted_drift(root, now, halted=True))
        return _keep(out, fn(root, now))
    return drift


def _refuse(method, url, headers, body=None):
    """The frame's transport off the live root: every request refused."""
    raise webfetch.UrlNotAllowed("a scratch-root tick makes no request")


def pre_halt(tick):
    now = tick.d.clock()
    is_live = live(tick)
    seam_lines = []
    ctx = {
        "root": tick.root,
        "live": is_live,
        "halted": bool(tick.halted),
        "docs_watch": _docs_seam(tick.d.docs_watch, seam_lines),
        "drift": _drift_seam(tick.d.drift, seam_lines, is_live),
    }
    lines = watch.run_due(tick.root, now, halted=bool(tick.halted),
                          fetch=None if is_live else _refuse, ctx=ctx)
    lines = [ln for ln in lines if not ln.endswith(": " + watch.IDLE_OFF)]
    return seam_lines + lines


def post_work(tick, rows, work, skipped):
    return watch_file.file_pending(tick.root, tick.d.clock(), tick.d.git,
                                   getattr(tick.d, "budget", None),
                                   halted=bool(tick.halted), dry=bool(tick.dry))
