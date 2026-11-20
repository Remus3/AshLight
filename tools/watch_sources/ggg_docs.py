"""LOOP-WATCH-SETTLED (F-030, AUTO-05, CARRY-01): the GGG developer docs
watch (decision 0044) as a registry source. Docs: docs/plan/06 W1.

The read itself is unchanged: tools/ggg_docs_watch.py keeps its six-page
read, its 24 h throttle, its state files and its User-Agent purpose. This
source only triggers that read through the tick's seam and turns what the
read left behind into findings; it never uses the frame's fetch (GGG hosts
are refused there anyway, LOOP-WATCH-GATE).

check(state, now, fetch, ctx):
- ctx["root"]: the tree the tick runs on (default: this checkout, and only
  when ctx["live"] is true; with neither the source reads nothing).
- ctx["docs_watch"](root, now): the tick's docs read (al_loop Deps
  docs_watch). When the key is absent ggg_docs_watch.safe_check is called,
  only when ctx["live"] is true, so a scratch-root test stays hermetic.
- ctx["docs_cache"]: the docs watch state folder (default: its sidecar
  Cache folder, read only when ctx["live"] is true).

Findings:
- kind "regopen" (row TC-OAUTH-REG-OPEN): the flag
  ops/runtime/ggg_docs/REG_OPEN exists under the root. The flag comes from
  the index page, a read under operator decision A-01, so this kind is
  built behind the A-01 constant of AUTO-11 (ggg_docs_watch.SHAPE_ALL_PAGES,
  off): while it is off no regopen finding is made and the hand-off's
  session-start check stays the only reader of the flag.
- kind "gggshape" (row GGG-SHAPE-<YYYYMMDD>): the docs watch state's
  last_shape record (AUTO-11) names the reference or data page. One finding
  per record: the page with the most changed field names (reference on a
  tie), n = that page's count capped at 99.

Kind names carry no separator: tools/watch_rows.py kind names refuse "_"
and tools/upstream_watch.py finding kinds refuse "-" (ruling recorded with
this package).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ggg_docs_watch  # noqa: E402

NAME = "ggg-docs"
KIND_REG = "regopen"
KIND_SHAPE = "gggshape"
REG_KEY = "TC-OAUTH-REG-OPEN"
PAGES = ("reference", "data")  # the template's <page> values
N_MAX = 99


def _root(ctx):
    if ctx.get("root") is not None:
        return Path(ctx["root"])
    return ROOT if ctx.get("live") else None


def _seam(ctx):
    if "docs_watch" in ctx:
        return ctx["docs_watch"]
    return ggg_docs_watch.safe_check if ctx.get("live") else None


def _cache(ctx):
    if ctx.get("docs_cache") is not None:
        return Path(ctx["docs_cache"])
    return ggg_docs_watch.cache_dir() if ctx.get("live") else None


def a01_on():
    """The A-01 constant of AUTO-11, read at call time (off by default)."""
    return getattr(ggg_docs_watch, "SHAPE_ALL_PAGES", False) is True


def reg_open_findings(root):
    if root is None or not a01_on():
        return []
    flag = ggg_docs_watch.runtime_dir(root) / ggg_docs_watch.FLAG_NAME
    if not flag.is_file():
        return []
    return [{"kind": KIND_REG, "key": REG_KEY, "tokens": {}}]


def shape_findings(docs_state):
    """At most one gggshape finding from the docs watch state's last_shape."""
    rec = (docs_state or {}).get("last_shape")
    if not isinstance(rec, dict):
        return []
    at = rec.get("at")
    if not isinstance(at, str) or not at.isascii() or not at.strip() or len(at) > 64:
        return []
    best = None
    for item in rec.get("pages") or []:
        if not isinstance(item, dict) or item.get("page") not in PAGES:
            continue
        count = item.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            continue
        rank = (count, -PAGES.index(item["page"]))
        if best is None or rank > best[0]:
            best = (rank, item["page"], count)
    if best is None:
        return []
    _rank, page, count = best
    return [{"kind": KIND_SHAPE, "key": f"shape {at.strip()}",
             "tokens": {"page": page, "n": str(min(count, N_MAX))}}]


def check(state, now, fetch, ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    root = _root(ctx)
    seam = _seam(ctx)
    if seam is not None and root is not None:
        seam(root, now)  # the settled read; its own 24 h throttle decides
    found = reg_open_findings(root)
    cache = _cache(ctx)
    if cache is not None:
        found += shape_findings(ggg_docs_watch.load_state(cache))
    return found


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": 0,  # every tick; the docs watch keeps its own 24 h gate
    "window": None,
    "needs_web_data": False,  # settled read, decision 0044
    "hosts": [],
    "urls": [],
    "purpose": ggg_docs_watch.UA_PURPOSE,
    "check": check,
}
