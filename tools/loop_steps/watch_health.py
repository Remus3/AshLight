"""AUTO-08 (WATCH-HEALTH, F-125; decision 0069): the watcher health step of
the loop tick (tools/loop_steps seam, AUTO-01).

pre_halt(tick): after loop_steps/upstream_watch.py (file-name order), even
  HALTed, never on a dry run. A source whose record in
  ops/runtime/watch/state.json reads FAILS_LINE (3) or more failures in a
  row gives ONE tick line per broken streak:
  `watch health: <name> failed <n> times in a row (<cause>); last good read <when>`.
  The streak is keyed by the record's last_ok; the noted streaks live in
  ops/runtime/watch/health.json {noted: {<name>: <last_ok or 'never'>}},
  written only on change; a good read (fails 0) clears the note. A source
  idle because web data is off is never a failure.
checklist(tick) -> kit rows (tick.d.checklist.item), appended by the seam to
  a running tick's checklist and to a HALTed tick's empty one:
  - one row per queued finding of ops/runtime/watch/pending.json: the id
    the finding's template renders (ops/loop/watch_rows, tokens and the
    tick's date) when it fits a checklist id, else watch-<source>-<n>;
    state 'queued', or 'queued, HALT' while HALTed (nothing is filed);
  - one row 'watch-idle' naming every source idle because web data is off,
    shown only when the tree has a config/local.json (the host made its
    web-data choice; a bare scratch root shows none).

Every read is under tick.root; the step makes no request and starts no
process. This module never imports al_loop. Python stdlib only.
"""

import datetime as _dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import loop_base  # noqa: E402
import upstream_watch as watch  # noqa: E402  tools/upstream_watch.py (the frame)
import watch_rows  # noqa: E402

FAILS_LINE = 3
NOTES_REL = watch.WATCH_REL / "health.json"
CONFIG_REL = Path("config/local.json")
IDLE_ID = "watch-idle"
CHECK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,47}$")
PLACEHOLDER = re.compile(r"<([^<>\s]+)>")
TASK_MAX = 70


def _notes(root):
    doc = loop_base.read_json(Path(root) / NOTES_REL, None)
    noted = doc.get("noted") if isinstance(doc, dict) else None
    if not isinstance(noted, dict):
        return {}
    return {k: v for k, v in noted.items() if isinstance(k, str) and isinstance(v, str)}


def failing(root):
    """[(name, record)] of the sources with FAILS_LINE or more failures in a
    row and not idle for web data, in name order."""
    out = []
    for name, rec in sorted(watch.load_state(root)["sources"].items()):
        if rec.get("idle") == watch.IDLE_OFF:
            continue
        if int(rec.get("fails") or 0) >= FAILS_LINE:
            out.append((name, rec))
    return out


def health_lines(root):
    """The three-in-a-row tick lines, once per broken streak."""
    root = Path(root)
    noted = _notes(root)
    before = dict(noted)
    recs = watch.load_state(root)["sources"]
    for name in list(noted):
        rec = recs.get(name)
        if not rec or not rec.get("fails") or rec.get("idle") == watch.IDLE_OFF:
            noted.pop(name)
    lines = []
    for name, rec in failing(root):
        streak = rec.get("last_ok") or "never"
        if noted.get(name) == streak:
            continue
        noted[name] = streak
        lines.append(loop_base.ascii_text(
            f"watch health: {name} failed {int(rec['fails'])} times in a row "
            f"({rec.get('cause') or 'network'}); last good read {streak}", watch.LINE_MAX))
    if noted != before:
        loop_base.atomic_write(root / NOTES_REL,
                               json.dumps({"noted": noted}, indent=1, sort_keys=True) + "\n")
    return lines


def pre_halt(tick):
    return health_lines(tick.root)


# ---------------------------------------------------------------- checklist

def _table(root):
    try:
        return watch_rows.load(root)
    except (watch_rows.WatchRowsError, OSError):
        return {}


def finding_id(table, finding, day):
    """The row id the finding's template renders, or None."""
    kdef = table.get(finding.get("kind"))
    idp = kdef.get("id") if isinstance(kdef, dict) else None
    if not isinstance(idp, str):
        return None
    tokens = finding.get("tokens") if isinstance(finding.get("tokens"), dict) else {}
    values = {k: v for k, v in tokens.items() if isinstance(v, str)}
    values.update({"YYYY-MM-DD": day.isoformat(), "YYYYMMDD": day.strftime("%Y%m%d")})
    try:
        out = PLACEHOLDER.sub(lambda m: values[m.group(1)], idp)
    except KeyError:
        return None
    return out if CHECK_ID.match(out) else None


def idle_sources(root):
    return sorted(n for n, rec in watch.load_state(root)["sources"].items()
                  if rec.get("idle") == watch.IDLE_OFF)


def checklist(tick):
    root = Path(tick.root)
    kit = tick.d.checklist
    day = _dt.datetime.fromtimestamp(tick.d.clock()).date()
    halted = bool(getattr(tick, "halted", False))
    found = watch.pending(root)
    table = _table(root) if found else {}
    rows, ids = [], set()
    for n, f in enumerate(found, 1):
        source = str(f.get("source") or "watch")
        iid = finding_id(table, f, day)
        if iid is None or iid in ids:
            iid = f"watch-{re.sub(r'[^A-Za-z0-9._-]', '-', source)[:30]}-{n}"
        ids.add(iid)
        act = (table.get(f.get("kind")) or {}).get("act")
        verb = {"row": "File row", "gate": "Mark done"}.get(act, "Act on finding")
        task = loop_base.ascii_text(f"{verb} {iid} from watch {source}", TASK_MAX)
        rows.append(kit.item(iid, task, "queued, HALT" if halted else "queued", None))
    idle = idle_sources(root) if (root / CONFIG_REL).is_file() else []
    if idle:
        task = "Watchers idle, web data off: " + ", ".join(idle)  # the kit clips
        rows.append(kit.item(IDLE_ID, task, None, None))
    return rows
