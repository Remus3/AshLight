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

AL channel code: `AL`. Kit: v32, vendored at `ops/fleet_kit/` (never edit;
MAIN ships new versions). Hand-off: `AL-NEXT-SESSION.txt` (tracked; its
`SESSION: <n>` line is the item-13 session counter, /done writes n+1).
Kit conformance: `tests/test_fleet_kit_conformance.py`.

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
E: root item that is not this repo.

## Minimal interaction (operator order 2026-11-16)

- Design every feature and every dev step for as little user interaction as
  possible: in play the app progresses and updates itself with no clicks;
  in build / debug the workflow runs itself. Every ROADMAP row states how
  (`ZERO-CLICK:`). It never overrides the ToS floor: the per-press clipboard
  / screen read stays a manual press, and nothing is sent to the game
  (decision 0004).

## Stack and ports

- Python 3.11+ standard library only for `server/`, `tools/`, `tests/`
  (decision 0002). Electron `45.3.3` (exact pin) for the overlay in `app/`;
  npm deps pinned exactly (`--save-exact`), `npm ci` from the lockfile. No CDN
  at runtime.
- Stdlib-only binds AshLight's own code. Optional external tools (LuaJIT and
  a Path of Building PoE2 source checkout, for build calcs) run only as
  hash-pinned, unmodified subprocesses fetched at setup into the AL sidecar
  (`Cache\`, `Build\`), never vendored or imported, off by default; the core
  works without them. They get only user-pasted build text and hotkey-read
  item text (decision 0004). No ToS floor change.
- Ports: block 8960-8979 (assigned by MAIN 2026-11-16). 8960 = core server
  (API, dashboard assets, SSE). Constants in `server/al/ports.py`; a port
  literal at a bind site is a defect.
- Bind 127.0.0.1 only; every API / SSE call needs the per-start token; keep
  the Host / Origin checks and the CSP. LAN access stays off.
- Setup / build / run: `scripts/setup.ps1`, `scripts/build.ps1`,
  `scripts/run.ps1` (idempotent; a re-run of a finished step is a no-op).

## Public-repo hygiene (local only for now)

- The repo is kept publish-ready but has NO remote (operator order
  2026-11-16): `.githooks/pre-push` refuses every push. Creating the GitHub
  remote is an operator act.
- No absolute machine path, account id, email or sibling tree name in any
  tracked file outside `ops/fleet_kit/`; per-host values live in gitignored
  `config/local.json`. `tools/leak_sweep.py` runs in pre-commit.
- ASCII + LF in every authored file (FLEET item 8); `tests/test_ascii_lf.py`.
- Third-party code: none copied without a license check recorded in
  `docs/decisions/`; GPL / AGPL / NC-licensed tools are studied for ideas only.

## Gates

- `python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python -m pytest -q`
  and `npm test --prefix app` green before any commit to main.
- Commits only via `python ops/fleet_kit/fleet_gitlock.py run --owner <id> -- git commit ...`.
- No AI or bot attribution trailer (FLEET item 17; the commit-msg hook strips).

## Loop (headless lanes, copied from the fleet's lane pattern) - ARMED

`tools/al_lane.py` (lanes `build`, `data`, `review`; kit `fleet_lanes.run_lane`,
own worktree, one governor slot at the call, fail closed) and `tools/al_loop.py
tick` (inbox folded into the tick via `fleet_inbox.classify`, ROADMAP rows as
the work list, runs cap from `~/.fleet/lanes.json`, progress files
`ops/loop/control/progress/lane-<i>.json` and `loop.json` with the item-13
checklist). ARMED 2026-11-17 (ROADMAP LOOP-ARM): per-user scheduled task
`\AshLightOps\LaneLoop` from `tools/loop_task.py install` (PT15M, IgnoreNew,
pythonw, interactive token, no stored password); read it back with
`tools/loop_task.py status`, remove with `tools/loop_task.py remove`. Rows
whose remaining work is an operator act carry `BLOCKED:` so the tick skips
them. Pause: `ops/loop/control/HALT`.

## Session workflow

- Start: read `AL-NEXT-SESSION.txt`, this file, `ROADMAP.md`, `git log -10`;
  triage `moon_sync_inbox/` with `fleet_inbox.classify()`; print the
  `Session <n> checklist` (kit `fleet_checklist.py`); render the local board
  (`fleet_board.py render --session <n>`, FLEET item 18).
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
- Clipboard / screen only per AshLight hotkey press, never a watcher, never
  input to the game (decision 0003). Reverses if: GGG's overlay rules change.
- Theorycraft via Path of Building PoE2 interop (codes first, then an
  optional pinned LuaJIT subprocess), never an own calc engine (decision
  0004). Reverses if: PoB drift breaks the bridge every release, PoB ships
  an official headless API, or its license changes.
- A detached stdlib keepalive supervisor restarts a dead or hung core;
  stop.ps1's stop.request is honoured (decision 0005). Reverses if: the
  supervisor proves unreliable, logon survival is wanted, or the stale
  heartbeat kill false-fires on slow machines.
- OVL-FPS never uses PresentMon or ETW Present tracing of the game, not even
  dev-only (decision 0006). Reverses if: GGG explicitly permits it or the
  operator rules OS performance telemetry is allowed.
- PoB2 share codes: stdlib codec, share-URL fetch deferred to TC-URL, no
  clipboard read in the codec (decision 0007). Reverses if: a real PoB2
  export fails to decode, or the operator orders TC-URL.
- LIVE-RESUME scans Client.txt backwards at start, no persisted state
  (decision 0008). Reverses if: GGG drops the marker / level-up lines or the
  32 MB cap misses the current run's deaths in normal play.
- Bundle no game / repoe-fork / poe2db / wiki data; build-time fetch into
  the sidecar cache only, with attribution (decision 0009). Reverses if: a
  source's license forbids that use or permits redistribution.
- server/al/procs.py is the one process registry; stop.ps1 stops core,
  supervisor and overlay; run.ps1 is idempotent per component (decision
  0010). Reverses if: the overlay gains a clean-exit channel or Electron
  moves out of app/node_modules.
- Logon autostart is an opt-in scheduled task, OFF by default (decision
  0011). Reverses if: the task is refused for a standard user or autostart
  is no longer wanted.
- Agent worktrees go under the sidecar via tools/wt_sidecar_hook.py
  (decision 0012). Reverses if: the harness gains a worktree base-dir
  setting or the hook breaks isolated spawns.
- Web data is one opt-in "web_data" setting, default OFF; nothing hits the
  network while off (decision 0013). Reverses if: an endpoint is forbidden,
  GGG policy changes, or the operator rules per-feature opt-in.
- Build view, item check card (one card slot, 20 s), graphics advisor read
  on a dashboard click, Copy-code clipboard write on the player's click
  (decision 0014). Reverses if: design section 10 allows two cards or
  decision 0003 restricts clipboard writes.
- Price check shares the item-check hotkey; contact only from gitignored
  config/local.json; the core publishes `price` in the snapshot, no own
  endpoint; prices from poe.ninja only, trade as a link (decisions 0015,
  0016, amended by 0017). Reverses if: GGG / poe.ninja drop the contact
  ask, price check needs its own hotkey, or the overlay may fetch.
- The app calls no trade2 endpoint; it only builds a trade-search URL the
  user opens in their own browser (decision 0017). Reverses if: GGG
  documents trade endpoints or permits third-party use in writing, the
  operator rules otherwise, or the ?q= URL form proves unstable.
- Optional calc component: PoB-PoE2 and LuaJIT hash-pinned in
  config/tc_pins.json, fetched by setup.ps1 -TcCalc only on opt-in, never
  vendored (decision 0018). Reverses if: GitHub archives stop being
  byte-stable, either license leaves MIT / permissive, or LuaJIT ships
  hashed release binaries.
- A trade accepted / cancelled line closes ONE open trade card: the named
  counterparty's, else the oldest (decision 0019). Reverses if: a PoE2 log
  line names the counterparty (then match by name only), or the oldest-card
  guess drops the wrong request in normal play.
- HUD-ACT: act splits from the log's area ids, zone levels read from the
  build-time repoe-fork world_areas snapshot, credit text only in
  theorycraft/datacredit.py (decision 0020). Reverses if: decision 0009
  reverses for repoe-fork, or live cruel / interlude ids break the prefixes.
- Game exit shows as an idle "game may be closed" state from Client.txt
  staleness (20 min, mtime-seeded at start), never an OS process-list
  check (decision 0029). Reverses if: GGG or the operator permits a
  process-presence check, AFK false positives make it useless, or a
  reliable quit / crash log line is verified.
- HUD-ACT-RESUME: act splits rebuild at core start from the current game
  run's area generations in Client.txt, no persisted state (decision 0023).
  Reverses if: decision 0008 reverses or GGG drops the area generation line.
- The build-time game-data snapshot follows the one web_data opt-in, default
  OFF; build.ps1 fetches only when web_data is true or -Snapshot is passed
  (decisions 0009 and 0013, amendments 2026-11-17). Reverses if: a core
  feature needs snapshot data and cannot degrade, the operator rules a
  build-time fetch is not "web data", or users miss the data and the switch.
- TC-CODE-REAL: real PoB2 exports checked by fixture, XML round trip byte
  exact, the code string only compared (xfail on a zlib mismatch)
  (decision 0021). Reverses if: a real code fails a check, or a feature
  needs the exact pasted string.
- TC-BRIDGE: own stdio JSON bridge (bridge.lua via PoB's unmodified
  HeadlessWrapper, `ALB1 <json>` replies), core imports nothing from it
  (decision 0022; amendment 2026-11-17: the luajit.exe hash record stops a
  stale or foreign exe, not a same-user tamper). Reverses if: PoB reshapes HeadlessWrapper every release
  or ships an official headless API, the live 0.1 percent test fails
  without patching PoB, or the stdout prefix framing proves unreliable.
- TC-DELTA: PoB-backed DPS / EHP deltas and per-mod weights, fixed 50/50
  blend and 1 percent sidegrade band, stat weights when the calc is off
  (decision 0024). Reverses if: TC-BRIDGE needs another calc contract, a
  user asks for an offence / defence lean, TC-UPGRADE-STATS finds a stat id
  source, or uncached probes make a press feel slow.
- TC-DRIFT: one read-only GitHub releases check per 24 h from the loop tick,
  a detached trial per new tag, the pin moves only via `tc_drift.py apply`
  after a green trial, committed by a session (decision 0025). Reverses if:
  GitHub limits or terms bar the daily read, PoB-PoE2 stops publishing
  releases or ships a headless API, or the loop gains safe auto-commit.
- Price book: unique and stackable poe.ninja overviews ride the rates
  refresh (same opt-in, contact, UA, league; per-type hourly gate + ETag),
  the press reads the cache only, movers from the same cache, auto league
  re-read every 6 h or after a 404, trade links follow the cached league
  while web data is on (decision 0026). Reverses if: poe.ninja asks for
  less polling or blocks it, decision 0013 goes per-feature, or the
  overview shapes break every release.
- LuaJIT for the optional calc builds with a system compiler, else a
  hash-pinned portable WinLibs MinGW-w64 .zip fetched into the sidecar
  Cache on -TcCalc only, PATH set only in the build subprocess, never
  vendored (decision 0027). Reverses if: WinLibs drops .zip assets, a
  license objection appears, or LuaJIT ships hashed Windows binaries.
- Theorycraft is proven end to end on the real reference build (PoB-sourced
  card deltas, kill fallback), with calc budgets in decision 0024 R7, a
  bridge.lua GC ceiling (384 MB Lua heap) and a PoB API drift guard test
  (decision 0028). Reverses if: a pin move or the target machine breaches
  the budgets, or the GC ceiling costs more than it saves.
