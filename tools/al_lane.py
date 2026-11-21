#!/usr/bin/env python3
"""AL laned headless driver (operator standing order 10, fleet kit v8).

    al_lane.py status
    al_lane.py run <lane> --prompt-file F [--writes-code] [--timeout S] [--dry-run]
               [--item "ID: task" ...] [--checklist-file F.json]

Roster lanes: build, data, review. Up to lane_cap() run at once (kit v25:
the live machine config `fleet_lanes.load_config()`, default 3). Each run goes
through the kit's `fleet_lanes.run_lane` (repo lane lock + its OWN clean git
worktree from the kit `fleet_lanes.worktree_path`: `<sidecar>/AL/Worktree/lane-<i>`
when the AL sidecar exists, else `<repo parent>/al-worktrees/lane-<i>`, detached
at main's HEAD) and
spawns through `fleet_headless.spawn` ONLY (account B proxy, fail closed - FLEET
item 10) with exactly ONE governor slot taken AT the call (`governor="queued"`).
No slot is held around git. Every run writes a progress file (FLEET item 12)
and records its duration in the ETA log (`tools/eta.py`).

SIDECAR (operator order 2026-11-16): the kit's child_env(code="AL") sets
CLAUDE_CODE_TMPDIR to <sidecar>/AL/Temp/claude; run_lane also points TEMP / TMP
of the spawned run at <sidecar>/AL/Temp (sidecar_temp_env). The sidecar root is
env AL_SIDECAR_ROOT (the AL folder itself) or the kit's
fleet_lanes.sidecar_dir("AL", ...); no sidecar = the parent's TEMP is kept.

Lanes never commit. After a code run the main session commits in the printed
worktree (detached HEAD) and merges that commit into main with --no-ff. A lane
worktree left dirty is refused by the kit on the next claim (never cleaned), so
commit or hand-resolve it first. Gitignored config the gates need
(config/leak_needles.json, config/local.json) is copied into the worktree when
missing. The prompt file is read, never echoed to chat.
"""

import argparse
import contextlib
import importlib.util
import json
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANES = ("build", "data", "review")
CODE = "AL"
SEED_CONFIG = ("config/leak_needles.json", "config/local.json")
# AUTO-18: the masked LIVE-1 report the ledger watch source writes; a LOG-SHAPE
# row's lane reads it. Unlike the config seeds, an older copy is overwritten.
SEED_FRESH = ("ops/runtime/watch/live1_report.json",)
# Headless -p has no prompt to approve edits; code lanes run in acceptEdits so
# file edits land in the lane worktree. Bash stays on the project allow list
# plus the gate commands below; commits and merges are done by the main session.
GATE_TOOLS = ("Bash(python -m pytest:*),Bash(npm test:*),Bash(node --test:*),"
              "Bash(python tools/leak_sweep.py:*),Bash(python tools/shots.py:*)")
# A dependency-bump item needs npm and git add of a regenerated lockfile.
# Dependabot bumps are re-applied in the main checkout by
# tools/dependabot_reapply.py, so no gh is granted to a lane.
DEP_TOOLS = ("Bash(npm install:*),Bash(npm ci:*),Bash(npm ls:*),Bash(npm view:*),"
             "Bash(npm outdated:*),Bash(npm audit:*),"
             "Bash(git add:*),Bash(git status:*),Bash(git diff:*)")
CODE_EXTRA = ("--permission-mode", "acceptEdits", "--allowedTools",
              GATE_TOOLS + "," + DEP_TOOLS)
sys.path.insert(0, str(ROOT / "tools"))
import eta  # noqa: E402

# lane_samples is imported at call time (run_lane), never here: lane_samples ->
# loop_base -> al_lane -> lane_samples is a cycle that crashed
# `python tools/lane_samples.py status` (row 171, plan 172 smoke test).


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


def kit():
    return _load("fleet_headless", "ops/fleet_kit/fleet_headless.py")


def lanes():
    return _load("fleet_lanes", "ops/fleet_kit/fleet_lanes.py")


def lane_cap():
    """Kit v25 LANE-CAP: the live per-tree lane cap, the machine config's
    lane_cap_max clamped to its governor_width (no config: 3). Re-read on
    every call; AL keeps no hard-coded cap (ADR 0007: no reason for less)."""
    return lanes().lane_cap(None)


def slot_count():
    """Kit v25: the machine-wide governor slot count AL's spawns queue for
    (live governor_width; no config: 3). spawn(governor="queued") takes its
    slot with cap=None, so AL borrows idle slots up to lane_cap()."""
    return int(lanes().load_config()["governor_width"])


def should_yield():
    """Kit v25 FAIR RELEASE, read only: True = do not start the next lane
    cycle (another tree waits, no slot free, AL above its fair share). The
    caller only declines to start work; it never stops a running worker.
    An unreadable governor reads False (the kit's own slot wait still bounds)."""
    try:
        return bool(lanes().should_yield(CODE))
    except Exception:  # noqa: BLE001 - advisory only
        return False


SIDECAR_ENV = "AL_SIDECAR_ROOT"  # the AL sidecar folder itself (tests, overrides)


def sidecar_root(environ=None):
    """The AL sidecar folder: env AL_SIDECAR_ROOT when set (an empty value =
    off), else the kit's <sidecar root>/AL when that folder exists, else None.
    Never spelled here: the kit builds its default from parts."""
    env = os.environ if environ is None else environ
    if SIDECAR_ENV in env:
        v = (env.get(SIDECAR_ENV) or "").strip().strip('"')
        return Path(v) if v and Path(v).is_absolute() else None
    try:
        d = lanes().sidecar_dir(CODE, "Temp")
    except Exception:  # noqa: BLE001 - a sidecar problem never blocks a run
        return None
    return d.parent if d is not None else None


def sidecar_temp(environ=None):
    """<AL sidecar>/Temp (created), or None without a sidecar."""
    root = sidecar_root(environ)
    if root is None or not root.is_dir():
        return None
    tmp = root / "Temp"
    try:
        tmp.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return tmp


@contextlib.contextmanager
def sidecar_temp_env(environ=None, temp=None):
    """TEMP / TMP point at the AL sidecar Temp folder for the duration (the
    kit child_env copies os.environ into the spawned run); restored after.
    No sidecar: nothing changes."""
    env = os.environ if environ is None else environ
    tmp = sidecar_temp(env) if temp is None else temp
    if tmp is None:
        yield None
        return
    saved = {k: env.get(k) for k in ("TEMP", "TMP")}
    env["TEMP"] = env["TMP"] = str(tmp)
    try:
        yield tmp
    finally:
        for k, v in saved.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v


def check_lane(lane):
    if lane not in LANES:
        raise SystemExit(f"unknown lane {lane!r}; lanes: {', '.join(LANES)}")
    return lane


def _stale(src, dst):
    """True when dst is missing or differs from src in size or mtime."""
    try:
        a = src.stat()
    except OSError:
        return False
    try:
        b = dst.stat()
    except OSError:
        return True
    return a.st_size != b.st_size or a.st_mtime_ns != b.st_mtime_ns


def seed_config(worktree, root=ROOT):
    """Copy gitignored gate config into a lane worktree when missing, and the
    fresh report seeds (SEED_FRESH) whenever the worktree copy is older or
    differs (copied with its mtime, so a repeat call is a no-op). Idempotent."""
    copied = []
    for rel in SEED_CONFIG:
        src, dst = Path(root) / rel, Path(worktree) / rel
        if src.is_file() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            copied.append(rel)
    for rel in SEED_FRESH:
        src, dst = Path(root) / rel, Path(worktree) / rel
        if src.is_file() and _stale(src, dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)
    return copied


def progress_task(index):
    """FLEET item 13 d: a lane's progress file is progress/lane-<i>.json, i = its
    lane-lock index (kit `fleet_checklist.lane_task`), so the widget reads one
    named file per live lane. The lane name rides in the step text."""
    return _load("fleet_checklist", "ops/fleet_kit/fleet_checklist.py").lane_task(index)


# LANE-CHECKLIST: lane ETA floors (s). Measured lane runs took 400-450 s of
# model time plus claim / gate / governor overhead, so a history median alone
# under-reads; a code lane never estimates below 15 min.
ETA_FLOOR_S = {"code": 900.0, "read": 300.0}
HEARTBEAT_S = 90.0      # progress rewrite cadence while the run lasts (60-120 s)
PCT_START, PCT_CAP = 5, 95  # running pct band: elapsed / eta, never 100 until done
REMAIN_MIN_S = 300      # eta_s written never drops below this while running
_CHECK_ID = re.compile(r"[^A-Za-z0-9._-]+")


def lane_eta(writes_code, kind, eta_kind=None):
    """The progress ETA (s): the recorded history median of the item kind
    (else the lane kind), never below the lane floor."""
    base = eta.estimate(eta_kind, default=eta.estimate(kind)) if eta_kind \
        else eta.estimate(kind)
    return max(float(base), ETA_FLOOR_S["code" if writes_code else "read"])


def running_pct(elapsed, eta_s):
    """pct from elapsed / eta, in [PCT_START, PCT_CAP]."""
    if eta_s <= 0:
        return PCT_CAP
    return int(max(PCT_START, min(PCT_CAP, 100.0 * max(elapsed, 0.0) / eta_s)))


def remaining_s(elapsed, eta_s):
    return int(max(REMAIN_MIN_S, eta_s - max(elapsed, 0.0)))


def norm_checklist(rows):
    """FLEET item 13 d rows [{id, task, state, eta_s}] (remaining tasks only),
    checked here so a bad row fails before the lane is claimed. Ids keep the
    kit's charset (others become '-'), at most 48 chars."""
    if rows is None:
        return None
    if not isinstance(rows, (list, tuple)):
        raise ValueError("checklist must be a list of {id, task, state, eta_s}")
    out = []
    for r in rows:
        if not isinstance(r, dict):
            raise ValueError(f"bad checklist row {r!r}")
        rid = _CHECK_ID.sub("-", str(r.get("id") or "")).strip("-._")[:48]
        task = " ".join(str(r.get("task") or "").split())
        if not rid or not task:
            raise ValueError(f"bad checklist row {r!r}")
        state = r.get("state")
        e = r.get("eta_s")
        out.append({"id": rid, "task": task,
                    "state": None if state is None else str(state),
                    "eta_s": None if e is None else max(0, int(e))})
    return out


def parse_items(items):
    """CLI --item "ID: task" -> checklist rows (state queued)."""
    rows = []
    for text in items or ():
        rid, sep, task = str(text).partition(":")
        if not sep or not rid.strip() or not task.strip():
            raise ValueError(f"--item {text!r}: expected 'ID: task'")
        rows.append({"id": rid.strip(), "task": task.strip(), "state": "queued",
                     "eta_s": None})
    return rows


def _rows_now(checklist, remain):
    """Rows for one write: a row with no eta_s carries the lane's remaining ETA."""
    if checklist is None:
        return None
    return [dict(r, eta_s=remain if r["eta_s"] is None else r["eta_s"]) for r in checklist]


class Heartbeat:
    """Rewrites the lane progress row every interval while the run lasts, so a
    2x-ETA staleness check fires only on a real hang. beat() is the one write;
    the thread only calls it. Write errors never touch the run."""

    def __init__(self, write, clock, t0, eta_s, interval=HEARTBEAT_S):
        self.write, self.clock, self.t0, self.eta_s = write, clock, t0, eta_s
        self.interval = interval
        self.stop_evt = threading.Event()
        self.thread = None

    def beat(self):
        elapsed = self.clock() - self.t0
        with contextlib.suppress(Exception):
            self.write(running_pct(elapsed, self.eta_s), remaining_s(elapsed, self.eta_s))

    def _loop(self):
        while not self.stop_evt.wait(self.interval):
            self.beat()

    def start(self):
        self.thread = threading.Thread(target=self._loop, name="al-lane-heartbeat",
                                       daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.stop_evt.set()
        if self.thread is not None:
            self.thread.join(timeout=10)


def run_lane(lane, prompt, writes_code=False, timeout=3600, dry_run=False, root=ROOT,
             spawn=None, lane_ctx=None, progress=None, record=eta.record,
             clock=time.time, model=None, effort=None, eta_kind=None,
             sample_retry=False, sample_label=None, checklist=None,
             heartbeat_s=HEARTBEAT_S):
    """One headless run on one lane. Returns the kit usage line plus "worktree".
    Progress goes to the MAIN checkout's progress/lane-<i>.json once the lane
    index is claimed; a dry run or a refused claim has no index and writes none.
    model / effort (plan 099 routing) reach the kit spawn only when given; a
    by-hand run without them keeps the kit default (pick_model / pick_effort).
    eta_kind (the loop item kind, e.g. item-plan) sets the progress ETA and is
    recorded beside the lane kind, so mixed item sizes on one lane stop skewing
    each other's estimate. Order Nd11eb1 item 6: 1 lane in 20 and every retry
    after a failure (sample_retry) run with persistence on and their transcript
    is copied to the sidecar when the run ends (tools/lane_samples.py).
    LANE-CHECKLIST: checklist (FLEET item 13 d rows, remaining tasks only)
    rides on every write of the lane progress file; the ETA is lane_eta()
    (history median, floored) and a Heartbeat rewrites the row every
    heartbeat_s while the spawn lasts, pct = elapsed / eta capped at 95. The
    kit spawn only closes the row (close_progress keeps the checklist)."""
    check_lane(lane)
    checklist = norm_checklist(checklist)
    import lane_samples  # call time only: see the note at the module imports
    route = {k: v for k, v in (("model", model), ("effort", effort)) if v is not None}
    run_id = f"lane-{lane}"
    if progress is None:
        progress = kit().write_progress
    kind = f"lane-{lane}-{'code' if writes_code else 'read'}"
    eta_s = lane_eta(writes_code, kind, eta_kind)

    def put(pct, step, eta_now, status, rows):
        extra = {} if rows is None else {"checklist": rows}
        progress(main, task, pct, step, eta_now, status, **extra)

    if dry_run:
        return {"lane": lane, "dry_run": True, "eta": eta.fmt(eta_s)}
    if lane_ctx is None:
        lane_ctx = lanes().run_lane
    if spawn is None:
        spawn = kit().spawn
    main = lanes().main_tree(root)
    task = None
    t0 = clock()
    ok = False
    sampled = None
    try:
        with lane_ctx(root, CODE, lane, run_id, cap=lane_cap()) as claim:
            task = progress_task(claim["index"])
            wt = Path(claim["worktree"])
            seed_config(wt, root)
            step = f"{lane}: running headless in {wt.name}"
            put(PCT_START, step, int(eta_s), "running", _rows_now(checklist, int(eta_s)))
            sampled = lane_samples.begin(main, retry=sample_retry)
            if sampled:
                route["session_id"] = sampled
            beat = Heartbeat(lambda pct, rem: put(pct, step, rem, "running",
                                                  _rows_now(checklist, rem)),
                             clock, t0, eta_s, heartbeat_s).start()
            try:
                with sidecar_temp_env():  # SIDECAR: TEMP / TMP under <sidecar>/AL/Temp
                    line = spawn(root, CODE, prompt, note=sample_label or run_id, writes_code=writes_code,
                                 timeout=timeout, cwd=wt, stdin=True,
                                 extra=CODE_EXTRA if writes_code else (),
                                 governor="queued", governor_timeout=timeout, kind="build",
                                 slot_id=lane, progress_task=task, **route)
            finally:
                beat.stop()  # before the kit / run_lane close the row
        line = dict(line, worktree=str(wt))
        ok = line.get("rc") == 0 and not line.get("error")
        return line
    finally:
        lane_samples.finish(main, sampled, sample_label or run_id)
        spent = clock() - t0
        record(kind, spent, ok=ok)
        if eta_kind:
            record(eta_kind, spent, ok=ok)
        if task is not None:
            # done: nothing of this run remains; failed: its rows still do
            put(100, f"{lane}: {'finished' if ok else 'failed'}", 0,
                "done" if ok else "failed",
                ([] if ok else _rows_now(checklist, 0)) if checklist is not None else None)


def status(root=ROOT):
    rows = []
    for row in lanes().repo_lane_state(root, lane_cap()):
        rows.append(" ".join(f"{k}={v}" for k, v in sorted(row.items())))
    for lane in LANES:
        rows.append(f"{lane}: eta={eta.fmt(eta.estimate(f'lane-{lane}-code'))}")
    rows.append("sidecar temp: " + ("set" if sidecar_temp() is not None else "none (parent TEMP)"))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="AL laned headless driver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    r = sub.add_parser("run")
    r.add_argument("lane")
    r.add_argument("--prompt-file", required=True)
    r.add_argument("--writes-code", action="store_true")
    r.add_argument("--timeout", type=int, default=3600)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--item", action="append", default=[], metavar="'ID: task'",
                   help="a checklist row for the progress file (repeatable)")
    r.add_argument("--checklist-file", help="JSON list of {id, task, state, eta_s}")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print("\n".join(status()))
        return 0
    try:
        rows = parse_items(a.item)
        if a.checklist_file:
            rows += json.loads(Path(a.checklist_file).read_text(encoding="utf-8"))
        checklist = norm_checklist(rows) if rows else None
    except (OSError, ValueError, TypeError) as exc:
        print(f"{a.lane}: bad checklist: {exc}", file=sys.stderr)
        return 64
    prompt = Path(a.prompt_file).read_text(encoding="utf-8")
    line = run_lane(a.lane, prompt, a.writes_code, a.timeout, a.dry_run,
                    checklist=checklist)
    if a.dry_run:
        print(f"{a.lane}: dry-run ok")
        return 0
    print(f"{a.lane}: rc={line.get('rc')} error={line.get('error')} "
          f"worktree={line.get('worktree')}")
    # plan 149 TOOLS-07: the same success test run_lane records (rc 0, no error)
    return 0 if line.get("rc") == 0 and not line.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
