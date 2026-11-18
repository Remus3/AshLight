# 08 - Orchestration

Date: 2026-11-18. Ultraplan plan section (docs/plan/README.md).
Status: final

How a normal session runs one wave of docs/plan/packages.json, hands-off,
under CLAUDE.md. Inputs: docs/plan/07-execution-plan.md (the plan; where
this file and 07 differ, 07 wins), docs/plan/packages.json,
tools/plan_check.py, CLAUDE.md, research 0047 (ledger rule), 0049 (merge
batches), 0058 (loop and watchers), decision 0012 and tools/wt_sidecar_hook.py,
tools/al_loop.py, tools/al_lane.py, the kit helpers under ops/fleet_kit
(read, never edited), .claude/agents, .claude/commands/done.md and the git
history of sessions 1 to 5.

What earlier sessions did (git log): each agent ran in a harness worktree
on a branch `worktree-agent-<id>`, main was merged into the branch, the
branch was merged into main with a `merge: ...` commit, and every merge
paid about two whole suites (research 0049 F5: 2.03 suite runs a merge,
7.5 to 9.3 merges an hour). The wave procedure keeps the branch-per-agent
shape and changes two things: the worktrees live under the AL sidecar, and
a package runs only its named tests while one whole suite runs per merge
batch on an integration worktree.

## Rules that hold in every section

- The main session only dispatches, monitors and reports (CLAUDE.md, FLEET
  COMMON box). Every command in this file is run by a sub-agent. The main
  session's tools here are Agent, SendMessage, the Workflow tool (section
  10) and, for a kill at 3x, the stop of that one agent.
- Owner id. Each agent uses its own: `<session id>.<agent id>`. It reads it
  from the denial text of this call, which the claims hook refuses before
  anything runs:

      python ops/fleet_kit/fleet_gitlock.py run --owner probe -- git commit --dry-run .

  The text names the full id. The agent types it literally as `<OWNER>` in
  every later `fleet_gitlock.py run`, `fleet_suite_gate.py run` and
  `fleet_claims.py release` call.
- Final progress write (F-198). The last progress write of a task carries
  the outcome in its step text, `done: <result>` or `failed: <cause>`, not
  the last working step.
- Ledger rule (F-017). A package never edits the integrator files:
  ROADMAP.md, CLAUDE.md, AL-NEXT-SESSION.txt, docs/decisions/README.md,
  docs/research/README.md, docs/plan/README.md and docs/design/reviews.log.
  It returns its row flip, review line, Settled line and index line in its
  result and the wave integrator applies them (section 6). reviews.log and
  the two docs README indexes merge with `merge=union` once LOOP-LEDGERS
  (wave 1) is on main; ROADMAP.md never does. Decision numbers are the
  reserved ones (07, Reserved decision numbers; a package's number is in
  its new_files entry); no package writes a new research note, and no
  agent takes "the next number" of either series.
- Loop and wave: the loop and a session never take the same row (section 8
  states the six points and the HALT removal point).
- Game ToS floor (CLAUDE.md): no agent starts the app, the core, the
  overlay or the loop, reads the live Client.txt or sends input anywhere.
  The stricter reading wins; a doubt goes to the adjudicator, which cannot
  lift the floor.
- Git: never force, never rewrite. No `--amend`, `--no-verify`, `push`,
  `rebase`, `reset`, `stash`, `clean`, `git add -A` or `commit -a`; no
  branch switch in the main checkout, which stays on main. Commits name
  their paths. Exit 3 from a kit helper or an index.lock error: wait 30 to
  60 s and retry. No AI or bot attribution (FLEET item 17).
- Heavy commands (a whole suite, a gated subset) run at low priority so
  play is not disturbed; from the PowerShell tool:

      (Get-Process -Id $PID).PriorityClass = 'BelowNormal'; <command>

- A command named below with "once <PACKAGE> is on main" does not exist
  before that package lands; the agent reads the tool's own usage text
  before the first use.

## 1. Start of a wave session

The operator types `continue`. The main session dispatches ONE start agent
(background, sonnet, effort low, task `w-start`) and prints what it
returns. The start agent, in this order:

1. Reads AL-NEXT-SESSION.txt (the `SESSION: <n>` line, the wave pointer,
   every `DEFERRED:` line, operator records), CLAUDE.md, ROADMAP.md and
   `git log -10`; triages `moon_sync_inbox/` with `fleet_inbox.classify()`
   (free; ANSWER / ACK / INFORMATION / TERMINAL notes are recorded, never
   answered; an ORDER / FIX / RULING note becomes a checklist row); runs
   the hand-off's `Session start checks` (today: whether
   ops/runtime/ggg_docs/REG_OPEN exists) and returns what they found.
2. Checks the ground: `git status --short` prints nothing and
   `git branch --show-current` prints `main` in the main checkout;
   `python ops/fleet_kit/fleet_checklist.py stale` exits 0 (it prints
   `stale: none`, or one line per OVERRUN or STALE row; exit 3 means a
   STALE row: section 3 first; an OVERRUN line of another task is
   reported, not acted on); `git worktree list` names leftover wave
   worktrees (`w<n>-...`), which are reused, never deleted.
3. Validates the plan: `python tools/plan_check.py check` prints
   `plan_check: ok <n> packages, <w> waves`.
4. Finds the open wave. The hand-off line

       WAVE POINTER: wave <n> done, next wave <n+1>

   is the claim; the ROADMAP rows decide. For the pointer's next wave this
   prints the session packages that are neither flipped nor carried. A
   row is flipped when ROADMAP.md holds `- [x] <ID> ` or, once AUTO-03 is
   on main, when docs/roadmap/done/<ID>.md exists (the done file marks
   the row done until /done folds it into ROADMAP.md, section 6); a
   carried package is one named by a `DEFERRED:` line of the hand-off:

       python -c "import json,os,re,subprocess,sys; w=json.loads(subprocess.run([sys.executable,'tools/plan_check.py','wave',sys.argv[1],'--json'],capture_output=True,text=True,check=True).stdout); t=open('ROADMAP.md',encoding='ascii').read(); d=set(re.findall(r'(?m)^DEFERRED: (\S+) ',open('AL-NEXT-SESSION.txt',encoding='ascii').read())); f=lambda i: re.search(r'(?m)^- \[x\] '+re.escape(i)+' ',t) or os.path.exists('docs/roadmap/done/'+i+'.md'); print(' '.join(p['id'] for p in w['packages'] if p.get('owner')!='loop' and p['id'] not in d and not f(p['id'])) or 'none open')" <n>

   `none open` moves on to wave n+1. The first wave that prints ids is the
   open wave; the session resumes at its first unmerged package (a flipped
   row on main is a merged package, because the flip rides in the merge
   batch, section 6). Carried packages are the ids of the `DEFERRED:`
   lines whose row is not flipped; they join this dispatch (section 3).
   Without the carried-id exclusion a deferred package would hold its
   wave open for ever.
5. Reads which waves this `continue` runs: the session group that holds
   the open wave.

       python -c "import json,sys; s=json.load(open('docs/plan/packages.json',encoding='utf-8'))['sessions']; print(next(x['waves'] for x in s if int(sys.argv[1]) in x['waves']))" <n>

6. Checks the operator gates (section 9) and, from wave 5 on, writes the
   folder hold (section 8).
7. Renders the item-13 checklist through the kit, never by hand: one row
   per carried id, then one row per open id of step 4 in merge order,
   then MERGE, INTEGRATE and CLOSE, then one row per later wave of this
   session's group (`W<m>: Run wave <m>`):

       python -c "import json,sys; sys.path.insert(0,'ops/fleet_kit'); import fleet_checklist as c; d=json.load(open('docs/plan/packages.json',encoding='utf-8')); ps={p['id']:p for p in d['packages']}; w=int(sys.argv[2]); g=next(x['waves'] for x in d['sessions'] if w in x['waves']); rows=[c.item(i,ps[i]['title']) for i in sys.argv[3:]]+[c.item('MERGE','Merge the wave in merge order, batch suites green'),c.item('INTEGRATE','Apply the integrator edits per batch'),c.item('CLOSE','Close the wave: gates, leak sweep, hand-off pointer')]+[c.item('W%d'%m,'Run wave %d'%m) for m in g if m>w]; c.emit(c.render(int(sys.argv[1]),rows,cap=True))" <session n> <wave n> <carried ids> <open ids>

   Past 20 rows the kit prints its own overflow line above the `/done`
   box. The start agent returns that text, the wave number, the open ids,
   the carried ids and anything wrong, as data.

The main session prints the checklist verbatim (`Session <n> checklist`,
last line the `/done` box; at most one trailing sentence, and only for an
ordering constraint such as "MERGE waits until every builder has
returned"). After every 4 or more completed rows it prints the remaining
rows only (item 13 b); when a later wave starts, its package rows are
added with `+`. The status board is not rendered (AL is opt-out).

## 2. Dispatch

### What is dispatched

- One builder per open worktree package of the wave (`isolation:
  worktree`, owner session), all at once: at most 12, 11 in wave 1 (14 in
  waves 4 and 18, 13 in waves 19 and 22: the close-out of 2026-11-18 put
  the publishing packages there as a fourth merge batch; never more than
  16, and every batch of at most 4 has its own whole suite: 07, Wave
  width, ruling R6), plus the carried packages. A package is dispatched
  only when every id in its
  `deps` has a flipped row; otherwise it is deferred with cause `waits on
  <id>`. Inside a Workflow run (section 10) the tool runs at most
  min(16, CPUs - 2) agents at once; builders past that queue.
- The main-checkout acts (`isolation: none`) as ONE serial chain beside
  the builders: one agent after another in merge order, each committed or
  read back before the next starts. An act that the wave's `gate` text or
  its own notes place last or alone (GP-09 in wave 5, AUTO-21 in wave 6,
  REL-CUTOVER-LIVE in wave 24) waits until the last merge batch has moved
  main. GP-09 additionally holds main from its gate 3 to its read-back,
  and wave 5 closes only after that (07, ruling R1).
- Loop-owned packages (`owner: loop`) are never dispatched by a session.
- One watcher (section 3).

The `agent` field of a package reads `builder` or `general-purpose`.
.claude/agents holds only adjudicator, design-reviewer and verifier, so
both values are dispatched as the general-purpose agent with the builder
prompt below.

### Where the worktrees live

CLAUDE.md (Sidecar): everything this tree makes outside its tracked files
lives under the AL sidecar; worktrees go under its `Worktree` folder,
beside the loop's `lane-0` to `lane-2`, which a wave agent never touches.
`python -c "from server.al import paths; print(paths.worktree_dir())"`
prints the folder. Names: `w<n>-<ID>` for a package, `w<n>-int` for the
wave's integration worktree. No package id holds the word `lane` except a
loop-owned one, so `fleet_done.py reap` never mistakes a wave worktree for
a lane.

Whether decision 0012's hook is wired is read, not assumed:

    python -c "import json; h=json.load(open('.claude/settings.json',encoding='utf-8')).get('hooks',{}); print('wired' if all('wt_sidecar_hook.py' in json.dumps(h.get(k,'')) for k in ('WorktreeCreate','WorktreeRemove')) else 'not wired')"

- Today it prints `not wired` (wiring is the operator act of parked
  package AUTO-26; an agent cannot edit .claude/settings.json). The
  method that works now, proven by the probe of 2026-11-18 (below), and
  the mode of wave 1: the builder is dispatched WITHOUT harness
  isolation and makes its own worktree by running the hook script by hand
  from the repository root, with the Bash tool:

      echo '{"hook_event_name": "WorktreeCreate", "cwd": ".", "name": "w<n>-<ID>"}' | python tools/wt_sidecar_hook.py

  The one stdout line is the absolute worktree path. The branch is
  `worktree-w<n>-<ID>`, cut from HEAD of main. A second run for the same
  name prints the same path (a resumed package reuses its worktree). The
  builder then works only under that path: file tools with paths under
  it, shell calls as `cd "<WT>" && <command>`. This is the same code path
  the wired hook runs (tests/test_wt_sidecar_hook.py proves it end to
  end).
- Once it prints `wired`: the builder is dispatched WITH harness
  isolation (Agent tool `isolation: "worktree"`; `isolation: 'worktree'`
  in a Workflow script). The harness calls the hook, the agent starts
  inside a sidecar worktree whose name the harness chooses;
  `git rev-parse --show-toplevel` prints the path and
  `git branch --show-current` the branch (`worktree-<name>`). The first
  wave after the wiring also closes AUTO-26 (its accept line).
- Probe (adjudicator LE-92, LE-99). It ran once, on 2026-11-18, in the
  planning session, by one sub-agent, ahead of the session 1 start the
  ruling names; session 1 does not repeat it. Method, as the ruling words
  it:

      echo '{"hook_event_name": "WorktreeCreate", "cwd": ".", "name": "c2-probe"}' | python tools/wt_sidecar_hook.py

  then an Edit and a Write under that path, two named test files, one
  commit through the git lock, one progress write, and the hook's
  WorktreeRemove (git worktree remove, no --force). Result: every step was
  allowed, with no permission prompt and no hook denial, so the unwired
  method above is used and the fallback below is not. What it proved:
  - the hook printed one path under the sidecar Worktree folder; the
    branch was `worktree-<name>`, cut from main;
  - the Edit and Write tools worked on absolute paths under the worktree,
    and `git status --porcelain` of the main checkout stayed empty;
  - `python -m pytest -q <files>` run after `cd "<WT>"` tested the
    worktree's files, not the main checkout's (40 passed; an untracked
    file that existed only in the worktree was checked too);
  - a commit through `fleet_gitlock.py run` landed on the worktree branch
    only and main did not move; the tracked git hooks ran there (the hooks
    path is shared through the common git dir), and both leak sweeps found
    the gitignored needle file of the main checkout (ARMED); the author
    was the operator identity, no trailer;
  - `fleet_headless.py progress --root .` run inside the worktree wrote
    its file into the main checkout and none into the worktree;
  - the hook's WorktreeRemove refused the tree while it held an
    uncommitted edit and removed it once `git -C <WT> status --short`
    printed nothing; the probe branch was deleted, nothing was merged.
- Fallback, only if the permission system refuses a builder's edits or
  shell calls under the sidecar path in the unwired method: harness
  isolation with the harness default folder, `.claude/worktrees/` inside
  the repository (gitignored), which packages.json names for AUTO-26 as
  the fallback only. It breaks the Sidecar placement rule (decision 0012,
  Alternatives), so the hand-off gets one `NOTE:` line and the wiring
  moves to the top of the batched operator ask. It is a temporary,
  recorded deviation, taken without waiting (adjudicator LE-92, LE-100);
  reaped at /done by fleet_done.py reap; ends when OA-12 is pasted. Not
  taken so far: the probe passed.

### What the kit does across worktrees

Read on 2026-11-18 by the probe in the source of the vendored kit (v32;
read, never edited). Builders, the merger and the watcher act on it:

- Git lock: one lock for the whole tree. Every worktree of the repository
  uses the lock file of the main checkout, so the commits and merges of
  all builders, the merger and the integrator go one at a time. Exit 3
  means another holder: wait 30 to 60 s and retry (Rules). Only the
  index.lock check is per worktree.
- Suite gate, one suite per tree: a gated run is keyed to the main
  checkout, whichever worktree starts it. A builder's gated subset (the
  timing files, a subset over 90 s, the fixed-port files), the batch suite
  on `w<n>-int` and any suite in the main checkout therefore queue behind
  each other, one at a time, beside the machine-wide slots. Expect waiting
  in a wave with several gated subsets. The agent that waits keeps its
  progress file fresh (so the wait does not read as STALE) and names who
  holds the gate (`python ops/fleet_kit/fleet_suite_gate.py status
  --brief`).
- Suite gate, uncommitted edits: the gate refuses a suite while another
  live agent holds uncommitted edits, but it looks only at the worktree it
  is started in, and it leaves docs and prose paths out. A suite started
  in the main checkout does not see edits held in a sidecar worktree, and
  a suite in one worktree does not see another's. So this refusal never
  stops a builder because of its neighbours, and it does not guard the
  batch suite: the merger runs the batch suite on `<INT>`, never in the
  main checkout, and only after every merged branch is committed (section
  4, steps 2 to 4). Inside one worktree the refusal does apply: a fix
  round and the first builder of a package never run at the same time.
- Claims: one registry in the main checkout for all worktrees; a path is
  claimed in its absolute form. A shell call that enters a worktree goes
  through the Bash tool with forward slashes (`cd "<WT>" && <command>`).
  The same call through the PowerShell tool with a backslash path made the
  claims hook record a path that does not exist (harmless, seen once in
  the probe; it rides in the kit report of AUTO-25). A heavy command that
  takes the low-priority PowerShell form of the Rules writes the worktree
  path with forward slashes too.
- Removal: a wave agent never removes a worktree (below). Where one must
  go (a probe, a mistyped name), the order is: revert or commit, read `git
  -C <WT> status --short` empty, then the hook's WorktreeRemove; never
  --force.

Worktrees are never removed by a wave agent. /done runs
`python ops/fleet_kit/fleet_done.py reap --apply`, which removes a clean
worktree whose every commit is on main and deletes its branch, and keeps
everything else (a deferred package keeps its worktree and branch).

### Model and effort

Set where the dispatch takes it (the `model` field of the Agent tool, the
`model` and `effort` options of a Workflow `agent()` call). The three
defined agents keep their own frontmatter and are never overridden.

- Builder, size S (10 to 30 minutes in packages.json): sonnet, effort
  medium.
- Builder, size M (30 to 60 minutes): opus, effort medium (the route the
  loop uses for plan rows, tools/loop_base.py).
- Builder, size L (65 to 90 minutes), or any size that edits a hotspot
  file (packages.json `hotspots`) or is tier P0: opus, effort high.
- Main-checkout act: by its size, as above.
- design-reviewer, verifier, adjudicator: sonnet, effort medium
  (.claude/agents).
- Merger: opus, effort high. Integrator: sonnet, effort medium.
- Start agent, watcher, wave close: sonnet, effort low.

### Builder prompt template

`<ID>` is the package id, `<N>` its wave, `<WIRED>` yes or no. The text
is passed as written; the three values are the only substitutions.

```text
You build ONE work package of the AshLight execution plan: <ID> (wave <N>).
Nothing else: no other package, no extra scope, no tidy-up outside it.
Your final message is data for the orchestrator: short, facts only.

1. OWNER ID. Run once:
   python ops/fleet_kit/fleet_gitlock.py run --owner probe -- git commit --dry-run .
   The hook refuses it and its text names your owner id
   (<session id>.<agent id>). Type that id literally wherever <OWNER>
   stands below.

2. PACKAGE. Print it and read every field (goal, files, new_files, tests,
   accept, zero_click, notes, integrator_edits, deps):
   python -c "import json,sys; print(json.dumps(next(p for p in json.load(open('docs/plan/packages.json',encoding='utf-8'))['packages'] if p['id']==sys.argv[1]),indent=1))" <ID>
   The notes name regions and line ranges; they are part of the task.

3. WORKTREE (<WT> below).
   WIRED = no: from the repository root, with the Bash tool:
   echo '{"hook_event_name": "WorktreeCreate", "cwd": ".", "name": "w<N>-<ID>"}' | python tools/wt_sidecar_hook.py
   The one output line is <WT>; your branch is worktree-w<N>-<ID>. If the
   branch already holds commits of this package (a resumed run), continue
   from them.
   WIRED = yes: you already are in your worktree; <WT> is the output of
   git rev-parse --show-toplevel, your branch that of
   git branch --show-current.
   <BASE> is the output of  cd "<WT>" && git merge-base main HEAD
   (the commit your work starts from; it stays right on a resumed run).
   Work ONLY under <WT>: every file you read or edit has a path under it;
   every shell call is  cd "<WT>" && <command>,  run with the Bash tool
   and <WT> written with forward slashes (a PowerShell cd with
   backslashes makes the claims hook record a wrong path).  Never edit a
   file in the main checkout, never switch a branch, never touch another
   worktree. The one write outside <WT> is your progress file (step 4).

4. PROGRESS after every step (task name w<N>-<ID>):
   cd "<WT>" && python ops/fleet_kit/fleet_headless.py progress --root . --task w<N>-<ID> --pct <0-100> --step "<text>" --eta-s <seconds left> --status running
   The first write gives est_min x 60 as --eta-s. The LAST write is
   --status done with --step "done: <result>", or --status failed with
   --step "failed: <cause>".

5. FILES. Edit only the paths in files, create only the paths in
   new_files. If the work needs any other path, or an existing test
   outside your files fails because of your change, stop: status failed,
   cause "needs <path>" or the test's name. Never touch the integrator
   files (ROADMAP.md, CLAUDE.md, AL-NEXT-SESSION.txt,
   docs/decisions/README.md, docs/research/README.md, docs/plan/README.md,
   docs/design/reviews.log), ops/fleet_kit/ or .claude/settings.json. A
   new decision uses the number in your new_files entry. Authored files
   are ASCII and LF; no machine path, account id, email or sibling tree
   name; server/, tools/ and tests/ stay standard library only.

6. FLOOR. The Game ToS floor in CLAUDE.md is absolute; the stricter
   reading wins. Never start the app, the core, the overlay or the loop;
   never read the live Client.txt; never send input anywhere. A choice the
   package text leaves open is ruled by you and recorded (decision,
   alternatives, why, reverses if) in your result, never waited on.

7. TESTS. Run the test files named in your tests field, by file name:
   cd "<WT>" && python -m pytest -q <test files>
   Never the whole suite. Through the suite gate instead, at low priority:
   cd "<WT>" && python ops/fleet_kit/fleet_suite_gate.py run --owner <OWNER> -- python -m pytest -q <test files>
   for tests/test_budgets.py, tests/test_fuzz.py, tests/test_soak.py and
   tests/test_math_perf.py, for a subset you expect to run over 90 s,
   and, until TEST-PORT-LEASE is on main, for tests/test_keepalive.py,
   tests/test_procs.py, tests/test_supervisor.py,
   tests/test_dash_console.py, tests/test_fullstack.py and
   tests/test_math_e2e_live.py. A gated run may wait: one suite per tree
   covers every worktree; keep your progress file fresh while you wait.
   If tools/test_select.py exists in <WT>,
   read its usage text and run the lists it prints instead of choosing by
   hand. If you touch app/ or web/:
   cd "<WT>" && npm test --prefix app
   If you add a decision or a dated amendment, leave
   test_every_decision_is_in_settled and
   test_every_dated_amendment_is_in_settled of tests/test_audit_batch4.py
   out: they are red until the integrator's commit. Then run the command
   of your accept line, except a whole-suite part (the merge batch runs
   it).

8. COMMIT on your branch, named paths only. For each new file first:
   cd "<WT>" && git add -N -- <path>
   then:
   cd "<WT>" && python ops/fleet_kit/fleet_gitlock.py run --owner <OWNER> -- git commit -m "<type>(<ID>): <subject>" -- <paths>
   <type> is one of feat, fix, perf, refactor, data, docs, test, chore,
   ops, security, deps, design, tools or loop, whichever fits the change.
   Once REL-SUBJECT-CHECK is on main (wave 8) the commit-msg hook refuses
   a subject without a known type.
   Never git add -A, commit -a, --amend, --no-verify, push, rebase, reset,
   stash or clean. Exit 3 or an index.lock error: wait 30 to 60 s, retry.
   No AI or bot attribution. Leave nothing uncommitted:
   cd "<WT>" && git status --short   prints nothing when you finish.

9. BUDGET. est_min is your estimate. At 2 x est_min without green tests,
   stop: commit what is coherent, status failed, cause "over budget".

10. A design_review package is reviewed by the session's design-reviewer
    after you return; you do not review yourself.

11. LAST TOOL CALL:
    python ops/fleet_kit/fleet_claims.py release --owner <OWNER>

12. RESULT, in this order, one line each:
    id: <ID>
    status: done | failed
    cause: <only when failed>
    worktree: <WT>
    branch: <branch>
    base: <BASE>
    tip: <output of git rev-parse HEAD in <WT>>
    files: <output of git diff --name-only <BASE>..HEAD in <WT>>
    tests: <each command run, its exit code and counts>
    row: flip <ID>
    settled: <the Settled bullet text for CLAUDE.md, or none>
    index: <the index line(s) for a docs README, or none>
    review: <none; the design-reviewer supplies the reviews.log line>
    deviations: <decision, alternatives, why, reverses if; or none>
```

A main-checkout act gets the same text with step 3 replaced by "You work
in the main checkout on branch main; no worktree; <WT> is the main
checkout, your branch is main, and <BASE> is the output of git rev-parse
HEAD read before your first commit" and `cd "<WT>" &&` dropped. A fix
round (section 5) gets the same text with step 3 replaced by the
worktree path and branch of the first builder, plus the findings to fix.

## 3. Monitoring

- Progress files: `ops/loop/control/progress/<task>.json` in the main
  checkout, written by the kit even from a worktree. Task names:
  `w<n>-<ID>` per package, `w<n>-merge`, `w<n>-integrate`, `w<n>-close`,
  `w<n>-watch`, `w-start`.
- The watcher (background, sonnet, effort low) supervises until every
  builder task of the wave reads done or failed, to a deadline of 2 x the
  longest est_min of the wave. Each slice: run

      python ops/fleet_kit/fleet_checklist.py stale

  (one line per running row past OVERRUN or STALE, else `stale: none`;
  exit 3 when a STALE row exists), read the wave's progress files, write
  its own (`w<n>-watch`), then wait for the next slice with the harness
  Monitor tool (an until-loop on the progress files, at most 9 minutes a
  slice), never a foreground sleep. It returns one line per task:
  `<task>: <status> <pct>% <step>`. When the wave runs as a Workflow run
  (section 10), the main session dispatches the watcher as a plain
  background agent beside the run; the script itself has no watcher. If
  the Monitor tool is not loaded, wait with a background Bash until-loop,
  run_in_background, at most 9 minutes, exiting early when
  `fleet_checklist.py stale` exits 3 or a wave progress file changes
  status; never a foreground sleep.
- The main session is told when a background agent ends; it does not hold
  its turn open on one event. Before any status answer it has the
  watcher's latest lines; the answer is the remaining checklist (item 13
  b), nothing else.
- Overrun: a package past 1.5 x its est_min, or a row the kit marks
  OVERRUN, is one chat line (`<ID>: overrun, <pct>% at <m> min of
  <est_min>`), once.
- Kill: a package past 3 x its est_min is stopped (the main session stops
  that one agent; inside a Workflow run, which cannot stop one agent, the
  builder's own stop at 2 x est_min is the limit and a run still silent
  at 3 x is stopped as a whole and started again, section 10). The
  watcher then closes the row:

      python ops/fleet_kit/fleet_headless.py progress --root . --task w<n>-<ID> --pct <last pct> --step "failed: killed at 3x est_min" --eta-s 0 --status failed

  Accepted as the Workflow equivalent of FLEET item 3 (adjudicator LE-96,
  2026-11-18). A restart reuses each worktree by name, keeps progress
  files, and passes the stopped id in args.defer.

- STALE: a row past 2 x its own ETA step with no write is a failure and
  is investigated at once, not at the deadline: the agent is stopped, the
  row is closed as above with `failed: stale, no progress write for <m>
  min`, and the package is deferred.
- A failed or stale package (builder failed, killed, stale, design review
  still FAIL after two fix rounds, verifier REFUTED three times and the
  adjudicator rules against merging, or backed out of a batch as the
  culprit) is DEFERRED to the next wave:
  - it is not merged; its worktree and branch are kept as they are;
  - its ROADMAP row stays `- [ ]` with `BLOCKED: session wave <n>`;
  - the hand-off gets one line under the wave pointer:
    `DEFERRED: <ID> (wave <n>): <cause>; branch <branch>`;
  - the wave still closes with the packages that merged.
- The next dispatch (the next wave, or the same wave run again) builds
  every carried package first-class beside the wave's own packages.
  Carried packages merge first, as a batch of their own, in their
  original merge order. A wave package that shares a path of `files` or
  `new_files`, or a non-empty `serial_group`, with a carried package, or
  whose `deps` name an unflipped row, is held (cause `held: waits on
  <ID>`); after the carried batch is on main the wave is run once more
  for the held packages, so no chain slips a wave.
- A package deferred twice goes to the adjudicator: retry with a named
  change, split, or park it (section 9); the ruling is acted on at once
  and recorded in the hand-off line.

## 4. Merging

One merger role per wave (opus, effort high, task `w<n>-merge`; one agent
for a batch's merges, one for its suite and the move of main), started
when every builder and the act chain have returned and every package to
merge is reviewed and verified (section 5). It follows 07, Gate commands,
steps 2 and 3. Research 0049 R1 gives the batch: K = 4 packages (5 in
wave 1) per whole suite.

Before the first batch:

- The main checkout is on main and `git status --short` prints nothing.
- Batches are the wave's `- Batches:` line in its `### Wave <n>` section
  of docs/plan/07-execution-plan.md (waves 1 to 24); a wave without that
  line is one batch in the `merge_order` of
  `python tools/plan_check.py wave <n>`. A package that is deferred just
  leaves its batch. Carried packages form batch 0. Wave 1:
  SEC-NO-DISCOVERY is a batch of one, first.
- The integration worktree `w<n>-int` is made by the merger with the
  hand-run hook command of section 2, wired or not (branch
  `worktree-w<n>-int`, cut from main after the act chain's commits). An
  integration worktree left by an interrupted run is reused: its merges
  are kept and the batch continues where it stopped.
- From wave 5 on (LOOP-WAVE-HOLD on main) the batch suite of step 4 and
  every command of step 5 that moves main or merges main into `<INT>`
  run under the loop's merge lock (ops/loop/control/merge.lock), each
  wrapped in the command that package adds:
  `python tools/loop_merge.py hold -- <command>` (07, Gate commands,
  step 2: "under the merge lock"). A lane merge that lands between two
  held commands makes the fast-forward of step 5 refuse, and step 5's
  fallback handles it. Before wave 5 HALT stops the loop, so no lane
  merge can move main and the hold command does not exist yet.

Per batch, packages in merge order:

1. Main into the branch first. In the package worktree:

       cd "<WT>" && python ops/fleet_kit/fleet_gitlock.py run --owner <OWNER> -- git merge --no-edit main

   Then the package's named tests again, in `<WT>`, as in the builder
   prompt step 7 (targeted, file-named; gated where that step says so).
   Red here, with main green: the package is deferred, the batch goes on.
2. The branch into the integration worktree, one merge commit a package:

       cd "<INT>" && python ops/fleet_kit/fleet_gitlock.py run --owner <OWNER> -- git merge --no-ff -m "merge: <ID> <title> (wave <n>)" <branch>

3. The integrator commits the batch's integrator_edits on `<INT>`
   (section 6). The suite runs after this commit, never before it: the
   Settled-list tests fail until the bullet is in CLAUDE.md.
4. The whole suite and the node suite on `<INT>`, the suite as a
   background command at low priority (wait plus hold can pass the
   10-minute foreground ceiling):

       cd "<INT>" && python ops/fleet_kit/fleet_suite_gate.py run --owner <OWNER> -- python -m pytest -q
       cd "<INT>" && npm test --prefix app

   The suite command is the one the wave's `gate` text names: `python -m
   pytest -q` up to wave 10, `python tools/suite_run.py` from wave 11 on
   (TEST-GATE-CALLERS lands in wave 10). Exit
   0 is not the verdict: the merger reads the tail (passed and failed
   counts). While it waits on the gate it reports who holds it:
   `python ops/fleet_kit/fleet_suite_gate.py status --brief`. The suite
   runs on `<INT>`, never in the main checkout: the gate's check for
   uncommitted edits sees only the worktree it starts in, and builders'
   gated subsets queue in the same one-suite-per-tree line (section 2,
   What the kit does across worktrees).
5. Green: main moves to the integration tip, in the main checkout:

       python ops/fleet_kit/fleet_gitlock.py run --owner <OWNER> -- git merge --ff-only worktree-w<n>-int

   Read back: `git rev-parse main` equals `git rev-parse
   worktree-w<n>-int`. If the fast-forward is refused because main moved
   (an act, a loop merge), main is merged into the integration branch
   (`git merge --no-edit main` on `<INT>` through the git lock), step 4
   runs again on the new tree, then the fast-forward. Main is never
   reset, never forced.
6. Red in step 4 (07, step 3): a failing Settled-list or index test is the
   integrator's commit to fix, never a reason to back a package out.
   Otherwise the failing test files are run on each package tip of the
   batch; the culprit's merge is reverted on `<INT>` (`cd "<INT>" &&
   python ops/fleet_kit/fleet_gitlock.py run --owner <OWNER> -- git
   revert --no-edit -m 1 <merge commit>`), and the integrator takes the
   culprit's own edits (row flip, Settled bullet, index line, review
   line) out of the integrator files by one new commit (a `git revert` of
   the integrator commit would also drop the other packages' edits);
   history is never rewritten. The culprit is deferred and one more suite
   runs. A Python traceback from fleet_suite_gate.py in the output is
   infrastructure (research 0049 F11): one retry, no verdict. So is a
   fleet_test_guard error at a teardown while a loop lane was writing
   ops/loop/control/loop_items (the hand-off NOTE): run the suite again.

After the last batch: the acts held for the end run one at a time on
main, each with its verifier and the integrator's commit of its edits.

Conflicts. Inside a wave no two packages share a file, so step 1 can
conflict only where a package left its own file list or main moved under
it.

- A conflict in a file of the package's own `files`: the merger resolves
  it keeping both intents (the package notes name its regions), commits
  the merge through the git lock and re-runs the package's tests.
- A conflict in a file outside the package's list is a contract breach:
  main's version of that file is kept
  (`cd "<WT>" && git checkout --theirs -- <path>`, a path restore inside
  the merge, never a branch switch; then `git add -- <path>` of that one
  path and the merge commit through the git lock), the package's tests
  are re-run, and the verifier
  checks the accept line again; if it no longer holds the package is
  deferred.
- An integrator file never conflicts by a package's hand (packages do not
  edit them); if one does, the integration side wins and the builder's
  result is corrected by the integrator.
- Hotspot files (packages.json `hotspots`: web/index.html,
  server/al/core.py, web/app.js, server/al/http.py, server/al/state.py,
  web/app.css and the rest of that list) have one editor a wave by plan;
  a second diff to one of them in a wave is a breach as above, never a
  hand merge of two features.
- Two failed resolution attempts, or a resolution that changes behaviour,
  go to the adjudicator; its ruling is recorded in the merge commit body
  (decision, alternatives, why). The fallback is always to defer the
  package, never to force.

Wave 1 also measures research 0049's open escape rate: the merger counts
the batches that needed a second suite. Above 10 percent of packages, the
session lowers the batch to 3 (width 9) until TEST-SELECT is on main
(07, Wave width); the count goes into the hand-off.

## 5. Reviews

Both run per package, after its builder returns and before its merge.

- Design review: every package with `design_review: true`, worktree
  package or main-checkout act (PLAY-TD-23-RECORDS, wave 31, is an act
  with the flag), by the `design-reviewer` agent, scope `git diff
  <base>..<tip>` in the package worktree (the main checkout for an act),
  with base and tip from the builder's result. Its verdict decides:
  PASS, or PASS WITH FINDINGS with no S1 and no S2 open, lets the
  package go on; anything else returns the findings to a fix round (a
  builder in the same worktree), then the
  review runs again; after two fix rounds still failing, the package is
  deferred. The reviewer returns the reviews.log line (date, scope,
  verdict with the four counts, the package id and what was fixed or
  stays OPEN, `audit=ROADMAP.md <ID>`); the integrator appends it. A
  conflict between the reviewer and the package text goes to the
  adjudicator.
- Verification: every done-claim, worktree package or main-checkout act,
  by the `verifier` agent before a ROADMAP box is ticked. It did not
  write the change. It re-runs the package's accept command fresh in the
  worktree (a whole-suite part of an accept line is proven by the batch
  suite, not here), reads `git diff --name-only <base>..<tip>` against
  `files` plus `new_files`, checks that no integrator file and no kit
  file changed, and answers VERIFIED or REFUTED with the command, exit
  code and counts. REFUTED sends the evidence to a fix round; refute
  rounds are capped at 3, then the adjudicator rules (merge with a
  recorded deviation, or defer).
- A package is merged only with VERIFIED (or the adjudicator's ruling)
  and, where flagged, a passing design review. The row is flipped by the
  integrator's commit of its batch, and that batch's whole suite is the
  second half of the proof: a culprit loses its flip with its merge.
- An act is already on main when it is reviewed. One that ends deferred
  keeps its commits on main and its row unflipped; its next fix round
  works in the main checkout.

## 6. Integrator

One integrator per wave (sonnet, effort medium, task `w<n>-integrate`),
the only writer of ROADMAP.md, CLAUDE.md, AL-NEXT-SESSION.txt, the three
README indexes and docs/design/reviews.log. It makes one commit per merge
batch, on the integration worktree, after that batch's merges and before
its suite (07, Gate commands, step 2 b); a wave with one batch has one
integrator commit. It applies, for exactly the packages merged in the
batch (plus, in the first batch, the acts of the chain that are verified):

    python -c "import json,sys; ps={p['id']:p for p in json.load(open('docs/plan/packages.json',encoding='utf-8'))['packages']}; [print(i, '|', e['file'], '|', e['change']) for i in sys.argv[1:] for e in ps[i]['integrator_edits']]" <ID> <ID> ...

- ROADMAP.md: the row flip. `- [ ] <ID>` becomes `- [x] <ID>` and
  ` -- done <date> (session wave <n>; verified)` is appended to the row's
  first line, the form the loop uses. Rows are never added here: they
  were landed once, in wave 0. Once AUTO-03 is on main (wave 1) the flip
  uses tools/roadmap.py as its usage text says: its `done` writes the new
  file docs/roadmap/done/<ID>.md (one line ` -- done <date> (session wave
  <n>; verified)`), which marks the row done and leaves ROADMAP.md alone
  until /done folds it (LOOP-DONE-FOLD, wave 3). The done file is a new
  path: `git add -N -- <path>` first, and it is named in the commit.
- CLAUDE.md: each new Settled bullet, with its "Reverses if", from the
  package's integrator_edits and the builder's `settled:` line; nothing
  inside the FLEET COMMON block.
- docs/decisions/README.md, docs/research/README.md, docs/plan/README.md:
  the index lines.
- docs/design/reviews.log: one line per design-reviewed package.
- AL-NEXT-SESSION.txt: only what a package's integrator_edits name; the
  wave pointer is written at wave close (section 7).

The commit, on `<INT>` (named paths: exactly the integrator files and
done files it changed or added, for example
`ROADMAP.md CLAUDE.md docs/decisions/README.md docs/design/reviews.log`):

    cd "<INT>" && python ops/fleet_kit/fleet_gitlock.py run --owner <OWNER> -- git commit -m "chore(integrate): wave <n> batch <b> (<IDs>)" -- <changed paths>

Edits of acts that run after the last batch, and of a wave that has no
worktree package, are committed the same way in the main checkout. The
integrator fixes a red Settled-list or index test of the batch suite by a
second commit; it never edits a package's own files.

## 7. Wave close

One close agent (sonnet, effort low, task `w<n>-close`), in the main
checkout, after the last batch and the last act:

1. `python tools/plan_check.py check` prints ok.
2. `git status --short` prints nothing; `git branch --show-current`
   prints main.
3. The open-row command of section 1 prints `none open`, or only ids
   that are deferred.
4. `python tools/leak_sweep.py --tree` exits 0 and prints no
   `[leak-sweep] HALT` line (exit 2 is a finding).
5. `python ops/fleet_kit/fleet_checklist.py stale` exits 0 and names no
   row of this wave.
6. From wave 5 on: the folder hold file is removed (section 8), after the
   last suite of the wave has ended.
7. The hand-off pointer. The close agent acts here as the wave's
   integrator (the integrator's work for the wave is done, so the file
   still has one writer). It replaces the pointer line in
   AL-NEXT-SESSION.txt with

       WAVE POINTER: wave <n> done, next wave <n+1>

   adds one `DEFERRED:` line per newly deferred package, drops the
   `DEFERRED:` line of every carried package that merged in this wave,
   keeps the others, adds wave 1's escape count, runs
   `python -m pytest -q tests/test_ascii_lf.py tests/test_leak_sweep.py`
   and commits:

       python ops/fleet_kit/fleet_gitlock.py run --owner <OWNER> -- git commit -m "docs(handoff): wave <n> done, next wave <n+1>" -- AL-NEXT-SESSION.txt

   Read back: the line is at HEAD (`git show HEAD:AL-NEXT-SESSION.txt`).

The whole-suite gate of the wave is the last batch suite: main sits on a
tree that suite passed, plus document commits. Then the session starts
the next wave of its group (section 1, steps 2 to 7, by a new start
agent, which reads the `DEFERRED:` lines from the hand-off again). When
no checklist row remains, or the usage window or the context ends the
session early, it runs /done unprompted: the main session dispatches
the whole ritual of .claude/commands/done.md to ONE background agent
(whole suite through the suite gate, `npm test --prefix
app`, the leak sweep, `python ops/fleet_kit/fleet_done.py reap --apply`,
the hand-off rewritten with `SESSION: <n+1>` and the pointer and
`DEFERRED:` lines carried verbatim, `python ops/fleet_kit/fleet_done.py
archive --auto`, `python ops/fleet_kit/fleet_done.py mark --session <n>
--status done`) and relays only its last line, `Done ritual complete,
safe to clear`. A session that stops inside a wave writes the same
pointer as before (the wave stays open); the next `continue` resumes at
the first unmerged package.

## 8. Loop interplay

HALT. `ops/loop/control/HALT` exists today and stays through the landing
and waves 1 to 5. The scheduled task keeps firing; while HALT exists the
tick only runs the reads allowed under HALT (the docs watch, decision
0044; later the release checks of ruling Q-13, read only) and returns.
A wave session never removes HALT, never installs, removes or starts
the task, and never starts a tick. HALT may be removed only after these
packages are on main with one whole green suite (07, HALT removal and
the headless loop): AUTO-01,
LOOP-HANDOFF-PREFIX, LOOP-PREFLIGHT-CMD, LOOP-FAILED-PARK, AUTO-02,
AUTO-03, LOOP-ROWFILES-MERGE, LOOP-ROWFILES-WORK, LOOP-DONE-FOLD,
AUTO-04, AUTO-06, LOOP-WAVE-HOLD, TEST-PLUGIN-PIN. The removal is package
AUTO-21, the last act of wave 6: the six checks of its notes (F-078),
each with its read-back, then the marker is deleted (an empty,
replaceable marker; the method is stated first, FLEET item 9) and the
next tick's `ops/loop/control/progress/loop.json` is read back. A red
check leaves HALT in place; AUTO-21 then runs again as the first act of
the next wave, and no loop-owned row is released until all six read
green.

How the loop and a session never take the same row (docs/plan/06, six
points):

1. Tag. Every session row carries `BLOCKED: session wave <n>` (landed in
   wave 0 from `python tools/plan_check.py rows`). The loop lists a row
   holding the word BLOCKED and never dispatches it; a row without the
   word is the loop's.
2. Claim order. A session that wants an untagged row first commits the
   tag on that row (one commit under the git lock), then reads
   `ops/loop/control/loop_items/<ID>.json`: a record in state dispatched,
   ran or committed means the loop has it; the session commits the tag
   away again and leaves the row. The record wins.
3. Dispatch re-check. The tick re-reads the row from HEAD inside the tick
   lock immediately before a dispatch and skips it when BLOCKED appeared
   (AUTO-06, wave 5).
4. Folder hold. From wave 5 on the start agent writes
   `ops/loop/control/wave_owned.json` (wave number, the folder prefixes
   of the wave's files and new_files, time) and the close agent removes
   it; the loop parks a finished item whose diff touches a held prefix as
   `wave-hold` and merges it when the file is gone (LOOP-WAVE-HOLD, wave
   4); a hold file older than 48 h is one checklist line and is not
   obeyed, so a wave that stops early cannot hold the loop for ever. The
   file is gitignored control state, never committed. It is written
   before the first builder is dispatched and removed after the wave's
   last suite, never while a suite of the session runs (the test guard
   watches control files).
5. Shared ground. Both sides commit through the kit git lock. The loop
   merges only into a clean main under `ops/loop/control/merge.lock`; the
   wave's merger takes the same lock for a batch (section 4). Wave agents
   work in worktrees, so main is clean between batches; a lane suite
   already running finishes first (one suite per tree).
6. Row files cannot conflict: a filed row and a finished row are new
   files, folded into ROADMAP.md only at /done (AUTO-03,
   LOOP-ROWFILES-MERGE).

Rows the headless loop may take once HALT is gone:

- the 16 packages packages.json marks `owner: loop`, each when the rows
  in its `DEPENDS:` are flipped (07 lists them with the wave after which
  each is released);
- watcher rows with lane `data`, requested dives, and hand-off bullets
  that start with `LOOP:`;
- a parked package that leaves wave 99 and passes the loop-owner test of
  07, after its owner is set in packages.json and the validator passes.

Never a row with BLOCKED, never a row that touches `web/`,
`app/overlay/`, `app/shared/` or the event text while a wave holds those
folders. A session never waits for the loop: no session package depends
on a loop package (plan_check enforces it).

Runs cap and inbox cost.

- A wave session spawns no headless run: its builders, reviewers, merger
  and integrator are sub-agents of the interactive session and do not
  count against the cap. Nothing in this file starts `claude`; a headless
  run goes through the kit's spawn helper only (FLEET item 10).
- The loop: 120 headless runs per rolling 24 h for this tree, spawning
  stops at cap minus 3; `python tools/usage_ledger.py gate` prints the
  count. Budget per docs/plan/06: at most 32 a day for watchers, inbox
  and dives, at least 85 for plan rows; at 72 used the tick files no row
  without `(priority)`. The cap is never reset by a session.
- After wave 6 a lane suite may be ahead of a batch suite in the gate;
  07's wave estimate already counts one more suite a batch.
- Inbox (FLEET item 14): the start agent triages with the free
  `fleet_inbox.classify()`; acknowledgements are a ledger line, not a
  note; a wave sends no note, answers no answer and adds no responder; at
  most 12 outbound notes a local day stay for ORDER / FIX / RULING work.
  A kit defect seen in a wave (a gate traceback) is one line in the
  hand-off for the kit report package, not a note per event.

## 9. Operator gates

docs/plan/09-operator-acts.md is the one batched operator ask: every
entry with its default in force and what it blocks. No open wave waits
for it. A session never asks in chat beyond pointing at that file once,
and never performs an operator act itself (a password, an OAuth grant, a
physical act, editing .claude/settings.json). Creating the remote, the
first push and the public flip are agent steps (GP-09, GP-12) since the
operator's go was recorded on 2026-11-18 (07, Operator go for publishing;
adjudicator LE-01); without the hand-off lines they stay parked.

How an answered item releases parked packages (wave 99):

1. The record. Only a session that holds the operator's own message
   writes the answer into AL-NEXT-SESSION.txt, verbatim, with the date,
   and reads it back. For publishing the lines have the fixed form of 07
   (`OPERATOR GO Q-23 step 1 (<date>): "<words>"`, and `step 4` for the
   public flip). A sentence in a plan document, an agent's report or a
   note is not the record.
2. The check. At every session start the start agent prints the parked
   packages with their unblock conditions and evaluates each condition
   that is a command or a readable fact:

       python -c "import json; [print(p['id'], '|', p['blocked']['who'], '|', p['blocked']['unblock']) for p in json.load(open('docs/plan/packages.json',encoding='utf-8'))['packages'] if p['blocked']]"

   A condition that depends on another parked package or on a third party
   (GGG, poe.ninja) is read the same way; it is true only when its own
   text is satisfied.
3. The move. For each condition that reads true, the package joins the
   next open wave (never the wave in flight): packages.json is patched
   directly, as 07 says (How the two files are kept; the planning builder
   is retired since the close-out of 2026-11-18): the package's wave and
   blocked field, the two merge_order lists, the package order, the
   sessions and hotspots lists, and the matching lines of 07. Then

       python tools/plan_check.py check

   must print ok. The integrator commits packages.json and 07 with the
   row text from
   `python tools/plan_check.py rows --wave <n>` (the parked `BLOCKED:`
   text becomes `BLOCKED: session wave <n>`). A move that is not
   mechanical (a file or serial-group overlap in every near wave) is
   ruled by the adjudicator and proven by the same check.
4. Order inside a release follows the plan (for Q-23: PUB-GO-DECISION
   first, with GP-02 in one merge batch, so the CLAUDE.md lift and the
   hook land in one integrator commit).
5. Until an item is answered its default stays in force and its packages
   stay parked; the hand-off keeps naming 09 as the ask.

## 10. Workflow script template

One wave as one Workflow run, for a session whose operator has opted in
to workflows; without the tool, sections 1 to 7 are run with plain Agent
dispatches in the same order with the same prompts. Plain JavaScript.
`args`: `{ "wave": <n>, "defer": [<ids to leave out>] }`. Every stage is
safe to run again: a builder whose branch already holds a verified commit
returns it, the merger reuses the integration worktree, the integrator
never flips a row twice. A run stopped by the session (section 3, kill)
is therefore started again as a new run with the stuck id in `defer`.

```js
export const meta = {
  name: 'al-wave',
  description: 'Run one wave of docs/plan/packages.json: build, review, verify, merge, integrate, close',
  whenToUse: 'A wave session after "continue"; args {wave, defer}',
  phases: [
    { title: 'Read', detail: 'the wave from plan_check, open rows, batches' },
    { title: 'Build', detail: 'one builder per package in its own worktree, acts in a chain' },
    { title: 'Review', detail: 'design review when flagged, then verification' },
    { title: 'Merge', detail: 'per batch: merge, integrator commit, whole suite, main moves' },
    { title: 'Close', detail: 'wave gates and the hand-off pointer' },
  ],
}

const W = args.wave
const DEFER = new Set(args.defer || [])
const DOC = 'docs/plan/08-orchestration.md'
const DATA = ' Your final message is data: short, facts only.'
const str = { type: 'string' }
const ids = { type: 'array', items: str }

const WAVE_SCHEMA = {
  type: 'object',
  required: ['n', 'wired', 'packages', 'batches'],
  properties: {
    n: { type: 'integer' },
    wired: { type: 'boolean' },
    packages: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'title', 'wave', 'size', 'est_min', 'design_review',
          'isolation', 'owner', 'hot', 'open', 'held', 'deps_open', 'after_merge'],
        properties: {
          id: str, title: str, wave: { type: 'integer' }, size: str,
          est_min: { type: 'integer' }, design_review: { type: 'boolean' },
          isolation: str, owner: str, hot: { type: 'boolean' },
          open: { type: 'boolean' }, held: { type: 'boolean' },
          deps_open: ids, after_merge: { type: 'boolean' },
        },
      },
    },
    batches: { type: 'array', items: ids },
  },
}
const BUILD_SCHEMA = {
  type: 'object',
  required: ['id', 'status'],
  properties: {
    id: str, status: { type: 'string', enum: ['done', 'failed'] }, cause: str,
    worktree: str, branch: str, base: str, tip: str, files: ids, tests: str,
    settled: str, index: str, deviations: str,
  },
}
const REVIEW_SCHEMA = {
  type: 'object',
  required: ['verdict', 's1', 's2', 'findings', 'review_line'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'PASS WITH FINDINGS', 'FAIL'] },
    s1: { type: 'integer' }, s2: { type: 'integer' },
    findings: str, review_line: str,
  },
}
const VERDICT_SCHEMA = {
  type: 'object',
  required: ['verdict', 'evidence'],
  properties: { verdict: { type: 'string', enum: ['VERIFIED', 'REFUTED'] }, evidence: str },
}
const RULING_SCHEMA = {
  type: 'object',
  required: ['ruling', 'merge'],
  properties: { ruling: str, merge: { type: 'boolean' }, record: str },
}
const MERGE_SCHEMA = {
  type: 'object',
  required: ['integration', 'merged', 'dropped'],
  properties: {
    integration: str, merged: ids,
    dropped: { type: 'array', items: { type: 'object', required: ['id', 'cause'], properties: { id: str, cause: str } } },
  },
}
const INTEGRATE_SCHEMA = {
  type: 'object',
  required: ['committed'],
  properties: { committed: { type: 'boolean' }, commit: str, flipped: ids },
}
const GATE_SCHEMA = {
  type: 'object',
  required: ['green', 'on_main', 'backed_out', 'suites'],
  properties: {
    green: { type: 'boolean' }, main_tip: str, on_main: ids, suites: { type: 'integer' },
    backed_out: { type: 'array', items: { type: 'object', required: ['id', 'cause'], properties: { id: str, cause: str } } },
  },
}
const CLOSE_SCHEMA = {
  type: 'object',
  required: ['closed'],
  properties: { closed: { type: 'boolean' }, pointer: str, problems: ids },
}

const tier = p => (p.size === 'L' || p.hot)
  ? { model: 'opus', effort: 'high' }
  : p.size === 'M' ? { model: 'opus', effort: 'medium' } : { model: 'sonnet', effort: 'medium' }
const fail = (b, id, cause) => Object.assign({}, b || {}, { id: id, status: 'failed', cause: cause })

// ---- Read: the wave as structured output ----------------------------------
phase('Read')
const wave = await agent(
  'Run `python tools/plan_check.py wave ' + W + ' --json` in the main checkout and return wave ' + W +
  ' of the AshLight plan as structured output, following ' + DOC + ' sections 1, 2 and 3.' +
  ' packages: every package of the wave in merge order, plus, first, every package named by a' +
  ' DEFERRED: line of AL-NEXT-SESSION.txt (its own wave number in `wave`). Copy id, title, size,' +
  ' est_min, design_review, isolation and owner ("session" when absent) from the tool output.' +
  ' open: its row is not flipped (no "- [x] <ID> " line in ROADMAP.md and no' +
  ' docs/roadmap/done/<ID>.md; section 1 step 4). deps_open: the ids' +
  ' of its deps whose row is not flipped. held: it shares a path of files or new_files, or a' +
  ' non-empty serial_group, with a carried package. hot: it edits a file of the packages.json' +
  ' hotspots list or its tier is P0. after_merge: an isolation none package that the wave gate' +
  ' text or its own notes place last or alone after the last batch. batches: the id lists of the' +
  ' "- Batches:" line of the wave section in docs/plan/07-execution-plan.md, in order, with one' +
  ' batch of the carried ids in front; no such line: one batch in merge order, worktree packages' +
  ' only. wired: the wiring command of section 2 prints "wired". Change no file.' + DATA,
  { label: 'read wave ' + W, phase: 'Read', schema: WAVE_SCHEMA, model: 'sonnet', effort: 'low' })
if (!wave) return { wave: W, closed: false, error: 'the reader returned nothing' }

const live = wave.packages.filter(p => p.owner !== 'loop' && p.open && !DEFER.has(p.id))
const ready = live.filter(p => !p.held && p.deps_open.length === 0)
const deferred = live.filter(p => !ready.includes(p)).map(p => ({
  id: p.id,
  cause: p.held ? 'held: waits on a carried package' : 'waits on ' + p.deps_open.join(', '),
}))
const builds = ready.filter(p => p.isolation === 'worktree')
const acts = ready.filter(p => p.isolation === 'none')
log('wave ' + W + ': ' + builds.length + ' builders, ' + acts.length + ' acts, ' + deferred.length + ' held')

// ---- Build, review, verify: one chain per package, no barrier ---------------
const builderText = (p, extra) =>
  'Read ' + DOC + ' section 2, "Builder prompt template", and follow it exactly with ID = ' + p.id +
  ', N = ' + p.wave + ', WIRED = ' + (wave.wired ? 'yes' : 'no') + '.' + (extra || '')

const build = p => agent(builderText(p), Object.assign(
  { label: 'build ' + p.id, phase: 'Build', schema: BUILD_SCHEMA, agentType: 'general-purpose' },
  tier(p), wave.wired ? { isolation: 'worktree' } : {}))

const act = p => agent(
  builderText(p, ' This package is a main-checkout act: work in the main checkout on branch main,' +
    ' no worktree, one act at a time; BASE is git rev-parse HEAD read before your first commit.'),
  Object.assign({ label: 'act ' + p.id, phase: 'Build', schema: BUILD_SCHEMA, agentType: 'general-purpose' }, tier(p)))

const fix = (p, b, what) => agent(
  builderText(p, ' This is a FIX ROUND: do not create a worktree; work in ' + b.worktree +
    ' on branch ' + b.branch + ' and fix only this, then commit and report as usual: ' + what),
  Object.assign({ label: 'fix ' + p.id, phase: 'Review', schema: BUILD_SCHEMA, agentType: 'general-purpose' }, tier(p)))

const review = async (b, p) => {
  if (!b) return fail(b, p.id, 'the builder returned nothing')
  if (b.status !== 'done' || !p.design_review) return b
  let cur = b
  for (let round = 1; round <= 3; round++) {
    const r = await agent(
      'Design review of package ' + p.id + ' per ' + DOC + ' section 5. Scope: `git diff ' +
      cur.base + '..' + cur.tip + '` in ' + cur.worktree + '. Return the verdict, the S1 and S2 counts, the findings' +
      ' as text and the one docs/design/reviews.log line for this package.' + DATA,
      { label: 'design ' + p.id + ' r' + round, phase: 'Review', schema: REVIEW_SCHEMA, agentType: 'design-reviewer' })
    if (!r) return fail(cur, p.id, 'the design review returned nothing')
    if (r.verdict !== 'FAIL' && r.s1 === 0 && r.s2 === 0) return Object.assign({}, cur, { review_line: r.review_line })
    if (round === 3) break
    const f = await fix(p, cur, r.findings)
    if (!f || f.status !== 'done') return fail(cur, p.id, 'design fix round ' + round + ' failed')
    cur = Object.assign({}, cur, { tip: f.tip })
  }
  return fail(cur, p.id, 'design review still failing after two fix rounds')
}

const verify = async (b, p) => {
  if (!b) return fail(b, p.id, 'the builder returned nothing')
  if (b.status !== 'done') return b
  let cur = b
  for (let round = 1; round <= 3; round++) {
    const v = await agent(
      'Verify the done-claim of package ' + p.id + ' per ' + DOC + ' section 5: worktree ' + cur.worktree +
      ', branch ' + cur.branch + ', base ' + cur.base + ', tip ' + cur.tip + '. Answer VERIFIED or REFUTED with the evidence.' + DATA,
      { label: 'verify ' + p.id + ' r' + round, phase: 'Review', schema: VERDICT_SCHEMA, agentType: 'verifier' })
    if (!v) return fail(cur, p.id, 'the verifier returned nothing')
    if (v.verdict === 'VERIFIED') return Object.assign({}, cur, { verified: true })
    if (round === 3) {
      const a = await agent(
        'Package ' + p.id + ' was refuted three times. Last evidence: ' + v.evidence +
        '. Rule per ' + DOC + ' section 5: merge with a recorded deviation, or defer.' + DATA,
        { label: 'adjudicate ' + p.id, phase: 'Review', schema: RULING_SCHEMA, agentType: 'adjudicator' })
      if (a && a.merge) return Object.assign({}, cur, { verified: true, ruling: a.ruling })
      return fail(cur, p.id, 'refuted three times; ruling: ' + (a ? a.ruling : 'none'))
    }
    const f = await fix(p, cur, v.evidence)
    if (!f || f.status !== 'done') return fail(cur, p.id, 'fix round ' + round + ' failed')
    cur = Object.assign({}, cur, { tip: f.tip })
  }
  return fail(cur, p.id, 'not verified')
}

const chain = async list => {
  const out = []
  for (const p of list) out.push(await verify(await review(await act(p), p), p))
  return out
}

phase('Build')
const [built, early] = await parallel([
  () => pipeline(builds, build, review, verify),
  () => chain(acts.filter(p => !p.after_merge)),
])

const okBuilt = new Map()
const okActs = []
const sortOut = (list, results, keep) => list.forEach((p, i) => {
  const r = (results || [])[i]
  if (r && r.status === 'done' && r.verified) keep(p, r)
  else deferred.push({ id: p.id, cause: r ? (r.cause || 'not verified') : 'the agent returned nothing' })
})
sortOut(builds, built, (p, r) => okBuilt.set(p.id, r))
sortOut(acts.filter(p => !p.after_merge), early, (p, r) => okActs.push(r))

// ---- Merge: per batch merge, integrator commit, whole suite, main moves -----
phase('Merge')
const merged = []
const batchLog = []
const actsFlipped = []
let mainTip = null
let stop = null
let pendingActs = okActs.map(r => r.id)
const park = (list, cause) => list.forEach(id => deferred.push({ id: id, cause: cause }))

const integrate = (where, pkgIds, results) => agent(
  'You are the wave ' + W + ' integrator (' + DOC + ' section 6, task w' + W + '-integrate). Apply the' +
  ' integrator_edits of exactly these packages and commit them as ONE commit in ' + where + ': ' +
  pkgIds.join(', ') + '. Builder results (settled, index and review lines): ' + JSON.stringify(results) + DATA,
  { label: 'integrate ' + pkgIds.join(' '), phase: 'Merge', schema: INTEGRATE_SCHEMA, model: 'sonnet', effort: 'medium' })

for (const batch of wave.batches) {
  const members = batch.map(id => okBuilt.get(id)).filter(Boolean)
  if (!members.length) continue
  if (stop) { park(members.map(x => x.id), stop); continue }
  const m = await agent(
    'You are the wave ' + W + ' merger (' + DOC + ' section 4, task w' + W + '-merge). Do steps 1 and 2' +
    ' for this batch, in this order: ' + JSON.stringify(members.map(x => ({ id: x.id, worktree: x.worktree, branch: x.branch }))) +
    '. Return the integration worktree path, the ids merged into it and the ids dropped with the cause.' + DATA,
    { label: 'merge ' + members.map(x => x.id).join(' '), phase: 'Merge', schema: MERGE_SCHEMA, model: 'opus', effort: 'high' })
  if (!m) { stop = 'the merger returned nothing'; park(members.map(x => x.id), stop); continue }
  m.dropped.forEach(x => deferred.push(x))
  if (!m.merged.length) continue
  const riding = pendingActs
  const i = await integrate('the integration worktree ' + m.integration, m.merged.concat(riding),
    members.filter(x => m.merged.includes(x.id)).concat(okActs.filter(r => riding.includes(r.id))))
  if (!i || !i.committed) { stop = 'the integrator commit is missing'; park(m.merged, stop); continue }
  const g = await agent(
    'You are the wave ' + W + ' merger (' + DOC + ' section 4). Do steps 4, 5 and 6 for the batch ' +
    m.merged.join(', ') + ' on ' + m.integration + ': whole suite and node suite, on green move main,' +
    ' on red find and back out the culprit and run one more suite. Return green, the ids now on main,' +
    ' the ids backed out with the cause, the number of whole suites run and the tip of main.' + DATA,
    { label: 'gate ' + m.merged.join(' '), phase: 'Merge', schema: GATE_SCHEMA, model: 'opus', effort: 'high' })
  if (!g || !g.green) { stop = 'the batch suite is not green'; park(m.merged, stop); continue }
  g.backed_out.forEach(x => deferred.push(x))
  merged.push(...g.on_main)
  actsFlipped.push(...riding)
  pendingActs = []
  mainTip = g.main_tip || mainTip
  batchLog.push({ ids: g.on_main, suites: g.suites })
}

// acts whose row flip found no batch to ride in: one commit in the main checkout
if (!stop && pendingActs.length) {
  const i = await integrate('the main checkout', pendingActs, okActs)
  if (i && i.committed) { actsFlipped.push(...pendingActs); pendingActs = [] }
}
park(pendingActs, 'done on main, row flip pending: ' + (stop || 'the integrator commit is missing'))

// acts the gate text places last or alone, after the last batch
const lateActs = acts.filter(p => p.after_merge)
if (stop) park(lateActs.map(p => p.id), stop)
else if (lateActs.length) {
  const lateOk = []
  sortOut(lateActs, await chain(lateActs), (p, r) => lateOk.push(r))
  if (lateOk.length) {
    const i = await integrate('the main checkout', lateOk.map(r => r.id), lateOk)
    if (i && i.committed) actsFlipped.push(...lateOk.map(r => r.id))
    else park(lateOk.map(r => r.id), 'done on main, row flip pending: the integrator commit is missing')
  }
}

// ---- Close ------------------------------------------------------------------
phase('Close')
const c = await agent(
  'Close wave ' + W + ' per ' + DOC + ' section 7 (task w' + W + '-close): the gates 1 to 6, then the' +
  ' hand-off pointer commit. Deferred packages, one DEFERRED: line each: ' + JSON.stringify(deferred) +
  '. Whole suites per batch (wave 1 escape count): ' + JSON.stringify(batchLog) +
  (stop ? '. The merge stopped early (' + stop + '): the wave stays open, keep the old pointer.' : '.') + DATA,
  { label: 'close wave ' + W, phase: 'Close', schema: CLOSE_SCHEMA, model: 'sonnet', effort: 'low' })

return {
  wave: W,
  merged: merged.concat(actsFlipped),
  deferred: deferred,
  batches: batchLog,
  main_tip: mainTip,
  stopped: stop,
  closed: !!(c && c.closed) && !stop,
  pointer: c ? c.pointer : null,
  problems: c ? (c.problems || []) : ['the close agent returned nothing'],
}
```

Notes on the template:

- Null results: an agent that is skipped or dies returns null; every
  stage turns that into a failed result with a cause, the package is
  deferred, and the wave goes on. A missing merger, integrator commit or
  green suite stops the merging (main is not moved for that batch) and
  the wave stays open.
- The return value is the whole report the main session needs: ids
  merged, ids deferred with their cause, suites per batch, the tip of
  main, whether the wave closed. The main session prints at most one
  line per deferred id and the item-13 b remaining rows, then starts the
  next wave or /done.
- A wave that holds a package with est_min of 60 or more and a history of
  overrun (an OVERRUN line or a kill in an earlier dispatch of it) is
  dispatched as plain background Agents (sections 1 to 7), not as a
  Workflow run, so that the one agent can be stopped at 3x (adjudicator
  LE-96).
- The script does not run /done and does not start the next wave: the
  main session reads one wave's result before it decides (a deferred
  package may ask for a second run of the same wave, section 3).

## Open points

- Closed 2026-11-18, settled by the probe (adjudicator LE-92, LE-99;
  section 2, Probe): a sub-agent may edit, test and commit under a
  hand-made sidecar worktree in the session's permission mode. Not yet
  seen: several builders at once (wave 1 is the first such run); if a
  builder is refused there, the fallback of section 2 is taken without
  waiting.
- The hand-off line `WAVE POINTER: ...` and the `DEFERRED:` lines are
  defined here; PLAN-LANDING writes the first pointer (`wave 0 done, next
  wave 1`) when it rewrites the hand-off (its accept line checks it since
  the close-out of 2026-11-18).
- Closed 2026-11-18: AUTO-26 in packages.json words the default as
  section 2 does (the hand-run sidecar worktree; `.claude/worktrees/` as
  the fallback only).
- Closed 2026-11-18 (07, Rulings 2026-11-18 (close-out 2); LE-92, LE-99,
  LE-100, LE-96): both questions had been ruled at the close-out and the
  rulings were applied late. The `.claude/worktrees/` fallback of section
  2 may be taken without waiting, as a recorded temporary deviation; the
  builder's own stop at 2 x est_min plus a whole-run restart at 3 x is
  accepted as the Workflow equivalent of the kill at 3x.
- Closed 2026-11-18 (07, Rulings 2026-11-18 (close-out 2), R1): GP-09 runs
  alone after wave 5's last batch and holds main until its read-back.
- Closed 2026-11-18 (07, ruling R6): waves 4, 18, 19 and 22 keep 14, 14,
  13 and 13 worktree packages as four merge batches, each with its own
  whole suite; the planned width stays 12, the ceiling 16.
- The integrator commits once per merge batch (07, Gate commands), not
  once per wave: the batch suite needs the Settled bullets first.

## Verification record

Independent verifier, 2026-11-18, HEAD 18914e1. Read-only on the
machine: no app, core, overlay or loop started, no Client.txt read, no
worktree created; only this file changed.

Checked:
- Package ids: every id named here exists in docs/plan/packages.json (396
  packages) with the wave and isolation the text gives (AUTO-03 and
  LOOP-LEDGERS wave 1, LOOP-WAVE-HOLD 4, AUTO-06 and TEST-PORT-LEASE 5,
  AUTO-21 6 as an act, TEST-SELECT 8, TEST-GATE-CALLERS 10,
  REL-CUTOVER-LIVE 24 as an act, AUTO-26, GP-02 and PUB-GO-DECISION 99);
  the HALT list equals AUTO-21's deps and 07's list; 16 loop-owned
  packages; wave 1 has 11 worktree and 4 main-checkout packages; no open
  wave has more than 12 worktree or 4 main-checkout packages; the only id
  holding a `lane` word (TEST-LOOP-SPLIT-LANES) is loop-owned.
- Commands run or read in source: tools/plan_check.py check, wave <n>
  --json and rows --wave (usage text; check prints ok 396 packages, 39
  waves); the open-row, session-group, wiring, worktree-folder and
  checklist one-liners (run; wiring prints not wired, the folder is the
  sidecar Worktree folder); fleet_checklist (item, render with cap,
  emit, `stale` exit 0 or 3), fleet_headless progress (--root --task
  --pct --step --eta-s --status, written in the main checkout from a
  worktree), fleet_gitlock run (commit, push, and merge / reset / revert
  lock only), fleet_suite_gate run and status --brief, fleet_done reap
  --apply, archive --auto and mark --session --status, fleet_claims
  release --owner, tools/wt_sidecar_hook.py (stdin JSON, one path line,
  branch worktree-<name>, idempotent), tools/leak_sweep.py --tree (exit
  2 on a HALT finding), tools/usage_ledger.py gate, tools/loop_base.py
  routes and MERGE_LOCK_REL, loop_items states dispatched / ran /
  committed, .claude/agents (three agents, sonnet, effort medium),
  .claude/commands/done.md. Future commands are named as such:
  tools/loop_merge.py hold (LOOP-WAVE-HOLD), tools/roadmap.py
  (AUTO-03), tools/test_select.py (TEST-SELECT), tools/suite_run.py
  (TEST-GATE-CALLERS).
- The Workflow template against the Workflow tool contract (meta
  literal, agent options label / phase / schema / model / effort /
  agentType / isolation, pipeline stage arguments, parallel, null
  results): it parses with node --check and runs end to end against
  stub agents (build, review with a fix round, verify, acts before and
  after the merge, a held package).
- Sources: 07 (How to read, Wave width, Gate commands, Batches lines of
  waves 1 to 24, HALT removal, Reserved decision numbers, Contract
  lines), every wave's gate text in packages.json, 06 (the six points,
  Runs budget, contract line F-198), 01 L12, rulings Q-12, Q-13, Q-17
  and Q-23, the hand-off (SESSION line, Session start checks, kit defect,
  loop_items NOTE, low-priority order). Floor and CLAUDE.md: nothing here
  starts the app, core, overlay or loop, reads the live Client.txt,
  sends input, pushes, rewrites history or edits ops/fleet_kit or
  .claude/settings.json. No private name, machine path or account id.

Changed:
- Section 1: the open-row command also counts a docs/roadmap/done/<ID>.md
  file as a flip (AUTO-03 writes done files, folded only at /done) and
  leaves out carried ids, which before held a wave with a deferred
  package open for ever; the checklist command now lists the carried and
  open ids only and adds the later waves of the group itself; the start
  agent runs the hand-off's Session start checks; `stale` is judged by
  its exit code (it prints OVERRUN lines too).
- Section 2: carried packages and the Workflow concurrency cap added;
  size ranges as packages.json has them (S up to 30, L from 65); builder
  results carry `base`, and the diff scopes use base..tip so a
  main-checkout act can be reviewed and verified.
- Section 3: the watcher beside a Workflow run.
- Section 4: the merge lock covers the batch suite and the move of main,
  through `tools/loop_merge.py hold -- <command>`, not steps 1 to 4
  only; suite_run.py from wave 11 (wave 10's gate still names pytest);
  a culprit's integrator edits leave by a new commit, since a revert of
  the batch's integrator commit would drop every package's edits; the
  fleet_test_guard teardown error counts as infrastructure; the
  `checkout --theirs` is marked as a path restore.
- Section 5: design review also for main-checkout acts
  (PLAY-TD-23-RECORDS); a deferred act stays on main.
- Section 6: the done file of tools/roadmap.py and its `git add -N`;
  the commit names the paths actually changed.
- Section 7: leak sweep and stale checks by exit code; the close agent
  is the one writer of the hand-off at close and drops the DEFERRED line
  of a carried package that merged.
- Section 8: reads allowed under HALT (Q-13), the 48 h hold-file rule,
  when the hold file is written and removed.
- Section 10: `base` in the build schema and prompts; acts get the
  design review in the chain; the reader's `open` matches section 1.
- Rules: no research number is reserved (no package writes a note);
  input list names research 0058 for the loop.

Close-out, 2026-11-18 (docs/plan/07, Rulings 2026-11-18 (close-out)):
- Section 2: the dispatch width names the four waves that hold 13 or 14
  worktree packages; GP-09 (wave 5) joins the acts that wait for the last
  merge batch; the AUTO-26 fallback wording (LE-91).
- Builder prompt step 8, sections 6 and 7: every commit subject carries a
  type, from wave 1 on, so nothing changes when REL-SUBJECT-CHECK lands
  in wave 8 (LE-54, LE-165).
- Sections 8 and 9: the plan is changed by patching packages.json (the
  builder is retired, LE-166); creating the remote, the first push and
  the flip are agent steps since the go was recorded (LE-01).
- The "Checked" lines above describe the plan before the close-out:
  GP-02 and PUB-GO-DECISION are now in wave 4, and waves 4, 18, 19 and 22
  hold more than 12 worktree packages (check still prints ok 396
  packages, 39 waves).

Close-out 2, 2026-11-18 (docs/plan/07, Rulings 2026-11-18 (close-out 2)):
- Section 2: the probe of a hand-made sidecar worktree ran and passed
  (LE-92, LE-99), so wave 1 uses the unwired method; the Fallback bullet
  says it is taken without waiting and reaped at /done (LE-100); new
  subsection on what the kit's git lock, suite gate and claims do across
  worktrees; the wide waves have a ceiling of 16 (R6); GP-09 holds main to
  its read-back (R1).
- Builder prompt steps 3 and 7: Bash with forward slashes for every cd
  into the worktree; a gated run may queue.
- Section 3: the watcher's wait without the Monitor tool, and the Workflow
  kill rule as accepted (LE-96). Section 4: the batch suite runs on the
  integration worktree, and why. Section 10: when a wave runs as plain
  background Agents (LE-96).
- Open points: the unverified-edit and the not-ruled entries are closed;
  R1 and R6 are recorded.
- The "no worktree created" line of the verifier above stays true for its
  own run; the probe is a later act of the planning session.
