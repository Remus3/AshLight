#!/usr/bin/env python3
"""AL loop tick (plan 015, operator order 2026-10-05).

    al_loop.py tick [--dry-run [--ignore-halt]] [--no-push]   one idempotent pass
    al_loop.py checklist                      print the last tick's checklist
    al_loop.py lane <ID>                      (internal) run one dispatched item
    al_loop.py review <ID>                    (internal, plan 098) review / fix / merge one item
    al_loop.py push                           (internal, plan 098) gate main and push
    al_loop.py session                        orders routed to the session (plan 091)
    al_loop.py session-done <ID> [--commit S] the session marks a routed order done

One tick, under ops/loop/control/loop.lock (fleet_watch.watch_lock):
  a. pre_halt steps (tools/loop_steps: the seam, phases and rules), then HALT ->
     "halted", exit 0 (--dry-run --ignore-halt goes on, writes nothing, prints
     the would-dispatch lines). A busy lock -> exit 0, nothing written.
  b. Inbox (config loop.inbox_dir / loop.outbox_dir): new notes by mtime through
     fleet_watch.run_source (baseline first), then kit v8 fleet_inbox (FLEET
     item 14): classify() free; skip / ack = a seen-ledger line, no note;
     ORDER / FIX / RULING escalate to a lane item, answered after merge (plan
     091: one naming ops/fleet_kit/, .claude/, CLAUDE.md or a kit version goes
     to the session instead, answered after `session-done`); else
     ONE triage spawn (kit v11 triage_spawn_kwargs(FLOORS_IN_HOOKS=False):
     sonnet, low, bare; kind triage). Answers
     to one destination go in ONE batch note, HOP lines, OutboundCap (12 a
     day, config may lower it). No governor slot (kit ruling: acknowledgements stay outside).
  d. Finished lane worktrees (before c, so a dirty worktree never blocks a
     claim). Plan 098: the tick only launches one DETACHED `review <ID>`
     worker per item (parallel, each in its own worktree), watches its pid
     and counts a dead one (MAX_ATTEMPTS, then parked); the worker runs:
     gates, review-lane verifier (refute rounds capped at 3, then
     accept and record), commit, merge --no-ff into main, flip the ROADMAP row
     in main inside the merge commit (never in the lane commit); a conflict in
     ROADMAP.md alone is resolved row by row (resolve_roadmap). Any other
     conflict keeps the lane commit under refs/al/keep/<id> and the item
     goes back out as a `resolve` run (plan 058, before new rows, at most
     MAX_ATTEMPTS per item) through the same gates / verifier / merge.
  c. Work list = open ROADMAP rows + hand-off items not tagged OPERATOR /
     physical / MAIN / NOTE. Each item is dispatched to a free lane as a
     DETACHED `al_loop.py lane <ID>` process that runs tools/al_lane.run_lane
     (kit lane + own worktree + one governor slot at the call, fail closed).
     ROADMAP.md (repo root) rows are bullets `- [ ] ID (lane) title. ACCEPT:`;
     a row's lane hint picks that lane when it is free.
  e. Idle (nothing open, nothing in flight): one Path of Exile 2 deep-dive
     lane per day (research doc + at most loop.max_new_plans_per_day rows).
  f. Spawning stops at RUNS_CAP - 3 and during a usage-limit backoff
     (ops/loop/control/backoff.json, 30 min doubling, cap 6 h). Plan 100: the
     run count is max(headless_budget.json, headless_usage.jsonl) in the
     window (tools/usage_ledger.py); each tick first labels kind-less usage
     rows kind build.
  g. inbox_status.json (kit write_status, next_tick) and
     ops/loop/control/progress/loop.json with a "checklist" array (FLEET item
     13 d: remaining tasks as kit rows {id, task, state, eta_s}, at most 20;
     "fire" = this tick's run count, the item-13 session number).
  Push (unless --no-push): with no remote named origin the push is a no-op
  that logs "push skipped: local only". With origin, when main is clean and
  ahead of origin/main the tick launches ONE detached `push` worker (plan
  098), which under the merge lock needs gates green and leak_sweep
  --pre-push clean, then runs `git push origin main`; .githooks/pre-push
  re-checks the ref rule, the identity gate and the leak sweep on every push.
  The loop pushes only while the gitignored config/local.json holds
  "loop_push": true (OA-11, default off; ruling Q-23); else it logs "push
  skipped: loop push is off" and a session pushes. No tool writes that key.
  Gates: ops/loop/gates.txt (one argv per line, no shell), else the ci.yml
  `run:` lines; neither = fail closed. Plan 096: Tick.gate runs once per tree
  state (verdicts cached by git tree id); a merge that only adds the ROADMAP
  flip carries the lane tree's verdict to main. The verifier runs no pytest.

Every side effect goes through Deps, so tests never spawn, never touch a git
remote and never call schtasks. Paths are resolved at run time.
"""

import argparse
import contextlib
import datetime as _dt
import hashlib  # noqa: F401
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import eta  # noqa: E402
import al_lane  # noqa: E402
import lane_samples  # noqa: E402,F401
import ledger_rotate  # noqa: E402
import usage_ledger  # noqa: E402
import loop_steps  # noqa: E402  AUTO-01: every tick step is a tools/loop_steps/ file
# Plan 107 / LOOP-SPLIT-TICK: helpers (loop_base), prompts, ROADMAP rows, inbox,
# merge, review and work-list code live in tools/loop_*.py, re-exported here as
# the same objects (tests and tools/al_tests.py read al_loop.X; unused = F401).
from loop_base import (  # noqa: E402
    ATTENTION_STATES, BACKOFF_BASE_S, BACKOFF_CAP_S, BACKOFF_REL, CODE, DEEP_EXTRA,
    DONE_STATES, GATE_RETRY, GATE_TIMEOUT_S, HALT_REL, HEADROOM, HOLD_STATES, INFRA_RX,
    KIT_CRASH_RX,
    IN_FLIGHT, Items, LOCK_REL, MAX_ATTEMPTS, MERGE_LOCK_REL,
    PROGRESS_TASK, PUSH_LAST_REL, PUSH_WORKER_REL, REVIEW_LOG_KEEP,
    REVIEW_START_S, TICK_TARGET_S, _BREAKAWAY, _DETACHED,
    _NO_WINDOW, _norm_path, ascii_text, atomic_write, epoch_of, is_limit, iso,
    load_config, read_json, route_kind, route_kw,
    CONTROL_REL, DEFAULT_MAX_NOTES, DEFAULT_MAX_PLANS, DELIVERY_REL, DEPENDS_RX,  # noqa: F401
    DEP_ID_RX, GATE_CACHE_MAX, GATE_CACHE_REL, HOP_RX, INBOX_REL, ITEMS_REL, KEEP_REF,  # noqa: F401
    LANE_TIMEOUT_S, LEGACY_LEDGER_REL, LIMIT_RX, NOTE_HEAD, NOTE_MAX, NOTE_STAMP,  # noqa: F401
    ORDERS_REL, OUTBOX_REL, RED_TTL_S, RESOLVABLE, ROADMAP_REL, ROUTES, ROUTE_EFFORTS,  # noqa: F401
    BLOCKED_RX, ROW_RX, SKIP_TAGS, STOP, TICK_S, WATCH_REL, _ROUTE_MODEL, eta_label,  # noqa: F401
    load_routes, next_number, read_jsonl, with_hop,  # noqa: F401
    DIRTY_WT_RX, MARKER_RX, MAX_ROUNDS, NEED_RX, VERDICT_RX, VERIFY_EXTRA,  # noqa: F401
)
from loop_prompts import (  # noqa: E402
    GATES, NO_ROADMAP, resolve_prompt,  # noqa: F401
    deep_dive_prompt, fix_prompt, handoff_prompt, plan_prompt, verify_prompt,  # noqa: F401
)
from loop_roadmap import (  # noqa: E402
    dispatchable,
    merge_subject,  # noqa: F401
    RUN_FIELDS, _norm_words, base_kind, flip_roadmap,  # noqa: F401
    resolve_roadmap, result_line, title_tokens,  # noqa: F401
    commit_body, commit_subject, dependency_cycles, handoff_items, is_duplicate,  # noqa: F401
    plan_depends, plan_doc, plan_titles, resolve_item, roadmap_flip_time,  # noqa: F401
    roadmap_rows, dive_backoff, dive_history,  # noqa: F401
)
from loop_inbox import (  # noqa: E402
    InboxMixin, session_done, parked_items, parked_status, session_orders,
    session_paths, FLOORS_IN_HOOKS, SESSION_TARGETS, inbox_prompt, order_id, queued_orders,  # noqa: F401
    triage_spawn_kwargs,  # noqa: F401
    missing_ordered, order_prompt, order_settled, session_needs, settled_notes,  # noqa: F401
)
from loop_gatefail import foreign_only  # noqa: E402  LOOP-GATE-RERUN
from loop_merge import GateCache, MergeMixin, last_lines  # noqa: E402
from loop_review import ReviewMixin  # noqa: E402
from loop_review import ROUND_LOG_CAP, ROUND_LOG_MAX_FINDINGS  # noqa: E402,F401
from loop_work import WorkMixin  # noqa: E402


# ---------------------------------------------------------------- dependencies

# Kit v12 race guards (FLEET-COMMON 16): every commit / push takes the tree's
# git lock; every whole pytest suite holds a machine-wide suite-gate slot.
LOOP_OWNER = "al-loop.main"
SUITE_GATE_REL = Path("ops/fleet_kit/fleet_suite_gate.py")


def _owner():
    return os.environ.get("FLEET_CLAIM_OWNER") or LOOP_OWNER


def _gitlock():
    return al_lane._load("fleet_gitlock", "ops/fleet_kit/fleet_gitlock.py")


def _python():
    p = Path(sys.executable)
    alt = p.with_name("python.exe") if p.name.lower() == "pythonw.exe" else p
    return str(alt if alt.exists() else p)


def _pythonw():
    p = Path(sys.executable).with_name("pythonw.exe")
    return str(p if p.exists() else sys.executable)


def _git_run(args, cwd, input=None):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          input=input, env=env, timeout=600, creationflags=_NO_WINDOW)


def _git(args, cwd, input=None, lock=None):
    """git; a commit or push runs under the tree's kit v12 git lock."""
    if not args or args[0] not in ("commit", "push"):
        return _git_run(args, cwd, input)
    lock = lock or _gitlock().git_lock
    try:
        with lock(cwd, _owner(), args[0]):
            return _git_run(args, cwd, input)
    except Exception as exc:  # lock timeout / refusal: report as a failed git call
        return subprocess.CompletedProcess(["git", *args], 3, "",
                                           f"git lock: {type(exc).__name__}: {exc}")


def hooks_path_problem(root, git):
    """Perf audit 2.10: why core.hooksPath does not resolve to an existing
    directory inside the repo (a moved checkout left it pointing elsewhere), or
    None. Reported in the tick log only; it never fails the tick."""
    try:
        r = git(["config", "core.hooksPath"], root)
    except Exception as exc:  # noqa: BLE001 - a check, never a tick failure
        return ascii_text(f"hooksPath check failed: {type(exc).__name__}", 200)
    val = (r.stdout or "").strip() if r.returncode == 0 else ""
    if not val:
        return "hooksPath unset: hooks not installed (python tools/install_hooks.py)"
    root = Path(root).resolve()
    hp = Path(val)
    hp = (hp if hp.is_absolute() else root / hp).resolve()
    if hp != root and root not in hp.parents:
        return "hooksPath points outside the repo: re-run python tools/install_hooks.py"
    if not hp.is_dir():
        return "hooksPath does not exist: re-run python tools/install_hooks.py"
    return None


CI_WORKFLOW_REL = Path(".github/workflows/ci.yml")
CI_SETUP_RX = re.compile(r"\bpip\s+install\b")
# The loop's gates: ops/loop/gates.txt (CI runs the same; `#` comments), else ci.yml.
GATES_REL = Path("ops/loop/gates.txt")


def gate_file_commands(text):
    """The commands of ops/loop/gates.txt, in order (blank and # lines dropped)."""
    return [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def ci_gate_commands(text):
    """The `run:` commands of the ci workflow, in order, minus environment
    setup (pip install). The loop's gates ARE these commands (fix-0130), so a
    lane can never merge what ci rejects."""
    cmds, block, indent = [], False, 0
    for line in text.splitlines():
        if block:
            if not line.strip():
                continue
            if len(line) - len(line.lstrip()) > indent:
                cmds.append(line.strip())
                continue
            block = False
        m = re.match(r"^(\s*)(?:-\s+)?run:\s*(.*?)\s*$", line)
        if not m:
            continue
        if m.group(2) in ("|", ">", "|-", ">-"):
            block, indent = True, len(m.group(1))
        elif m.group(2):
            cmds.append(m.group(2).strip("\"'"))
    return [c for c in cmds if not CI_SETUP_RX.search(c)]


SUMMARY_RX = re.compile(r"^=+ short test summary info =+\s*$", re.M)
GATE_TAIL_MAX = 1500


def gate_tail(stdout, stderr=""):
    """TEST-PLUGIN-PIN: the part of a gate's output a red verdict needs. The
    pytest short test summary (FAILED ids, then the count line) when present,
    else the last lines of stdout; a short stderr tail goes first so the
    output still ENDS with the ids and the count line."""
    out = stdout or ""
    hits = list(SUMMARY_RX.finditer(out))
    if hits:
        out = out[hits[-1].end():]
    err = last_lines(stderr, 500)
    body = last_lines(out, GATE_TAIL_MAX)
    return (err + "\n" + body) if err else body


def _run_gate(argv, cwd):
    r = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                       timeout=GATE_TIMEOUT_S, creationflags=_NO_WINDOW,
                       encoding="utf-8", errors="replace")
    return r.returncode, gate_tail(r.stdout, r.stderr)


SHELL_OPERATOR_CHARS = set("();<>|&")


def _shell_operator(cmd):
    """The first unquoted shell operator in a ci run command, or None. The
    loop runs gates as argv without a shell (one local Python, not ci's
    3.11 + 3.14 matrix), so `a && b` would pass "&&" to a and never run b."""
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    for tok in lex:
        if tok and set(tok) <= SHELL_OPERATOR_CHARS:
            return tok
    return None


SUITE_RUN_REL = "tools/suite_run.py"


def _whole_suite(argv):
    """True for the whole suite: the one runner `python tools/suite_run.py`
    (TEST-GATE-CALLERS), or a pytest run that names no test FILE."""
    if len(argv) == 2 and argv[1].replace("\\", "/") == SUITE_RUN_REL:
        return True
    if "pytest" not in argv:
        return False
    rest = argv[argv.index("pytest") + 1:]
    return not any(a.endswith(".py") or "::" in a for a in rest)


def _gate_argv(cmd):
    """argv of one gate command; a whole suite runs under the kit suite gate.
    No worker flags are added: tools/suite_run.py picks the mode itself
    (TEST-GATE-CALLERS; plan 097's XDIST_ARGS left with it)."""
    argv = shlex.split(cmd)
    if argv[0] == "python":
        argv[0] = _python()
    elif argv[0] == "npm" and sys.platform == "win32":
        argv[0] = "npm.cmd"
    if _whole_suite(argv):
        argv = [_python(), str(ROOT / SUITE_GATE_REL), "run", "--owner", _owner(), "--", *argv]
    return argv


def gate_commands(cwd):
    """(commands, source rel) of cwd's gates: ops/loop/gates.txt when it
    exists, else the ci workflow's run lines; (None, why) when neither exists."""
    try:
        text = (Path(cwd) / GATES_REL).read_text(encoding="utf-8")
        return gate_file_commands(text), GATES_REL.as_posix()
    except OSError:
        pass
    try:
        text = (Path(cwd) / CI_WORKFLOW_REL).read_text(encoding="utf-8")
    except OSError:
        return None, (f"no {GATES_REL.as_posix()} or {CI_WORKFLOW_REL.as_posix()}: "
                      "gates fail closed")
    return ci_gate_commands(text), CI_WORKFLOW_REL.as_posix()


def _gates(cwd, run=_run_gate):
    """(ok, detail): exactly cwd's own gate commands (ops/loop/gates.txt, else
    .github/workflows/ci.yml), in order; fail closed without one."""
    cmds, src = gate_commands(cwd)
    if cmds is None:
        return False, src
    if not cmds:
        return False, f"no gate command in {src}: gates fail closed"
    for cmd in cmds:
        if not cmd.strip():  # plan 149 TOOLS-11: `run: ""` names no command
            return False, f"empty gate command in {src}: fail closed"
        op = _shell_operator(cmd)
        if op is not None:
            return False, f"{cmd}: shell operator {op!r} unsupported by loop gates: fail closed"
    retries = []
    for cmd in cmds:
        for attempt in (1, 2):
            try:
                rc, tail = run(_gate_argv(cmd), cwd)
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                return False, "".join(retries) + f"{cmd}: {type(exc).__name__}"
            # TEST-GATE-CALLERS: a kit traceback is infrastructure, not a red
            # verdict: one retry, logged (Tick.gate steps each GATE_RETRY line)
            if rc != 0 and attempt == 1 and KIT_CRASH_RX.search(tail or ""):
                retries.append(f"{GATE_RETRY} {cmd} rc={rc}: kit traceback, retried once\n")
                continue
            break
        if rc != 0:
            return False, "".join(retries) + f"{cmd} rc={rc}\n{tail}"
    return True, "".join(retries) + f"gates green ({len(cmds)}, {src})"


def _leak_pre_push(cwd, ref_line):
    r = subprocess.run([_python(), "tools/leak_sweep.py", "--pre-push"], cwd=str(cwd),
                       input=ref_line + "\n", capture_output=True, text=True, timeout=600,
                       creationflags=_NO_WINDOW)
    return r.returncode == 0


def loop_push_on(main):
    """OA-11 / ruling Q-23: the loop pushes only while the operator's
    gitignored config/local.json holds "loop_push": true (a real boolean);
    absent, false, or an unreadable file means off."""
    doc = read_json(Path(main) / "config" / "local.json", {})
    return isinstance(doc, dict) and doc.get("loop_push") is True


def tree_key(cwd):
    """Plan 096: the git tree id of cwd's working tree as `git add -A` would
    stage it (the gate cache key). Clean: HEAD^{tree}. Dirty: write-tree over
    a TEMPORARY copy of the index, so the real index and files are never
    touched. Ignored files are not tree state. None when cwd is not a work
    tree root or git fails (the gates then run uncached)."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}

    def run(args, extra=None):
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                              env=dict(env, **(extra or {})), timeout=600,
                              creationflags=_NO_WINDOW)

    def out(r):
        return r.stdout.strip() if r.returncode == 0 else ""

    try:
        top = out(run(["rev-parse", "--show-toplevel"]))
        if not top or _norm_path(Path(top)) != _norm_path(cwd):
            return None
        st = run(["status", "--porcelain"])
        if st.returncode != 0:
            return None
        if not st.stdout.strip():
            return out(run(["rev-parse", "HEAD^{tree}"])) or None
        idx = Path(out(run(["rev-parse", "--git-path", "index"])) or "index")
        idx = idx if idx.is_absolute() else Path(cwd) / idx
        # SIDECAR rule: the scratch index lives beside the real one in the git
        # dir (inside the repo's .git), never in the machine TEMP
        with tempfile.TemporaryDirectory(prefix="al-gate-", dir=str(idx.parent)) as td:
            tmp = {"GIT_INDEX_FILE": str(Path(td) / "index")}
            if idx.is_file():
                shutil.copyfile(idx, tmp["GIT_INDEX_FILE"])
            elif run(["read-tree", "HEAD"], tmp).returncode != 0:
                return None
            if run(["add", "-A"], tmp).returncode != 0:
                return None
            return out(run(["write-tree"], tmp)) or None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _launch(root, iid, popen=subprocess.Popen, cmd="lane"):
    """Start a worker (`lane <ID>`, plan 098 `review <ID>` / `push`) detached.
    It breaks away from the Task Scheduler job when the job allows it, so the
    tick's end never ends the worker."""
    argv = [_pythonw(), str(Path(root) / "tools" / "al_loop.py"), cmd] + ([iid] if iid else [])
    kw = dict(cwd=str(root), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, close_fds=True)
    flags = _NO_WINDOW | _DETACHED
    try:
        return popen(argv, creationflags=flags | _BREAKAWAY, **kw).pid
    except OSError:
        return popen(argv, creationflags=flags, **kw).pid


class Deps:
    """Every side effect of a tick. Tests override attributes."""

    def __init__(self, root=ROOT, **over):
        self.root = Path(root)
        k, fw, fl = al_lane.kit(), _load_watch(), al_lane.lanes()
        self.kit, self.watch = k, fw
        self.inbox = al_lane._load("fleet_inbox", "ops/fleet_kit/fleet_inbox.py")
        self.checklist = al_lane._load("fleet_checklist", "ops/fleet_kit/fleet_checklist.py")
        # plan 100: the governor counts max(budget file, usage log) runs;
        # Order Nd11eb1 item 2: with the tree's machine cap, not the bare default
        self.budget = usage_ledger.gate_budget(k, self.root, CODE)
        self.spawn = k.spawn
        self.should_skip = k.should_skip
        self.pick_effort = k.pick_effort
        self.write_status = k.write_status
        self.lock = lambda path: fw.watch_lock(path)
        self.lane_state = lambda: fl.repo_lane_state(self.root, al_lane.lane_cap())
        self.lane_cap = al_lane.lane_cap  # kit v25: live machine config
        self.should_yield = al_lane.should_yield  # kit v25: fair release
        self.lane_worktree = lambda i: fl.worktree_path(self.main_tree, CODE, i)
        self.pid_alive = fl.pid_alive
        self.main_tree = fl.main_tree(self.root)
        self.launch = lambda iid: _launch(self.root, iid)
        self.launch_review = lambda iid: _launch(self.root, iid, cmd="review")
        self.launch_push = lambda: _launch(self.root, None, cmd="push")
        self.git = _git
        self.gates = _gates
        self.tree_key = tree_key  # plan 096: gate cache key
        self.leak_pre_push = _leak_pre_push
        self.estimate = eta.estimate
        self.record = eta.record
        self.clock = time.time
        self.rotate = ledger_rotate.rotate_daily  # plan 138
        self.drift = _drift_check  # TC-DRIFT: daily PoB-PoE2 release check
        self.docs_watch = lambda r, now: __import__("ggg_docs_watch").safe_check(r, now)
        # plan 093: the machine roster FLEET_ROSTER the kit statusline reads; tests pass None
        self.roster_path = os.environ.get("FLEET_ROSTER") or None
        for key, val in over.items():
            setattr(self, key, val)


def _drift_check(root, now):
    """TC-DRIFT (tools/tc_drift.py): one line when a check ran, else None; never raises."""
    try:
        import loop_depbot, tc_drift  # noqa: E401  PUB-DEPBOT-TICK: daily worker
        return loop_depbot.join(loop_depbot.loop_check(root, now), tc_drift.loop_check(root, now))
    except Exception as exc:  # noqa: BLE001 - a drift fault must not stop the tick
        return f"tc drift: {type(exc).__name__}: {exc}"


def _load_watch():
    return al_lane._load("fleet_watch", "ops/fleet_kit/fleet_watch.py")


# ---------------------------------------------------------------- backoff

def backoff_until(root):
    doc = read_json(Path(root) / BACKOFF_REL, {}) or {}
    return float(doc.get("until", 0) or 0)


def backoff_hit(root, now, reason):
    doc = read_json(Path(root) / BACKOFF_REL, {}) or {}
    prev = int(doc.get("delay_s", 0) or 0)
    delay = min(prev * 2, BACKOFF_CAP_S) if prev else BACKOFF_BASE_S
    doc = {"delay_s": delay, "until": now + delay, "reason": ascii_text(reason, 200),
           "since": iso(now)}
    atomic_write(Path(root) / BACKOFF_REL, json.dumps(doc))
    return doc


def backoff_clear(root):
    p = Path(root) / BACKOFF_REL
    if p.exists() and (read_json(p, {}) or {}).get("delay_s"):
        atomic_write(p, json.dumps({"delay_s": 0, "until": 0}))


def spawn_block(root, budget, now):
    """Why spawning must stop now (item f), or None. Shared by the tick and the
    detached lane worker, which re-checks after dispatch."""
    if (Path(root) / HALT_REL).exists():
        return "halted"
    if backoff_until(root) > now:
        return "backoff"
    if not budget.readable():
        return "budget unreadable"
    if budget.used() >= budget.cap - HEADROOM:
        return "runs cap"
    return None


# ---------------------------------------------------------------- plan 137 stalls

STALL_FLOOR_S = 600  # a progress file is never stalled under 10 min of silence


def stall_of(doc, now, floor_s=STALL_FLOOR_S):
    """Seconds a running lane's progress doc has been silent when that exceeds
    max(2 x its eta_s, floor_s) (FLEET item 12), else None. A finished,
    failed or blocked doc never stalls; a missing doc or `updated` is unknown,
    and unknown is not stalled."""
    if not isinstance(doc, dict) or doc.get("status") != "running":
        return None
    updated = epoch_of(doc.get("updated"))
    if updated is None:
        return None
    try:
        eta_s = float(doc.get("eta_s") or 0)
    except (TypeError, ValueError):
        eta_s = 0.0
    silent = now - updated
    return int(silent) if silent > max(2 * eta_s, floor_s) else None


# ---------------------------------------------------------------- the tick

class Tick(InboxMixin, MergeMixin, ReviewMixin, WorkMixin):
    halted = ignore_halt = False  # AUTO-01: set by tick()

    def __init__(self, deps, dry_run=False, no_push=False):
        self.d, self.dry, self.no_push = deps, dry_run, no_push
        self.root = deps.root
        self.cfg = load_config(self.root)
        self.items = Items(self.root)
        self.log = []
        self.pushed = None
        self.fi = deps.inbox
        self.cap = self.fi.OutboundCap(self.root, cap=self.cfg["max_notes_per_day"],
                                       clock=deps.clock)
        self.awaiting = self.capped = self.paused = 0
        self.open_ids = set()  # open ROADMAP row ids, set by work_list()
        self.last_tree = None  # plan 096: tree id of the last gate() call
        self.checklist_dropped = 0  # plan 168: set by checklist()

    def route(self, kind, note):
        """Plan 099: spawn() model / effort keywords for one run of `kind`."""
        return route_kw(self.cfg["routes"], kind, note, self.d.pick_effort)

    # -- plan 096: one authoritative gate run per tree state
    def gate(self, cwd, changed=None):
        """(ok, detail) of the ci gates on cwd's tree, from the verdict cache
        when this exact tree was gated; else one run, recorded when the tree
        did not change under it and the verdict is not an infrastructure red.
        LOOP-GATE-RERUN: `changed` (a callable giving the lane diff's names)
        lets a cached red whose failing ids all lie outside that diff run
        again ONCE per tree (an unrelated flake or infrastructure red must not
        park a good item); the re-run's verdict is cached marked `rerun`."""
        now = self.d.clock()
        key = self.d.tree_key(cwd)
        self.last_tree = key
        cache = GateCache(self.root)
        e = cache.get(key, now) if key else None
        rerun = False
        if e and not e["ok"] and changed is not None and not e.get("rerun") \
                and foreign_only(e.get("detail") or "", changed()):
            rerun = True
            if not self.dry:  # spend the once now, so an uncached re-run red keeps it spent
                cache.put(key, False, e.get("detail"), e.get("where") or Path(cwd).name,
                          epoch_of(e.get("ts")) or now, via=e.get("via"), rerun=True)
            self.step(f"gates cached red {key[:12]} outside the diff: re-run once")
        elif e:
            self.step(f"gates cached {'green' if e['ok'] else 'red'} {key[:12]}")
            return e["ok"], e.get("detail") or ""
        ok, detail = self.d.gates(cwd)
        for line in (detail or "").splitlines():
            if line.startswith(GATE_RETRY):
                self.step(line)
        if key and not self.dry and (ok or not INFRA_RX.search(detail or "")) \
                and self.d.tree_key(cwd) == key:
            cache.put(key, ok, detail, Path(cwd).name, self.d.clock(), rerun=rerun and not ok)
        return ok, detail

    # -- gates on spawning (item f)
    def blocked(self):
        return spawn_block(self.root, self.d.budget, self.d.clock())

    def spawn(self, prompt, kind="build", **kw):
        """kit spawn + backoff bookkeeping. Returns the usage line or None.
        kind (kit v8: build / inbox / triage) labels the usage line."""
        try:
            line = self.d.spawn(self.root, CODE, prompt, stdin=True, kind=kind, **kw)
        except self.d.kit.Refused as exc:
            self.step(f"spawn refused: {exc}")
            if is_limit(str(exc)):
                backoff_hit(self.root, self.d.clock(), str(exc))
            return None
        text = f"{line.get('error') or ''} {line.get('result') or ''}"
        if line.get("rc") != 0 and is_limit(text):
            backoff_hit(self.root, self.d.clock(), text)
            self.step("usage limit hit: backoff")
            return None
        if line.get("rc") == 0 and not line.get("error"):
            backoff_clear(self.root)
        return line

    def step(self, text):
        self.log.append(ascii_text(text, 200))

    # -- lanes in flight
    def reap_lost(self):
        """Under the tick lock no dispatch is mid-flight, so a "dispatched"
        record without a pid is a launch that never happened (a crashed tick).
        A refused / lost record out of attempts becomes gave-up, never silent."""
        if self.dry:
            return
        for rec in self.items.all().values():
            state = rec.get("state")
            if state == "dispatched" and (not rec.get("pid") or
                                          not self.d.pid_alive(rec["pid"])):
                rec.update(state="lost", attempts=rec.get("attempts", 0))
                self.items.put(rec)
                self.step(f"{rec['id']}: lane process gone")
                state = "lost"
            if state in ("refused", "lost") and rec.get("attempts", 0) >= MAX_ATTEMPTS:
                rec["state"] = "gave-up"
                self.items.put(rec)
                self.step(f"{rec['id']}: gave up after {rec.get('attempts', 0)} attempts: "
                          f"{rec.get('error') or state}")
            if state == "blocked" and rec.get("blocked_runs", 0) >= MAX_ATTEMPTS:
                rec.update(state="gave-up",
                           error=f"blocked {rec['blocked_runs']} times on "
                                 f"{', '.join(rec.get('needs') or [])}")
                self.items.put(rec)
                self.step(f"{rec['id']}: gave up: {rec['error']}")

    def lane_progress(self, rec):
        """Plan 137: this run's `p<id>-build.json` from the lane worktree, then
        the main checkout (a lane may be unable to write the main copy); the
        newest parsable `updated` wins and a doc older than the dispatch is a
        previous run's, ignored."""
        since = epoch_of(rec.get("dispatched"))
        if since is None:
            return None
        trees = [self.d.lane_worktree(r["index"]) for r in self.d.lane_state()
                 if r.get("state") == "RUNNING" and r.get("lane") == rec.get("lane")]
        best, best_t = None, None
        for tree in trees + [self.d.main_tree]:
            doc = read_json(Path(tree) / self.d.kit.PROGRESS_REL / f"p{rec['id']}-build.json")
            t = epoch_of(doc.get("updated")) if isinstance(doc, dict) else None
            if t is not None and t >= since and (best_t is None or t > best_t):
                best, best_t = doc, t
        return best

    def stalls(self):
        """Plan 137: flag (never kill, CLAUDE.md loop rule 1) a live dispatched
        lane whose progress went silent; the record carries `stalled_s` for the
        checklist. One `lane-stall` timing row once a stall passes 3 x ETA."""
        if self.dry:
            return
        now = self.d.clock()
        for rec in self.items.all().values():
            if rec.get("state") != "dispatched" or not rec.get("pid") or \
                    not self.d.pid_alive(rec["pid"]):
                continue
            doc = self.lane_progress(rec)
            silent = stall_of(doc, now)
            if silent is None and "stalled_s" not in rec:
                continue
            cur = self.items.get(rec["id"])  # the lane worker may have just finished
            if not isinstance(cur, dict) or cur.get("state") != "dispatched":
                continue
            if silent is None:
                cur.pop("stalled_s", None)
                self.items.put(cur)
                continue
            cur["stalled_s"] = silent
            self.step(f"{rec['id']}: stalled {silent // 60}m")
            try:
                eta_s = float(doc.get("eta_s") or 0)
            except (TypeError, ValueError):
                eta_s = 0.0
            if silent > 3 * eta_s and cur.get("stall_recorded") != cur.get("dispatched"):
                self.d.record("lane-stall", silent)
                cur["stall_recorded"] = cur.get("dispatched")
            self.items.put(cur)

    # -- d. finished worktrees
    def finished(self):
        """Plan 098: the tick never reviews inline. Each ran / committed item
        gets one detached `review <ID>` worker (gates in its own worktree,
        verifier, fix rounds, commit, merge), so independent items are gated
        in parallel and the tick stays short. The tick only launches, watches
        and reaps those workers."""
        now = self.d.clock()
        for rec in self.items.all().values():
            if rec.get("state") not in HOLD_STATES:
                continue
            if self.dry:
                self.step(f"{rec['id']}: would launch review")
                continue
            if rec.get("review_launch"):
                if self.review_alive(rec, now):
                    continue
                if not self.review_crashed(rec):
                    continue
            if rec["state"] == "ran":  # a committed item only merges: no spawn
                why = self.blocked()
                if why:
                    self.step(f"{rec['id']}: review waits: {why}")
                    continue
            self.launch_review(rec, now)

    def review_alive(self, rec, now):
        pid = rec.get("worker_pid")
        if pid:
            return bool(self.d.pid_alive(pid))
        launched = epoch_of(rec.get("review_launch"))
        return launched is not None and now - launched < REVIEW_START_S

    def review_crashed(self, rec):
        """A review worker that died (or never started): counted; True when it
        may be relaunched now. At MAX_ATTEMPTS the item is parked for a
        session: ran -> failed-dirty (retry_refused keeps the work as an
        unmerged WIP commit), committed -> merge-refused under its keep ref."""
        rec.pop("worker_pid", None)
        rec.pop("review_launch", None)
        n = rec.get("review_crashes", 0) + 1
        rec["review_crashes"] = n
        if n < MAX_ATTEMPTS:
            self.items.put(rec)
            self.step(f"{rec['id']}: review worker gone ({n}/{MAX_ATTEMPTS}), relaunch")
            return True
        rec["error"] = f"review worker died {n} times"
        if rec["state"] == "committed":
            self.keep(rec)
            rec["state"] = "merge-refused"
        else:
            rec["state"] = "failed-dirty"
        self.items.put(rec)
        self.step(f"{rec['id']}: {rec['error']}, parked {rec['state']}")
        return False

    def launch_review(self, rec, now):
        """The marker is written BEFORE the launch and the record is never
        written after it, so the tick never overwrites the worker's writes."""
        rec["review_launch"] = iso(now)
        rec.pop("worker_pid", None)
        self.items.put(rec)
        try:
            self.d.launch_review(rec["id"])
        except Exception as exc:  # noqa: BLE001 - OSError, ValueError: next tick retries
            cur = self.items.get(rec["id"]) or rec
            cur.pop("review_launch", None)
            cur["error"] = ascii_text(f"review launch: {type(exc).__name__}: {exc}", 300)
            self.items.put(cur)
            self.step(f"{rec['id']}: review launch failed ({type(exc).__name__})")
            return
        self.step(f"{rec['id']}: review worker launched")

    def dirty(self, wt):
        r = self.d.git(["status", "--porcelain"], wt)
        return r.returncode != 0 or bool(r.stdout.strip())

    # -- push
    def push_needed(self):
        """Commits main is ahead of origin/main (git only, no gates), 0 when
        there is nothing to push, main is not clean on main, no remote
        named origin exists, or the operator's loop_push switch is off."""
        if self.no_push or self.dry:
            return 0
        main, g = self.d.main_tree, self.d.git
        if g(["remote", "get-url", "origin"], main).returncode != 0:
            self.step("push skipped: local only")
            return 0
        if not loop_push_on(main):
            self.step("push skipped: loop push is off")
            return 0
        if g(["rev-parse", "--abbrev-ref", "HEAD"], main).stdout.strip() != "main" or \
                self.dirty(main):
            self.step("push skipped: main not clean")
            return 0
        ahead = g(["rev-list", "--count", "origin/main..main"], main).stdout.strip()
        return int(ahead) if ahead.isdigit() else 0

    def launch_push(self):
        """Plan 098: the tick never gates main itself; when main is ahead it
        launches ONE detached push worker (none while one is in flight)."""
        if not self.push_needed():
            return
        now, p = self.d.clock(), self.root / PUSH_WORKER_REL
        doc = read_json(p, {})
        if isinstance(doc, dict) and doc:
            pid, launched = doc.get("pid"), epoch_of(doc.get("launched"))
            if (pid and self.d.pid_alive(pid)) or (
                    not pid and launched is not None and now - launched < REVIEW_START_S):
                self.step("push worker in flight")
                return
        atomic_write(p, json.dumps({"launched": iso(now)}))
        try:
            self.d.launch_push()
        except Exception as exc:  # noqa: BLE001 - next tick retries
            with contextlib.suppress(OSError):
                p.unlink()
            self.step(f"push launch failed ({type(exc).__name__})")
            return
        self.step("push worker launched")

    def push(self):
        ahead = self.push_needed()
        if not ahead:
            return
        main, g = self.d.main_tree, self.d.git
        ok, detail = self.gate(main)  # plan 096: an already gated tree is not re-run
        if not ok:
            self.step("push skipped: gates red on main")
            return
        local = g(["rev-parse", "main"], main).stdout.strip()
        remote = g(["rev-parse", "origin/main"], main).stdout.strip()
        if not self.d.leak_pre_push(main, f"refs/heads/main {local} refs/heads/main {remote}"):
            self.step("push skipped: leak sweep HALT")
            return
        r = g(["push", "origin", "main"], main)
        self.pushed = r.returncode == 0
        self.step(f"push {'ok' if self.pushed else 'failed'}: {ahead} commit(s)")

    # -- g. checklist (FLEET item 13 d: remaining tasks only, kit rows)
    def checklist(self, rows, work, skipped):
        recs = self.items.all()
        now = self.d.clock()
        out, listed = [], set()
        self.checklist_dropped = 0  # plan 168: rows past the kit ROWS_MAX, counted

        def est(rec):
            """Item-kind median (item-<kind>), else the lane-run median
            (tools/al_lane records both), less the time already spent since
            dispatch; open items assume lane build."""
            e = self.d.estimate(f"lane-{rec.get('lane') or 'build'}-code")
            if rec.get("kind"):
                e = self.d.estimate(f"item-{rec['kind']}", default=e)
            if rec.get("state") in ("dispatched", "ran", "committed"):
                with contextlib.suppress(TypeError, ValueError):
                    e -= now - _dt.datetime.fromisoformat(rec.get("dispatched")).timestamp()
            return max(int(e), 0)

        def add(iid, title, state, eta_s):
            if len(out) >= self.d.checklist.ROWS_MAX:
                self.checklist_dropped += 1
                return
            if state:
                state = ascii_text(state, self.d.checklist.STATE_MAX)
            out.append(self.d.checklist.item(iid, ascii_text(" ".join(str(title).split()), 70)
                                             or iid, state, eta_s))

        def blocked_on(rec):
            return "blocked on " + ", ".join(rec.get("needs") or [])

        def shown(rec, state):
            """Plan 058 step 5: a resolve lane in flight reads `resolving, run n/2`;
            plan 098: a held item with a review worker in flight reads `reviewing`."""
            if rec.get("kind") == "resolve" and state in IN_FLIGHT:
                return f"resolving, run {rec.get('resolve_runs', 1)}/{MAX_ATTEMPTS}"
            if state in HOLD_STATES and rec.get("review_launch"):
                return "reviewing"
            return state

        def stalled(rec):
            """Plan 137: a silent dispatched lane reads `stalled, <n>m silent`."""
            if rec.get("state") == "dispatched" and rec.get("stalled_s"):
                return f"stalled, {int(rec['stalled_s']) // 60}m silent"
            return None

        for item in work:
            rec = recs.get(item["id"]) or {}
            state = rec.get("state", "open")
            listed.add(item["id"])
            if state in DONE_STATES:
                continue
            if state == "blocked":
                add(item["id"], item["title"], blocked_on(rec), None)
                continue
            if stalled(rec):
                add(item["id"], item["title"], stalled(rec), None)
                continue
            e = 0 if state in ATTENTION_STATES else est(rec)
            add(item["id"], item["title"], None if state == "open" else shown(rec, state), e)
        for h in skipped:  # plan 019: rows waiting on an open dependency
            if h.get("reason"):
                listed.add(h["id"])
                rec = recs.get(h["id"]) or {}
                add(h["id"], h["text"],
                    blocked_on(rec) if rec.get("state") == "blocked" else h["reason"], None)
        for iid, rec in sorted(recs.items()):
            if iid not in listed and rec.get("state") not in DONE_STATES:
                if rec.get("state") == "blocked":
                    add(iid, rec.get("title", ""), blocked_on(rec), None)
                    continue
                if stalled(rec):
                    add(iid, rec.get("title", ""), stalled(rec), None)
                    continue
                add(iid, rec.get("title", ""), shown(rec, rec.get("state")),
                    0 if rec.get("state") in ATTENTION_STATES else est(rec))
        for h in skipped:
            if not h.get("reason"):
                add(h["id"], h["text"], f"{h['skip']}-only, skipped", None)
        return out

    def status_parked(self, now):
        """Order Nd11eb1 item 3: the parked item and its age beside the kit's
        status fields (the kit owns the schema and rewrites the file on a spawn,
        so the next tick restores these). Nothing parked = the file is untouched."""
        extra = parked_status(parked_items(self.root, self.cfg["inbox_dir"], now))
        if not extra:
            return
        path = self.root / self.d.kit.STATUS_REL
        doc = read_json(path, None)
        if isinstance(doc, dict):
            atomic_write(path, json.dumps(dict(doc, **extra), indent=1))
        if extra.get("parked_warning"):
            self.step(extra["parked_warning"])

    def write(self, state, task, lines, started):
        if self.ignore_halt:  # AUTO-01: a dry run past HALT writes no record
            return {"state": state, "task": task, "log": self.log, "checklist": lines}
        now = self.d.clock()
        try:
            self.d.write_status(self.root, CODE, state, task, started, self.d.budget,
                                task_eta_s=None, next_tick=now + self.cfg["tick_s"])
            self.status_parked(now)
        except OSError:
            pass
        fire = fire_count(read_json(self.root / self.d.kit.PROGRESS_REL / f"{PROGRESS_TASK}.json"))
        took = round(max(now - started, 0), 1)
        if took > TICK_TARGET_S:  # plan 098: the tick target is under 60 s
            self.step(f"tick took {int(took)}s, target {TICK_TARGET_S}s")
        doc = {"task": PROGRESS_TASK, "pct": 100, "step": "; ".join(self.log)[-200:] or state,
               "eta_s": self.cfg["tick_s"], "status": "done", "updated": iso(now),
               "state": state, "fire": fire, "tick_s": took, "log": self.log[-40:],
               "checklist": lines,
               # plan 168: the overflow past the kit ROWS_MAX is never silent
               "checklist_dropped": self.checklist_dropped}
        atomic_write(self.root / self.d.kit.PROGRESS_REL / f"{PROGRESS_TASK}.json",
                     json.dumps(doc, indent=1))
        return doc

    def run(self):
        started = self.d.clock()
        bad_hooks = hooks_path_problem(self.root, self.d.git)
        if bad_hooks:
            self.step(bad_hooks)
        if not self.dry:  # plan 100: label pre-kit-v8 usage rows kind build
            n = usage_ledger.backfill_kind(self.root / self.d.kit.USAGE_REL)
            if n:
                self.step(f"usage rows backfilled kind build: {n}")
        self.reap_lost()
        if not self.dry:  # plan 138: cap the control ledgers once a local day
            res = self.d.rotate(self.root, self.d.clock())
            for line in ledger_rotate.lines(res) if res is not None else ():
                self.step(line)  # AUTO-23: summary, then any STALE line
            loop_steps.lines("work", self)  # AUTO-01: TC-DRIFT and later work steps
        self.stalls()
        if not self.blocked():
            self.inbox()
        else:
            self.step(f"spawning paused: {self.blocked()}")
        self.finished()
        self.retry_refused()
        self.settle_conflicts()
        self.recover_lane_dirty()
        rows, work, skipped = self.work_list()
        self.rearm(rows)
        self.dispatch(work)
        recs = self.items.all()
        in_flight = [r for r in recs.values() if r.get("state") in ("dispatched", "ran", "committed")]
        open_work = [w for w in work if dispatchable(recs.get(w["id"]), self.open_ids)]
        if not open_work and not in_flight:
            dd = self.deep_dive_item()
            if dd:
                work.append(dd)
                self.step("idle: deep-dive")
                self.dispatch([dd])
            elif getattr(self, "dive_backed_off", False):
                self.step("idle: deep-dive backed off to weekly (3 dives, 0 plans)")
            else:
                self.step("idle: deep-dive already done today")
        loop_steps.lines("post_work", self, rows, work, skipped)
        self.launch_push()
        lines = loop_steps.rows(self, self.checklist(rows, work, skipped))
        why = self.blocked()
        state = {"halted": "halted", "backoff": "backoff", "runs cap": "limit",
                 "budget unreadable": "refused"}.get(why, "running" if in_flight else "idle")
        task = f"{len(in_flight)} lanes" if in_flight else "Idle"
        return self.write(state, task, lines, started)


def _fire_of(doc):
    """A loop.json doc's fire count; 0 for a malformed doc or value (plan 149
    TOOLS-08: a bad loop.json never stops the tick write or the checklist)."""
    v = doc.get("fire") if isinstance(doc, dict) else None
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        return 0
    try:
        return max(int(v), 0)
    except (ValueError, OverflowError):
        return 0


def fire_count(prev):
    """This tick's fire number: the previous loop.json's plus one."""
    return _fire_of(prev) + 1


def handoff_session(text):
    """The `SESSION: <n>` counter of a hand-off file (CLAUDE.md loop rule 5), or None."""
    m = re.search(r"^SESSION:\s*(\d+)\b", text or "", re.M)  # AUTO-01: `SESSION: 7   (...)`
    return int(m.group(1)) if m else None


def render_checklist(doc, session=None):
    """The item-13 block for a loop.json doc: `Session <n> checklist`, one
    line per remaining task, then the /done line (kit fleet_checklist.render).
    n is the hand-off session counter when given (interactive session, FLEET
    item 13 a), else the tick's fire count (a headless fire uses its run count)."""
    cl = al_lane._load("fleet_checklist", "ops/fleet_kit/fleet_checklist.py")
    rows = doc.get("checklist") if isinstance(doc, dict) else None
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    n = session if session is not None else _fire_of(doc)
    return cl.render(n, rows)


def tick(dry_run=False, no_push=False, deps=None, ignore_halt=False):
    if ignore_halt and not dry_run:  # AUTO-01: past HALT only as a dry run
        raise ValueError("ignore_halt needs dry_run")
    d = deps or Deps()
    t = Tick(d, dry_run, no_push)
    t0, t.halted, t.ignore_halt = d.clock(), (d.root / HALT_REL).exists(), ignore_halt
    loop_steps.lines("pre_halt", t)  # 0044 docs watch: even HALTed, never dry
    if t.halted and not ignore_halt:
        t.step("HALT file present")
        return t.write("halted", "Halted", loop_steps.rows(t), t0)
    try:
        with d.lock(d.root / LOCK_REL):
            doc = t.run()
    except d.watch.LockBusy:
        return {"state": "busy"}
    if not dry_run:
        d.record("loop-tick", d.clock() - t0)
    return doc


# ---------------------------------------------------------------- lane worker

def lane_checklist(rec):
    """LANE-CHECKLIST (FLEET item 13 d): the dispatched item as the lane
    progress file's one remaining row; eta_s None = the lane's live ETA."""
    title = ascii_text(" ".join(str(rec.get("title") or rec.get("label")
                                    or rec["id"]).split()), 70)
    return [{"id": str(rec["id"]), "task": title or str(rec["id"]),
             "state": f"{rec.get('lane') or 'lane'} running", "eta_s": None}]


def lane_worker(iid, deps=None, run_lane=None):
    """The detached process for one dispatched item: one al_lane.run_lane call."""
    d = deps or Deps()
    items = Items(d.root)
    rec = items.get(iid)
    if not rec or rec.get("state") != "dispatched":
        return 0
    halt = d.root / HALT_REL

    def pause(why):
        # the dispatch never ran: give its attempt (and resolve run) back, the
        # tick re-dispatches
        rec.update(state="paused", error=f"paused: {why}",
                   attempts=max(rec.get("attempts", 1) - 1, 0))
        if rec.get("kind") == "resolve":
            rec["resolve_runs"] = max(rec.get("resolve_runs", 1) - 1, 0)
        items.put(rec)
        return 0

    why = spawn_block(d.root, d.budget, d.clock())  # may have changed since dispatch
    if why:
        return pause(why)
    if d.should_yield():  # kit v25: do not start this cycle; nothing is killed
        return pause("should_yield")
    run_lane = run_lane or al_lane.run_lane
    cfg = load_config(d.root)
    timeout = cfg["lane_timeout_s"]
    extra = {"extra": DEEP_EXTRA} if rec.get("kind") == "deep-dive" else {}
    # plan 099: model / effort by item kind, recorded on the item
    route = route_kw(cfg["routes"], route_kind(rec), f"lane-{rec['lane']}", d.pick_effort)
    rec["route"] = route

    def spawn(root, code, prompt, **kw):
        kw.update(extra, halt_file=halt)  # the kit refuses if HALT appears meanwhile
        if rec.get("kind") == "resolve":
            # plan 058: lanes have no git merge in their allow list, so the
            # worker starts the merge in the claimed (clean, main) worktree
            # and the lane only resolves; conflicts are the expected rc 1
            r = d.git(["merge", "--no-ff", "--no-commit", "-q", rec["keep_ref"]], kw["cwd"])
            if r.returncode != 0 and d.git(["rev-parse", "-q", "--verify", "MERGE_HEAD"],
                                           kw["cwd"]).returncode != 0:
                return {"rc": 1, "error": ascii_text(f"resolve merge refused: {r.stderr}",
                                                     300), "result": None}
        return d.spawn(root, code, prompt, **kw)

    try:
        line = run_lane(rec["lane"], rec["prompt"], writes_code=True, timeout=timeout,
                        root=d.root, spawn=spawn, eta_kind=f"item-{rec.get('kind') or 'plan'}",
                        sample_retry=rec.get("attempts", 1) > 1, sample_label=rec["id"],
                        checklist=lane_checklist(rec), **route)
    except Exception as exc:  # noqa: BLE001 - LaneRefused, Refused, OSError: all retryable
        text = f"{type(exc).__name__}: {exc}"
        if is_limit(text):
            backoff_hit(d.root, d.clock(), text)
        if halt.exists():
            return pause("halted")
        if "admission" in text.lower():  # kit v25: low RAM / high CPU, retry next tick
            return pause(ascii_text(text, 200))
        # a dirty lane worktree: retrying cannot clear it, so it waits without
        # burning attempts until the tick sees that tree clean and unheld
        state = "lane-dirty" if "dirty" in text.lower() else "refused"
        rec.update(state=state, error=ascii_text(text, 300))
        items.put(rec)
        return 1
    text = f"{line.get('error') or ''} {line.get('result') or ''}"
    if line.get("rc") != 0 and is_limit(text):
        backoff_hit(d.root, d.clock(), text)
    rec.update(state="ran", worktree=line.get("worktree"), rc=line.get("rc"),
               error=line.get("error"), finished=iso(d.clock()),
               result=result_line(line.get("result")))
    items.put(rec)
    return 0


# ---------------------------------------------------------------- plan 098 workers

def review_worker(iid, deps=None):
    """The detached process reviewing one ran / committed item: Tick.process
    (gates in its own worktree, verifier, fix rounds, commit, merge under the
    merge lock). It owns the record while it runs; markers are cleared only on
    a normal end, so a crash leaves its dead pid for the tick to count."""
    d = deps or Deps()
    items = Items(d.root)
    rec = items.get(iid)
    if not rec or rec.get("state") not in HOLD_STATES:
        return 0
    me, pid = os.getpid(), rec.get("worker_pid")
    if pid and pid != me and d.pid_alive(pid):
        return 0
    t0 = d.clock()
    rec["worker_pid"] = me
    items.put(rec)
    t = Tick(d)
    rc = 0
    try:
        t.process(rec)
    except Exception as exc:  # noqa: BLE001 - recorded; the dead pid is counted
        t.step(f"{iid}: review worker error {type(exc).__name__}: {exc}")
        rc = 1
    cur = items.get(iid) or rec
    if rc == 0 and cur.get("worker_pid") == me:
        cur.pop("worker_pid", None)
        cur.pop("review_launch", None)
    cur["review_log"] = (t.log or cur.get("review_log") or [])[-REVIEW_LOG_KEEP:]
    items.put(cur)
    d.record("loop-review", d.clock() - t0)
    return rc


def push_worker(deps=None):
    """The detached push: Tick.push (main clean, ahead, gates green on main,
    leak sweep) under the merge lock, so main cannot move while it gates."""
    d = deps or Deps()
    p = d.root / PUSH_WORKER_REL
    doc = read_json(p, {})
    doc = doc if isinstance(doc, dict) else {}
    me, pid = os.getpid(), doc.get("pid")
    if pid and pid != me and d.pid_alive(pid):
        return 0
    t0 = d.clock()
    atomic_write(p, json.dumps({"pid": me, "launched": doc.get("launched") or iso(t0)}))
    t = Tick(d)
    try:
        with d.lock(d.root / MERGE_LOCK_REL):
            t.push()
    except d.watch.LockBusy:
        t.step("push deferred: merge lock busy")
    finally:
        if (read_json(p, {}) or {}).get("pid") == me:
            with contextlib.suppress(OSError):
                p.unlink()
    atomic_write(d.root / PUSH_LAST_REL,
                 json.dumps({"finished": iso(d.clock()), "pushed": t.pushed, "log": t.log[-10:]}))
    d.record("loop-push", d.clock() - t0)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="AL loop tick")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tick")
    t.add_argument("--dry-run", action="store_true")
    t.add_argument("--no-push", action="store_true")
    t.add_argument("--ignore-halt", action="store_true", help="AUTO-01: with --dry-run only")
    sub.add_parser("checklist")
    ln = sub.add_parser("lane")
    ln.add_argument("item")
    rv = sub.add_parser("review", help="plan 098: (internal) review / fix / merge one item")
    rv.add_argument("item")
    sub.add_parser("push", help="plan 098: (internal) gate main and push")
    sub.add_parser("session", help="plan 091: orders routed to the session")
    sd = sub.add_parser("session-done", help="plan 091: mark a routed order done")
    sd.add_argument("item")
    sd.add_argument("--commit")
    a = ap.parse_args(argv)
    if a.cmd == "session":
        rows = [f"{o['id']} {o.get('note', '')} needs: {', '.join(o['needs'])}"
                for o in session_orders(ROOT)]
        print(ascii_text("\n".join(rows) or "none"))
        return 0
    if a.cmd == "session-done":
        rec = session_done(ROOT, a.item, a.commit)
        print(f"{a.item}: {'session-done' if rec else 'not a queued order'}")
        return 0 if rec else 2
    if a.cmd == "tick":
        if a.ignore_halt and not a.dry_run:
            ap.error("--ignore-halt is valid only with --dry-run")  # exit 2
        doc = tick(a.dry_run, a.no_push, ignore_halt=a.ignore_halt)
        print(ascii_text("\n".join([*(x for x in doc.get("log") or [] if ": would " in x),
                                    f"loop: {doc.get('state')}"]), 4000))
        return 0
    if a.cmd == "lane":
        return lane_worker(a.item)
    if a.cmd == "review":
        return review_worker(a.item)
    if a.cmd == "push":
        return push_worker()
    doc = read_json(ROOT / "ops/loop/control/progress/loop.json", {}) or {}
    try:  # FLEET item 13 a: an interactive session heads with the hand-off counter
        session = handoff_session((ROOT / f"{CODE}-NEXT-SESSION.txt").read_text(encoding="utf-8"))
    except OSError:
        session = None
    # kit v10: emit() never raises (a cp1252 console gets "[ ]", pythonw prints nothing)
    al_lane._load("fleet_checklist", "ops/fleet_kit/fleet_checklist.py").emit(render_checklist(doc, session))
    return 0


if __name__ == "__main__":
    sys.exit(main())
