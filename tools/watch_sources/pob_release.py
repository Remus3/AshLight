"""LOOP-WATCH-SETTLED (F-030, AUTO-05): the PoB-PoE2 release check
(decision 0025) as a registry source. Docs: docs/plan/06 W2.

The read itself is unchanged: tools/tc_drift.py keeps its one releases read
per 24 h, its state file ops/runtime/tc_drift.json and its User-Agent
purpose. This source only triggers that check through the tick's seam and
turns a known static trial verdict into a finding; it never uses the
frame's fetch.

check(state, now, fetch, ctx):
- ctx["root"]: the tree the tick runs on (default: this checkout, and only
  when ctx["live"] is true; with neither the source reads nothing).
- ctx["drift"](root, now, halted=<bool>): the tick's release check (al_loop
  Deps drift). A seam without a `halted` parameter is called only while the
  loop is not HALTed. When the key is absent tc_drift.loop_check is called,
  only when ctx["live"] is true, so a scratch-root test stays hermetic.
- HALT is ctx["halted"] or the file ops/loop/control/HALT under the root.
  While HALTed the check, the record and the static trial still happen
  (ruling Q-13: tc_drift.loop_check(halted=True) never launches a live
  trial) and no finding is made; the finding comes on the first tick after
  HALT is gone.

Finding: kind "pobrelease" (row POB-<VTAG>), key the new tag, once the
check reads "new" and the trial of that tag has a verdict: static-green or
live-green -> green, static-red -> red. A live "red", "untested" or "error"
makes no finding (no known static verdict).
"""

import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import tc_drift  # noqa: E402

NAME = "pob-release"
KIND = "pobrelease"
HALT_REL = Path("ops") / "loop" / "control" / "HALT"
TAG_RX = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
VERDICTS = {"static-green": "green", "live-green": "green", "static-red": "red"}


def _root(ctx):
    if ctx.get("root") is not None:
        return Path(ctx["root"])
    return ROOT if ctx.get("live") else None


def _seam(ctx):
    if "drift" in ctx:
        return ctx["drift"]
    return tc_drift.loop_check if ctx.get("live") else None


def _takes_halted(fn):
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return "halted" in params or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def halted_now(root, ctx):
    if ctx.get("halted"):
        return True
    return root is not None and (Path(root) / HALT_REL).exists()


def vtag(tag):
    """v0.24.0 -> V0-24-0 (the row id part)."""
    return tag.upper().replace(".", "-")


def finding(drift_state):
    """The pobrelease finding for a tc_drift state, or None."""
    st = drift_state if isinstance(drift_state, dict) else {}
    tag, pin = st.get("latest"), st.get("pinned")
    if st.get("status") != "new":
        return None
    if not (isinstance(tag, str) and TAG_RX.fullmatch(tag)):
        return None
    if not (isinstance(pin, str) and TAG_RX.fullmatch(pin)):
        return None
    tr = st.get("trial") if isinstance(st.get("trial"), dict) else {}
    if tr.get("tag") != tag:
        return None
    verdict = VERDICTS.get(tr.get("verdict"))
    if verdict is None:
        return None
    return {"kind": KIND, "key": tag,
            "tokens": {"VTAG": vtag(tag), "tag": tag, "pin": pin, "verdict": verdict}}


def check(state, now, fetch, ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    root = _root(ctx)
    if root is None:
        return []
    halted = halted_now(root, ctx)
    seam = _seam(ctx)
    if seam is not None:
        if _takes_halted(seam):
            seam(root, now, halted=halted)
        elif not halted:
            seam(root, now)
    if halted:
        return []
    rec = finding(tc_drift.load_state(root))
    return [rec] if rec else []


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": 0,  # every tick; tc_drift keeps its own 24 h gate
    "window": None,
    "needs_web_data": False,  # settled read, decision 0025
    "hosts": [],
    "urls": [],
    "purpose": tc_drift.UA_PURPOSE,
    "check": check,
}
