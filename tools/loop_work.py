"""AL loop work: the Tick's work list, lane choice and dispatch methods as
WorkMixin (LOOP-SPLIT-TICK, the plan 107 pattern of tools/loop_merge.py;
tools/al_loop.py re-exports every name here). Rows come through the loader
tools/roadmap.py (ROADMAP.md plus docs/roadmap/new|done/ files) and wait on
the `DEPENDS: <ids>` in their own text (LOOP-ROWFILES-WORK, F-029). A row
carrying BLOCKED is listed with its reason and never dispatched, and dispatch
re-reads a row from HEAD right before it launches (AUTO-06, decision 0055).
Every side effect goes through self.d (Deps). Stdlib only."""

import datetime as _dt
import re
from pathlib import Path

import al_lane
import roadmap
from loop_base import (
    BLOCKED_RX, CODE, DIRTY_WT_RX, HOLD_STATES, MAX_ATTEMPTS, _norm_path,
    ascii_text, epoch_of, iso,
)
from loop_inbox import order_prompt, order_settled, session_needs, settled_notes
from loop_prompts import deep_dive_prompt, handoff_prompt, plan_prompt
from loop_roadmap import (
    archived_rows, dependency_cycles, dispatchable, dive_backoff, dive_history, handoff_items,
    plan_titles, resolve_item, roadmap_flip_time,
)


# ---------------------------------------------------------------- BLOCKED reasons

BLOCKED_REASON_RX = re.compile(r"\bBLOCKED\b:?([^.]*)")
BLOCKED_REASON_MAX = 60
BLOCKED_DEFAULT = "operator act (see ROADMAP)"


def blocked_reason(text):
    """'BLOCKED: <reason>' for a tagged row: the text after 'BLOCKED:' up to
    the next full stop, at most BLOCKED_REASON_MAX characters (decision 0055:
    session wave <n>, session, operator act, gate); a bare BLOCKED keeps the
    old 'operator act (see ROADMAP)'. None for an untagged row."""
    m = BLOCKED_REASON_RX.search(text or "")
    if not m:
        return None
    why = " ".join(ascii_text(m.group(1)).split())
    if len(why) > BLOCKED_REASON_MAX:
        why = why[:BLOCKED_REASON_MAX - 3].rstrip() + "..."
    return f"BLOCKED: {why or BLOCKED_DEFAULT}"


def head_row(git, tree, iid):
    """Row iid as committed at HEAD of tree: HEAD:ROADMAP.md, then its
    docs/roadmap/new/<iid>.md file, with its docs/roadmap/done/<iid>.md mark
    applied (the composition of roadmap.load_rows, read through git show).
    None when HEAD cannot be read or holds no such row."""
    def show(rel):
        try:
            r = git(["show", f"HEAD:{rel}"], tree)
        except Exception:  # noqa: BLE001 - an unreadable HEAD is "no evidence"
            return None
        return r.stdout if r.returncode == 0 and isinstance(r.stdout, str) else None

    texts = [show(roadmap.ROADMAP_REL)]
    marks = {}
    if roadmap.FILE_ID_RX.match(iid):
        texts.append(show(f"{roadmap.NEW_REL}/{iid}.md"))
        line = (show(f"{roadmap.DONE_REL}/{iid}.md") or "").rstrip("\n")
        if roadmap.DONE_LINE_RX.match(line):
            marks[iid] = line
    for text in texts:
        if not text:
            continue
        for row in roadmap.roadmap_rows(roadmap._apply_done(text, marks)):
            if row["id"] == iid:
                return row
    return None


# ---------------------------------------------------------------- work list and dispatch

class WorkMixin:
    """c. the work list (orders, ROADMAP rows, hand-off items), the free lanes
    and the detached dispatch; e. the idle deep-dive item. Needs the Tick's
    blocked, step, dirty and orders."""

    def rearm(self, rows):
        """Plan 019 4c, once per record: a no-change plan whose own row is
        still open and one of whose DEPENDS rows closed after its dispatch
        ran against code that was not on main yet: blocked again. The close
        time is the record's merged_at, else the commit that flipped the row
        or added its done file (roadmap_flip_time). A dependency with no row
        is pending."""
        row_open = {r["id"]: r["open"] for r in rows}
        for rec in self.items.all().values():
            iid = rec["id"]
            if rec.get("state") != "no-change" or "rearmed" in rec or not row_open.get(iid):
                continue
            deps = self.plan_deps(iid, row_open, rows=rows)
            if not deps:
                continue
            since = epoch_of(rec.get("dispatched"))
            late, pending = [], []
            for dep in deps:
                if row_open.get(dep, dep not in self.closed_ids(rows)):
                    pending.append(dep)
                    continue
                flip = epoch_of((self.items.get(dep) or {}).get("merged_at"))
                if flip is None:
                    flip = epoch_of(roadmap_flip_time(self.d.git, self.d.main_tree, dep))
                if since is not None and flip is not None and flip > since:
                    late.append(dep)
            if pending and not late:
                continue  # decided once those rows flip
            if self.dry:
                self.step(f"{iid}: would {'re-arm' if late else 'settle no-change'}")
                continue
            if late:
                rec.update(state="blocked", needs=late + pending, rearmed=True)
                self.step(f"{iid}: re-armed, blocked on {', '.join(late + pending)}")
            else:
                rec["rearmed"] = False  # genuine no-change: never reconsidered
            self.items.put(rec)

    def plan_deps(self, iid, row_open, log=False, rows=None):
        """The DEPENDS: ids in row iid's own text (F-029: the row, never a
        plan doc or brief, is read), every one of them: an id with no row is
        a dependency too (it waits, visibly; the old fail-open rule ended
        with LOOP-ROWFILES-WORK). rows: the loaded rows (default: loaded
        through tools/roadmap.py from the main tree). row_open and log are
        kept for the call shape; a wait is shown by the work list."""
        if rows is None:
            rows = self.load_rows()
        row = next((r for r in rows if r["id"] == iid), None)
        if row is None:
            return []
        return list(row.get("depends") or roadmap.depends(row.get("text") or ""))

    def load_rows(self):
        """The main tree's rows through the loader (ROADMAP.md plus the
        docs/roadmap/new|done/ files); [] when they cannot be read."""
        try:
            return roadmap.load_rows(self.d.main_tree)
        except OSError:
            return []

    def closed_ids(self, rows):
        """Ids that count as done for a DEPENDS wait: the done rows, plus the
        rows tools/roadmap_fold.py archived (cached per tick)."""
        cached = getattr(self, "_archived_ids", None)
        if cached is None:
            try:
                cached = {r["id"] for r in archived_rows(self.d.main_tree)}
            except OSError:
                cached = set()
            self._archived_ids = cached
        return cached | {r["id"] for r in rows if not r["open"]}

    def row_waits(self, row, rows):
        """The wait reasons of an open row: one 'waits on <ids>' for its
        DEPENDS rows that are still open, one 'waits on <id> (no such row)'
        for each DEPENDS id that names no row (open, done or archived)."""
        row_open = {r["id"]: r["open"] for r in rows}
        closed = self.closed_ids(rows)
        deps = self.plan_deps(row["id"], row_open, rows=rows)
        open_deps = [d for d in deps if row_open.get(d)]
        unknown = [d for d in deps if d not in row_open and d not in closed]
        why = [f"waits on {', '.join(open_deps)}"] if open_deps else []
        why += [f"waits on {d} (no such row)" for d in unknown]
        return open_deps, why

    # -- c. work list
    def work_list(self):
        main = self.d.main_tree
        self._archived_ids = None  # re-read once per work list
        rows = self.load_rows()
        try:
            hand = handoff_items((main / f"{CODE}-NEXT-SESSION.txt").read_text(encoding="utf-8"))
        except OSError:
            hand = []
        # orders first, then ROADMAP rows whose status says "priority", then the rest
        open_rows = sorted((r for r in rows if r["open"]),
                           key=lambda r: "priority" not in r["status"].lower())
        # plan 058: resolve runs first, so a conflicting change is folded into
        # main before more lanes build on stale main; each replaces its own row
        work = [resolve_item(rec) for rec in self.items.all().values()
                if rec.get("keep_ref") and (rec.get("state") == "merge-conflict" or (
                    rec.get("kind") == "resolve"
                    and rec.get("state") in ("refused", "lost", "paused")))]
        resolving = {w["id"] for w in work}
        skipped = []
        settled = settled_notes(self.root)
        for o in self.orders():
            if o["id"] in resolving:
                continue
            rec = self.items.get(o["id"])
            if order_settled(o, rec, settled) and not rec:
                continue  # answered by hand: never re-run, never listed
            hits = session_needs(o, rec)
            if hits:  # plan 091 / 161: never a lane item; the session carries it out
                if not order_settled(o, rec, settled):
                    skipped.append({"id": o["id"], "text": o["title"], "skip": "session",
                                    "reason": "session: needs " + ", ".join(hits)})
                continue
            work.append({"id": o["id"], "kind": "order", "title": o["title"],
                         "note": o["note"], "label": f"order {o['id']}: {o['title']}",
                         "prompt": order_prompt(o)})
        # plan 019 / F-029: a row whose DEPENDS: names an open row, or an id
        # with no row at all, waits (skipped, shown, never dispatched)
        row_open = {r["id"]: r["open"] for r in rows}
        self.open_ids = {iid for iid, is_open in row_open.items() if is_open}
        waiting = {}
        for r in open_rows:
            if r["id"] in resolving:
                continue
            if BLOCKED_RX.search(r.get("text") or ""):
                skipped.append({"id": r["id"], "text": r["title"], "skip": "blocked",
                                "reason": blocked_reason(r.get("text"))})
                continue
            wait, why = self.row_waits(r, rows)
            if wait:
                waiting[r["id"]] = wait
            if why:
                skipped.append({"id": r["id"], "text": r["title"], "skip": "waits",
                                "reason": "; ".join(why)})
            else:
                work.append({"id": r["id"], "kind": "plan", "title": r["title"],
                             "text": r.get("text") or r["title"],
                             "lane_hint": r.get("lane"),
                             "label": f"row {r['id']}: {r['title']}"})
        for cycle in dependency_cycles(waiting):
            self.step(f"dependency cycle: {' -> '.join(cycle)}")
        for h in hand:
            if h["skip"]:
                skipped.append(h)
            elif h["id"] not in resolving:
                work.append({"id": h["id"], "kind": "handoff", "text": h["text"],
                             "title": h["text"], "label": f"hand-off {h['id']}"})
        return rows, work, skipped

    @staticmethod
    def held_worktrees(recs):
        return {_norm_path(r["worktree"]) for r in recs.values()
                if r.get("state") in HOLD_STATES and r.get("worktree")}

    def worktree_unusable(self, wt, held):
        """A lane worktree the kit would refuse (dirty) or that holds another
        item's unmerged work. A missing one is usable: the kit creates it."""
        return _norm_path(wt) in held or (Path(wt).is_dir() and self.dirty(wt))

    def free_lanes(self):
        """Lane names safe to dispatch now. Read fresh at dispatch time, lane
        locks first, then records: a worker that finished mid-tick is "ran"
        and still holds its worktree (fix 2026-10-05). The kit claims the
        LOWEST non-RUNNING index, not a named one, so slots stop at the first
        such index whose worktree is dirty or held (the claim would refuse)."""
        by_index = {r.get("index"): r for r in self.d.lane_state()}
        rows = [by_index.get(i) or {"index": i, "state": "FREE", "lane": None}
                for i in range(self.d.lane_cap())]  # no lock row: a FREE index
        recs = self.items.all()
        running = {r["lane"] for r in rows if r["state"] == "RUNNING"}
        busy = running | {r.get("lane") for r in recs.values()
                          if r.get("state") in ("dispatched",) + HOLD_STATES}
        names = [n for n in al_lane.LANES if n not in busy]
        held = self.held_worktrees(recs)
        # dispatched but not yet claimed: those take the lowest free indexes
        unclaimed = sum(1 for r in recs.values()
                        if r.get("state") == "dispatched" and r.get("lane") not in running)
        slots = 0
        for row in rows:
            if row["state"] == "RUNNING":
                continue
            if unclaimed:
                unclaimed -= 1
                continue
            if self.worktree_unusable(self.d.lane_worktree(row["index"]), held):
                break
            slots += 1
        return names[:slots]

    def recover_lane_dirty(self):
        """A lane-dirty record whose refused worktree (named in its error) is
        now clean and holds no ran / committed item's work goes back to
        "refused": dispatchable, attempts kept, so MAX_ATTEMPTS still bounds
        it (out of attempts: gave-up). A still-dirty tree (a crashed run) keeps
        it waiting; no worktree in the error keeps it as is. Idempotent."""
        recs = self.items.all()
        held = self.held_worktrees(recs)
        for rec in recs.values():
            if rec.get("state") != "lane-dirty":
                continue
            m = DIRTY_WT_RX.search(rec.get("error") or "")
            if not m or self.worktree_unusable(Path(m.group(1)), held):
                continue
            if self.dry:
                self.step(f"{rec['id']}: would clear lane-dirty")
                continue
            if rec.get("attempts", 0) >= MAX_ATTEMPTS:
                rec["state"] = "gave-up"
                self.step(f"{rec['id']}: gave up after {rec.get('attempts', 0)} attempts: "
                          f"{rec.get('error')}")
            else:
                rec.update(state="refused",
                           error=ascii_text(f"lane-dirty cleared: {rec.get('error')}", 300))
                self.step(f"{rec['id']}: lane-dirty cleared, {Path(m.group(1)).name} clean")
            self.items.put(rec)

    def row_taken(self, item):
        """Decision 0055: why a plan row listed by the work list must not be
        dispatched now, else None. Re-read under the tick lock right before
        the dispatch: the row as committed at HEAD (a session claims a row by
        committing its BLOCKED tag first), then the main tree's rows through
        the loader; a BLOCKED tag or a close in either one wins. A HEAD that
        cannot be read, or holds no such row, is no evidence either way."""
        if item.get("kind") != "plan":
            return None
        iid = item["id"]
        fresh = [head_row(self.d.git, self.d.main_tree, iid)]
        fresh.append(next((r for r in self.load_rows() if r["id"] == iid), None))
        for where, row in zip(("HEAD", "main tree"), fresh):
            if row is None:
                continue
            why = blocked_reason(row.get("text"))
            if why:
                return f"{why} (at {where})"
            if not row["open"]:
                return f"closed (at {where})"
        return None

    def dispatch(self, work):
        free = self.free_lanes()
        for item in work:
            if not free:
                break
            rec = self.items.get(item["id"])
            if not dispatchable(rec, self.open_ids):
                continue
            taken = self.row_taken(item)
            if taken:  # tagged or closed since the work list: never worked twice
                self.step(f"{item['id']}: not dispatched, {taken}")
                continue
            pick = item.get("lane_hint") if item.get("lane_hint") in free else free[0]
            if self.dry:
                free.remove(pick)
                self.step(f"{item['id']}: would dispatch to lane {pick}")
                continue
            why = self.blocked()
            if why:
                self.step(f"dispatch paused: {why}")
                return
            if self.d.should_yield():  # kit v25: cycle boundary, never a kill
                self.step("dispatch paused: should_yield (another tree waits for a slot)")
                return
            lane = pick
            free.remove(lane)
            prompt = {"plan": plan_prompt, "handoff": handoff_prompt}.get(item["kind"])
            prompt = item.get("prompt") or prompt(item)
            # plan 019: the blocked-run count and the one-time re-arm survive a dispatch
            keep = {k: rec[k] for k in ("blocked_runs", "rearmed") if rec and k in rec}
            # plan 058: a resolve run starts its own attempt count at a conflict
            attempts = 0 if rec and rec.get("state") == "merge-conflict" else \
                (rec or {}).get("attempts", 0)
            new = dict(item, **keep, state="dispatched", lane=lane, prompt=prompt,
                       attempts=attempts + 1, rounds=0, dispatched=iso(self.d.clock()))
            if item["kind"] == "resolve":
                new["resolve_runs"] = item.get("resolve_runs", 0) + 1
            self.items.put(new)
            try:
                new["pid"] = self.d.launch(item["id"])
            except Exception as exc:  # noqa: BLE001 - OSError, ValueError: retryable
                new.update(state="lost", error=ascii_text(f"launch: {type(exc).__name__}: "
                                                          f"{exc}", 300))
                self.items.put(new)
                free.insert(0, lane)
                self.step(f"{item['id']}: launch failed ({type(exc).__name__})")
                continue
            self.items.put(new)
            self.step(f"{item['id']}: dispatched to lane {lane}")

    # -- e. idle mode
    def deep_dive_item(self):
        date = _dt.datetime.fromtimestamp(self.d.clock()).strftime("%Y%m%d")
        iid = f"DD-{date}"
        if self.items.get(iid) and not dispatchable(self.items.get(iid)):
            return None
        if list((self.d.main_tree / "docs" / "research").glob(f"*-deep-dive-{date}.md")):
            return None
        # W44: weekly after 3 dives in a row proposed 0 plans; any plan resets
        today = _dt.datetime.fromtimestamp(self.d.clock()).date()
        if dive_backoff(dive_history(self.d.main_tree, self.d.git), today):
            self.dive_backed_off = True
            return None
        prompt = deep_dive_prompt(self.d.main_tree, date, self.cfg["max_new_plans_per_day"],
                                  plan_titles(self.d.main_tree))
        return {"id": iid, "kind": "deep-dive", "date": date, "title": "idle deep-dive",
                "label": f"deep-dive {date}", "prompt": prompt}
