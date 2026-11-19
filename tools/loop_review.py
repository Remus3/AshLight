"""AL loop review: the Tick's review, refute-round and commit methods as
ReviewMixin (LOOP-SPLIT-TICK, the plan 107 pattern of tools/loop_merge.py;
tools/al_loop.py re-exports every name here). Every side effect goes through
self.d (Deps). Stdlib only."""

import contextlib
from pathlib import Path

import al_lane
import lane_samples
from loop_base import (
    GATE_TIMEOUT_S, MARKER_RX, MAX_ROUNDS, NEED_RX, NOTE_HEAD, ROADMAP_REL, VERDICT_RX,
    VERIFY_EXTRA, _norm_path, ascii_text, epoch_of, read_json,
)
from loop_gatefail import foreign_only
from loop_inbox import missing_ordered
from loop_prompts import fix_prompt, verify_prompt
from loop_roadmap import commit_body, commit_subject, is_duplicate, plan_titles

ROUND_LOG_CAP = 2000  # plan 129: chars kept per finding in a round_log entry
ROUND_LOG_MAX_FINDINGS = 10


# ---------------------------------------------------------------- review and commit

class ReviewMixin:
    """d. a finished lane worktree: gates, verifier and fix rounds, the lane
    commit (salvaged under a keep ref when a hook refuses it). Needs the Tick's
    gate, spawn, route, blocked, step, dirty, merge, keep, orders and
    held_worktrees."""

    def process(self, rec):
        wt = Path(rec["worktree"])
        if rec["state"] in ("committed", "wave-hold"):
            # LOOP-WAVE-HOLD: a wave-held record only merges (merge re-checks
            # the hold and parks it again while the folder is still held)
            return self.merge(rec)
        if not wt.is_dir() or not self.dirty(wt):
            if rec.get("rc") == 0 and self.blocked_marker(rec, wt):
                return
            rec["state"] = "no-change" if rec.get("rc") == 0 else "lost"
            self.items.put(rec)
            self.step(f"{rec['id']}: {rec['state']}")
            return
        rounds = rec.get("rounds", 0)
        rec.pop("gate_foreign", None)
        while True:
            # plan 129: after fix round 3 the review is still labelled round 3
            rnd = min(rounds + 1, MAX_ROUNDS)
            ok, detail = self.gate(wt)
            findings = [] if ok else ["gates failed: " + detail]
            self.log_round(rec, rnd, "gates", findings)
            if not ok and self.park_foreign(rec, detail, wt):
                break
            extra = self.extra_checks(rec, wt)
            self.log_round(rec, rnd, "extra_checks", extra)
            findings += extra
            if not findings:
                # plan 129: a clean tree after fix round 3 still gets one
                # review-only verifier pass; no producer answer follows it
                if self.blocked():
                    return  # retry next tick
                note = f"lane-review-{rec['id']}"
                line = self.spawn(verify_prompt(rec, rnd, self.last_tree),
                                  note=note, **self.route("verify", note),
                                  writes_code=False, cwd=wt, extra=VERIFY_EXTRA, kind="build",
                                  governor="queued", governor_timeout=GATE_TIMEOUT_S,
                                  timeout=GATE_TIMEOUT_S)
                if not line:
                    return  # refused or usage limit: backoff / next tick retries
                if line.get("rc") != 0:
                    # a crashed verifier is no verdict, but it is counted: after
                    # MAX_ROUNDS of them the item waits for the adjudicator
                    rec["verify_errors"] = rec.get("verify_errors", 0) + 1
                    rec["error"] = ascii_text(f"verifier rc={line.get('rc')} "
                                              f"{line.get('error') or ''}", 300)
                    self.log_round(rec, rnd, "verifier", [rec["error"]], always=True)
                    self.items.put(rec)
                    self.step(f"{rec['id']}: verifier failed "
                              f"{rec['verify_errors']}/{MAX_ROUNDS}")
                    if rec["verify_errors"] < MAX_ROUNDS:
                        return
                    rec["verdict"] = "adjudicate"
                    break
                m = VERDICT_RX.findall(line.get("result") or "")
                if m and m[-1].upper() == "PASS":
                    rec["verdict"] = "PASS"
                    self.log_round(rec, rnd, "verifier", [], always=True)
                    break
                findings = [(line.get("result") or "no verdict line")[-6000:]]
                self.log_round(rec, rnd, "verifier", findings)
            if rounds >= MAX_ROUNDS:
                # after round 3 the adjudicator rules (CLAUDE.md rule 7): the
                # loop never self-accepts; the item waits unmerged for a session
                rec["verdict"] = "adjudicate"
                break
            if self.blocked():
                return
            rounds += 1
            rec["rounds"] = rounds
            self.items.put(rec)
            note = f"lane-build-{rec['id']}"
            # Order Nd11eb1 item 6: a fix round is a retry after a failure, sampled
            sampled = lane_samples.begin(self.d.main_tree, retry=True)
            line = self.spawn(fix_prompt(rec, rounds, findings), note=note,
                              **self.route("fix", note), writes_code=True, cwd=wt, extra=al_lane.CODE_EXTRA, kind="build",
                              governor="queued", governor_timeout=self.cfg["lane_timeout_s"],
                              timeout=self.cfg["lane_timeout_s"],
                              **({"session_id": sampled} if sampled else {}))
            lane_samples.finish(self.d.main_tree, sampled, rec["id"])
            if not line:
                return
        rec["rounds"] = rounds
        self.commit(rec, wt, ok)

    def park_foreign(self, rec, detail, wt):
        """LOOP-FAILED-PARK (F-024): a red gate whose failing tests all lie
        outside the lane's diff ends the fix rounds where they stand (round 0
        on the first gate): a fix round cannot repair a foreign break. The
        item is parked for a session (state adjudicate, WIP kept under a keep
        ref by commit()), never dropped. True when it parked."""
        ids = foreign_only(detail, self.changed_names(wt))
        if not ids:
            return False
        rec["gate_foreign"] = [ascii_text(i, 200) for i in ids[:20]]
        rec["verdict"] = "adjudicate"
        rec["error"] = ascii_text("gate failure outside the lane diff: " + ", ".join(ids), 300)
        self.step(f"{rec['id']}: gate failure outside the lane diff, parked "
                  f"after {rec.get('rounds', 0)} rounds")
        return True

    @staticmethod
    def log_round(rec, rnd, source, findings, always=False):
        """Plan 129: keep what each refute round found on the loop item, so an
        adjudicator reads it instead of reconstructing it. ASCII, each finding
        capped (its tail: a verifier's verdict and findings end its reply)."""
        if not findings and not always:
            return
        entry = {"round": rnd, "source": source,
                 "findings": [ascii_text(f)[-ROUND_LOG_CAP:]
                              for f in findings[:ROUND_LOG_MAX_FINDINGS]]}
        if rec.get("rounds", 0) >= MAX_ROUNDS:
            entry["final"] = True  # the review-only pass after fix round 3
        rec.setdefault("round_log", []).append(entry)

    def blocked_marker(self, rec, wt):
        """Plan 019 4a: True when this run's lane left a fresh `"status":
        "blocked"` progress marker (worktree first, then the main checkout)
        and the record is now blocked. Lane worktrees are reused, never
        cleaned, so a marker older than this run's dispatch is stale."""
        if rec.get("kind") != "plan":  # a resolve run is never a blocked plan
            return False
        rel = self.d.kit.PROGRESS_REL / f"p{rec['id']}-build.json"
        since = epoch_of(rec.get("dispatched"))
        for tree in (wt, self.d.main_tree):
            doc = read_json(Path(tree) / rel)
            if not isinstance(doc, dict) or doc.get("status") != "blocked":
                continue
            updated, needs = epoch_of(doc.get("updated")), doc.get("needs")
            if updated is None or not isinstance(needs, list) or not needs or \
                    not all(isinstance(n, str) and NEED_RX.match(n) for n in needs):
                self.step(f"{rec['id']}: malformed blocked marker ignored "
                          "(needs a row-id 'needs' list and a parsable 'updated')")
                continue
            if since is None or updated < since:
                self.step(f"{rec['id']}: stale blocked marker ignored")
                continue
            needs = list(dict.fromkeys(needs))
            rec.update(state="blocked", needs=needs,
                       blocked_runs=rec.get("blocked_runs", 0) + 1)
            self.items.put(rec)
            self.step(f"{rec['id']}: blocked on {', '.join(needs)}")
            return True
        return False

    def extra_checks(self, rec, wt):
        if rec.get("kind") == "resolve":
            return self.marker_checks(wt)
        if rec.get("kind") == "order":
            return self.order_checks(rec, wt)
        if rec.get("kind") != "deep-dive":
            return []
        main_titles = plan_titles(self.d.main_tree)
        new = {k: v for k, v in plan_titles(wt).items() if k not in main_titles}
        out = []
        cap = self.cfg["max_new_plans_per_day"]
        if len(new) > cap:
            out.append(f"{len(new)} new ROADMAP rows, cap is {cap} per day: "
                       f"keep the best {cap}")
        for k, title in sorted(new.items()):
            dup = is_duplicate(title, main_titles.values())
            if dup:
                out.append(f"row {k} '{title}' duplicates existing '{dup}': drop it")
        if not list((wt / "docs" / "research").glob(f"*-deep-dive-{rec['date']}.md")):
            out.append(f"missing docs/research/NNNN-deep-dive-{rec['date']}.md")
        return out

    def changed_names(self, wt):
        """Tracked changes vs HEAD plus untracked files of the lane worktree."""
        names = set()
        for args in (["diff", "HEAD", "--name-only", "-z"],
                     ["ls-files", "--others", "--exclude-standard", "-z"]):
            r = self.d.git(args, wt)
            if r.returncode == 0:
                names.update(n.replace("\\", "/") for n in r.stdout.split("\0") if n)
        return names

    def order_checks(self, rec, wt):
        """Plan 163: a FIX order whose ordered files are missing from the diff
        never reaches the verifier (keep-ref 9e52b0e passed with an empty app/
        diff). A file marked BLOCKED / NOT-APPLICABLE by path is exempt."""
        order = next((o for o in self.orders() if o["id"] == rec.get("id")), None)
        if order is None:
            return []
        name, text = order.get("note", ""), order.get("text", "")
        if self.fi.note_class(name, text[:NOTE_HEAD]) != "FIX":
            return []
        roadmap = Path(wt) / ROADMAP_REL
        road = roadmap.read_text(encoding="utf-8", errors="replace") \
            if roadmap.is_file() else ""
        miss = missing_ordered(text, self.changed_names(wt), road, order["id"],
                               lambda p: (Path(wt) / p).exists())
        return [f"FIX {order['id']}: ordered files missing from the diff: "
                f"{', '.join(miss)} - change them or mark each BLOCKED / "
                "NOT-APPLICABLE by path in the order's blocked-items section"] if miss else []

    def marker_checks(self, wt):
        """Plan 058: a resolve run must leave no conflict marker in any file it
        changed (the commit's `git add -A` would stage a marker as resolved)."""
        bad = []
        for name in sorted(self.changed_names(wt)):
            with contextlib.suppress(OSError):
                if MARKER_RX.search((Path(wt) / name).read_text(encoding="utf-8",
                                                                errors="replace")):
                    bad.append(name)
        return [f"conflict marker left in {', '.join(bad)}: resolve it"] if bad else []

    def commit(self, rec, wt, gates_ok):
        rounds = rec.get("rounds", 0)
        passed = rec.get("verdict") == "PASS"
        # the ROADMAP row is flipped in main at merge, never in the lane commit
        # (fix-0130: lane flips of adjacent rows collided on every parallel merge)
        # PUBREPO 1b: Conventional Commits subject; the label stays in the body
        foreign = not gates_ok and bool(rec.get("gate_foreign"))
        if foreign:
            head = commit_subject(rec, wip="gate failure outside the lane diff, adjudicate")
        elif not gates_ok:
            head = commit_subject(rec, wip="gates failed, not merged")
        elif not passed:
            head = commit_subject(
                rec, wip=f"no verifier PASS after {MAX_ROUNDS}/{MAX_ROUNDS}, adjudicate")
        else:
            head = commit_subject(rec)
        msg = (f"{head}{commit_body(rec)}"
               f"refute-rounds: {rounds}/{MAX_ROUNDS}\n"
               f"verifier: {rec.get('verdict', 'none')}\nloop item: {rec['id']}\n")
        rec["gates_ok"] = gates_ok  # a refused commit is salvaged with the same verdict
        r = self.d.git(["add", "-A"], wt)
        if r.returncode == 0:
            r = self.d.git(["commit", "-q", "-F", "-"], wt, input=msg)
        if r.returncode != 0:
            return self.commit_refused(rec, wt, r, msg)
        rec["commit"] = self.d.git(["rev-parse", "HEAD"], wt).stdout.strip()
        if not gates_ok or not passed:
            rec["state"] = "failed" if not gates_ok and not foreign else "adjudicate"
            # LOOP-FAILED-PARK: the WIP commit survives a re-claimed lane
            # worktree under refs/al/keep/<id> until a session rules on it
            self.keep(rec)
            self.items.put(rec)
            self.step(f"{rec['id']}: {rec['state']} after {rounds} rounds, WIP kept unmerged")
            return
        rec["state"] = "committed"
        self.items.put(rec)
        self.merge(rec)

    def commit_refused(self, rec, wt, r, msg):
        """fix-loop-stall: a refused lane commit (a pre-commit hook in the lane
        worktree, which runs the lane's own possibly stale tools) no longer
        parks staged work in the lane: the tree is kept as a commit under
        refs/al/keep/<id> and the worktree reset, so the dirty lowest lane
        index stops wedging every dispatch. Verified work then goes through
        merge(), whose main-side commit runs main's hooks over the same lines;
        anything else is failed, kept unmerged for a session."""
        why = ((r.stderr or "") + (r.stdout or "")).strip()
        rec["error"] = ascii_text(f"lane commit refused: {why[-260:]}", 300)
        if not self.salvage(rec, wt, msg):
            rec["state"] = "failed-dirty"
            self.items.put(rec)
            self.step(f"{rec['id']}: commit refused, salvage failed, worktree left dirty")
            return
        ok = rec.get("gates_ok") and rec.get("verdict") == "PASS"
        foreign = not rec.get("gates_ok") and bool(rec.get("gate_foreign"))
        rec["state"] = "committed" if ok else "adjudicate" if foreign else "failed"
        self.items.put(rec)
        self.step(f"{rec['id']}: lane commit refused, work kept under {rec['keep_ref']}, "
                  f"lane worktree reset")
        if ok:
            self.merge(rec)

    def salvage(self, rec, wt, msg):
        g = self.d.git
        if g(["add", "-A"], wt).returncode != 0:
            return False
        tree = g(["write-tree"], wt)
        if tree.returncode != 0:
            return False
        parents = ["-p", "HEAD"]
        mh = g(["rev-parse", "-q", "--verify", "MERGE_HEAD"], wt)
        if mh.returncode == 0 and mh.stdout.strip():
            parents += ["-p", mh.stdout.strip()]
        c = g(["commit-tree", tree.stdout.strip(), *parents, "-F", "-"], wt,
              input="salvaged (lane commit refused by hook): " + msg)
        if c.returncode != 0:
            return False
        rec["commit"] = c.stdout.strip()
        self.keep(rec)
        if not rec.get("keep_ref"):
            return False
        if mh.returncode == 0:
            g(["merge", "--abort"], wt)  # a resolve run's merge in progress
        return g(["reset", "-q", "--hard", "HEAD"], wt).returncode == 0

    def retry_refused(self):
        """fix-loop-stall backfill, idempotent: a failed-dirty record whose
        worktree still holds its staged work (and no other item's) re-runs
        commit(), which salvages it when the lane hook refuses again."""
        recs = self.items.all()
        for rec in recs.values():
            if rec.get("state") != "failed-dirty" or not rec.get("worktree"):
                continue
            wt = Path(rec["worktree"])
            others = self.held_worktrees({k: v for k, v in recs.items() if k != rec["id"]})
            if not wt.is_dir() or _norm_path(wt) in others or not self.dirty(wt):
                continue
            if self.dry:
                self.step(f"{rec['id']}: would retry the refused commit")
                continue
            self.commit(rec, wt, rec.get("gates_ok", rec.get("verdict") == "PASS"))
