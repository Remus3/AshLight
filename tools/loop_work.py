"""AL loop work: the Tick's work list, lane choice and dispatch methods as
WorkMixin (LOOP-SPLIT-TICK, the plan 107 pattern of tools/loop_merge.py;
tools/al_loop.py re-exports every name here). Every side effect goes through
self.d (Deps). Stdlib only."""

import datetime as _dt
from pathlib import Path

import al_lane
from loop_base import (
    BLOCKED_RX, CODE, DIRTY_WT_RX, HOLD_STATES, MAX_ATTEMPTS, ROADMAP_REL, _norm_path,
    ascii_text, epoch_of, iso,
)
from loop_inbox import order_prompt, order_settled, session_needs, settled_notes
from loop_prompts import deep_dive_prompt, handoff_prompt, plan_prompt
from loop_roadmap import (
    dependency_cycles, dispatchable, dive_backoff, dive_history, handoff_items, plan_depends,
    plan_doc, plan_titles, resolve_item, roadmap_flip_time, roadmap_rows,
)


# ---------------------------------------------------------------- work list and dispatch

class WorkMixin:
    """c. the work list (orders, ROADMAP rows, hand-off items), the free lanes
    and the detached dispatch; e. the idle deep-dive item. Needs the Tick's
    blocked, step, dirty and orders."""

    def rearm(self, rows):
        """Plan 019 4c, once per record: a no-change plan whose own row is
        still open and one of whose Depends-on rows flipped [x] after its
        dispatch ran against code that was not on main yet: blocked again."""
        row_open = {r["id"]: r["open"] for r in rows}
        for rec in self.items.all().values():
            iid = rec["id"]
            if rec.get("state") != "no-change" or "rearmed" in rec or not row_open.get(iid):
                continue
            deps = self.plan_deps(iid, row_open)
            if not deps:
                continue
            since = epoch_of(rec.get("dispatched"))
            late, pending = [], []
            for dep in deps:
                if row_open[dep]:
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

    def plan_deps(self, iid, row_open, log=False):
        """Depends-on ids of plan iid that have a ROADMAP row; a missing doc or
        an unknown id is no dependency (fail open: a typo never wedges the
        queue)."""
        text = plan_doc(self.d.main_tree, iid)
        if text is None:  # AL: a row's plan doc is optional; no doc, no gate, no log
            return []
        out = []
        for dep in plan_depends(text):
            if dep in row_open:
                out.append(dep)
            elif log:
                self.step(f"{iid}: depends on {dep}: no ROADMAP row, ignored")
        return out

    # -- c. work list
    def work_list(self):
        main = self.d.main_tree
        try:
            rows = roadmap_rows((main / ROADMAP_REL).read_text(encoding="utf-8"))
        except OSError:
            rows = []
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
        # plan 019: a row whose plan doc depends on an open row waits (skipped)
        row_open = {r["id"]: r["open"] for r in rows}
        self.open_ids = {iid for iid, is_open in row_open.items() if is_open}
        waiting = {}
        for r in open_rows:
            if r["id"] in resolving:
                continue
            if BLOCKED_RX.search(r.get("text") or ""):
                skipped.append({"id": r["id"], "text": r["title"], "skip": "blocked",
                                "reason": "BLOCKED: operator act (see ROADMAP)"})
                continue
            wait = [dep for dep in self.plan_deps(r["id"], row_open, log=True)
                    if row_open[dep]]
            if wait:
                waiting[r["id"]] = wait
                skipped.append({"id": r["id"], "text": r["title"], "skip": "waits",
                                "reason": f"waits on {', '.join(wait)}"})
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

    def dispatch(self, work):
        free = self.free_lanes()
        for item in work:
            if not free:
                break
            rec = self.items.get(item["id"])
            if not dispatchable(rec, self.open_ids):
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
