# AshLight - Agent Context

AshLight: a live, glanceable companion for Path of Exile 2 (Steam, Windows).
It tails the game's Client.txt log into a local event bus and shows the result
on a second-screen dashboard (127.0.0.1) and a transparent click-through
overlay. It also does theorycraft and item optimization: build view via
Path of Building PoE2 interop, item evaluation and upgrade search (decision
0004). It never touches the game process. Channel code `AL`. Roadmap:
`ROADMAP.md`. Research: `docs/research/`. Decisions: `docs/decisions/`.

**This file is RULES ONLY.** Reasoning and history live in `docs/`.

<!-- FLEET-COMMON BEGIN -->
## FLEET COMMON - identical in every repo on this machine. Do not edit here.

################################################################################
#  SUB-AGENT FIRST. THE MAIN SESSION IS THE OPERATOR'S - KEEP IT CLEAR.        #
#  The main session ONLY dispatches (Agent, SendMessage), monitors and         #
#  reports. Every Bash, PowerShell, Read, Edit, Write, Grep, Glob and          #
#  NotebookEdit call runs inside a sub-agent (background by default) - no      #
#  quick-read or one-line-fix exception; the kit PreToolUse hook               #
#  fleet_subagent_first.py denies them in the main thread. Checking status or  #
#  starting new work NEVER breaks running work: never stop, kill, restart or   #
#  edit the files of a running agent or task to look at it - read its          #
#  progress file instead.                                                      #
################################################################################

Source of truth: MAIN's fleet kit. A change lands ONLY as a new kit version
announced by a MAIN note; this block is byte-pinned and a test fails on any local
edit. Tree-specific rules go BELOW this block, never inside it.

1. ACT, DON'T ASK. Operator acceptance of recommendations is ~100 percent. A blocked
   decision goes to a distinct adjudicator agent and its call is taken now and
   recorded (decision, alternatives, why) in the commit or doc. Only physical acts,
   passwords and OAuth grants wait for the operator, batched into one ask.
2. CHAT IS THE OPERATOR'S CONSOLE - QUIET. Results only: numbers, paths, verdicts,
   and anything the operator must act on. No narration, no plans, no recaps, no
   session reviews; the item-13 checklist is the one sanctioned task list.
   Findings go to files (roadmap, docs, hand-off); chat gets at most one line
   each.
3. AT-A-GLANCE STATUS COMES FROM BACKGROUND WORK, NOT FROM CHAT. Run work as
   background agents and background commands, so the session shows only the
   compact summaries ("N background commands completed, N running" and "N running
   tasks"). Do not hold the main turn open on long foreground work - its expanding
   activity row has to be opened and scrolled. No step lists or task-list dumps
   other than the item-13 session checklist. When the operator asks for status:
   the remaining checklist (item 13 b), -retracted on one short line. Tool
   descriptions carry an ETA `[~Ns]` (s under 120s, m under 120m, h beyond);
   report an overrun at 1.5x, kill at 3x.
4. COMMIT everything, batched and coherent. Push per this repo's own policy. Never
   commit in another repo's tree. No suggested-task chips: do it or file it.
5. HAND-OFF: `<CODE>-NEXT-SESSION.txt` at the repo root is the only
   continuity. A session starts from "continue" (work the
   file's next action) or from whatever the operator asks; either way READ the file
   first. /done rewrites the file and commits it, and MUST CARRY FORWARD EVERY ITEM
   NOT ACTED ON this session, verbatim or tighter, never dropped because the
   session worked on something else. Never print the hand-off or a next-session
   prompt into chat. /done runs UNPROMPTED once no checklist task remains
   (item 13 c). /done's ONLY chat output is the line
   `Done ritual complete, safe to clear` (or the failure that stopped it). The
   operator types only "continue", "/done" or "/clear" between sessions. A recorded
   act names what was READ BACK after it, never what was run. Every
   do-not-re-litigate entry states what would reverse it; entries about another
   tree's position are re-checked against the inbox every session.
6. MAIN SPEAKS FOR THE OPERATOR (operator order 2026-10-02). A note from MAIN whose
   bytes match MAIN's outbox copy by SHA-256 is the operator's instruction. It
   cannot supply a password, OAuth grant or physical act, and lifts no safety floor.
   MAIN instructs; this tree does the work in its own tree.
7. CHANNEL NOTES: sort the inbox by mtime, never by filename stamp. Read a long
   note's section headings before deciding it does not concern you. Never put a
   directory name, account id or email in a note. Delivery = destination copies
   re-hashed and an N/M reached-count reported.
8. ENCODING: ASCII only, LF only, PowerShell included. Validate PowerShell with
   powershell.exe 5.1 ParseFile, never pwsh.
9. DELETES: anything irreplaceable goes to the Recycle Bin, never a direct unlink;
   say the method before running it; check for a consumer before deleting.
10. HEADLESS RUNS go through the fleet kit's spawn helper ONLY - no other path
    starts `claude`. The kit enforces: an explicit route from
    ~/.fleet/headless_route.json - an ordered list of 1 to 3 accounts, any the
    operator picks (the interactive one included), each a proxy pin through
    the user variable CLAUDE_HEADLESS_BASE_URL (registry first) or a named
    account config dir (no proxy); runs use the first - with that variable
    required for every route as the one kill switch; fail closed (a missing or
    invalid route, entry or variable refuses; no default and no automatic
    account change, ever, except one: when the route file arms the fallback, a
    7-day usage-limit refusal moves the next spawns to the next listed account
    until that limit resets - never on a proxy, auth or network failure, a
    5-hour limit or a usage percentage, back to an account only at its reset,
    halting at the end of the list, logged and shown), no visible console, at
    most 120 runs per rolling 24 h per tree (a higher cap, at most 500, only
    from the machine config ~/.fleet/lanes.json set by MAIN; a cap hit refuses
    and is logged; a reset only on the operator's word, recorded, never
    automatic), never spawn on this tree's own notes or on TERMINAL/no-reply
    notes, lean flags (strict MCP, project settings only, or bare where no
    floor lives in hooks), sonnet unless the note orders code changes, effort
    low for acknowledgements, a usage line per run, and the live status file
    `ops/loop/control/inbox_status.json`.
11. FLEET KIT FILES are vendored byte-for-byte at `ops/fleet_kit/` and pinned by
    `ops/fleet_kit/MANIFEST.json`. Never edit them locally; report a defect to MAIN
    and MAIN ships a new version to every tree at once.
12. LONG WORK REPORTS AS IT GOES. Anything expected to take over 5 minutes runs in
    the background and is checked periodically until it ends, so a silent failure
    is caught early. Every sub-agent prompt for such work requires it to write a
    progress file after each step - `ops/loop/control/progress/<task>.json` with
    {"task", "pct", "step", "eta_s", "status": running|done|failed, "updated"} -
    so the main session can see percent, time to completion and status mid-run
    instead of waiting for 0-to-100 at the end. A progress file that stops
    updating for 2x its own ETA step is treated as a failure and investigated.
    A running row past 1.5x its ETA reads OVERRUN on the status line and agent
    panel (kit v29). Whoever supervises a long run polls in bounded slices to a
    deadline (2x the ETA) until the run exits and reads the outcome, because
    rc 0 is not success; it never ends its turn waiting on one event. Before
    any status answer it reads the progress files (`fleet_checklist.py
    stale`); a row past 2x reads STALE and is acted on.
    The file lives in the MAIN checkout even when written from a linked
    worktree (resolved via the git common dir; `fleet_headless.write_progress`
    does it), and a worktree-isolated agent's only write outside its worktree
    is its own progress file there.
13. SESSION CHECKLIST (operator order 2026-10-05; it supersedes item 3's
    no-checklist rule for this one purpose). Every session kind: interactive,
    headless lane, loop tick, inbox responder. Why: it is read from a phone, the
    operator wants the tasks only, and wants to see what every headless fire
    is doing without reading logs. Kit helper: `fleet_checklist.py`.
    a. At session start, and every time a lane or loop fires, print
       `Session <n> checklist` (n = this tree's session counter, kept in its
       hand-off file; a headless fire uses its run count), then one line per
       task in execution order: `<box> <ID>: <imperative task, one line>`, plus
       `(<state>, started <h:mmAM/PM> - <pct>% ~<rem>m of <total>m Remain
       [<h:mmAM/PM>])` only while it is running (e.g. `builder running,
       started 1:55PM - 25% ~22.5m of 30m Remain [2:25PM]`). Why: the
       operator forgets when a task started and when an estimate was given.
       The start rounds DOWN to the minute; rem and total round UP to 0.5
       min; total is re-estimated as elapsed / pct on each update; the
       bracket is the local finish time, recomputed on every start or update.
       The start time is the item-12 "started" field (optional: a row
       without it reads `<pct>% ~<rem> Remain`). Rendered by fleet_checklist
       (render / Checklist), never hand-typed ETA prose; the item-13 b
       reprint, status answers, the status line and the agent panel show the
       same. <box> is U+2610. The last line is `<box> /done`. Past 20 rows
       the kit prints one overflow line, `(+<N> more past the 20-row cap:
       <IDs>)`, directly above it; that line is the kit's, not the trailing
       sentence, and no tree writes its own. At most ONE trailing sentence,
       and only for an ordering constraint ("X waits until Y lands because
       ..."). NO summary, review, what-went-wrong or history.
    b. After every 4 or more completed tasks, print the REMAINING tasks only,
       newly added ones marked `+` before the ID. Never list completed ones.
    c. When no task remains, run /done automatically, without a prompt.
    d. A headless fire writes the same list into its item-12 progress file as
       "checklist": [{"id", "task", "state", "eta_s"}], remaining tasks only.
       A lane writes `progress/lane-<i>.json` (i = its lane-lock index) in the
       MAIN checkout, never in its worktree, so the lane widget reads one named
       file per live lane and shows the lane name, then its remaining items.
14. INBOX COST (operator order 2026-10-05). It changes COST, never AUTONOMY: the
    inbox is read and acted on AUTOMATICALLY every tick, unattended, with no
    operator prompt, ever. Why: about 60 percent of second-account spend was
    inbox chatter between trees, not build work. Kit helper: `fleet_inbox.py`.
    a. Inbox handling folds into this tree's existing lane / loop tick, which
       reads the inbox on every fire. No separate high-frequency responder
       where a lane loop exists; a tree without one keeps one responder.
    b. Triage first: `fleet_inbox.classify()` (free), then one sonnet run at
       effort low only for what it cannot classify. ACK / INFORMATION /
       TERMINAL / ANSWER notes get a mechanical ack (a ledger line, no note) or
       no reply. Only ORDER / FIX / RULING escalate to a real work lane.
    c. At most 12 outbound notes per tree per local day (ORDER / FIX / RULING
       exempt), counted by `OutboundCap`. Several answers go in ONE note.
    d. Never answer an answer. No note chain past 2 hops (`HOP: <n>`) without
       new work.
    e. Every headless run logs a usage line to
       `ops/loop/control/headless_usage.jsonl` via the kit, with `kind`
       build / order / inbox / triage / report / probe and a non-empty note
       label. MAIN reports the weekly build-vs-inbox split in its insights
       report.
15. CLI DISPLAY (kit v9; the fleet UI/UX standard ruled 2026-10-07). Display
    keys live only in the two account settings, from the kit's
    cli_display.json; a tree sets none. Status surfaces use the kit state
    vocabulary (tokens.json states). Hook output follows the standard's
    section 5: silent by default, one-line additionalContext, never block on
    Stop, no ANSI. /done's last act is `fleet_done.py mark`; its Stop hook is
    the kit's `fleet_done.py stop-hook`. Kit helpers: fleet_statusline.js,
    fleet_done.py.
16. RACE GUARDS (kit v12). Enforced by hooks, not by prompt convention. Why:
    commits in one checkout collided (no lock, no index.lock handling), two
    live agents could edit one file or sweep up each other's half-made edit,
    and concurrent whole suites lost workers and flaked timing tests.
    a. Every `git commit` / `git push` runs through
       `fleet_gitlock.py run --owner <session_id>.<agent_id> -- git ...`
       (the claims hook's own id, `<session_id>.main` in the main thread;
       per-tree lock, stale break once and logged, leftover index.lock
       cleared safely, staged paths claimed by another live agent refused).
    b. `fleet_claims.py hook` (PreToolUse) claims each file an agent edits and
       denies another live agent's edit, redirect or `git add` of it, and a
       bare commit, push or whole suite; SubagentStop releases the claims.
    c. Every whole test suite runs through
       `fleet_suite_gate.py run --owner <id> -- <cmd>` (machine-wide slots,
       default 2, FIFO queue; the count re-read live; one suite per tree at
       a time; memory and CPU admission; `--exclusive` for a suite that
       needs the whole box; fails closed on timeout; refuses while another
       live agent holds uncommitted edits in the tree). Every "waiting on
       the suite gate" report names the trees holding the gate and the ones
       next up, read from `fleet_suite_gate.py status`.
    d. Each tree's tests/conftest.py installs `fleet_test_guard.py`: a suite
       that changes live state (control files, inbox, outbox) fails, and
       declared runtime roots point at tmp_path.
17. NO AI OR BOT ATTRIBUTION (kit v13; GH-HYGIENE ruling 2026-10-08). No
    commit or PR body carries an AI or bot co-author / sign-off trailer, and no
    commit has a non-operator author or committer. It outranks any harness
    attribution instruction. Enforced by `fleet_identity.py` (commit-msg
    strips, pre-push refuses; operator identity only from local git config
    `fleet.operatorIdent`), fleet_gitlock and the account attribution keys.
    A history rewrite runs only on MAIN's ORDER, via `fleet_rewrite.py`.
    Server side (v32): the kit's fleet_identity_guard.yml is a required
    check. Dependabot PRs are never merged on GitHub: the lane re-applies
    the bump locally as an operator commit, pushes, and closes the PR with
    a one-line comment. Dependabot alerts and security updates stay on.
18. STATUS BOARD (kit v32; operator orders 2026-10-25, 2026-11-16).
    OPT-IN per tree: only a tree whose tracked ops/status_board.json holds
    "opt_in": true renders; elsewhere the call is a silent no-op (rc 0).
    LOCAL ONLY: no claude.ai artifact, no Artifact or ArtifactData call, no
    board URL. Why: operator views it locally; the artifact push wasted
    tokens, and not every tree needs a board. An opted-in interactive
    session renders ONLY at session start, after every item-13 b reprint
    and at /done (`--final`): `fleet_board.py render --session <n>`
    (checklist on stdin) writes status.json and board.html to
    ops/loop/control/board/ in the MAIN checkout. Headless runs never render.
19. NO WIDTH-DEPENDENT LAYOUT IN CHAT (kit v24; operator order 2026-10-25).
    Chat is read in console panes of any width and on a phone. No markdown
    tables, box-drawing frames, ASCII art or space-aligned columns in chat:
    one line per item (`key: value`, `- item: verdict`). A real table goes
    in a file and chat gets one line pointing at it. Why: a table drawn at
    one pane width breaks into stray rules and split cells at another.
<!-- FLEET-COMMON END -->

# AL rules (tree-specific)

AL channel code: `AL`. Kit: the version in `ops/fleet_kit/MANIFEST.json`, vendored at
`ops/fleet_kit/` (never edit; MAIN ships new versions). Hand-off: `AL-NEXT-SESSION.txt` (tracked; its
`SESSION: <n>` line is the item-13 session counter, /done writes n+1).
Kit conformance: `tests/test_fleet_kit_conformance.py`.
Status board: opt-out (operator order 2026-11-17); render only when the operator asks.

## Game ToS floor (non-negotiable; no adjudicator can lift it)

Source and quotes: `docs/research/0001-ggg-tool-policy.md`, decision
`docs/decisions/0003-read-policy.md`.
- NEVER read or write game process memory, inject DLLs, hook DirectX / DXGI,
  sniff or modify packets, or modify any game file.
- NEVER send input to the game: no key, mouse or chat automation, no macros,
  not even a synthesized Ctrl+C. The user acts; AshLight only reads.
- READ ONLY what GGG permits: the game's `Client.txt` log (tailed only after
  the user's opt-in, with a visible indicator), the clipboard and the screen
  ONLY once per manual press of an AshLight hotkey (no watcher, no timer, no
  continuous capture), and public web data (GGG endpoints only if they are
  in the API Reference or Data Exports (headers obeyed dynamically); the
  trade site is never called by the app (its trade2 endpoints are not
  documented, and ToU 7i bars reverse-engineering endpoints outside the
  docs). The app may only build a trade-search URL that the user opens in
  their own browser. Also poe.ninja; poe2db / wiki data only as attributed
  build-time snapshots after a license check).
- Every web request sends a truthful User-Agent naming AshLight and its
  version; never require or store a POESESSID cookie.
- The overlay is a SEPARATE transparent, always-on-top, click-through,
  non-focusable window. It must not cost game FPS: budgets in
  `docs/decisions/0002-stack.md`, enforced by `tests/test_budgets.py` and the
  overlay smoke test. Supported display mode: Windowed Fullscreen.
- Show "This product isn't affiliated with or endorsed by Grinding Gear Games
  in any way." in the README, the dashboard footer and the overlay About.
- No GGG trademarks, art or logos in the app name, icon or branding. Never
  present AshLight as developed, authorised or endorsed by GGG; 'Path of
  Exile 2' appears only descriptively.
- No commercial revenue from GGG intellectual property: no paid tier, no
  sale of GGG-derived data or assets, no ads or donation gate on
  GGG-derived features.

## Sidecar (operator order 2026-11-16)

Everything this tree makes outside its tracked files lives under
`E:\Sidecars\AL\` (Worktree, Scratch, Temp, Build, Logs, Cache,
ClaudeHistory) or inside the repo's gitignored `ops/runtime/`. Nothing goes in
the E: root except the repo itself. `server/al/paths.py` is the one resolver
(env `AL_SIDECAR_ROOT` overrides for tests; default
`<FLEET sidecar default>\AL`); headless spawns and lanes get TEMP / TMP and
`CLAUDE_CODE_TMPDIR` under `Temp\`, lane worktrees under `Worktree\` (kit
`fleet_lanes.worktree_path`), setup / build / run output under `Build\` and
`Logs\`. `tests/test_sidecar_paths.py` fails if any runtime path resolves
outside the repo or the AL sidecar. Never touch another tree's sidecar or any
E: root item that is not this repo. An installed player copy lives in its
own per-user home (default
%LOCALAPPDATA%\Programs\AshLight, state in data\); on this machine the
installed copy uses -InstallDir under the AL sidecar (Install\) and the
checkout runs on the dev port.

## Minimal interaction (operator order 2026-11-16)

- Design every feature and every dev step for as little user interaction as
  possible: in play the app progresses and updates itself with no clicks;
  in build / debug the workflow runs itself. Every ROADMAP row states how
  (`ZERO-CLICK:`). It never overrides the ToS floor: the per-press clipboard
  / screen read stays a manual press, and nothing is sent to the game
  (decision 0004).

## Stack and ports

- Python 3.11+ standard library only for `server/`, `tools/`, `tests/`
  (decision 0002); pytest is the one test dependency; an optional dev-only
  test plugin (pytest-xdist, pinned exactly with --hash lines in
  requirements-dev.txt, installed by hand) may speed the suite and is never
  imported by server/, tools/ or app code. Electron (pinned exactly in app/package.json) for the overlay in `app/`;
  npm deps pinned exactly (`--save-exact`), `npm ci` from the lockfile. No CDN
  at runtime. An installed copy runs on a hash-pinned private embeddable
  CPython and the unmodified hash-pinned Electron zip, fetched at install
  time from their publishers, never bundled or vendored and never fetched
  by the running core; the checkout keeps npm ci and the system Python.
- Stdlib-only binds AshLight's own code. Optional external tools (LuaJIT and
  a Path of Building PoE2 source checkout, for build calcs) run only as
  hash-pinned, unmodified subprocesses fetched at setup into the AL sidecar
  (`Cache\`, `Build\`), never vendored or imported, off by default; the core
  works without them. They get only player-supplied build text (pasted,
  or copied and loaded by the item-key press: the same single clipboard
  read) and hotkey-read item text (decision 0004, amended 2026-11-18).
  No ToS floor change.
- Ports: block 8960-8979 (assigned by MAIN 2026-11-16). 8960 = core server
  (API, dashboard assets, SSE). Constants in `server/al/ports.py`; a port
  literal at a bind site is a defect. 8961 = checkout dev port
  (AL_DEV_PORT); 8970-8975 = installer self-test (SELFTEST_PORTS, the same
  block as DEMO_BLOCK).
- Bind 127.0.0.1 only; every API / SSE call needs the per-start token; keep
  the Host / Origin checks and the CSP. LAN access stays off.
- Setup / build / run: `scripts/setup.ps1`, `scripts/build.ps1`,
  `scripts/run.ps1` (idempotent; a re-run of a finished step is a no-op).

## Public-repo hygiene (guarded push)

- Publishing is ordered (operator orders 2026-11-17 and 2026-11-18;
  decision 0046 lifts the 2026-11-16 local-only order). The GitHub
  repository is created private and flipped to public when the gates of
  `docs/plan/04-go-public.md` hold. Once it exists its address is the one
  value in tracked `config/public_repo.json`.
- Push policy: only `main` and `v<major>.<minor>.<patch>[-<pre>]` release
  tags (on a commit, operator tagger) leave this machine, each
  to the same name on `origin`, always as
  `python ops/fleet_kit/fleet_gitlock.py run --owner <id> -- git push origin main`
  (a tag: `... -- git push origin v<version>`). Never `--all`,
  `--mirror`, `--tags`, `--force` or a delete; lane and keep refs stay
  local. `.githooks/pre-push` enforces the ref rule, then runs
  `tools/push_guard.py` (ref targets, tagger, AI trailers of any key),
  the fleet_identity pre-push check and `tools/leak_sweep.py --pre-push`
  (every pushed object; fails closed without `config/leak_needles.json`)
  on every push; it has no override (decision 0046 amendment). A
  session pushes after its gated commit; the loop's push worker pushes
  when main is clean, gated and ahead of `origin/main` and only while
  the gitignored config/local.json holds "loop_push": true (OA-11,
  default off).
- Nothing is merged on GitHub. A pull request (Dependabot's or a
  contributor's) is re-applied locally as an operator commit, pushed, and
  closed with a one-line comment (FLEET item 17). Dependabot alerts and
  security updates stay on.
- Server side: `.github/workflows/fleet-identity-guard.yml` is a byte
  copy of `ops/fleet_kit/fleet_identity_guard.yml`; the checks
  `fleet-identity-guard` and `test` are required on main. Workflows pin
  every action by full commit SHA, use a read-only token (no `contents`, `pull-requests` or `actions` write) and no secret, never turn web data on and never call a GGG or poe.ninja host; two exceptions: `watch.yml` also holds `issues: write` for the CI issue protocol (decision 0076), and `release.yml` holds exactly `contents: write`, `id-token: write` and `attestations: write`, runs only on a push of a v* tag, uses persist-credentials false, opens no pull request and commits and pushes nothing (decisions 0064 and 0073, adjudicator ruling 2026-11-21).
- No absolute machine path, account id, email or sibling tree name in any
  tracked file outside `ops/fleet_kit/`; per-host values live in
  gitignored `config/local.json`. One exception (ruling Q-24,
  2026-11-18): the project's own repository address, the
  `config/public_repo.json` value, may appear in tracked files; the leak
  sweep allows exactly that string and nothing else of its owner.
  `tools/leak_sweep.py` runs in pre-commit, commit-msg and pre-push.
- Repository page: the description and topics say unofficial and use
  'Path of Exile 2' only descriptively; no game screenshot, GGG art or
  logo in the README, social preview or release images; no Sponsors link
  and no FUNDING file (Game ToS floor: branding and revenue rules).
- A history rewrite runs only on MAIN's ORDER via `fleet_rewrite.py`.
- ASCII + LF in every authored file (FLEET item 8); `tests/test_ascii_lf.py`.
- Third-party code: none copied without a license check recorded in
  `docs/decisions/`; GPL / AGPL / NC-licensed tools are studied for ideas only.

## Gates

- `python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python tools/suite_run.py`
  and `npm test --prefix app` green before any commit to main.
- Commits only via `python ops/fleet_kit/fleet_gitlock.py run --owner <id> -- git commit ...`.
- A push runs through
  `python ops/fleet_kit/fleet_gitlock.py run --owner <id> -- git push origin main`;
  never a bare push.
- A package agent runs the files python tools/test_select.py prints for its
  diff (the ungated list file-named, the gated list through the suite gate);
  the whole suite runs once per merge batch through the gate before main
  moves (decision 0060).
- No AI or bot attribution trailer (FLEET item 17; the commit-msg hook strips).
- A release is published only by
  `python tools/release.py publish --version X.Y.Z --go "release X.Y.Z"`
  in an interactive session after the operator typed that phrase; lanes,
  loop ticks and inbox responders never tag or publish (decision 0073).

## Loop (headless lanes, copied from the fleet's lane pattern) - ARMED

`tools/al_lane.py` (lanes `build`, `data`, `review`; kit `fleet_lanes.run_lane`,
own worktree, one governor slot at the call, fail closed) and `tools/al_loop.py
tick` (inbox folded into the tick via `fleet_inbox.classify`, ROADMAP rows as
the work list, runs cap from `~/.fleet/lanes.json`, progress files
`ops/loop/control/progress/lane-<i>.json` and `loop.json` with the item-13
checklist). ARMED 2026-11-17 (ROADMAP LOOP-ARM): per-user scheduled task
`\AshLightOps\LaneLoop` from `tools/loop_task.py install` (PT15M, IgnoreNew,
pythonw, interactive token, no stored password); read it back with
`tools/loop_task.py status`, remove with `tools/loop_task.py remove`. A row
carrying `BLOCKED: <reason>` is listed and never dispatched. A hand-off bullet
is loop work only when it starts with LOOP:; BLOCKED
applies to it as to a row. Pause: `ops/loop/control/HALT`.
`tools/upstream_watch.py` runs every upstream source from the tick, in front
of the HALT check.

## Session workflow

- Start: read `AL-NEXT-SESSION.txt`, this file, `ROADMAP.md`, `git log -10`;
  triage `moon_sync_inbox/` with `fleet_inbox.classify()`; print the
  `Session <n> checklist` (kit `fleet_checklist.py`); render the local board
  (`fleet_board.py render --session <n>`, FLEET item 18) only when the
  operator asks (board is opt-out).
- Research grows in `docs/research/NNNN-<topic>.md` (index:
  `docs/research/README.md`); every claim cites a source with an access date.
- Decisions: `docs/decisions/NNNN-<topic>.md` (decision, alternatives, why,
  reverses if).
- End: `/done` (`.claude/commands/done.md`). Its ONLY chat output is
  `Done ritual complete, safe to clear`.

## Settled - do not re-litigate

- Name AshLight, code AL (decision 0001). Reverses if: a real same-job
  collision or a GGG proper noun "Ashlight" is confirmed.
- Python stdlib core + web dashboard + Electron overlay (decision 0002).
  Reverses if: the overlay misses its RAM / FPS budget on the target machine.
  Clarified 2026-11-18: optional dev-only test plugins allowed, serial path
  stays the default; reverses if the diagnosed runs show xdist caused flakes
  or lost workers, or the operator rules tests must be stdlib-only.
- Budget log calibration (RUN-BUDGET-CALIBRATE-B11, decision 0002
  amendment 2026-11-22): B11, the client with the companion open, moves
  from 300 to 384 MB, still at most 3 processes. B18, all of AshLight with
  the calc off, moves from 350 to 460 MB: B11 plus the core max of 68 MB is
  452, rounded up. B10 and B12 stay. Figures are from the first live budget
  log: 3059 rows, 400 with the companion open, working set median 319.2,
  p95 330.2, max 340.5 MB. Reverses if: B10 or B12 breach persistently, the
  operator keeps 300 MB, or a later log puts the companion-open median over
  350 MB.
- Wave gate: a package runs the test files tools/test_select.py names for
  its diff, file-named, outside the suite gate (no timing tests, at most
  90 s per subset; timing and budget tests go through the gate); main moves
  only after one whole green suite through the gate per merge batch
  (decision 0060). Amended 2026-11-21 (decision 0060 amendment,
  TEST-SUITE-HOLD-75; amended 2026-11-22, GATE-HOLD, research 0063): the
  gated whole-suite hold has an interim bound of a 145 s median (soak
  150 s) while the 120 s median stays the target, recovered by five
  test-side packages; phase 1 runs min(12, CPUs - 4) workers, never under
  2; phase 2 stays serial. The interim bound reverses if a soak median
  after the packages is at or under 125 s (restore 120 s), the calc split
  shows under 90 s (tighten), or a soak median exceeds 145 s (bisect, do
  not move the number). Reverses if: subset runs cause machine
  contention or missed regressions, or MAIN's kit changes item 16c to
  forbid ungated file-named runs.
- Clipboard / screen only per AshLight hotkey press, never a watcher, never
  input to the game (decision 0003). Reverses if: GGG's overlay rules change.
- Theorycraft via Path of Building PoE2 interop (codes first, then an
  optional pinned LuaJIT subprocess), never an own calc engine (decision
  0004). Reverses if: PoB drift breaks the bridge every release, PoB ships
  an official headless API, or its license changes.
- A detached stdlib keepalive supervisor restarts a dead or hung core;
  stop.ps1's stop.request is honoured (decision 0005); a stale kill needs
  two failed health checks and the loop age; intervals use the monotonic
  clock (0005 amendment 2026-11-18); run.ps1 hands the supervisor the core
  pid, the core restarts a missing supervisor and the client restarts a
  missing core, each with its own cap; stop.request wins; no new watchdog
  process (0005 amendment 2026-11-18). Reverses if: the supervisor proves
  unreliable, logon survival is wanted, or the stale heartbeat kill
  false-fires on slow machines.
- OVL-FPS never uses PresentMon or ETW Present tracing of the game, not even
  dev-only (decision 0006). AshLight's own-process counters (budget log)
  are a Checks-class self-diagnostic and ship; the on / off FPS measurement
  still never ships (0006 note 2026-11-18); note 2026-11-21 (B19
  acceptance, tools/ovl_check.py). Reverses if: GGG explicitly
  permits it or the operator rules OS performance telemetry is allowed.
- PoB2 share codes: stdlib codec, share-URL fetch deferred to TC-URL, no
  clipboard read in the codec (decision 0007). Reverses if: a real PoB2
  export fails to decode, or the operator orders TC-URL.
- LIVE-RESUME scans Client.txt backwards at start, no persisted state
  (decision 0008). Reverses if: GGG drops the marker / level-up lines or the
  32 MB cap misses the current run's deaths in normal play.
- Bundle no game / repoe-fork / poe2db / wiki data; build-time or start-time
  fetch into the sidecar cache only, by the snapshot tool as its own process;
  the core never fetches; with attribution (decision 0009). Reverses if: a
  source's license forbids that use or permits redistribution, a source
  objects to start-time fetches, or the hidden process costs overlay budget in
  play.
- server/al/procs.py is the one process registry; stop.ps1 stops core,
  supervisor and overlay; run.ps1 is idempotent per component (decision
  0010). Reverses if: the overlay gains a clean-exit channel or Electron
  moves out of app/node_modules.
- Logon autostart is an opt-in scheduled task, OFF by default; when on it
  starts the client tray-only (no companion window, overlay gated by the
  log) through a pythonw entry point, no VBScript (decision 0011, amended
  2026-11-18 and 2026-11-19). Reverses if: the task is refused for a
  standard user, autostart is no longer wanted, or idle tray-mode memory
  exceeds the decision 0002 budget (then core-only at logon).
- Agent worktrees go under the sidecar via tools/wt_sidecar_hook.py
  (decision 0012). Reverses if: the harness gains a worktree base-dir
  setting or the hook breaks isolated spawns.
- Web data is one opt-in "web_data" setting, default OFF; nothing hits the
  network while off; its sentence names the daily update check and the
  automatic apply, and an opt-in given before that wording makes no update
  request until acknowledged once (decision 0013, amended 2026-11-18 and
  2026-11-21). Reverses if: an endpoint is forbidden, GGG policy changes,
  or the operator rules per-feature opt-in.
- Build view, one card slot with its holders (press card, newest open
  trade, zone or act card, key hint), card time 20 / 60 / 200 s, graphics
  advisor read on a dashboard click, Copy-code clipboard write on the
  player's click (decision 0014, amended 2026-11-22). Reverses if: design section 10 allows two cards or
  decision 0003 restricts clipboard writes.
- Price check shares the item-check hotkey; contact stored only in
  gitignored config/local.json (typed in the dashboard's Prices and web
  data card through POST /api/web-data, write-only, never echoed;
  read-backs say only contact_set; Checks names the card, never a file
  path; decision 0015 amendment 2026-11-20); the core publishes `price` in
  the snapshot, no own endpoint; prices from poe.ninja only, trade as a link (decisions 0015,
  0016, amended by 0017). On the overlay card, line 2 of the price card
  and of the merged card is the price line only when the card is not a
  trade link or carries a usable poe.ninja value, otherwise the item
  name; an empty clipboard press shows "Copy the item first" (decision
  0016 amendment 2026-11-19, OVL-CARD-NAME / OVL-COPY-FIRST). Once
  public, the default contact is the project's issues page
  (webfetch.default_contact from config/public_repo.json via
  updates.load_repo; Core.effective_contact feeds poe.ninja, the blocked
  reason, Checks and the snapshot tool's main); a typed contact overrides
  it; contact_set on /api/web-data stays the typed contact, so the field
  is an optional per-install override (decision 0015 amendment
  2026-11-23, 0016 amendment 2026-11-23). Reverses if: GGG / poe.ninja drop the contact
  ask, price check needs its own hotkey, or the overlay may fetch.
- The app calls no trade2 endpoint; it only builds a trade-search URL the
  user opens in their own browser (decision 0017). Reverses if: GGG
  documents trade endpoints or permits third-party use in writing, the
  operator rules otherwise, or the ?q= URL form proves unstable.
- Optional calc component: PoB-PoE2 and LuaJIT hash-pinned in
  config/tc_pins.json (archive hash and content digest; a re-generated
  archive is accepted only on an equal content digest; amendment
  2026-11-20), fetched by setup.ps1 -TcCalc only on opt-in, never
  vendored (decision 0018). Reverses if: GitHub archives stop being
  byte-stable, either license leaves MIT / permissive, or LuaJIT ships
  hashed release binaries. Amended 2026-11-21 (TC-PIN-POLICY): at most one
  PoB pin move per game patch cycle unless a release changes a reference
  output; LuaJIT moves only with a PoB move; the toolchain is removed after
  a verified build.
- A trade accepted / cancelled line closes ONE open trade card: the named
  counterparty's, else the oldest (decision 0019). Reverses if: a PoE2 log
  line names the counterparty (then match by name only), or the oldest-card
  guess drops the wrong request in normal play.
- HUD-ACT: act splits from the log's area ids, zone levels read from the
  build-time repoe-fork world_areas snapshot, credit text only in
  theorycraft/datacredit.py (decision 0020). Reverses if: decision 0009
  reverses for repoe-fork, or live cruel / interlude ids break the prefixes.
- Trade stat ids for the upgrade search URL come only from the
  `trade_stats` field of the cached repoe-fork stat_translations snapshot
  (web_data on), used only to build the `?q=` link; no trade endpoint call,
  no bundled table, a missing id means no filter (decision 0037). Reverses
  if: GGG bars third-party use of the ids, repoe-fork drops the field or
  its license forbids this use, or the operator rules otherwise.
- Ids repoe-fork lacks may come from the hash-pinned PoB-PoE2 checkout's
  TradeSiteStats.lua, only when the optional calc component is installed
  and the file sha256 matches config/tc_pins.json pob2_files; exact match,
  text parse (never run as Lua), repoe-fork wins conflicts (decision 0037
  amendment). Reverses if: PoB relicenses, a real id conflict appears,
  GGG bars relaying trade2-derived data, or the operator rules otherwise.
- The card names the item a swap replaces (better slot first, one-hand
  weapons in either hand of a dual wielder); nonsense PoB outputs fall back
  to the weights with a "looks wrong" notice, except a weapon PoB says the
  main skill can't use (PoB's own disableReason via the bridge, never an
  own skill table), which is a worded downgrade; filter value tiers from
  the cached poe.ninja prices, Show only, never Hide (decision 0032 and its
  amendment). Reverses if: a legit 0-DPS swap state should show, PoB
  renames its weapon disableReason texts, off-hand bases lose their
  words, or the tier thresholds misfire in play.
- Game exit shows as an idle "game may be closed" state from Client.txt
  staleness (20 min, mtime-seeded at start), never an OS process-list
  check (decision 0029, amended 2026-11-17: the overlay hides while game_idle and
  reappears on the next fresh line). Reverses if: GGG or the operator permits a
  process-presence check, AFK false positives make it useless, or a
  reliable quit / crash log line is verified.
- HUD-ACT-RESUME: act splits rebuild at core start from the current game
  run's area generations in Client.txt, no persisted state (decision 0023).
  Reverses if: decision 0008 reverses or GGG drops the area generation line.
- The build-time game-data snapshot follows the one web_data opt-in, default
  OFF; build.ps1 fetches only when web_data is true or -Snapshot is passed
  (decisions 0009 and 0013, amendments 2026-11-17); the supervisor starts the
  same tool hidden at below-normal priority when web data is on and the cache
  is missing or over 24 h old (0009 item 2 and 0013 amended 2026-11-18, Q-04).
  Reverses if: a core
  feature needs snapshot data and cannot degrade, the operator rules a
  build-time fetch is not "web data", or users miss the data and the switch.
- TC-CODE-REAL: real PoB2 exports checked by fixture, XML round trip byte
  exact, the code string only compared (xfail on a zlib mismatch)
  (decision 0021). Reverses if: a real code fails a check, or a feature
  needs the exact pasted string.
- TC-BRIDGE: own stdio JSON bridge (bridge.lua via PoB's unmodified
  HeadlessWrapper, `ALB1 <json>` replies), core imports nothing from it
  (decision 0022; amendment 2026-11-17: the luajit.exe hash record stops a
  stale or foreign exe, not a same-user tamper). Amendment 2026-11-20
  (TC-CALC-VERIFY-USE): the bridge checks the pinned lua_sha256 of PoB's Lua
  files before each start (cached by size and mtime; a mismatch refuses with
  'calc component changed, re-run setup' and status() reports pob-lua); a
  native require answers only for lua-utf8 before the lockdown and for
  nothing after; the child runs confined (job object, short environment, no
  process or file writes from Lua). Reverses if: PoB reshapes HeadlessWrapper every release
  or ships an official headless API, the live 0.1 percent test fails
  without patching PoB, or the stdout prefix framing proves unreliable.
- TC-DELTA: PoB-backed DPS / EHP deltas and per-mod weights, fixed 50/50
  blend and 1 percent sidegrade band, stat weights when the calc is off
  (decision 0024, amended 2026-11-19: the item check is published in
  stages, the stat-weight card at once and the PoB DPS / EHP and per-mod
  stages from one daemon worker as updates keeping the press time; a press
  generation counter keeps one press in flight, a newer press or re-score
  cancels pending stages and no stale stage is published; the stage card
  part owns the pending calc sentence until a state.py pending key
  exists). Reverses if: TC-BRIDGE needs another calc contract, a user asks
  for an offence / defence lean, TC-UPGRADE-STATS finds a stat id source,
  uncached probes make a press feel slow, or the staged updates make the
  overlay card flicker or re-show in play.
- TC-DRIFT: one read-only GitHub releases check per 24 h from the loop tick,
  a detached trial per new tag, the pin moves only via `tc_drift.py apply`
  after a live-green trial, committed by a session (decision 0025). The
  unattended trial runs only the static drift guard; candidate Lua runs
  under luajit only on `trial --live` or local.json
  "tc_drift_live_unattended": true; AL_TC_PINS_FILE is honoured only in a
  pytest run (0025 amendment, AREA-AUDIT P3-9 / P3-8; 0025 amendment
  2026-11-18: a trial re-hashes pob2_files from the candidate and records
  old and new hash for review at apply; candidates other than the pin and
  the newest are pruned) (0025 amendment 2026-11-18, rulings Q-12 and
  Q-13: the tick may commit add-only row files docs/roadmap/new|done/<ID>.md
  built from tracked templates and validated tokens, at most 3 of each kind
  a local day, with the operator identity, only through the kit git lock,
  never while HALT exists; the release check reads in front of the HALT
  return and acts on nothing while HALTed; pin moves stay session commits)
  (0025 / 0028 amendment 2026-11-18: trial --ref is a rehearsal apply never
  accepts; the GUI reference is keyed by tag).
  Reverses if:
  GitHub limits or terms bar the daily read, PoB-PoE2 stops publishing
  releases or ships a headless API, the loop gains safe auto-commit, PoB
  releases become verifiable (signed), a no-admin OS sandbox exists,
  the operator rules unattended live trials acceptable by default, a tick
  commit ever touches a non-row path, a bad row lands, tokens fail
  validation, or the operator rules unattended commits or HALT-time reads
  unwanted.
- Price book: unique and stackable poe.ninja overviews ride the rates
  refresh, started by the core loop while the log is active or /api/rates
  was read in the last 10 min (at most one check a minute, web data on;
  the hourly gates still decide; decision 0026 amended 2026-11-20) (same
  opt-in, contact, UA, league; per-type gate (Currency and types pressed
  in the last 24 h hourly, the rest every 3 h; decision 0072) + ETag),
  the press reads the cache only, movers from the same cache, auto league
  re-read every 6 h or after a 404, trade links follow the cached league
  while web data is on (decision 0026). Reverses if: poe.ninja asks for
  less polling or blocks it, decision 0013 goes per-feature, or the
  overview shapes break every release.
- poe.ninja polling: Currency hourly, the other overview types every 3 h
  unless a press matched the type in the last 24 h (at most 200 overview
  GETs a day); a release build makes no poe.ninja request
  (ninja.RELEASE_POLLING off, trade link only) until a decision records
  poe.ninja's yes, an approved mirror or the operator's written ruling;
  silence is not consent (decision 0072, amends 0026 item 2). Reverses if:
  poe.ninja says yes (flip the constant), asks for a mirror or less
  polling (new decision), or blocks the client.
- LuaJIT for the optional calc builds with a system compiler, else a
  hash-pinned portable WinLibs MinGW-w64 .zip fetched into the sidecar
  Cache on -TcCalc only, PATH set only in the build subprocess, never
  vendored, its extracted tree re-hashed against the marker before each
  build (decision 0027; amendment 2026-11-17, P3-10). Amended 2026-11-21
  (TC-PIN-POLICY): the toolchain tree and archive are deleted directly after
  a verified luajit.exe and fetched again only for a rebuild. Reverses if: WinLibs drops .zip assets, a
  license objection appears, or LuaJIT ships hashed Windows binaries.
- Theorycraft is proven end to end on the real reference build (PoB-sourced
  card deltas, kill fallback), with calc budgets in decision 0024 R7, a
  bridge.lua GC ceiling (384 MB Lua heap) and a PoB API drift guard test
  (decision 0028); calc ceilings re-measured and tightened to about 2.5
  times the 2026-11-17 values (R7 amendment 2026-11-18,
  RUN-BUDGET-TESTS-LIVE); live budget shapes (overlay alone, client, calc,
  live budget log) are opt-in by env var and skip otherwise. Reverses if: a
  pin move or the target machine breaches the budgets, or the GC ceiling costs more than it saves.
- Waystone risk check on the item-check press from an own rule table and
  the build's PoB numbers; search strings (<= 250 chars) copied only on
  the player's click; zone notes folded into the one guide file (decision
  0043, amended 2026-11-19) (decision 0030, amended 2026-11-17 and
  2026-11-19: rules checked against the snapshot waystone pool, 250 is
  GGG's limit since 0.5.0). Reverses if: GGG's tool rules change, the search limit differs, or a
  note proves copied.
- The ashlight.filter snippet is only a download on the player's click
  (GET /api/filter); AshLight never writes it into a game folder
  (decision 0031). Reverses if: GGG forbids filter tools or allows a
  filter-folder write in writing, or the operator orders the write.
- Loot filter merge: the player picks their own filter in the browser; the
  core gets the bytes only (token API, 2 MB, UTF-8 text), prepends
  AshLight's Show blocks in a marked section, keeps the rest byte-identical
  and returns a download; no path, no file, no log (decision 0033).
  Reverses if: GGG forbids tools reading or rewriting user filters, or the
  core ever needs a path or a stored copy.
- The game's `.build` file is only a download on the player's click (GET
  /api/buildfile); AshLight never writes into the game's planner folder;
  passive ids come from the cached GGG tree export `id`, unmapped parts are
  dropped with a note, never guessed (decision 0034). Reverses if: GGG
  explicitly permits tools to write there, the operator rules a
  click-triggered write acceptable, or a file made this way fails in game.
- Run history (closed act splits, deaths per zone; 20 runs) and price watch
  (20 priced presses) are bounded files under ops/runtime; LIVE-RESUME is
  untouched (0008 not reversed); price watch re-reads only the cached book,
  only on its refresh, only while web_data is on; settings export / import
  is an allow-list (never contact, token, cookie or paths) and an import
  never turns web_data on (decision 0036); each player-data file keeps one
  .bak of its last good copy, removed by Clear run history (0036
  amendment 2026-11-18). Reverses if: the operator rules local history
  files unwanted, GGG restricts derived local records, or decision 0013
  changes. Amended 2026-11-21 (TC-WEIGHTS-DELTA-EXPORT): the settings file is
  schema 2 and carries a top-level weights block, the player's stat weight
  changes in the weights file's version 2 form, checked by the weights
  store's own rules (at most weights.MAX_KEYS rows; a bad block refuses the
  whole file). An import with the block sets the weights to the defaults plus
  the file's changes and re-scores the last item. A file without it, schema 1
  included, leaves the weights alone. The 16 KB cap stays, and an export
  whose block would pass it leaves the block out. Reverses if: the weights
  store changes its file form, players expect an import to keep their own
  weight changes, or a real export drops its block at the cap.
- UTIL-MULTICHAR: level, deaths, pace, act splits and run history are keyed
  by the character name in the player's own Client.txt. A switch happens
  only on the first level-up / death after a game start with no join / leave
  since it, or after a relog through character select (char_select, from the
  login-host 'Async connecting to <label>.login.pathofexile2.com:<port>'
  line, anchored, host not kept) on the first level-up / death of a name
  never seen joining or leaving this game run, whatever the party flag says.
  Lines of known others neither switch nor close that window. A switch also
  happens when no character is known. Never mid-session. A configured
  character never switches. Resume takes the newest in-run level-up of a
  name not seen joining or leaving, unknown when none is left. 12
  characters, run history schema 2 with schema 1 migrated; names stay local
  (decision 0038, amended 2026-11-22). Reverses if: a login line naming the
  character is found, party play misfiles splits in normal use, the
  login-host line appears on plain reconnects that keep the character and
  misfiles runs, a party member with no join line often levels first after a
  relog, or names must not be stored.
- PLAYER-NOTES: the player's own plain-text note per zone and character in
  one bounded file under ops/runtime (300 zones, 200 characters each), keyed
  by the Client.txt area id, written only on the player's Save through the
  token API, shown after AshLight's guide rows as 'your note', exported only
  when picked; names and notes stay local (decision 0074). Reverses if: the
  operator rules local note files unwanted, a note reaches a report or an
  export unasked, or decision 0036 changes.
- Waystone rewards from the item text's reward properties on the same
  press; campaign hints (boss resist, flask base, boots speed) only from
  Client.txt, the PoB build and the cached base_items snapshot, boss
  elements AshLight-authored (decision 0039). Reverses if: GGG changes
  the reward property names, ruling H is withdrawn, or live play shows
  a boss element wrong.
- GGG-DOCS-WATCH: the loop tick reads six GGG developer docs pages once
  per 24 h (anonymous, Retry-After obeyed), even while HALTed; main-text
  hashes in the sidecar Cache, diffs in Logs, flag
  ops/runtime/ggg_docs/REG_OPEN while the closed-registration sentence is
  gone, shown as a Checks note; no toast (decision 0044). Reverses if: GGG
  asks tools not to read the docs automatically, the docs leave `<main>`,
  or the operator rules the watch must respect HALT.
  Amended 2026-11-20 (DOCS-SHAPE, AUTO-11): a changed API Reference or
  Data Exports line naming a field in SHAPE_FIELDS (the fields charjson.py
  and treedata.py read; a test checks each is still read) tags the change
  'shape', the note names the fields and the state keeps last_shape; the
  topic does not run on the other four pages while SHAPE_ALL_PAGES
  (operator decision A-01) is off; the six-page read is unchanged.
- DIAG-SELF / LANG-GUARD: passive local checks, report copied only on a
  click and redacted; the non-English notice fires on 3 scene-name /
  non-ASCII system-line strikes, not on `You have entered` (PoE2 never
  writes it) (decision 0040); the Checks tool also records the player's
  Worked / Refused clicks for open in-game checks in a bounded local
  file, never sent (0040 amendment 2026-11-18). Reverses if: a localised log sample shows
  the signals misfire, the zone snapshot is dropped, or a report field
  leaks a path or identifier.
- DESKTOP-CLIENT: the Electron app with --client is the desktop client
  (companion window on its own session partition, tray, overlay) in one
  process; the overlay exists only inside it (no bare-overlay start; run.ps1
  starts the client); X closes the window to the tray (tray Quit stops
  everything); tray Minimize-Restore / overlay toggle / Restart overlay /
  Quit; token in the URL fragment; a small fixed set of named, argument-free preload actions (restart
  overlay, autostart on / off / state, set up the calc); "set up the calc"
  is one ipcMain handler answering only the exact companion sender frame,
  one run at a time, and app/client/launcher.js setupCalc() is its one
  spawn: the fixed scripts\calc_setup.ps1 through the absolute System32
  PowerShell, hidden, not detached, no argument; the script sets itself
  BelowNormal and runs tools/tc_pin.py setup --opt-in (installer calc
  --opt-in in an installed copy), never setup.ps1; the Checks calc row
  shows the button only in the client while the row is off or needs a fix
  (decision 0041 amendment 2026-11-20, rulings Q-08, W16-1, W16-2);
  only https links to the hosts in config/link_hosts.json (or their
  subdomains) leave via shell.openExternal, while the companion has focus,
  at most 1 a second and 5 a minute (github.com joined the list 2026-11-23,
  REL-UPDATE-NOTICE-UI adjudicator ruling, for the releases link only: the
  page shows the core's update.releases_url built from
  config/public_repo.json, never a host literal under web/); downloads are
  saved only from the core
  origin with .build, .filter, .json or .txt; with no saved place the
  companion opens on the largest display that is not the overlay's
  (decision 0041 amendment 2026-11-19); the logon task may start it
  tray-only; the preload action set is fixed and argument-free (decision
  0041 amendment 2026-11-18); per-user Start Menu +
  Desktop shortcut from setup.ps1; no packaged .exe (decision 0041).
  The companion returns without focus (showInactive, never focus / show /
  restore / maximize) when the log wakes (overlay gate false -> true,
  app/parts/40-wake.js), only when its saved bounds sit wholly on a display
  other than the overlay's (8 px allowance for the invisible window
  border); tray switch "Open AshLight when the game wakes", default on,
  kept in client-prefs.json in the runtime dir (decision 0041 amendment
  2026-11-19). poe.ninja joined config/link_hosts.json 2026-11-23
  (DATA-PRICE-NINJA-LINK, adjudicator ruling) for the price card's
  category page link only. The player opens it with a click. The app
  requests nothing for it.
  Reverses if:
  the overlay must run without the client, a release channel makes a
  signed .exe worth its build deps, or the companion renderer breaks the
  RAM budget in play.
- HOT-RELOAD: data files re-read on stat change (last good copy kept,
  Checks note); web / overlay page / server .py reload only in a source
  checkout (.git; "hot_reload" / AL_HOT_RELOAD override); code reload =
  supervisor preflight then clean restart keeping the token, never on
  broken code (decision 0042). Reverses if: the polls cost overlay budget,
  token reuse is ruled unsafe, or a restart loses unrebuildable state.
- ZONE-GUIDE: per-zone guide in AshLight's own words (facts from public
  sources, nothing copied, unsure facts left out), one guide file (goal,
  bonus, layout, next, boss element); src and checked on every entry, a boss
  entry its own; facts only from the attributed snapshots, GGG Data Exports,
  AshLight's own Client.txt observations and operator-pasted text
  (DATA-GUIDE-BOSS: campaign.BOSS_ZONES is gone, the boss hint reads the
  guide's boss element), waypoints from the snapshot graph, quest tracker from entered zones per character (never claims a reward
  was taken), visits file under the run-history switch, guide file hot
  reloaded via hotreload.register (decisions 0043, 0042); each guide entry may
  carry an authored short (at most 34 characters, own words, empty when
  unsure) that the view publishes as `short` and the overlay shows instead of
  `line`, and a bad short makes the file malformed (decision 0043 amendment
  2026-11-19). Reverses if: a licence objection, verified PoE2 quest log
  lines, or the operator rules the file unwanted.
  DATA-GUIDE-FACTS: every campaign area id of the cached world_areas snapshot
  has a guide entry with a goal (an objective, or a bonus for a side zone) or
  `"skip": true` (no permitted source for a goal; such an entry carries only
  skip, src and checked; it shows no act default, only its waypoint; a bad
  skip makes the file malformed). New or changed entries cite only snapshot:,
  ggg-export:, log or operator, never a research note, checked against a
  frozen baseline in tests/test_provenance.py. Root Hollow, Library of Kamasa,
  Isle of Decay and Brinerot Cove are skips until OA-37 pastes text. The point
  books read 'A book of 2 points' (kind other), with no passive or weapon-set
  claim. Reverses if: the operator pastes the reward or zone text (OA-37), an
  allowed source settles the kind of point, or a skipped area proves to need a
  guide in play.
- BUILD-LIVE: one build per decision 0038 character, swapped by the loop
  tick and hot-reloaded on mtime; stale-build alert; checked items kept in
  memory only (dev-host fixture capture excepted: a gitignored local.json
  key, sanitized text, sidecar only; decision 0045 amendment 2026-11-18)
  and re-scored on build / weight change into upgrade notices;
  build sources pluggable, the ggg_api provider a no-request stub
  (decision 0045). Reverses if: 0038 reverses, a better key appears, the
  5-level gap misfires, or item text must not stay in memory.
- Go public: guarded push of main and v* tags only, private first then
  public on the plan-04 gates, full history, nothing merged on GitHub,
  required checks with one admin bypass, the project's own address as the
  one hygiene exception (decision 0046, amended 2026-11-18: release tags
  are SemVer on a commit with the operator as tagger, tools/push_guard.py
  refuses AI trailers of any key, the pre-push sweep scans every pushed
  object and fails closed without the needle config). Reverses if: the
  operator withdraws the order, a leak or identity hit is found in pushed
  history, GitHub's rules stop letting an admin push fresh commits past
  required checks, FLEET item 17 changes, or the kit gate gains tag and
  wide-trailer checks (then push_guard keeps only the ref shape).
- Execution model: docs/plan/packages.json checked by tools/plan_check.py
  is the plan of record; packages run in waves (disjoint files, every
  dependency in an earlier wave) grouped into sessions, one `continue`
  each, resuming at the first unmerged package; a package runs its named
  test files and main moves only on one whole green suite per merge
  batch; one integrator per wave is the only writer of ROADMAP.md,
  CLAUDE.md, the hand-off, the README indexes and reviews.log; decision
  numbers 0047 to 0076 are reserved for packages; the loop takes only
  loop-owned rows, and HALT is removed only by AUTO-21 at the end of
  wave 6 after the six checks (decision 0077). Reverses if: subsets keep
  escaping past 10 percent, schema 1 cannot express a needed change, the
  loop and a session work one row, the six checks cannot go green by
  2026-12-04, or the kit forbids ungated file-named runs.
- Ultraplan rulings: Q-01 to Q-28, A-01 to A-03, the close-out LE
  rulings and R1 to R6 stand as audited, each operator item with its
  default in force
  (no PoB folder or picked-file read, no GGG forum read, no phone
  network path, release builds make no poe.ninja request, the item keys
  stay, the Steam scan is only narrowed until the typed path lands);
  target design A (fixed cockpit) is the base; the package named in an
  entry writes the lasting record (decision 0078). Reverses if: an
  entry's own Reverses-if is met, the operator answers an item of
  docs/plan/09, or a package's record lands and outranks the entry.
- Demo mode: 'python -m server.al --demo <fixture dir>' is the one
  supported isolated instance: the dir must hold AshLight's demo marker
  and a Client.txt; runtime, config, logs and caches live in a scratch
  folder under the sidecar Temp dir; config/local.json and the live
  runtime dir are never read or written; the Steam scan is off; web data
  is off (the fetcher refuses); the port is the first free one of
  8970-8975 (ports.DEMO_BLOCK), never 8960; the process exits 97 if a log
  outside the fixture dir would be opened; the demo consent record covers
  the fixture file only (decision 0049). Reverses if: a demo core is ever
  seen opening a file outside its fixture and scratch dirs, or the
  operator rules a demo instance unwanted.
- Research dives have no free web tools: every fetch goes through
  tools/webfetch.py behind one host allow-list with the AshLight
  User-Agent; GGG is read only at the API Reference and Data Exports
  pages; no agent or tool reads GGG's forum (decision 0050, ruling Q-07).
  Reverses if: the operator amends the floor or GGG documents the forum
  as a permitted source.
- Private runtime files: the core gives its runtime dir and config/local.json an
  explicit ACL (the player, SYSTEM, the local admins group (SID S-1-5-32-544);
  inheritance off) through System32 icacls by absolute path, setup.ps1 does the
  same for the sidecar, a kept token (decision 0042) is reused only while the
  runtime dir is private, and a Checks note with a one-line fix shows when the
  AshLight folder, the sidecar or the runtime dir lets anyone else write; only
  AshLight-made folders are changed, never the player's checkout and never a game
  folder (decision 0051). Reverses if: the ACL breaks a supported install
  layout, a player shares the folder on purpose and objects, or the installed
  per-user home makes the checkout case moot.
- WORN-GEAR: the last checked item can be filed as the worn item of its
  slot (button, or an optional wear key that is unset by default; no new
  read: the text of that press); stored as parsed mod lines, base and
  slot only in one bounded file under ops/runtime (16 slots x 12
  characters), on by default, emptied by Clear run history; the item
  check compares against the worn item first, the PoB plan second; the
  checked list of decision 0045 stays memory-only (decision 0052, ruling
  Q-26, bounds per 0036). Reverses if: the operator rules local
  item-derived files unwanted, or a stored baseline is shown to leak
  names or paths.
- Main-process parts seam (app/parts/): Electron main-process features
  live as app/parts/NN-name.js files that app/parts.js loads in
  file-name order (hooks early, ready, overlayWindow, clientWindow,
  configChanged, gate, toggled, quit; a throwing part is logged and
  skipped); app/main.js keeps the two windows' creation, the IPC
  handlers and the one clipboard read (decision 0053). Reverses if: a
  part needs an order that file names cannot give, a packaged build
  cannot list the directory, or the floor scan stops covering app/parts.
- Core hello: clients prove the core before they send anything: GET
  /api/hello takes a fresh 128-bit nonce and HMAC-SHA256(token, 'client' +
  nonce), never the token, and answers HMAC-SHA256(token, 'server' + nonce +
  bound port); the Electron main process, the supervisor and run.ps1 check it
  once per token value and after any request error, before they send the
  token, post item text or load the dashboard; the proof is this route's
  token gate and no process is looked at (decision 0054; core part
  SEC-HELLO-CORE, Electron part SEC-HELLO-CLIENT, run.ps1 part SEC-HELLO-PS
  landed wave 23). Reverses if: a client that cannot compute an HMAC must be
  supported, the handshake pushes a start past its budget, or the stack
  rule's token wording is ruled to mean the token itself on every call.
- NO-DISCOVERY: only the real entry point with no configured log path
  runs the Steam library scan; a core given a runtime dir or a log path
  never scans; a configured Client.txt path that is missing stays
  configured (Checks row), with no fall-through to the scan; a consent
  path that is a file must be named Client.txt (decision 0003 amendment
  2026-11-18). Reverses if: the operator rules on A-03 that the Steam
  scan must go (the typed path is then the only route), or stale
  configured paths strand players in normal use.
- Licence: Apache-2.0 for AshLight's own code; NOTICE names "The
  AshLight authors"; the kit is described as a vendored development
  kit; nothing third-party is bundled, data only as attributed sidecar
  snapshots (decision 0047). Reverses if: the operator wants a named
  holder, or a bundled dependency forces another licence.
- GGG OAuth application prepared: public client, authorization code
  with PKCE, scope account:characters only (account:profile and
  account:item_filter not requested), loopback redirects on 8979 and
  8978, access token in memory only until GGG answers the refresh
  question in writing; the operator sends it when REG_OPEN appears
  (decision 0048, amends 0004 item 4). Reverses if: GGG requires
  account:profile for consent or the User-Agent, refuses the loopback
  ports, or the operator drops live import.
- Loop and wave contract: BLOCKED in a row means not for the loop, with a
  reason the checklist echoes (session wave <n>, session, operator act,
  gate); a hand-off bullet is loop work only with LOOP:; a session claims
  an untagged row by committing the tag first and the loop's item record
  wins; a wave holds folders with ops/loop/control/wave_owned.json and
  merges under the loop's merge lock; HALT is removed only after the six
  checks (decision 0055). Reverses if: a row is worked twice in practice,
  or the tag traffic on ROADMAP.md causes merge conflicts.
- Plug-in folder for ticks, Checks rows and routes: a new core tick,
  Checks row or token-gated /api/ route is one new module under
  server/al/plug/ (attach / facts / rows / ROUTES, discovered by name);
  Core.tick_all runs the tick list in a fixed order and throttles a
  repeating tick error; plug routes run only after the handler guard and
  only under /api/ (decision 0056). Reverses if: the F-193 route table
  replaces the lookup, discovery fails in the installed layout, or a plug
  module is found to bypass the token, Host / Origin or CSP checks.
- CAMPAIGN-KEEP: with no build the item check answers keep or vendor from
  AshLight's own level-band rule table (server/al/data/level_rules.json,
  JSON conditions never run as code, hot reloaded, entries carry src and
  checked); nothing copied from another tool; a loaded build or a worn item
  wins (decision 0057). Reverses if: the thresholds misfire in levelling
  play, a licence objection to a fact source appears, or the worn-gear
  baseline makes the table unused.
- Hotkeys: effective keys, rebind in the app, self-healing fallback.
  HOTKEYS-LIVE: at most 2 global keys are registered by default (item check,
  show / hide) and any further key ships unset; the client re-registers on a
  config change with no restart; a taken key falls back to the first free
  key of a short safe list (Ctrl or Alt held, never a game key); the results
  and the player's overlay on / off go to ops/runtime/hotkeys.json, the core
  publishes the effective keys and every surface prints those, never a
  literal (decision 0058). OVL-KEYS-CORE (2026-11-20): the core reads the
  client's ops/runtime/hotkeys.json only on a stat change (8 KB cap, every
  key through safe_accelerator), publishes snapshot hotkeys (eval / toggle:
  key, want, registered, fallback; overlay_on), and the token-gated POST
  /api/hotkeys writes eval_hotkey / overlay_toggle to config/local.json,
  refusing a game key or the other chord's key; Checks shows hotkey and
  hotkey_toggle rows plus an overlay_off note; the core registers no key and
  sends nothing. Reverses if: a fallback key clashes with a game
  bind in play, GGG's overlay rules change (decision 0003), or the operator
  orders fixed keys.
- Go-public gate 6 limits binary blobs to 500 KB and text blobs to 2 MB,
  checked by tools/blob_gate.py; no history rewrite (decision 0079).
  Reverses if: a text blob over 2 MB appears (split it), MAIN orders a
  rewrite (then restore the uniform 500 KB), or a leak or accident is
  found hiding in a text blob under 2 MB.
- Electron upgrade policy: Electron stays on the newest stable major: patch
  and minor weekly to the newest release at least 3 days old, within 24 h on
  an npm audit advisory; major N+1 between 14 and 42 days after its .0.0, one
  major at a time; never past end of life; bumps are loop rows filed by the
  dev-loop watcher, the app itself never checks versions; setup.ps1 refuses
  the npm step while the client runs (decision 0070). Reverses if: a bad
  upstream release passes the waiting period and the gates, Electron changes
  its release schedule, or the operator rules bumps must be manual.
- CI timing: AL_CI=1 is set only in ci.yml; under it decision 0002's
  timing budgets skip with the value printed (structural checks stay),
  test waits widen 3x and the CDP page-live wait gets one bounded retry;
  no rerun plugin; the core's listen backlog is 128; gate 12 = two
  consecutive green ci runs with fleet-identity-guard green, a red run
  resets the count (decision 0080). Reverses if: dedicated runners make
  timing stable, an AL_CI skip hides a regression seen locally, or the
  backlog fix shows no effect and failures persist (then a local-only
  marker for the browser tests).
- Durable core stores: write_private and _write_config go through jsonfile
  (config/local.json and consent.json keep one .bak, private like the main
  file; the token file keeps none); config and consent reads restore a damaged
  file from its .bak, and a config with no good .bak still raises
  ConfigUnreadable; a failed run history, map ladder, price watch, zone visits
  or session summary save stays in memory and is retried from the core tick by
  a per-store jsonfile.Saver (1, 5, 30, then every 60 s); while one is
  unsaved, new changes wait in the state; Clear removes the visits .bak even
  when its write fails; plug/stores.py shows one Checks row while a store is
  unsaved and one note after a restore, for the life of the core, naming the
  store and never a path (RUN-DURABLE-STORES, F-014). Reverses if: back-off
  delays hide a lasting save failure from players, or the restore note
  misfires on files that were not damaged.
- Installed copies live in a per-user home (%LOCALAPPDATA%\Programs\AshLight;
  -InstallDir or AL_HOME moves it): code in app\<version>\ plus the marker
  install.json, all player state in data\; the resolver refuses a home with a
  steamapps or "Path of Exile 2" path component by path text only, with no
  registry read, library file or folder listing (decision 0059). Reverses if:
  the installed copy cannot serve daily dev use, or the override breaks the
  sidecar path test.
- Electron pin: tracked config/electron_pin.json (version = the electron entry
  of app/package.json, the line's end-of-life date, and for x64 and arm64 the
  zip url, SHA-256 and size plus the electron.exe SHA-256 and size, every
  value read from the public release) is used by tools/electron_pin.py
  (stdlib; tc_pin's archive and hash helpers; AshLight User-Agent; github.com
  and its release asset hosts only) to fetch into the sidecar Cache, refuse a
  wrong zip before unpacking, unpack to app/node_modules/electron/dist plus
  path.txt and check electron.exe; verify-exe hashes in full only when size or
  mtime changed since the last good check (sidecar Build); an unknown
  architecture warns and reports no client; it is a setup-time fetch, not
  gated by web_data (Q-20), and is wired into setup.ps1 and run.ps1
  (decision 0068). Reverses if: Electron stops publishing SHASUMS256.txt
  or release zips on GitHub, electron's npm package changes its dist/path.txt
  layout, or a signed release channel replaces the pin.
- Electron and npm supply chain: npm runs only as npm ci --ignore-scripts
  from the lockfile under the tracked app/.npmrc (which also sets an
  AshLight User-Agent); the Electron zip is fetched only by
  tools/electron_pin.py (AshLight User-Agent, SHA-256 from
  config/electron_pin.json), never by electron's install.js; setup and
  run.ps1 verify electron.exe against the pin (decision 0068). Reverses if:
  the operator rules the User-Agent bullet binds only AshLight's own
  requests (decision A-02: the .npmrc user-agent line may go), Electron
  stops publishing hash-verifiable zips, or a packager needs electron as a
  dev entry.
- TC-CALC-CONFINE-PROC: Calc child confinement: every bridge start passes
  the child only the allow-listed environment names (SYSTEMROOT, WINDIR,
  TEMP, TMP, LUA_PATH, LUA_CPATH). On Windows the child starts suspended and
  is resumed only once it is inside its own job object (stdlib ctypes): kill
  on job close, one active process, 1536 MB per-process memory limit. The
  job handle closes with the bridge or the core. A start that cannot be
  confined is killed and raises BridgeUnavailable (decision 0022 amendment
  2026-11-19). Reverses if: PoB needs another environment name or a helper
  process, a real build needs more than the memory limit, or job objects are
  refused in a supported install layout. TC-CALC-CONFINE-LUA: after the
  HeadlessWrapper load bridge.lua removes os.execute, io.popen,
  os.tmpname, package.loadlib and the ffi require route, empties
  package.cpath, makes os.remove / os.rename / write-mode io.open return
  nil plus a reason and io.output to a file raise, and drops the debug
  functions that reach the kept originals; PoB stays unmodified; a
  test-only probe proves each call fails (listed in CALC_TESTS of
  tests/test_marks.py) and the drift guard fails if PoB starts using a
  dropped entry point. Reverses if: PoB's headless path needs a dropped
  entry point, or a pin moves its start out of the HeadlessWrapper load.
- RUN-ZONE-RESET: SessionState._enter_zone() is the one per-zone reset
  (state.ZONE_FIELDS, listed again in tests/test_bus_state.py), called from
  the scene, area-generated, area-entered and log_opened arms. Each zone
  entry moves a zone generation counter on: a generation line and its scene
  line count as one entry, a scene with no generation line before it counts
  as its own, and a game start is "no zone". Zone cards (schedule_zone_card
  / zone_cards, at most 4) and slow producers that pass zone_gen publish
  only while the generation is unchanged. restore() counts as a zone entry.
  _REPLAY_TYPES is unchanged. The card and event text helpers live in
  server/al/text/ (common.py, events.py), and state.py re-exports every
  moved name as the same object. Reverses if: a per-zone field must survive
  a zone entry, the generation-plus-scene pairing misfires on a real log,
  or F-103's later steps reshape server/al/text/.
- OVL-SHELL-GUARDS: Electron shell guards: app/parts/10-guards.js turns the
  sandbox on for every renderer, denies navigation, popups and webview
  attach on any webContents its creator did not register, keeps WebGL off
  and quits on an inspect switch, a remote-debugging port or NODE_OPTIONS
  unless AL_DEV=1; IPC answers only the exact sender frame; an overlay
  restart runs at most once per 2 s (decision 0061). Both sessions (the
  default one and persist:client) cancel every request that is not an app
  page (file: under the app folder), the loopback core on the configured
  port, blob: / data: or (AL_DEV=1) devtools (app/egress.js,
  app/parts/15-egress.js; refused origins logged once each, at most 64);
  the icon render page carries a no-network CSP (decision 0061 amendment
  2026-11-19). Amended 2026-11-21 (OVL-APP-SCHEME): the overlay page and
  the companion's starting page load from one privileged app scheme
  al-app (origin al-app://app, standard and secure, registered at the
  parts' early hook by app/parts/12-pages.js and served with
  protocol.handle on the default session and persist:client), never from
  file://; app/pages.js serves a fixed list of eight files looked up
  exactly (anything else, and any method but GET or HEAD, is 404 and
  reads no file), reads each one fresh with no-store so hot reload still
  works, and sends the CSP as a header (the overlay's connect-src is
  http://127.0.0.1:<port> exactly, the starting page connects nowhere,
  frame-ancestors 'none'); al:config answers only the scheme URL; the
  egress lock allows the scheme's one host and refuses every file: URL;
  the core adds APP_ORIGIN al-app://app to FILE_ORIGINS for GET /events
  only and echoes it in Access-Control-Allow-Origin, while null and
  file:// were refused from OVL-APP-SCHEME-STRICT on (decision 0061
  amendment 2026-11-21). Amended 2026-11-21 (OVL-APP-SCHEME-STRICT, F-174):
  the core now accepts only that app origin instead of null and file://
  (FILE_ORIGINS = {APP_ORIGIN} on the read-only path set {"/events"}; Origin
  null and file:// are refused). Reverses if: the live smoke shows the feed blocked or the
  window not painting from the scheme, Electron drops protocol.handle or
  registerSchemesAsPrivileged, or a page needs a file outside the list.
  Reverses if: a needed
  feature must navigate or open a window, the guards cost the overlay budget
  (decision 0002), or Electron removes an API they rely on.
- DEP-04 changelog: One changelog generator (tools/release.py notes):
  per-version files in docs/releases/, CHANGELOG.md as their
  concatenation, commit subject types enforced by the commit-msg hook,
  Security grouped by commit type and row kind, never by id prefix
  (decision 0062). Reverses if: the drafts need a rewrite every release.
- DEP-06 runtimes and command builder: paths.python_exe / electron_exe
  read the install marker's "python" / "electron" plain folder name under
  <home>/runtime, with no stat of the runtime folder (None for an unusable
  name; a checkout uses the running interpreter and
  app/node_modules/electron/dist); paths.python_cmd is the one Python
  spawn builder: today's `-m` form in a checkout, `<python>
  <payload>/boot.py <module>` in an install, with an optional payload root
  so version N+1 can self-test while N runs; keepalive core_command /
  run_preflight and procs.electron_dir go through it; boot.py at the
  payload root puts its own folder first on sys.path and runs the module
  as `__main__`; the runtime's ._pth stays the publisher's file (spike
  record docs/ops/runtime-spike-record.md). Reverses if: a boot.py start
  breaks a module that relies on `-m` semantics, or a re-spawn site cannot
  take the builder (then the ._pth line plus a `-c` self-test).
- Installed-copy runtimes: CPython at the exact version and sha256 in
  config/runtime_pins.json (the embeddable amd64 zip) and the unmodified
  Electron zip at the exact version and sha256 in config/electron_pin.json,
  fetched at install by the installer's own process
  (pinfetch.ensure_runtime: hosts www.python.org, github.com,
  release-assets.githubusercontent.com, objects.githubusercontent.com;
  AshLight User-Agent, no cookie; a wrong hash leaves nothing in the
  target), never bundled and never fetched by the running core; boot.py
  plus one command builder (paths.python_cmd); no Electron fuse flipped
  (decision 0063). Scripts find Python, Electron and the paths only through
  scripts/al_env.ps1 (Get-AlPython, Get-AlPythonCmd, Invoke-AlPython,
  Get-AlPaths, Get-AlElectron: `<python> -m` in a checkout, `<python>
  <payload>oot.py <module>` with the private runtime in an install);
  setup.ps1 and build.ps1 refuse an installed home; build.ps1 -Package runs
  tools/release.py build alone; the client's children get home.js
  childEnv(), which strips app/guards.js STRIPPED_ENV (ELECTRON_RUN_AS_NODE,
  NODE_OPTIONS) (REL-RUNTIME-SCRIPTS). Reverses if: the spike fails, a
  publisher drops hash-verifiable assets, a licence objection appears, a
  script needs a lookup al_env.ps1 cannot give, or calc_setup.ps1 must keep
  its own.
- A release is the app zip, install.ps1, release.json, SHA256SUMS.txt, the
  notes file and an SBOM, built reproducibly by tools/release.py build from
  one git ref; no installer framework, no packaged .exe, no signing at
  first; no Electron, CPython, game data, PoB source or LuaJIT in any
  artifact (decision 0064; 0041 point 9 stands). Reverses if: the operator
  gets a signing identity, or SmartScreen friction measurably blocks
  installs. Amended 2026-11-21 (DEP-15, adjudicator ruling): the
  tag-triggered .github/workflows/release.yml holds exactly permissions
  contents: write, id-token: write, attestations: write (rebuild, compare,
  attest, publish the draft release), no secret, persist-credentials false,
  actions pinned by full SHA; tests/test_workflows.py pins the three
  scopes. Reverses if: GitHub changes those scopes, a run writes anything
  beyond release assets, or the operator rules CI must not publish.
- Versioning and release trigger: SemVer 0.y.z, tag = v + VERSION; a
  release only from a REL-PREP milestone row or an explicit version
  request, published only on the operator's phrase `release X.Y.Z`
  through tools/release.py publish (tools/rel_publish.py: every gate
  checked, every refusal named, a refusal changes nothing), never by a
  lane, tick or inbox responder; CI rebuilds and publishes on the tag;
  the rehearsal names the configured remote and pushes nothing; the
  no-remote gate is kept and proven by the injected-git test (decision
  0073). Reverses if: the operator rules that milestones may publish
  themselves, or the remote is removed. Amended 2026-11-21: release.yml
  scopes as in the 0064 entry (DEP-15).
- KINDLER: the build generator "Kindler" ranks AshLight-authored archetype
  templates (server/al/data/archetypes.json, JSON never run as code, src
  and checked, hot reloaded, nothing copied) scored only by Path of
  Building through the bridge: at most 12 candidates in 60 s on the
  Generate click only, a partial labelled; calc off shows one unscored
  template with no DPS or EHP; tree node ids checked against the cached
  tree export, never guessed; up to 6 tabs in ops/runtime/gen_builds.json
  (0036 bounds, cleared by Clear run history, exported, no item text);
  tri-state toggles; no own calc, tree search or optimiser (decision 0081,
  amends 0004; amended 2026-11-19: Pasted build tab fixed, Kindler tabs
  move left / right, rename (32 characters) and close with an inline
  confirm; one result key, PoB-ranked by the 0024 blend, ties by template
  id then variant, byte-identical repeats, a partial never cached as
  final; stages from levelling to maps with skills, support links, gem
  timing from the gems snapshot, ordered passives, ascendancy and per-slot
  item focus; per-tab "follow Play guidance" on by default, reading only
  published zone, act and level, never claiming a step done).
  KINDLER-DATA: theorycraft/archetypes.py checks archetypes.json (schema
  1, fixed key allow-lists, src and checked per template and stage, hot
  reloaded); resolve() only looks up and drops tree node ids missing from
  the cached export with a note, gems unchecked until a gems snapshot
  exists; the validator check() (connectivity from class and ascendancy
  start, order, point budget (level - 1) + bonus_points, gem and zone ids)
  runs only in tests and KINDLER-TEMPLATES. KINDLER-TEMPLATES: 4 authored
  templates (melee, spell, minion, bow), 7 stages from G1_1 to early maps;
  gem names from cached base_items until DATA-GEMS-SNAP, no gem levels or
  bonus points authored. KINDLER-ENGINE: POST /api/kindler-generate
  {id, op generate|read} runs one Generate at a time on Kindler's own
  daemon worker; candidates in toggle-match then id order, one variant
  per stage skill, at most 12; PoB XML takes its class index and
  ascendancy id from the cached tree export, gem level 20, no items;
  ranked by percent of the best candidate under the 0024 blend, ties
  template id then variant; key over class, toggles, archetypes sha256,
  PoB commit, tree export sha256, 10-level band; final results cached in
  memory (16 keys), never partial or calc-off. KINDLER-PLAN:
  theorycraft/kindlerplan.py builds the top-ranked template's plan (stages
  with skills and support links, gem steps at the snapshot level else the
  authored level marked unchecked, ordered passives with point count and
  budget, ascendancy nodes by trial, per-slot focus); with the calc on,
  non-weapon slots are ranked by PoB per-mod weights from one plain rare
  amulet probe item (at most delta.MAX_PROBES calcs per result, one run at
  a time on the planner's daemon worker, cached in memory per result key);
  weapon slots, calc off and stats with no key or zero weight keep the
  authored order; the stage resolver reads only published area_id,
  area_level and level (zone, act, area level outside acts, level band,
  nearest planned level) and never claims a step done; POST
  /api/kindler-generate op plan answers {state, plan, focus, current},
  current null while follow is off; support applies is null until the
  bridge reports it. KINDLER-UI-RESULT: the plan card is built on first
  show after the editor card; stages one at a time with Previous / Next
  stage, three card pages (Skills and gems, Passives, Item focus) cut into
  parts of at most 10 rows, gem and stat names open the shared item info
  popover, a Follow Play guidance chip with a Now badge and a why line, no
  weight or score number, plan read only via op plan.
  Reverses if: PoB drift makes route XML unreliable,
  12 candidates in 60 s breach the 0024 / 0028 budgets,
  automatic regeneration is wanted and shown to cost no FPS, 6 tabs prove
  too few, a name collision or GGG use of the word is found, the operator
  rules generated builds out of scope, authored node lists prove too
  costly to keep, a real PoB output makes the repeat-run test
  non-identical, the follow default annoys players in play, PoB stops
  reporting support applicability through the bridge, attack scoring
  needs items (KINDLER-WEAPON-BASE), a review rules another rank
  baseline, per-slot local mods change the focus ranking in play, or the
  stage priority misfires in play.
- DATA-GEMS-SNAP: snapshot.SOURCES adds repoe-fork's poe2 gems.json, cached
  as the gems.json that theorycraft/archetypes.py reads (GEMS_FILE), with
  the same web_data opt-in, cache, User-Agent and attribution as base_items
  (decision 0009), a 64 MB cap (the reader's GEMS_MAX_BYTES) and no contact;
  its snapprobe probe "gems" needs an object of at least 150 entries and at
  least 100 gem names counted by archetypes.gem_index (name at the top or
  under base_item / active_skill), never one named field; a failing body
  keeps the cached copy and shows the "skill gem list" Checks row; no second
  credit line (the repoe-fork sentence of datacredit.ATTRIBUTION covers it).
  Reverses if: repoe-fork drops or renames gems.json, its terms forbid this
  use, or real files trip the 150 / 100 thresholds.
- UI 0082: item names are link-like buttons opening one shared,
  fixed-position item info popover (web/iteminfo.js, one open, Escape
  returns focus, never resizes a card) over a cache-only token-gated GET
  /api/iteminfo; the visible "AshLight" header text goes (mark
  decorative, sr-only h1, document.title kept) and "Version <x.y.z>,
  build <12 hex>" shows in the footer and Settings > About and data by
  widening RUN-BUILD-STAMP-UI; cards on Build and items and Run collapse
  to their title row, open cards share the freed height by grid fr
  tracks, Play and Settings never collapse, an alert expands its card
  (decision 0082; amended 2026-11-19: collapse buttons only in the
  desktop client window (window.alClient), state in the core in
  ops/runtime/ui_layout.json behind token-gated GET / PUT /api/ui/layout,
  card-id allow-list, one .bak, Saver retry, no localStorage, not
  exported, not cleared by Clear run history). Amended 2026-11-23
  (UI-CARD-COLLAPSE): plug routes may be PUT (do_PUT falls through to the
  plug after the guard, else 405); GET / PUT /api/ui/layout in
  server/al/plug/uilayout.py; web/pager.js fitRows / refit give a card
  whose column-mate is collapsed a fixed extra row count (264 px full, 236
  px compact at s = 1), and web/search.js rowPager uses it; the Recent
  card is keyed eventsbox by its class; alerts open their card until the
  player's click. Reverses if: the popover
  covers Play regions in play or native popover misbehaves in Electron,
  item names stop being unique cache keys, plain-browser users miss a
  visible name or a screen-reader check fails the heading order, the
  build format stops splitting at "+", a collapsed card hides a needed
  alert or the fr sharing makes the pager flicker, decision 0075 rules
  otherwise, the operator rules the title text should stay, or the
  operator wants the browser to collapse cards, the layout exported or
  cleared with run history, a plug PUT route bypasses the guard, or the
  fixed extra rows show slack, overflow or flicker in play.
- Item info data: the popover reads local caches only (repoe-fork
  base_items and uniques, the poe.ninja price book while web_data is on),
  unknown fields omitted, never guessed; no drop_level, drop rates,
  monster drop lists, NPC prices or disenchant yields (no permitted
  source); "where found" only from PoB-PoE2's CurrencyNames.lua,
  WorldAreas.lua and Uniques Source lines, text-parsed under sha256 pins
  while the calc component is installed, never run as Lua, repoe-fork wins
  (amends 0037); no GGG exchange call; a "More on poe2db" link opens only
  on the player's click (decision 0083; amended 2026-11-19: AshLight keeps
  Apache-2.0, link only to poe2db / wiki, no text or data fetched, bundled
  or snapshotted until a source permits app use, then only by decision
  0009's opt-in sidecar route with any community figure labelled
  "community estimate"). GET /api/iteminfo (ITEM-INFO-CORE) is a
  token-gated plug route: an exact name (at most 120 characters) over
  cached base_items, the cached uniques snapshot (snapshot.ITEM_SOURCES,
  same opt-in) and the price book while web_data is on; an unknown name is
  200 with empty fields; price entries keep only https poecdn.com icons;
  its words live in server/al/text/iteminfo.py (copy sheet
  docs/design/copy/iteminfo.md). ITEM-INFO-POB-TEXT: where_found rows come
  only from PoB-PoE2 Uniques/<slot>.lua Source lines and WorldAreas.lua
  isMap, read as text (theorycraft/pobtext.py) under one pob2_files sha256
  per file with the marker check, parsed once per pin and only for the
  core's default lookup; CurrencyNames.lua is absent from the pin and
  Special/ is not read; credited by source id path-of-building. Reverses
  if: a permitted source for drops, vendor or disenchant data appears, a
  source publishes an API or app-use terms or gives written permission,
  GGG opens registration, PoB relicenses or a Source line proves wrong in
  play, poe2db objects to deep links or leaves config/link_hosts.json, PoB
  reshapes its Source lines, a pin brings CurrencyNames.lua, or the
  operator asks for drop_level.
- Updates: one read of the project's releases/latest per 24 h inside the
  web-data opt-in; verified by size, SHA-256 against SHA256SUMS and the API
  digest; staged, applied at the next client start after a 24 h hold, rolled
  back by itself; a Settings switch gives click-only; the attestation is
  verified by CI and people, not by the installed updater (decision 0065,
  amends decision 0013 and decision 0018 item 6). Reverses if: GitHub or GGG
  terms bar the daily read, a bad release auto-applies in practice, the
  operator wants click-only, or a stdlib-verifiable signature becomes
  available.
  Amended 2026-11-21 (DEP-17, F-077), network half: `installer update
  --yes` and update.stage_from_release download, verify and stage the
  release in the releases/latest answer that server/al/updates.py cached,
  so there is still one releases read per 24 h. Nothing is requested
  unless the home's data/local.json has web_data true and an acknowledged
  wording (web_data_ack), nor for a pre-release, a version that is not
  newer, a version in update_skip.json, or a version already staged from
  the same zip. Every asset url must be
  https://github.com/<repo>/releases/download/<tag>/<name> for the cached
  repository. Downloads go through payload.installer_stream over
  api.github.com, github.com and the two GitHub asset hosts only, with the
  installer User-Agent and no cookie; they start only on a click or while
  game_idle is true, and run at below-normal priority. Each asset is
  checked against its API size and its API digest when one is given, and
  the zip and release.json against SHA256SUMS.txt; an answer with no
  digest is recorded ("digest": "absent") and SHA256SUMS.txt alone
  decides. Any mismatch stages nothing. A changed runtime pin is fetched
  in the installer process and checked against the new pin. The Sigstore
  attestation is not verified (the standard library cannot). Reverses if:
  GitHub drops the asset digest field or moves its asset hosts, the cached
  answer goes stale enough to miss releases, or the operator rules the
  typed --yes line must also wait for game_idle.
  Amended 2026-11-22 (REL-UPDATE-APPLY-NOW, F-077): one 'Update now'
  click finishes the update. When that click's run stages a version (or
  one was staged already) the core writes <runtime>/apply_now.request
  holding only the version; an automatic idle run never writes it. The
  desktop client's 30 s watch takes the file (launcher.takeApplyRequest:
  at most 4 KB, removed on read, plain SemVer only); launcher.applyNow
  writes stop.request, waits up to 20 s for the hello check to fail and
  core.alive to go, runs `installer apply-staged --home <home>` without
  --if-due (the click skips the 24 h hold) and relaunches from the new
  marker version (exit 10) or restarts the core through run.ps1; a core
  that does not stop is never switched under, the version applies at the
  next start. Reverses if: the stop-then-apply cuts a press or a calc in
  play, the 30 s watch delay proves too slow, or the operator wants the
  click to wait for the next start again.
- Install checks (REL-UPDATE-CHECKS, F-077, DEP-11): in an installed copy,
  Checks shows an "Installed copy" row with the version, the previous
  version and the last update result (its age written in from "at"). It
  also shows at most one "Update" row: a fail row with the fix after a
  rollback to the running version, which clears after 7 days or when the
  next update result replaces it, else a note naming the newest staged
  version. A checkout has no row. The report puts these rows first, under
  the header fields. Core.diag_facts()["install"] reads the marker
  (paths.read_marker), <home>/staged, data/update_skip.json and
  logs/reports/last-update.json through jsonfile, never restoring a .bak.
  It passes on only checked versions, fixed words and times, never the
  free-text reason. It never imports server/al/install, never fetches and
  never switches. Reverses if: the installer's report or staged format
  changes, report.py gains its own install fields, or the 7-day clear
  hides a repeated rollback.
- Uninstall: uninstall.ps1 needs no Python, removes only items proven
  AshLight's own, keeps <home>\data unless -Purge (Recycle Bin), asks
  nothing by default, never reads a game folder and ends with one fixed
  sentence about files the player may have copied; checkout mode never
  removes Worktree, Scratch or ClaudeHistory (decision 0066). Reverses if:
  players lose data they wanted kept or keep data they wanted gone, in
  practice.
- Cut-over migrate: `installer migrate` (server/al/install/migrate.py)
  copies a checkout's player data into <home>/data using one allow-list
  table in code: consent, run history, map ladder, price watch, zone
  visits, session summaries, hints, verdicts, worn gear, gen_builds,
  ui_layout, theorycraft/weights.json and the build/ tree (plain files
  only, no links). A never-list removes the token, token.reuse, pid files,
  core.alive, stop.request, keepalive, hot reload, .tmp and .bak files even
  if the table names them. From local.json only the settingsio ALLOWED keys
  (each validated) plus contact and client_log move. web_data never moves
  (decisions 0013 and 0036): the home keeps its own value, and a checkout
  that had it on is reported as `offered web_data`, with no path. The dev
  keys (loop, loop_push, hot_reload, tc_drift_live_unattended) and port
  never move. The contact goes only into the home's local.json. The
  checkout is only read. A file the home already has is kept unless
  --force. A home local.json that still equals the first-run document
  counts as fresh. Every target must be inside the data folder, and a home
  that is not laid out is refused. The output names files relative to the
  data folder and prints no path. Reverses if: a player-data store is added
  outside the table, the cut-over must also carry dev keys, or copying
  client_log is ruled out.
- Upstream watcher frame: One tool and one state file run every upstream
  source on the dev loop (tools/upstream_watch.py); new sources read
  repository metadata or the exact public metadata and docs pages they list,
  and only while the dev host's web_data is on; the docs watch and the
  release check keep their settled reads; CI reads GitHub and public
  registries only, never a GGG host or poe.ninja, and never commits; row
  text comes only from tracked templates (decision 0069). Amended
  2026-11-21 (LOOP-CI-ISSUES, adjudicator ruling): METADATA_TAILS gains
  /issues, /actions/workflows/watch.yml and /actions/workflows/watch.yml/runs,
  read-only repository metadata on api.github.com for the CI issue protocol
  (decision 0076 item 6); other /actions/ and /issues/ sub-paths stay refused.
  Reverses if: GitHub treats these as non-metadata, or the operator limits
  watchers to the earlier tails. Reverses if: a
  source's owner asks tools not to read it automatically, the metadata-only
  rule hides a break only a data read shows, or the operator exempts a
  source from the web-data gate in writing.
- Observability records: AshLight records only its own behaviour: in-memory
  counters behind the token-gated /api/debug and the probe command, a 1 MB
  budget log of its own processes, a typed event log with no free-text field,
  and a report built on the player's click from an allow-list of fields; never
  the game process or window, no Client.txt text, nothing uploaded (decision
  0067; decision 0006 method 3, decision 0040 class). Reverses if: a record is
  found to hold a path, name, chat or item text, the sampler costs overlay
  budget, or GGG restricts derived local records.
- OBS-PARSE-LEDGER: per-pattern hit counts and masked log shapes (allow-list
  mask, 200 shapes, 64 KB, hour-grain times, two-sighting rule) in
  ops/runtime/logshapes.json only under their own consent line beside the
  Client.txt opt-in; revoking deletes the file; no raw line, name, chat or
  item text is ever stored or sent; in-memory class counters need no extra
  consent (decision 0071). RUN-LEDGER-WIRE (decision 0071 amendment
  2026-11-20): server/al/plug/ledger.py, fed by Core.feed_line; hit counts,
  masked shapes, five read-back booleans and up to 4 masked waystone
  property-block shapes kept only while the ledger consent is on; the file
  is written at most once a minute and only on change, a write and the
  revoke-delete share core.ledger_lock and a revoke empties memory; two
  "Game log" Checks notes (3 anchored misses in one game run; a resume scan
  stopped at its 32 MB cap). Reverses if: a mask gap stores a name or a chat
  word, GGG restricts derived local records, the operator rules the ledger
  unwanted, the once-a-minute write costs overlay budget, or the sticky
  drift note misfires in normal play.
- DOCS-FRESH: tools/docs_fresh.py check is a list of small fact functions
  (FACTS); each reads a value from tracked files and matches where docs quote
  it (Electron pin in app/main.js and decision 0002; VERSION in
  app/package.json and the lockfile; the setup.ps1 Python / Node floors,
  AL_PORT / PORT_BLOCK and the scripts named in README; the kit version in
  CLAUDE.md while quoted and design 0001; the disclaimer word for word in
  README; TEST-DOCS-FACTS-UI: the default item-check and show / hide keys
  from server/al/hotkeys.py FALLBACKS (never web/ text) where README quotes
  them, the decision 0002 budget numbers from tests/test_budgets.py where
  README and decision 0002 quote them, every core-read settings key of
  config/local.example.json named in README, and the tab labels where
  README names a tab); a stale quote fails tests/test_docs_fresh.py naming the file; no
  request, no write. Reverses if: a fact's pattern misfires on a legitimate
  rewording, or the later fact packages need a different table shape.
- CI issue protocol: The CI watcher writes one labelled issue per finding with a one-line key body from the workflow's bot account and never commits; never a GGG or poe.ninja host; outside decision 0013's scope; the tick trusts only that account and the key pattern and files the row from its own template; failover to the dev loop when the workflow is not active or 48 h silent; npm-audit stays a dev-loop source (CI never sets web_data); .github/workflows/watch.yml holds exactly permissions contents: read and issues: write (GITHUB_TOKEN, no secret, persist-credentials false, actions pinned by full SHA), opens no pull request and writes no contents (decision 0076; adjudicator ruling 2026-11-21). Reverses if: anonymous issue reads are refused, issue spam makes the label unusable, issue writes expose more than labelled issues, the tick accepts a forged key, or the operator rules no write scope is allowed.
- RUN-VERDICTS-UI: the Checks tool's 'Tried in game' card (web/verdicts.js;
  the #verdicts mount with its h4 sits after #checks-list) reads GET
  /api/verdicts once at wire time and lists the fixed checks. A check stays
  open, with Worked and Refused buttons, until its newest verdict is worked.
  One click posts the verdict with the optional note typed above the list;
  the note is printable ASCII of at most 200 characters, and a bad note is
  refused, never cut. No timer, no clipboard, no modal, text only through
  textContent. GET /api/report (server/al/plug/report.py, a token-gated plug
  route) returns {"report": diag.report()} built from fresh diag_facts on
  the click. The player's click that opens the Checks fold builds the
  read-only preview (#checks-preview), and Copy report writes exactly the
  previewed text, synchronously inside its own click. With no preview yet
  (the fold opened by itself, or the build failed) that click builds the
  preview and the next click copies. The clipboard is never written after a
  wait; nothing is uploaded (decisions 0014, 0040, 0056). Reverses if: a
  browser or Electron refuses the synchronous copy, the summary click proves
  unreliable as the build trigger, players re-record worked checks often
  enough to need a retry control, or RUN-QUIET-FEED reshapes the report.
- REL-STAGE-SANDBOX: `release.py stage --sandbox` (off by default; operator
  act OA-14) adds step 8, sandbox_phases(). It builds a scratch folder under
  <sidecar>/Temp with the staged assets and the cached pinned runtimes,
  mapped read-only. A .wsb file turns off networking, clipboard, GPU, audio,
  video and printers, and maps one writable results folder. A generated
  phase script installs, reads back the per-user uninstall key, the
  shortcuts and the home, uninstalls, reads back again, writes result.json
  and shuts the sandbox down. The tool only checks that
  %SystemRoot%\System32\WindowsSandbox.exe exists. It never turns a Windows
  feature on and never asks for elevation, and a missing feature fails the
  step with the reason. A runtime that is not cached also fails the step and
  is never downloaded. stage.json "sandbox" is "skipped" without the flag,
  else the step's status. Reverses if: Windows Sandbox drops .wsb mapped
  folders or LogonCommand, the live OA-14 run shows the desktop mapping or
  ProtectedClient breaks the phases, or the operator rules a missing feature
  should be a skip, not a FAIL.
- RUN-SECOND-LINE-CLIENT (F-127, decision 0005 amendment 2026-11-18): the
  desktop client's main process (app/client/window.js, never the overlay
  page) runs the hello health check every 30 s from its first open; after 4
  failed checks in a row it runs scripts\run.ps1 once through the launcher,
  at most once per 15 minutes, and connect()'s own start counts toward that
  limit. run.ps1 converges, so it starts only the missing core and
  supervisor. When keepalive.json says "gave-up", Launcher.readGiveUp passes
  on only the restart count and a known reason word, and giveUpLine turns
  them into a fixed sentence with no path. That sentence shows on the failed
  page when there is no start-error line. An open companion follows the
  watch's start: the starting page, then the dashboard or the failed page.
  There is no tray note (design 0001 section 7.1). Reverses if: the watch
  restarts a core the player stopped on purpose, 4 x 30 s proves too slow or
  too eager in play, or a give-up reason has to say more than the count and
  the reason.
- OVL-KEY-HINT: the hint is the last card-slot holder (after moment). When
  the slot is empty it shows one muted line, '<key>: check an item'. The
  key is the bound item-check key from the published hotkeys view; no
  known key means no hint. The line has no expiry (expires_at null) and
  is exempt from the dashboard-twin rule, which points at the item-check
  help text. Any card hides it, and so does an open trade request while
  parts.trade is on, on both the core and the page; parts.hint off hides
  it. It is due while no real press was ever recorded and fewer than 3
  game sessions (log_opened seen while a key was known) were counted. The
  marker key_hint {pressed, sessions} is validated in the OverlayView
  store, so once the hint retires it never returns, across a core
  restart. It reads nothing and sends nothing. Reverses if: players miss
  the line after 3 sessions, the key-known session rule misfires in play,
  or the hint shows over a card in play.
- OVL-SMOKE-DAILY (AUTO-22, F-199): the loop step
  tools/loop_steps/overlay_smoke.py runs the opt-in live overlay smoke
  (python -m pytest -q tests/test_overlay_smoke.py with AL_OVERLAY_SMOKE=1,
  hidden, below-normal priority, 600 s limit) from post_work at most once a
  local day (state ops/runtime/watch/overlay_smoke.json), never HALTed or
  dry, and only when the dev host's own core reports game_idle true
  (loopback, ports.resolve, runtime token after the hello proof, no proxy);
  a core that is not reachable is unknown, runs nothing and leaves the day
  open; a scratch root without injected seams reads no core and starts
  nothing; a red verdict is one checklist row 'overlay-smoke' that stays
  until a later green run and files nothing; it never lists processes or
  windows and sends no input (decision 0029). Reverses if: the smoke breaks
  play on an idle day, game_idle misfires as idle while the operator plays,
  or the operator rules the smoke must stay manual.
- DIVE-ON-DEMAND (AUTO-13, F-171): a watcher source asks for a research
  dive by writing ops/runtime/watch/dive_request.json through
  upstream_watch.request_dive. The tick step tools/loop_steps/dive_request.py
  checks every URL with tools/webfetch.py allowed(). A request that is
  malformed or has a refused URL is dropped, never retried. A request waits
  while a DD-<date> record or a deep-dive research file of today exists (one
  dive a day, shared with the idle dive), and while the runs budget is
  unreadable or at or over 60 percent of its cap. Otherwise it is dispatched
  as a deep-dive DD-<date> even when rows are open: the spawn uses
  DEEP_EXTRA (no WebFetch or WebSearch), and the request file is removed
  once the record reads dispatched. The idle dive is skipped while the
  newest dive, idle or requested, is under 7 days old, whatever it
  proposed. Reverses if: requested dives crowd out row work, the 60 percent
  share proves wrong in practice, or a source needs more than one dive a
  day.
- TC-CALC-IDLE (F-154, decision 0028 amendment 2026-11-22): calcwire.Provider stamps last_used when __call__ makes a calc and around every calc / calc.raw call, counts calls in flight, and reap(idle) stops luajit after IDLE_STOP_S = 1200 s without a call or at once while the game is idle (Core.tick_calc reads the state's decision 0029 game-idle flag only while a calc runs; never a process-list check), never while a press holds it (a call in flight or one that ended under PRESS_HOLD_S = 30 s ago); turning tc_calc off still stops it at once; the next press or build load makes a fresh calc behind the first staged card, and a call on a dropped calc is adopted again; exepin.verified caches a match by the exe's size and mtime plus the recorded hash; bridge.lua's 384 MB GC ceiling stays (a full collect per load measured +0.22 s per load for about 220 MB the idle stop frees). Reverses if: restarts make presses feel slow in play, game_idle misfires while playing, a press is cut by a stop, or the full collect measures cheaper than the ceiling.
- REL-UPDATE-TRIGGER (F-077, DEP-17): with a newer release in the cached
  update answer, web data on, the wording acknowledged, "update_click_only"
  off and game_idle true (decision 0029, never a process check), the core
  starts the installer's `<python> boot.py server.al.install update --yes
  --home <home>` hidden, detached and below-normal (updates.maybe_start from
  tick_update), at most once a day per version, never beside a run still
  going, never for a version already staged, never in a checkout. The
  token-gated POST /api/update-now (Host / Origin / Sec-Fetch-Site checks,
  empty JSON body only, answers {started, state} with a fixed word) starts it
  at once without the idle gate or click-only (core.update_now).
  "update_click_only" is on the settings allow-list. The snapshot 'update'
  block adds staged and click_only. The core only starts the process and
  downloads nothing; applying stays the client's next start (apply-now filed
  as REL-UPDATE-APPLY-NOW). Reverses if: the installer's update command
  changes, game_idle misfires as idle in play, or the operator rules the
  automatic start unwanted.
- RUN-PERF-PARSE-ONCE (F-178, F-108 B6): a hot-reload watch with
  from_doc builds its value from the document its check already parsed,
  so each change is parsed once; with share=True every watch on one file
  uses one SharedDoc; world_areas feeds the zone level table and the
  waypoint graph, and base_items the base list and the flask table, from
  one parse each; each table keeps its own last good copy and note
  (decision 0042); the parsed document is kept only for a table that
  joins late, until the next get finds every table up to date (at most
  10 s), then dropped; zoneguide.FileCache is gone (the graph is a watch
  outside the Checks registry and keeps its last good copy);
  tests/test_budget_start.py checks bytes parsed at start are at most 1.2
  times the JSON bytes opened. Reverses if: holding the document until
  the next get breaks B5, a table needs a different size cap or check
  from the other table on its file, or the per-table notes misfire.
- LOOP-DEV-CHECKS (F-125, AUTO-08, F-130): diag.check_loop_tick shows a
  developer NOTE row (dev_loop) while the "updated" stamp of
  ops/loop/control/progress/loop.json is more than 2 h old; it reads that
  file only, never a process list or the scheduled task, and a missing or
  bad file means no row. diag.check_electron_eol shows a NOTE row
  (electron_eol) for every user while the "eol" of the tracked
  config/electron_pin.json is 30 days away or less, or past, worked out
  offline and naming the date: a checkout is told to update and run
  AshLight's setup again (no script name, RUN-NO-DEAD-ENDS), an installed
  copy that a newer release brings it by itself; no pin file or a bad value
  means no row. Core.diag_facts adds loop_tick_age_s and electron_eol, read
  only by a real core. No request, no process. Reverses if: the loop moves
  its status file or the "updated" field, the pin drops "eol", or the 2 h
  or 30 day thresholds misfire in use.
- Load-only gate reds of salvaged loop rows (wave 32 LOOP-SALVAGE): the
  refute-round timing failures of LP-B (decision 0084:
  test_math_perf luajit memory, test_budgets core idle CPU),
  PLAY-TD-21C-HISTORY-MOVE (decision 0085: test_budgets core idle CPU and
  tailer idle CPU) and RUN-DATAAGE-SHARED-PARSE (decision 0086:
  test_soak core bounded, core idle CPU, and a real_loop_body reading at
  whole steps of the 15.6 ms Windows CPU-time unit) stand as load or timer
  noise, not regressions: those rows change web/ files or attach-time
  reads only, no budget number moves (decisions 0002, 0080) and no rerun
  plugin is added. RUN-DATAAGE-SHARED-PARSE itself: the data age
  tracker's world_areas watch uses the shared parse (hotreload
  from_doc=acts.ids_from_doc, share=True), filled once at attach from the
  zone table's parse; a later Checks pass parses nothing
  (tests/test_budget_start.py). Reverses if: the same tests fail again on
  a quiet machine with only that row's diff applied (then a regression
  row and a bisect), or a later change gives one of those rows a per-tick
  or web-asset cost in the measured path.
- Fixed cockpit Play, four tabs, dark by default: Play is a fixed cockpit
  of 7 regions with fixed tracks (full, compact and flow classes from em
  queries on width and height, scale steps 1 / 1.25 / 1.5 / 2); four tabs
  (Play, Build and items, Run, Settings); dark by default with a Theme
  choice (Dark / Follow Windows / Light); every trade row keeps its own
  Dismiss; the zone-guide line on HUD line 2 is an opt-in (On entry is the
  default); the overlay stays 2 HUD lines plus one card (decision 0075).
  Reverses if: a play state needs two contexts at once in region C, the
  no-scroll rule cannot hold with real strings at scale 1, players report
  hunting through Settings more than once a session, or the corner map
  proves routinely covered by the 2-line HUD.
- RUN-CHARACTER-PIN (F-157): the Characters card's picker line holds a
  'This is my character' toggle (#char-pin, aria-pressed, chip style). It
  shows from the first character on and pins the character the picker
  shows: the picked one, else the one being played. One click calls POST
  /api/character (server/al/plug/charpin.py, token-gated plug route after
  the handler guard, body capped at 4096). The route writes the same
  "character" key of config/local.json; a name must be one AshLight has
  seen (state or run history), and "" or null frees the pin.
  SessionState.set_character is the one setter that fixes or frees the
  character: a fixed name never switches (decision 0038), a parked name is
  loaded, and with no character known yet the fields seen so far become
  its own. The snapshot publishes character_pinned. Core.tick_config
  (attached by the plug, after the built-in ticks, so TICK_ORDER is
  unchanged) re-reads poll_ms and character through _config() on every
  pass. A change since the last apply takes effect within that tick:
  poll_ms through settingsio's 50 to 5000 check, also on the running
  tailer's next wait. A core given its character keeps it until the file
  changes. Reverses if: players pin by mistake in play, a hand-edited
  character must wait for a restart, or the per-pass config read breaks
  the tick budget.
- RUN-FEED-TRUTH (F-175, F-178): when the dashboard's EventSource closes for
  good (readyState 2), the page asks /api/health with its token. A 401 after a
  live feed shows 'AshLight restarted. Open it again from the tray.' and the
  page stops retrying. A 401 before any live feed shows the wrong-link word.
  Any other answer runs connect() again every 3 s. A feed that is only
  reconnecting is left to the browser's "retry: 3000". The SSE keep-alive is a
  named "alive" event (http.py SSE_ALIVE_EVENT, every 15 s, checked on its
  own, not as an elif after the pushes). The overlay marks a live feed with no
  frame for 45 s (render_gate FEED_STALE_MS) with the reconnecting word
  "offline". That check runs in paint() and the existing schedule() timer,
  with no new timer. The dashboard's render() paints nothing while the page is
  hidden and paints the newest snapshot once when it shows again. The 1 s
  ticker runs only while the page shows and game_idle is not true (web/app.js
  pacer). Reverses if: a core restart that keeps its token is misread as a
  restart, the 3 s retry loads the core, the 45 s mark misfires in play, or a
  hidden page misses a needed update.
- REL-AUTOSTART-SETTINGS (F-073, F-077, DEP-17; decisions 0011, 0065):
  Settings > Appearance and tools holds one 'Start with Windows' row
  (web/autostart.js). It shows the same recorded choice as the tray. It reads
  the client's autostartState once when it is wired, and the click goes
  through the preload's argument-free autostartOn or autostartOff. After a
  click it reads the record again at 1.5, 4 and 10 s, and if the record never
  follows, the box goes back and the row says "Not saved". In a plain browser
  the box is disabled and the row reads 'Set this in the AshLight app.' The
  About and data update block adds three controls, all in an installed copy
  only (the "install" Checks row is present). The first is a line naming a
  staged version when that version is not the newest. The second is 'Update
  now', shown while a newer or staged version exists and web data is on and
  acknowledged. It sends one POST /api/update-now with the token header, a
  JSON content type and no body, and the answer word is said in plain words
  beside it. The third is the click-only switch, saved as a one-key settings
  import ({kind, schema 1, settings: {update_click_only}}). The player's value
  holds until the snapshot's click_only agrees. Reverses if: the client gains
  a completion signal for the autostart script, the core gets its own
  click-only route, or the bounded re-reads prove too slow or too eager in
  use.
