"""AL loop merge: the gate-verdict cache and the Tick's merge into main as
MergeMixin (plan 107 split of tools/al_loop.py, which re-exports every name
here). Every side effect goes through self.d (Deps). Stdlib only.

LOOP-WAVE-HOLD (F-033, AUTO-06): a merge whose diff touches a folder a
session's wave holds (ops/loop/control/wave_owned.json) parks as wave-hold
and merges once the file is gone; a hold file older than 48 h is one
checklist row and is not obeyed. A wave's merge agent takes the loop's merge
lock with

    python tools/loop_merge.py hold [--root DIR] [--wait-s N] -- <command>

which waits for the lock (exit 3 when it stays busy past --wait-s), runs the
command under it and exits with the command's code.

LOOP-ADJUDICATE-MERGE: a record parked in state adjudicate (refute rounds
spent, gate-unknown, foreign red) is merged by a session, once ruled, with

    python tools/loop_merge.py adjudicate <ID> --ruling "<text>" [--root DIR]

which refuses a missing or blank ruling (exit 2), records the ruling on the
item, runs the loop's gates (gate verdict cache included) on the kept commit
in a temporary detached worktree under the AL sidecar Temp folder, and on
green merges it into main exactly as the loop does (merge lock, wave hold,
done file, kit git lock on the commit, `ruling:` line in the merge body).
Exit 0 merged, 1 red gates or a deferred / refused merge (the record stays
parked or moves to the loop's own merge state), 2 refused."""

import datetime as _dt
import importlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from loop_base import (
    GATE_CACHE_MAX, GATE_CACHE_REL, IN_FLIGHT, KEEP_REF, MAX_ROUNDS, MERGE_LOCK_REL,
    RED_TTL_S, RESOLVABLE, ROADMAP_REL, WAVE_HOLD_MAX_S, WAVE_HOLD_NOTICE_ID,
    WAVE_OWNED_REL, ascii_text, atomic_write, epoch_of, iso, read_json,
)
import roadmap
from loop_gatefail import keep_ids
from loop_roadmap import base_kind, commit_body, flip_roadmap, merge_subject, resolve_roadmap


# ---------------------------------------------------------------- wave hold

def _norm_prefix(p):
    """A held prefix as a repo-relative posix path without a trailing slash;
    '' for anything that is not a usable path."""
    if not isinstance(p, str):
        return ""
    p = p.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.strip("/")


def held_names(names, prefixes):
    """The names that lie under a held prefix: the prefix itself or a path
    below it (`tools` holds tools/x.py, never tools_extra/x.py)."""
    return [n for n in names
            if any(n == p or n.startswith(p + "/") for p in prefixes)]


def read_wave_hold(root, now):
    """None when no hold file exists, else {wave, prefixes, age_s, stale,
    why}. stale is True for a file older than WAVE_HOLD_MAX_S, one with no
    readable time (its age cannot be judged) or one that is not a hold
    document; a stale hold is reported, never obeyed."""
    path = Path(root) / WAVE_OWNED_REL
    if not path.exists():
        return None
    doc = read_json(path, None)
    if not isinstance(doc, dict) or not isinstance(doc.get("prefixes"), list):
        return {"wave": None, "prefixes": [], "age_s": None, "stale": True,
                "why": "unreadable"}
    prefixes = [q for q in (_norm_prefix(p) for p in doc["prefixes"]) if q]
    wave = doc.get("wave")
    wave = wave if isinstance(wave, int) and not isinstance(wave, bool) else None
    t = doc.get("time")
    if isinstance(t, (int, float)) and not isinstance(t, bool):
        ts = float(t)
    else:
        ts = epoch_of(t) if isinstance(t, str) else None
    if ts is None:
        return {"wave": wave, "prefixes": prefixes, "age_s": None, "stale": True,
                "why": "no readable time"}
    age = max(now - ts, 0.0)
    stale = age > WAVE_HOLD_MAX_S
    return {"wave": wave, "prefixes": prefixes, "age_s": age, "stale": stale,
            "why": f"{int(age // 3600)} h old" if stale else ""}


def _lock_path(root):
    """The loop's merge lock in the MAIN checkout of root (a linked worktree
    such as w<n>-int answers its main checkout's lock)."""
    import al_lane
    return al_lane.lanes().main_tree(root) / MERGE_LOCK_REL


def hold(cmd, root, wait_s=1800.0, poll_s=5.0, lock=None, busy=None,
         run=subprocess.call, sleep=time.sleep, clock=time.time, say=None):
    """Run cmd under the loop's merge lock (MERGE_LOCK_REL of root's main
    checkout) through the kit watch lock. A busy lock is retried every poll_s
    until wait_s has passed, then 3 is returned and cmd never runs. Returns
    cmd's exit code."""
    path = _lock_path(root)
    if lock is None or busy is None:
        import al_lane
        fw = al_lane._load("fleet_watch", "ops/fleet_kit/fleet_watch.py")
        lock = lock or fw.watch_lock
        busy = busy or fw.LockBusy
    end, told = clock() + max(float(wait_s), 0.0), False
    while True:
        try:
            with lock(path):
                return run(list(cmd))
        except busy as exc:
            if clock() >= end:
                if say:
                    say(f"merge lock busy past {int(wait_s)} s: {exc}")
                return 3
            if say and not told:
                say(f"merge lock busy ({exc}), waiting")
                told = True
            sleep(max(float(poll_s), 0.1))


# ---------------------------------------------------------------- gate verdicts

def _is_done_file(name):
    """True for a docs/roadmap/done/<ID>.md row file path (repo-relative)."""
    m = roadmap.PATH_RX.match(name)
    return bool(m) and m.group(1) == "done"


def last_lines(text, limit):
    """TEST-PLUGIN-PIN: the longest run of whole LAST lines of text within
    limit chars (the last limit chars when even the final line is longer).
    A red gate's ids and count line sit at the end of its output."""
    text = (text or "").rstrip()
    if len(text) <= limit:
        return text
    keep, size = [], -1
    for line in reversed(text.splitlines()):
        if size + 1 + len(line) > limit:
            break
        keep.append(line)
        size += 1 + len(line)
    return "\n".join(reversed(keep)) if keep else text[-limit:]


class GateCache:
    """Plan 096: gate verdicts by tree id, ops/loop/control/gate_verdicts.json
    in the main checkout, newest GATE_CACHE_MAX kept. Plan 098: written by
    parallel review workers and the push worker too; each write is atomic, a
    racing read-modify-write can only drop an entry (that tree is re-gated),
    never record a wrong verdict."""

    def __init__(self, root):
        self.path = Path(root) / GATE_CACHE_REL

    def _trees(self):
        doc = read_json(self.path, {})
        trees = doc.get("trees") if isinstance(doc, dict) else None
        return dict(trees) if isinstance(trees, dict) else {}

    def get(self, key, now):
        """The usable entry for key: green, or red younger than RED_TTL_S."""
        e = self._trees().get(key) if key else None
        if not isinstance(e, dict) or not isinstance(e.get("ok"), bool):
            return None
        if not e["ok"]:
            ts = epoch_of(e.get("ts"))
            if ts is None or now - ts > RED_TTL_S:
                return None
        return e

    def put(self, key, ok, detail, where, now, via=None, rerun=False):
        trees = self._trees()
        trees.pop(key, None)  # re-insert: dict order is recency
        # LOOP-TRUNC: the ids block survives the short cached tail
        e = {"ok": bool(ok), "detail": keep_ids(ascii_text(detail or ""), 300),
             "ts": iso(now),
             "where": ascii_text(where, 80)}
        if via:
            e["via"] = via
        if rerun:
            e["rerun"] = True  # LOOP-GATE-RERUN: this tree's one re-run is spent
        trees[key] = e
        keep = dict(list(trees.items())[-GATE_CACHE_MAX:])
        atomic_write(self.path, json.dumps({"trees": keep}, indent=1))
        return e

    def carry(self, src, dst, git, cwd, now):
        """Record dst green on src's green verdict when every name the two
        trees differ in is ROADMAP.md or a file under docs/roadmap/done/ (the
        loop's own row close at merge; LOOP-ROWFILES-MERGE). True if dst is
        green afterwards."""
        e = self.get(src, now) if src and dst else None
        if not e or not e["ok"]:
            return False
        if src == dst:
            return True
        r = git(["diff", "--name-only", src, dst], cwd)
        if r.returncode != 0:
            return False
        names = {n.strip() for n in (r.stdout or "").splitlines() if n.strip()}
        if not all(n == ROADMAP_REL.as_posix() or _is_done_file(n) for n in names):
            return False
        self.put(dst, True, e.get("detail"), "carry", now, via=src)
        return True


class MergeMixin:
    """Plan 107: mixed into al_loop.Tick. The Tick's merge into main, ROADMAP
    flip and kept commits."""

    def merge(self, rec):
        """Plan 098: every merge into main holds MERGE_LOCK_REL, whoever calls
        it (review worker, the tick's salvage path); a busy lock defers the
        merge and the item stays committed for the next worker."""
        try:
            with self.d.lock(self.root / MERGE_LOCK_REL):
                if self.wave_held(rec):
                    return None
                return self._merge(rec)
        except self.d.watch.LockBusy:
            self.step(f"{rec['id']}: merge lock busy, merge deferred")

    def wave_held(self, rec):
        """LOOP-WAVE-HOLD: True (record parked as wave-hold) when a live hold
        file names a prefix the item's diff touches. A stale hold is one
        checklist row (wave_hold_notice) and is not obeyed. An unreadable diff
        under a live hold parks too: the next tick re-checks."""
        hold = read_wave_hold(self.root, self.d.clock())
        self.wave_hold_notice(hold)
        if hold is None or hold["stale"] or not hold["prefixes"] or not rec.get("commit"):
            rec.pop("wave_hold", None)
            return False
        r = self.d.git(["diff", "--name-only", f"HEAD...{rec['commit']}"], self.d.main_tree)
        if r.returncode != 0:
            hit = ["(diff unreadable)"]
        else:
            names = [n.strip() for n in (r.stdout or "").splitlines() if n.strip()]
            hit = held_names(names, hold["prefixes"])
        if not hit:
            rec.pop("wave_hold", None)
            return False
        first = rec.get("state") != "wave-hold"
        rec["state"] = "wave-hold"
        rec["wave_hold"] = {"wave": hold["wave"],
                            "paths": [ascii_text(n, 120) for n in hit[:5]]}
        self.items.put(rec)
        if first:
            w = hold["wave"] if hold["wave"] is not None else "?"
            self.step(f"{rec['id']}: wave {w} holds {ascii_text(hit[0], 80)}, merge parked")
        return True

    def wave_hold_notice(self, hold):
        """The one checklist row of a stale hold file: an item record
        WAVE_HOLD_NOTICE_ID in state wave-hold-stale (no commit, no worktree,
        no row, so only the checklist reads it); dropped by the next merge
        that finds the file gone or fresh."""
        items = self.items
        cur = items.get(WAVE_HOLD_NOTICE_ID)
        if hold is not None and hold["stale"]:
            w = hold["wave"] if hold["wave"] is not None else "?"
            title = f"Remove stale wave {w} hold file ({hold['why']}), not obeyed"
            if not isinstance(cur, dict) or cur.get("title") != title:
                items.put({"id": WAVE_HOLD_NOTICE_ID, "kind": "notice",
                           "state": "wave-hold-stale", "title": title})
                if not isinstance(cur, dict):
                    self.step(f"wave hold file stale ({hold['why']}), not obeyed")
        elif cur is not None and items.drop(WAVE_HOLD_NOTICE_ID):
            self.step("stale wave hold notice cleared")

    def _merge(self, rec):
        main = self.d.main_tree
        br = self.d.git(["rev-parse", "--abbrev-ref", "HEAD"], main).stdout.strip()
        if br != "main" or self.dirty(main):
            self.step(f"{rec['id']}: main not clean on main, merge deferred")
            return
        g = self.d.git
        if g(["merge-base", "--is-ancestor", rec["commit"], "HEAD"], main).returncode == 0:
            # already in main (a crash after the merge commit): re-run is a no-op
            rec["state"] = "merged"
            self.drop_keep(rec)
            self.step(f"{rec['id']}: already merged")
            self.items.put(rec)
            return
        r = g(["merge", "--no-ff", "--no-commit", "-q", rec["commit"]], main)
        why, flipped_row = None, False
        if r.returncode != 0 and not self.resolve_roadmap_conflict(main):
            why = "merge conflict"
        done_rel = None
        if why is None and base_kind(rec) == "plan":
            # LOOP-ROWFILES-MERGE (F-029): the row closes with a done file
            # inside the merge commit; ROADMAP.md is never edited here (the
            # fold at /done writes it). A refused write (no such row, row
            # already done, done file already there) closes nothing and the
            # merge goes on, as a no-op flip did. A legacy numeric id (\d{3})
            # has no row-file form, so only it keeps the ROADMAP.md flip.
            rounds = rec.get("rounds", 0)
            date = _dt.datetime.fromtimestamp(self.d.clock()).strftime("%Y-%m-%d")
            note = f"loop; refute {rounds}/{MAX_ROUNDS} {rec.get('verdict', 'PASS')}"
            if roadmap.FILE_ID_RX.match(str(rec["id"])):
                try:
                    done_rel = roadmap.write_done(main, rec["id"], note, date=date)
                except (roadmap.RowFileError, OSError) as e:
                    self.step(f"{rec['id']}: no done file ({ascii_text(str(e), 120)})")
                if done_rel is not None:
                    flipped_row = True
                    if g(["add", "--", done_rel], main).returncode != 0:
                        why = "done file stage refused"
            else:
                rm = main / ROADMAP_REL
                try:
                    text = rm.read_text(encoding="utf-8")
                    flipped = flip_roadmap(text, rec["id"], f"done {date} ({note})")
                    if flipped != text:
                        atomic_write(rm, flipped)
                        if g(["add", ROADMAP_REL.as_posix()], main).returncode != 0:
                            why = "roadmap stage refused"
                        flipped_row = True
                except OSError:
                    pass
        state = "merge-conflict"
        if why is None:
            # PUBREPO 1b: `merge: <topic>`, never the lane / worktree name
            msg = (f"{merge_subject(rec)}{commit_body(rec)}"
                   f"refute-rounds: {rec.get('rounds', 0)}/{MAX_ROUNDS}\n")
            ruling = rec.get("ruling")
            if isinstance(ruling, dict) and ruling.get("text"):
                # LOOP-ADJUDICATE-MERGE: a session's ruling rides in the merge
                msg += f"ruling: {ascii_text(ruling['text'], RULING_MAX)}\n"
            c = g(["commit", "-q", "-F", "-"], main, input=msg)
            if c.returncode != 0:
                # main's own hook (leak sweep) refused clean merged content: a
                # resolve run would merge cleanly, change nothing and be refused
                # again, so it is parked for a session with the hook output
                why, state = "merge commit refused", "merge-refused"
                out = ((c.stderr or "") + (c.stdout or "")).strip()
                rec["error"] = ascii_text(f"main merge commit refused: {out[-260:]}", 300)
        if why:
            g(["merge", "--abort"], main)
            if done_rel is not None:
                # the abort may leave the new done file behind: main stays clean
                g(["rm", "-q", "--cached", "--ignore-unmatch", "--", done_rel], main)
                try:
                    (main / done_rel).unlink()
                except OSError:
                    pass
            rec["state"] = state
            self.keep(rec)
            self.step(f"{rec['id']}: {why}, aborted")
        else:
            rec["state"] = "merged"
            if flipped_row:  # plan 019 4c: when this row's done file was written
                rec["merged_at"] = iso(self.d.clock())
            self.drop_keep(rec)
            self.step(f"{rec['id']}: merged")
            self.carry_verdict(rec, main)
        self.items.put(rec)

    def carry_verdict(self, rec, main):
        """Plan 096: main's new tree inherits the lane tree's green verdict
        when the merge added only the ROADMAP row flip (main had not moved),
        so push() does not gate the same code twice."""
        g = self.d.git
        src = g(["rev-parse", f"{rec['commit']}^{{tree}}"], main)
        dst = g(["rev-parse", "HEAD^{tree}"], main)
        if src.returncode or dst.returncode:
            return
        src, dst = src.stdout.strip(), dst.stdout.strip()
        if src != dst and GateCache(self.root).carry(src, dst, g, main, self.d.clock()):
            self.step(f"{rec['id']}: gate verdict carried to main {dst[:12]}")

    def keep(self, rec):
        """Plan 058 step 1: point refs/al/keep/<id> at the unmerged commit in
        the main checkout; only a ref that was written is recorded."""
        ref = KEEP_REF + rec["id"]
        if rec.get("commit") and self.d.git(["update-ref", ref, rec["commit"]],
                                            self.d.main_tree).returncode == 0:
            rec["keep_ref"] = ref

    def drop_keep(self, rec):
        ref = rec.pop("keep_ref", None)
        if ref:
            self.d.git(["update-ref", "-d", ref], self.d.main_tree)

    def settle_conflicts(self):
        """Plan 058, idempotent, before dispatch: a merge-conflict whose commit
        is already in main (merged by hand) is merged and its ref dropped; one
        without a ref (recorded before plan 058) gets one if its commit still
        exists. Any other record drops its ref once that commit is in main
        (failed / adjudicate / gave-up keep theirs for a session)."""
        if self.dry:
            return
        g, main = self.d.git, self.d.main_tree
        for rec in self.items.all().values():
            state = rec.get("state")
            if state in IN_FLIGHT or not rec.get("commit"):
                continue
            if state != "merge-conflict" and not rec.get("keep_ref"):
                continue
            in_main = g(["merge-base", "--is-ancestor", rec["commit"], "HEAD"],
                        main).returncode == 0
            if in_main and state in RESOLVABLE:
                rec["state"] = "merged"
                self.drop_keep(rec)
                self.step(f"{rec['id']}: conflict merged by hand, ref dropped")
            elif state == "merge-conflict" and not rec.get("keep_ref"):
                self.keep(rec)
                if not rec.get("keep_ref"):
                    continue
                self.step(f"{rec['id']}: kept under {rec['keep_ref']}")
            elif state != "merge-conflict" and in_main:
                self.drop_keep(rec)
            else:
                continue
            self.items.put(rec)

    def resolve_roadmap_conflict(self, main):
        """True when the only unmerged path is ROADMAP.md and the row-level
        resolver settles it (staged); False leaves the merge for --abort."""
        g, rel = self.d.git, ROADMAP_REL.as_posix()
        u = g(["diff", "--name-only", "--diff-filter=U"], main)
        if u.returncode != 0 or u.stdout.split() != [rel]:
            return False

        def stage(n):
            s = g(["show", f":{n}:{rel}"], main)
            return s.stdout if s.returncode == 0 else ""

        out = resolve_roadmap(stage(1), stage(2), stage(3))
        if out is None:
            return False
        atomic_write(main / ROADMAP_REL, out)
        if g(["add", rel], main).returncode != 0:
            return False
        self.step("ROADMAP-only conflict auto-resolved by row")
        return True


# ---------------------------------------------------------------- adjudicate

RULING_MAX = 300
ADJUDICATE_STATE = "adjudicate"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def _gate_worktree(g, main, path, commit):
    """A fresh detached worktree of commit at path (a leftover from a crashed
    run at the same path is removed first). True when it was made."""
    path = Path(path)
    if path.exists():
        g(["worktree", "remove", "--force", str(path)], main)
    g(["worktree", "prune"], main)
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    return g(["worktree", "add", "-q", "--detach", str(path), commit],
             main).returncode == 0


def adjudicate_merge(t, iid, ruling, gate_dir=None):
    """LOOP-ADJUDICATE-MERGE: merge the kept commit of the adjudicate record
    iid on the session's ruling, through the Tick t (al_loop.Tick: its deps,
    items, gate cache and merge). Returns (rc, message): 0 merged, 1 red
    gates or a merge the loop deferred / refused, 2 refused before anything
    ran."""
    import al_lane
    text = ascii_text(ruling, RULING_MAX).strip() if isinstance(ruling, str) else ""
    if not text:
        return 2, f"{iid}: no ruling given (--ruling TEXT): refused"
    if not isinstance(iid, str) or not _SAFE_ID.match(iid):
        return 2, f"{ascii_text(str(iid), 80)}: not a loop item id: refused"
    d = t.d
    rec = t.items.get(iid)
    if not isinstance(rec, dict):
        return 2, f"{iid}: no loop record: refused"
    if rec.get("state") != ADJUDICATE_STATE:
        return 2, f"{iid}: state {rec.get('state')!r}, not adjudicate: refused"
    g, main = d.git, d.main_tree
    commit = rec.get("commit")
    if not commit or g(["cat-file", "-e", f"{commit}^{{commit}}"], main).returncode != 0:
        ref = rec.get("keep_ref")
        r = g(["rev-parse", "--verify", "-q", f"{ref}^{{commit}}"], main) if ref else None
        if r is None or r.returncode != 0 or not r.stdout.strip():
            return 2, f"{iid}: no kept commit to merge: refused"
        commit = rec["commit"] = r.stdout.strip()
    if gate_dir is None:
        tmp = al_lane.sidecar_temp()
        if tmp is None:
            return 2, f"{iid}: no AL sidecar Temp folder for the gate worktree: refused"
        gate_dir = tmp / f"adjudicate-{iid}"
    now = d.clock()
    rec["ruling"] = {"text": text, "at": iso(now)}
    t.items.put(rec)
    if not _gate_worktree(g, main, gate_dir, commit):
        rec["ruling"]["gates"] = "unknown: gate worktree not made"
        t.items.put(rec)
        return 1, f"{iid}: gate worktree not made, record stays adjudicate"
    try:
        al_lane.seed_config(gate_dir, root=main)
        ok, detail = t.gate(gate_dir)
    finally:
        g(["worktree", "remove", "--force", str(gate_dir)], main)
        g(["worktree", "prune"], main)
    rec = t.items.get(iid) or rec
    word = "green" if ok else "red"
    rec.setdefault("ruling", {"text": text, "at": iso(now)})
    rec["ruling"]["gates"] = keep_ids(ascii_text(f"{word}: {detail or ''}"), RULING_MAX)
    if not ok:
        t.items.put(rec)
        return 1, f"{iid}: gates red, record stays adjudicate: {ascii_text(detail, 200)}"
    rec["verdict"] = "RULED"
    t.items.put(rec)
    t.merge(rec)
    cur = t.items.get(iid) or rec
    state = cur.get("state")
    tail = "; ".join(t.log[-3:])
    if state == "merged":
        return 0, f"{iid}: merged on the ruling ({tail})"
    return 1, f"{iid}: not merged, state {state} ({tail})"


def _cli_tick(root):
    """The real Tick for the command line. Only this process's entry point
    reaches it (loop_merge.py runs as __main__, al_loop is not loaded yet),
    so no second copy of al_loop can diverge from a running tick's."""
    mod = importlib.import_module("al_loop")
    return mod.Tick(mod.Deps(Path(root)) if root else mod.Deps())


# ---------------------------------------------------------------- CLI

def main(argv=None):
    """`hold [--root DIR] [--wait-s N] [--poll-s N] -- <command...>` or
    `adjudicate <ID> --ruling TEXT [--root DIR]`."""
    args = list(sys.argv[1:] if argv is None else argv)
    usage = ("usage: loop_merge.py hold [--root DIR] [--wait-s N] [--poll-s N] "
             "-- <command...>\n"
             "       loop_merge.py adjudicate <ID> --ruling TEXT [--root DIR]")
    if args and args[0] == "adjudicate":
        return _main_adjudicate(args[1:], usage)
    if not args or args[0] != "hold" or "--" not in args:
        print(usage, file=sys.stderr)
        return 2
    i = args.index("--")
    opts, cmd = args[1:i], args[i + 1:]
    root, wait_s, poll_s = Path(__file__).resolve().parent.parent, 1800.0, 5.0
    try:
        while opts:
            key, val = opts.pop(0), opts.pop(0)
            if key == "--root":
                root = Path(val)
            elif key == "--wait-s":
                wait_s = float(val)
            elif key == "--poll-s":
                poll_s = float(val)
            else:
                raise ValueError(key)
    except (IndexError, ValueError):
        print(usage, file=sys.stderr)
        return 2
    if not cmd:
        print(usage, file=sys.stderr)
        return 2
    return hold(cmd, root, wait_s=wait_s, poll_s=poll_s,
                say=lambda s: print(f"loop_merge hold: {s}", file=sys.stderr))


def _main_adjudicate(args, usage):
    """`adjudicate <ID> --ruling TEXT [--root DIR]`: one command per ruled
    record (ZERO-CLICK)."""
    if not args or args[0].startswith("--"):
        print(usage, file=sys.stderr)
        return 2
    iid, opts, ruling, root = args[0], args[1:], None, None
    try:
        while opts:
            key, val = opts.pop(0), opts.pop(0)
            if key == "--ruling":
                ruling = val
            elif key == "--root":
                root = val
            else:
                raise ValueError(key)
    except (IndexError, ValueError):
        print(usage, file=sys.stderr)
        return 2
    if ruling is None:
        print(usage, file=sys.stderr)
        return 2
    rc, msg = adjudicate_merge(_cli_tick(root), iid, ruling)
    print(ascii_text(msg, 600), file=sys.stdout if rc == 0 else sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
