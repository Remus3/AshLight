"""AUTO-17 (W12 of docs/plan/06, REFRESH-SOURCE; decision 0069): stale docs,
a stale screenshot manifest and an unplanned release become rows.

A local source: it makes no request (hosts and urls are empty, so the
frame's fetch refuses every URL). It runs at most once a local day and reads
the tree only, through three tools of the tree run as subprocesses:

- `python tools/docs_fresh.py stale --today <date>` (AUTO-14): exit 1 with
  one line per dated PENDING / UNVERIFIED marker older than 30 days;
- `python tools/shots.py check` (AUTO-15): exit 0 fresh, 1 stale;
- `python tools/release.py notes --count` (AUTO-16): one line
  '<n> <YYYY-MM-DD>', the rows merged since the last tag (or the root) and
  the date of the oldest of them;
plus ops/loop/control/wave_owned.json (LOOP-WAVE-HOLD, read through
tools/loop_merge.read_wave_hold) and ROADMAP.md with the row files
(tools/roadmap.py load_rows). A tool file that is absent, a runner that
gives nothing, or output of another shape makes that kind idle for the day,
never a failure.

Root: ctx["root"]; else this checkout, only when ctx["live"] is true; with
neither the source reads nothing and finds nothing (hermetic loop tests).
Runner: ctx["refresh_runner"](root, argv) -> (exit code, stdout) or None
when given (tests); else a below-normal, windowless subprocess that starts
only when ctx["live"] is true.

Findings (templates in ops/loop/watch_rows/refresh.json; each kind queued at
most once per 7 days, state["data"]["filed"][kind] = the local date):
- docsfresh (row DOCS-FRESH-<YYYYMMDD>, lane data): docs_fresh stale lists
  N >= 1 markers. Key "docs:<YYYYMMDD>", token N (capped at 9999).
- shots (row SHOTS-<YYYYMMDD>, lane data): shots check has said stale on
  every daily run since a date at least 3 days ago (data["shots_since"],
  cleared by a fresh answer) and no live (non-stale) wave hold holds web/.
  Key "shots:<YYYYMMDD>", token SINCE (the first stale date).
- reldue (row REL-DUE-<YYYYMMDD>, lane review, BLOCKED: session): at least
  10 rows merged and the oldest of them at least 30 days old (so at least 30
  days since the last tag), and no REL-PREP- or REL-DUE- row open. Key
  "notes:<YYYYMMDD>", tokens N (capped at 9999) and D (days, capped at 999).
  It never bumps, stages, tags or pushes.
The frame queues a key once for all time; filing (and the HALT check before
any commit) is tools/watch_file.py's job.
"""

import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

KIND_DOCS = "docsfresh"
KIND_SHOTS = "shots"
KIND_REL = "reldue"
KINDS = (KIND_DOCS, KIND_SHOTS, KIND_REL)
KEY_PREFIX = {KIND_DOCS: "docs", KIND_SHOTS: "shots", KIND_REL: "notes"}

DOCS_TOOL = Path("tools/docs_fresh.py")
SHOTS_TOOL = Path("tools/shots.py")
NOTES_TOOL = Path("tools/release.py")

REFILE_DAYS = 7          # each kind queued at most once per 7 days
SHOTS_STALE_DAYS = 3     # stale manifest for this many days before a row
REL_MIN_ROWS = 10
REL_MIN_DAYS = 30
N_MAX = 9999
D_MAX = 999
OUT_MAX = 256 * 1024
RUNNER_TIMEOUT_S = 120
WEB_PREFIX = "web"
RELEASE_ROW_PREFIXES = ("REL-PREP-", "REL-DUE-")

_COUNT_RX = re.compile(r"^(\d{1,6})(?:\s+(\d{4}-\d{2}-\d{2}))?$")


def _root(ctx):
    root = ctx.get("root")
    if root:
        return Path(root)
    return ROOT if ctx.get("live") else None


def default_runner(root, argv):
    """(exit code, stdout) of `python <argv>` in root (below normal
    priority, no window, 120 s), or None when it could not run."""
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run([sys.executable, *argv], cwd=str(root), capture_output=True,
                           text=True, timeout=RUNNER_TIMEOUT_S, creationflags=flags,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return r.returncode, r.stdout


def _runner(ctx):
    runner = ctx.get("refresh_runner")
    if runner is not None:
        return runner
    return default_runner if ctx.get("live") else None


def _run(root, runner, tool, args):
    """(exit code, stdout text) of one tool, or None (tool absent, runner
    absent or broken, output not text)."""
    if runner is None or not (Path(root) / tool).is_file():
        return None
    try:
        got = runner(Path(root), [tool.as_posix(), *args])
    except Exception:  # noqa: BLE001 - a broken tool only idles its kind
        return None
    if not isinstance(got, (tuple, list)) or len(got) != 2:
        return None
    rc, out = got
    if isinstance(rc, bool) or not isinstance(rc, int):
        return None
    if not isinstance(out, str) or len(out) > OUT_MAX:
        return None
    return rc, out


# ---------------------------------------------------------------- readers

def stale_markers(root, runner, today):
    """The number of stale dated markers, 0 for none, None when unknown."""
    got = _run(root, runner, DOCS_TOOL, ["stale", "--today", today.isoformat()])
    if got is None:
        return None
    rc, out = got
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if rc == 0 and not lines:
        return 0
    if rc == 1 and lines:
        return len(lines)
    return None


def shots_stale(root, runner):
    """True stale, False fresh, None unknown."""
    got = _run(root, runner, SHOTS_TOOL, ["check"])
    if got is None:
        return None
    return {0: False, 1: True}.get(got[0])


def merged_count(root, runner):
    """(rows merged since the last tag, date of the oldest or None), or None."""
    got = _run(root, runner, NOTES_TOOL, ["notes", "--count"])
    if got is None or got[0] != 0:
        return None
    lines = [ln.strip() for ln in got[1].splitlines() if ln.strip()]
    if len(lines) != 1:
        return None
    m = _COUNT_RX.match(lines[0])
    if not m:
        return None
    oldest = None
    if m.group(2):
        try:
            oldest = _dt.date.fromisoformat(m.group(2))
        except ValueError:
            return None
    return int(m.group(1)), oldest


def web_held(root, now):
    """True when a live (non-stale) wave hold file holds web/ or a folder
    above or below it; a stale or absent hold holds nothing."""
    try:
        import loop_merge
        hold = loop_merge.read_wave_hold(Path(root), now)
    except Exception:  # noqa: BLE001 - an unreadable hold file is reported elsewhere
        return False
    if not hold or hold.get("stale"):
        return False
    for p in hold.get("prefixes") or ():
        if p == WEB_PREFIX or p.startswith(WEB_PREFIX + "/"):
            return True
    return False


def release_row_open(root):
    """True when a REL-PREP- or REL-DUE- row is open; an unreadable roadmap
    reads as open (no row is filed on a guess)."""
    try:
        import roadmap
        rows = roadmap.load_rows(Path(root))
    except Exception:  # noqa: BLE001
        return True
    return any(r["open"] and str(r["id"]).startswith(RELEASE_ROW_PREFIXES) for r in rows)


# ---------------------------------------------------------------- check

def _date(text):
    try:
        return _dt.date.fromisoformat(text) if isinstance(text, str) else None
    except ValueError:
        return None


def _may_file(filed, kind, today):
    last = _date(filed.get(kind))
    return last is None or (today - last).days >= REFILE_DAYS


def check(state, now, fetch, ctx):
    ctx = ctx or {}
    root = _root(ctx)
    if root is None:
        return []
    data = dict(state.get("data") or {})
    today = _dt.datetime.fromtimestamp(now).date()
    if data.get("day") == today.isoformat():
        return []
    data["day"] = today.isoformat()
    stamp = today.strftime("%Y%m%d")
    filed = {k: v for k, v in dict(data.get("filed") or {}).items() if k in KINDS}
    runner = _runner(ctx)
    found = []

    def emit(kind, tokens):
        found.append({"kind": kind, "key": f"{KEY_PREFIX[kind]}:{stamp}", "tokens": tokens})
        filed[kind] = today.isoformat()

    n = stale_markers(root, runner, today)
    if n and _may_file(filed, KIND_DOCS, today):
        emit(KIND_DOCS, {"N": str(min(n, N_MAX))})

    stale = shots_stale(root, runner)
    if stale is False:
        data.pop("shots_since", None)
    elif stale is True:
        since = _date(data.get("shots_since"))
        if since is None or since > today:
            since = today
            data["shots_since"] = today.isoformat()
        if ((today - since).days >= SHOTS_STALE_DAYS
                and _may_file(filed, KIND_SHOTS, today) and not web_held(root, now)):
            emit(KIND_SHOTS, {"SINCE": since.isoformat()})

    if _may_file(filed, KIND_REL, today):
        got = merged_count(root, runner)
        if got is not None and got[0] >= REL_MIN_ROWS and got[1] is not None:
            days = (today - got[1]).days
            if days >= REL_MIN_DAYS and not release_row_open(root):
                emit(KIND_REL, {"N": str(min(got[0], N_MAX)), "D": str(min(days, D_MAX))})

    data["filed"] = filed
    state["data"] = data
    return found


SOURCE = {
    "name": "refresh",
    "home": "loop",
    "cadence_s": 0,
    "window": None,
    "needs_web_data": True,
    "hosts": [],
    "urls": [],
    "purpose": "dev: watcher refresh",
    "check": check,
}
