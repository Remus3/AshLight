"""AUTO-09 (ELECTRON-WATCH, F-130; W8 of docs/plan/06; decisions 0069, 0070):
the Electron release watcher.

What it reads: the two public JSON files research 0046 R1 names, 2 requests
per run, purpose 'electron watch', only while web_data is on (the frame
never calls a gated source otherwise; strict reading: the operator may
exempt this source in writing, until then it waits like every other):
- S9, the npm registry dist-tags of the electron package (DIST_TAGS_URL):
  {"latest": "46.0.1", "45-x-y": "45.3.4", ...};
- S2, the Electron release schedule (SCHEDULE_URL): a list of
  {"version": "46.0.0", "stableDate": "YYYY-MM-DD", "endOfLife": ...}.
From the tree (ctx["root"], or this checkout only when ctx["live"] is true;
with neither the source reads nothing and makes no request): the pin, the
electron entry of app/package.json (an exact X.Y.Z), and the end-of-life
date `eol` of config/electron_pin.json (F-044) when its version is on the
pinned line; without it the end-of-life rule is idle.

Rules (decision 0070, the written upgrade policy):
- Bump (kind "electronbump", row ELECTRON-<MAJ>-<MIN>-<PAT>, key the
  version): the newest release of the pinned line (the dist-tag
  "<MAJ>-x-y", or "latest" when that is on the line) that is newer than
  the pin and at least BUMP_AGE_S (3 days) old, at most one per
  BUMP_GAP_S (7 days). A release's age counts from the first run that saw
  it as a line head (state["data"]["heads"]): the dist-tags carry no date,
  and a first-seen age is never younger than the real one is old, so the
  3-day wait is kept or exceeded, never cut short.
- Major (kind "electronmajor", row ELECTRON-MAJOR-<MAJ>, key
  "major-<MAJ>", so once per major for all time by the frame's seen list):
  for MAJ = pinned major + 1 (one major at a time), at the earlier of
  (a) the schedule's stableDate of MAJ is at least MAJOR_AGE_D (14) days
      past and the registry already carries a MAJ.x.y release, or
  (b) today is within EOL_LEAD_D (30) days of the pinned line's eol.
A HALTed tick runs the same check: the frame queues the findings and
tools/watch_file.py files nothing while HALT exists (ruling Q-13).

Findings only; row text comes from ops/loop/watch_rows/electron.json.
Python stdlib only; no subprocess, no runtime file.
"""

import datetime as _dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

NAME = "electron"
KIND_BUMP = "electronbump"
KIND_MAJOR = "electronmajor"
DIST_TAGS_URL = "https://registry.npmjs.org/-/package/electron/dist-tags"
SCHEDULE_URL = "https://releases.electronjs.org/schedule.json"
PACKAGE_REL = Path("app") / "package.json"
PIN_REL = Path("config") / "electron_pin.json"

DAY_S = 24 * 3600
BUMP_AGE_S = 3 * DAY_S
BUMP_GAP_S = 7 * DAY_S
MAJOR_AGE_D = 14
EOL_LEAD_D = 30
HEADS_MAX = 20

VERSION_RX = re.compile(r"([0-9]{1,3})\.([0-9]{1,4})\.([0-9]{1,4})")
DATE_RX = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _uw():
    import upstream_watch  # the frame; on sys.path whenever a source runs
    return upstream_watch


def _shape(text):
    return _uw().SourceError("shape", text)


def vtuple(text):
    """(major, minor, patch) of an exact X.Y.Z string, else None."""
    m = VERSION_RX.fullmatch(text) if isinstance(text, str) else None
    return tuple(int(p) for p in m.groups()) if m else None


def _date(text):
    if not (isinstance(text, str) and DATE_RX.fullmatch(text)):
        return None
    try:
        return _dt.date.fromisoformat(text)
    except ValueError:
        return None


def _root(ctx):
    if ctx.get("root") is not None:
        return Path(ctx["root"])
    return ROOT if ctx.get("live") else None


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def pin_of(root):
    """The exact electron version app/package.json pins, or None (no file)."""
    doc = _read_json(Path(root) / PACKAGE_REL)
    if not isinstance(doc, dict):
        return None
    for section in ("dependencies", "devDependencies"):
        deps = doc.get(section)
        if isinstance(deps, dict) and "electron" in deps:
            ver = deps["electron"]
            if vtuple(ver) is None:
                raise _shape("the electron pin in app/package.json is not an exact X.Y.Z")
            return ver
    return None


def eol_of(root, pin):
    """The pinned line's end-of-life date from config/electron_pin.json, or
    None (no file, no date, or the file is for another line)."""
    doc = _read_json(Path(root) / PIN_REL)
    if not isinstance(doc, dict):
        return None
    ver = vtuple(doc.get("version"))
    if ver is None or ver[0] != vtuple(pin)[0]:
        return None
    return _date(doc.get("eol"))


def _get(fetch, url):
    uw = _uw()
    status, _headers, body = fetch(url)
    if status != 200:
        raise uw.SourceError("status", f"HTTP {status}")
    try:
        return json.loads((body or b"").decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise uw.SourceError("shape", "response is not JSON") from None


def line_head(tags, major):
    """The newest exact X.Y.Z on `major` the dist-tags name, or None."""
    best = None
    for key, ver in tags.items():
        if not isinstance(key, str) or key not in (f"{major}-x-y", "latest"):
            continue
        vt = vtuple(ver)
        if vt and vt[0] == major and (best is None or vt > vtuple(best)):
            best = ver
    return best


def newest_major(tags):
    majors = [vtuple(v)[0] for v in tags.values() if vtuple(v)]
    return max(majors) if majors else None


def schedule_row(schedule, major):
    """The schedule entry of `major` ({"version": "<major>.0.0", ...}), or None."""
    for item in schedule:
        if isinstance(item, dict):
            vt = vtuple(item.get("version"))
            if vt and vt[0] == major:
                return item
    return None


def bump_finding(data, now, pin, head):
    """Record `head` as seen and return the bump finding when due, or None.
    `data` is updated in place (heads, last_bump_at, last_bump)."""
    heads = data.get("heads") if isinstance(data.get("heads"), dict) else {}
    pt = vtuple(pin)
    heads = {v: t for v, t in heads.items()
             if vtuple(v) and vtuple(v) > pt and isinstance(t, (int, float))}
    if head and vtuple(head) > pt and head not in heads:
        heads[head] = float(now)
    if len(heads) > HEADS_MAX:
        keep = sorted(heads, key=vtuple)[-HEADS_MAX:]
        heads = {v: heads[v] for v in keep}
    data["heads"] = heads
    ripe = [v for v, t in heads.items() if now - t >= BUMP_AGE_S]
    if not ripe:
        return None
    last = data.get("last_bump_at")
    if isinstance(last, (int, float)) and now - last < BUMP_GAP_S:
        return None
    ver = max(ripe, key=vtuple)
    if data.get("last_bump") == ver:
        return None
    data["last_bump_at"] = float(now)
    data["last_bump"] = ver
    maj, mnr, pat = vtuple(ver)
    return {"kind": KIND_BUMP, "key": ver,
            "tokens": {"MAJ": str(maj), "MIN": str(mnr), "PAT": str(pat),
                       "version": ver, "pin": pin}}


def major_finding(today, pin, eol, tags, schedule):
    """The major finding for pinned major + 1 when either rule holds, else None."""
    pin_major = vtuple(pin)[0]
    nxt = pin_major + 1
    due = None
    row = schedule_row(schedule, nxt)
    stable = _date(row.get("stableDate")) if row else None
    newest = newest_major(tags)
    if stable and newest is not None and newest >= nxt \
            and (today - stable).days >= MAJOR_AGE_D:
        due = "release"
    if eol is not None and (eol - today).days <= EOL_LEAD_D:
        due = due or "eol"
    if due is None:
        return None
    shown = eol
    if shown is None:
        own = schedule_row(schedule, pin_major)
        shown = _date(own.get("endOfLife")) if own else None
    return {"kind": KIND_MAJOR, "key": f"major-{nxt}",
            "tokens": {"MAJ": str(nxt), "PINMAJ": str(pin_major),
                       "eol": shown.isoformat() if shown else "unknown"}}


def check(state, now, fetch, ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    root = _root(ctx)
    if root is None:
        return []
    pin = pin_of(root)
    if pin is None:
        return []
    eol = eol_of(root, pin)
    tags = _get(fetch, DIST_TAGS_URL)
    if not isinstance(tags, dict):
        raise _shape("dist-tags must be an object")
    schedule = _get(fetch, SCHEDULE_URL)
    if not isinstance(schedule, list):
        raise _shape("the release schedule must be a list")
    data = dict(state.get("data")) if isinstance(state.get("data"), dict) else {}
    today = _dt.datetime.fromtimestamp(now).date()
    head = line_head(tags, vtuple(pin)[0])
    found = []
    bump = bump_finding(data, now, pin, head)
    if bump:
        found.append(bump)
    major = major_finding(today, pin, eol, tags, schedule)
    if major:
        found.append(major)
    data.update(pin=pin, head=head, newest_major=newest_major(tags),
                eol=eol.isoformat() if eol else None)
    state["data"] = data
    return found


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": DAY_S,
    "window": None,
    "needs_web_data": True,
    "hosts": [],
    "urls": [DIST_TAGS_URL, SCHEDULE_URL],
    "purpose": "electron watch",
    "check": check,
}
