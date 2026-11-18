# 0051 - Observability review

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B14
observability. What AshLight records about itself today (logs, the Checks
report, /api/health, progress and usage files, the GGG docs watch), what is
missing, and a ranked plan inside the ToS floor and the privacy rules.
Product code was read and probed, never changed.
Status: verified

## Sources (all accessed 2026-11-17; re-fetched 2026-11-18 by the verifier)

Web:

- GGG: https://www.pathofexile.com/developer/docs - the overlay rules for
  apps that use the screen, the clipboard or the game's logs; one general
  sentence on players' privacy; nothing on storing or sharing log data;
  new app registration still closed.
- PYLOG: https://docs.python.org/3/library/logging.handlers.html
  (RotatingFileHandler; the page is for Python 3.15.2).
- PYFAULT: https://docs.python.org/3/library/faulthandler.html
- ELCRASH: https://www.electronjs.org/docs/latest/api/crash-reporter
- ELAPP: https://www.electronjs.org/docs/latest/api/app
- ELWC: https://www.electronjs.org/docs/latest/api/web-contents
- ELGONE: https://www.electronjs.org/docs/latest/api/structures/render-process-gone-details
- ELINIT: https://raw.githubusercontent.com/electron/electron/main/lib/browser/init.ts
  (the main process's default handler for an uncaught exception); the
  same handler is on the 45-x-y branch that app/ pins (only its import
  line differs).
- GHFORM: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema
- GHTPL: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository
- DRAIN: https://pinjiahe.github.io/files/pdf/research/ICWS17.pdf ("Drain:
  An Online Log Parsing Approach with Fixed Depth Tree", ICWS 2017; the
  author read a search summary only; the verifier downloaded the PDF,
  whose text layer is mostly not extractable, so only the title is
  confirmed. Used only behind a Rejected item.)

Repo (path:line cited in the body): server/al/ (entry point, core, diag,
http, logfile, parser, bus, state, keepalive, procs, webfetch, paths,
the calc bridge), app/ (main, overlay gate, hotkey, client window), web/,
tools/ (loop, docs watch, ledger rotation, usage ledger, log synthesiser),
scripts/, ROADMAP.md, AL-NEXT-SESSION.txt, decisions 0002 to 0045 as
cited, research 0002 and 0032, docs/audit/2026-11-17-audit.md.

Local evidence (this machine, 2026-11-17; no Client.txt line was read):

- L1: AshLight's own files under `<sidecar>\Logs` (sizes, line counts,
  message kinds with numbers masked).
- L2: one GET each of /api/health, /api/version and /api/state on the
  running core (key names and sizes only). L4: /api/state read twice,
  125 s apart, with no game activity.
- L3: three throwaway probes in `<sidecar>\Scratch\up-0051\` on synthetic
  data: redact_probe.py, shape_proto.py, dead_tailer_probe.py (the last
  one runs a core on a temp runtime dir and a temp log file).

## Summary

AshLight knows that its parts run, not what they did. Liveness is covered
(16 checks, /api/health, the supervisor). Behaviour is not: 123 core log
lines in 24 hours, all start or stop; 5 counters nothing reads; a version
shared by every commit (381 on 2026-11-18); a dead log reader that shows
as healthy (F1).
Best step: a local parse ledger (R1) of per-pattern hit counts and masked
shapes of the lines the parser missed. Normal play then closes LIVE-1
with no play script, and it is the alarm for the 1.0 log format on
2026-12-11; a prototype masked 20,000 hostile lines with 0 leaked tokens
(two edge gaps found in verification, closed by R1's acceptance tests).
Then: a build stamp everywhere (R2), crash records and no error box over
the game (R3), counters with a debug endpoint and a probe command (R4),
"why is this not showing" rows (R5), a public-tracker report (R6), log
care and cleanups (R7 to R10). Limits: nothing leaves the machine but
text the player copies; no log text, name, path or token goes to disk;
nothing looks at the game process, window or screen.

## Current state

Logs, all under `<sidecar>\Logs`, none rotated:

- core.log: `logging.FileHandler`, level INFO, local time, format
  `time level logger message` (server/al/__main__.py:69-88); 44 log call
  sites in server/; unhandled exceptions of any thread are logged
  (__main__.py:115-130, tests/test_core_crash_log.py) and native faults
  go to the same stream through faulthandler (__main__.py:77-84);
  request lines are DEBUG, so never written (server/al/http.py:132-134).
  L1: 123 lines, 7.7 KB in 24 hours, all INFO from logger `al`: 44
  `listening`, 39 `shutting down`, 38 `stop requested`, 2 others.
- keepalive.log: own appender, local ISO time and the supervisor pid
  (server/al/keepalive.py:535-545). L1: 117 lines, 4 message kinds.
- overlay.log: the Electron main `log()`, UTC ISO time, no level
  (app/main.js:44-60); renderer console text is forwarded without its
  level (app/main.js:247-249). L1: 169 lines.
- tc-bridge.log: the calc subprocess's stderr, appended raw, no time
  stamps (server/al/theorycraft/bridge.py:158-163). L1: 18,019 lines,
  387 KB in under a day; 12,024 lines (66.7 percent) are one repeated
  "missing node" message; some lines are two writers interleaved.
  (Verifier re-count 2026-11-18: 18,166 lines, 390 KB, 12,122 of them
  the same message, 66.7 percent.)
- run.log, setup.log, build logs: appended by the scripts (run.ps1:98).

Health surfaces:

- GET /api/health: 5 keys (ok, name, version, port, tailing), 74 bytes,
  token required (http.py:234-238); called by the supervisor
  (keepalive.py:194-206), run.ps1:113 and app/client/link.js:127-134.
- GET /api/version: name, version, disclaimer, data credit
  (http.py:239-244); the dashboard uses only the credit
  (web/app.js:1102-1110).
- Checks (decision 0040): 14 rows plus 2 conditional ones, rebuilt every
  5 s from local facts (server/al/core.py:847-919; diag.py:226-234);
  folded, opens by itself on a new failure (web/checks.js:77-131); "Copy
  report" writes a 15-line, 709-byte text inside the click
  (web/checks.js:140-156; L2); values are masked by a known-value list
  plus an e-mail and a drive-path pattern (diag.py:239-279; patterns at
  diag.py:267-268).
- Snapshot `tailer` block: consented, reading, path, last_reset, idle,
  last_line_at, and the resume scan's bytes and milliseconds
  (state.py:925-927; core.py:674-699). That scan is the only timed
  operation in server/.
- Process registry: `python -m server.al.procs status`
  (procs.py:182-196); state files under ops/runtime, one of them
  keepalive.json with a `restarts` count (keepalive.py:252-262).

Counters that exist and are read by nothing outside tests:
`Tailer.lines`, `Tailer.dropped_lines` (server/al/logfile.py:220, 225,
331-345), `EventBus.published`, `subscriber_count`,
`Subscription.dropped` (server/al/bus.py:22-29, 62, 75, 108-111).
`events_seen` is in the snapshot (state.py:1432, 1831); no page shows it.

Development side:

- Progress files `ops/loop/control/progress/<task>.json` (FLEET item 12)
  and loop.json with tick seconds, a 40-line log tail and the checklist
  (tools/al_loop.py:1447-1455).
- Usage ledger `ops/loop/control/headless_usage.jsonl` with
  `tools/usage_ledger.py count / gate / spend` (usage_ledger.py:4-7); a
  daily rotation of 5 control ledgers and finished progress files
  (tools/ledger_rotate.py:9-15, 40).
- GGG docs watch (decision 0044): state.json in the sidecar Cache, page
  diffs in the sidecar Logs, one line per change in
  `ops/runtime/ggg_docs/notes.log`, the flag REG_OPEN
  (tools/ggg_docs_watch.py:292-345); its tick line goes into loop.json
  (al_loop.py:1547-1548). Last run today: ok, 6 of 6 pages.
- The hand-off tells every session to probe /api/health and the process
  list before touching the live client (AL-NEXT-SESSION.txt:112-114).

Worth keeping: passive checks, redaction, copy on a click and no upload
(decision 0040, ruling J); the core's crash logging with its test; the
heartbeat and the supervisor log; the progress files.

## Findings

- F1 (high) A dead log reader shows as healthy. `Tailer._run` catches
  OSError only (logfile.py:245-251) and the bus listeners run inside
  that thread (bus.py:78-79; core.py:664-668). Probe L3: after one
  exception in a listener the thread is dead, the snapshot still says
  reading (state.py:1573 sets it once), the Checks row is pass, "Reading
  Client.txt." (diag.py:80-86; core.py:882), `ensure_tailing` does not
  start a new one (core.py:730-734), the next log line is never read,
  and /api/health alone says tailing false (http.py:237). For the
  player every live number freezes under a green Checks card; 20
  minutes later the overlay hides as "game may be closed". (Verifier:
  the one trace is the "unhandled exception in thread" line that the
  thread hook writes to core.log, __main__.py:121-127; no surface
  reads it.)
- F2 (high) LIVE-1 waits for an operator play script although the
  evidence flows past every day. The parser drops what it does not
  understand with no count and no record: 5 `return None` exits
  (parser.py:177, 192, 197, 206, 210), and `Core.feed_line` keeps
  nothing (core.py:664-668). Unknown system lines become events with the
  raw body (parser.py:159) that no consumer keeps. No per-pattern hit
  count exists, so "did the death pattern ever match live" has no
  answer. Research 0002 asked for a debug sink on day one (0002:190,
  328) and found 365 distinct shapes in 1,102 lines by a one-off manual
  read (0002:290). Row: ROADMAP.md:9-31.
- F3 (high) The version identifies nothing. `VERSION = "0.1.0"` since
  the first commit (server/al/__init__.py:7); every commit shares it (356
  at drafting, 381 on 2026-11-18), and
  the report header, /api/health, the Server header and the User-Agent
  carry only that. No surface has a commit id; build-stamp.json records
  none, only a source hash and the build time (scripts/build.ps1:196-204,
  hash from build.ps1:138), nothing in server/ reads it
  (paths.py:141) and it does not exist on this machine. The dashboard
  and the overlay show no version (web/index.html:602-636;
  app/main.js:267-268). DIAG-SELF closed with "Build stamp not shown"
  (ROADMAP.md:955-956). app/package.json:3 repeats the version; no test
  ties the two.
- F4 (high) Crash paths have gaps. (a) app/main.js registers no handler
  for an uncaught exception or rejection (0 `process.on(` in app/), so
  Electron's default applies: a modal error box (ELINIT), a
  focus-taking window during play. Whether an unhandled promise
  rejection in the main process reaches the same box is UNVERIFIED;
  R3 handles both either way. (b) No handler for a lost renderer
  or child process, an unresponsive page or a failed load (ELAPP, ELWC,
  ELGONE): a crashed overlay page leaves a dead window and no line. (c)
  L1: 4 of 44 core starts have no end record of any kind, and
  keepalive.log has 0 crash lines; core.log lines carry no pid, so a
  second core (a dev run) writes into the same file untraceably. (d)
  The supervisor's `restarts` count (keepalive.py:255) is read by
  nothing: a core that crash-looped and recovered looks healthy.
- F5 (medium) No counter or timing is exposed. The 5 counters above are
  unread; the SSE client count is a bare semaphore (http.py:62, 91); the
  10 tick functions of the 0.5 s core loop run unmeasured
  (__main__.py:215-265) although one cost 10 ms a tick at scale (audit
  P8-5, 2026-11-17-audit.md:947-950); `webfetch.request`, the single
  outbound path, counts nothing (webfetch.py:183-210); no calc latency
  or press outcome is kept. Decision 0002's RAM budgets (core under 60
  MB, overlay under 250 MB) are measured by tests only, so OVL-BUDGET's
  active in-map figure waits for an operator act (ROADMAP.md:56-62).
- F6 (medium) "Why is this not showing" has no answer in 5 common
  cases: the overlay is hidden (4 gate conditions, 1 logged:
  app/overlay_gate.js:24, 40; Checks says only "running": diag.py:231);
  an item-check press never arrived (one line in overlay.log only:
  app/eval_hotkey.js:44); the calc fails at run time (Checks knows
  installed and pinned only: diag.py:142-155); lines are read but not
  understood (F2); the core restarted (F4d).

(F2 detail: the 5 exits are in `parse_body`; `parse_line` has 3 more:
an overlong line, a line with neither the prefix nor the log-open
marker, and the pass-through of a body `parse_body` refused
(parser.py:220, 225, 234).)
- F7 (medium) The report redactor is safe only because no free text
  reaches it. Probe L3, synthetic strings: a drive path with a space is
  masked up to the space; a UNC path, a POSIX home path, an IPv4
  address with port, a host name and a 48-hex token-like run pass
  unmasked; only the current character is on the mask list
  (core.py:899) though 12 are tracked (state.py:63); a character named
  like a label word blanks that label (audit P8-7). Today's report is
  fixed sentences, ages and the port; a bundle with log tails would
  leak.
- F8 (medium) The report forces one full state push a minute to every
  SSE client. Its first line has a minute stamp (diag.py:284-285), it
  rides in the snapshot (state.py:1887) and any change bumps the
  version (state.py:1274-1282). L4: version 187 to 189 in 125 s with 0
  new events. The Checks view is 2,424 of 6,384 snapshot bytes (38
  percent, L2). The idle overlay parses 6.4 KB a minute for nothing.
  Verifier correction (synthetic probe on diag.view, 2026-11-18): the
  report stamp is not the only minute clock. The "Last log line" and
  "Price book" rows print a relative age (diag.py:89-97, 128-140), so
  with a line under an hour old or web data on, the rows themselves
  change every minute; only with web data off and a quiet log is the
  stamp the sole change. Removing the report alone does not stop the
  pushes; the rows need absolute times that the page turns into ages.
- F9 (medium) Every parsed event goes to every SSE client in an
  "events" frame that no page listens to (http.py:754-763; listeners:
  web/app.js:1127-1134, app/overlay/overlay.js:79-85). It holds other
  players' chat, whisper text, the game server address (parser.py:209)
  and raw unknown system lines. Local and token-gated, so no leak, but
  data without a consumer should stay in the core, and each chat line
  costs an encode and a write on the overlay's path (196 global chat
  lines in 10 minutes in the 0002 sample, 0002:275).
- F10 (low) Logs grow without bound and read badly: no rotation (L1), 3
  time-stamp formats in 3 app logs, no level in overlay.log, no start
  line with version, build or pid (__main__.py:180; app/main.js:404).
- F11 (low) Development records: subagent_first.jsonl is 1.55 MB and
  11,214 rows after 26 hours (2.06 MB and 14,861 rows on 2026-11-18) and
  is not on the rotation list
  (ledger_rotate.py:40) though it has the `at` field the rule needs; a
  failing GGG docs watch shows for one 15-minute tick only (its line is
  overwritten in loop.json, and state.json's status and errors are read
  by nothing: core.py:902-910 reads only the flag); every session
  hand-rolls its own health probe.

## Limits on what may be recorded

ToS and policy:

- Log-derived data may be used only while the user knows what the app
  does with it (GGG; decision 0003). The docs set no rule on storing it
  and ask in general for respect of players' privacy (GGG). So a new use
  of Client.txt content needs wording on the consent card; counting
  AshLight's own behaviour does not.
- Only Client.txt (after opt-in), the clipboard or screen once per
  hotkey press, and public web data may be read. So observability never
  looks at the game process or its window (decision 0029), captures the
  screen, traces frames (decision 0006) or reads a game config file.
- No report, shape, metric or dump leaves the machine by itself (ruling
  J, research 0032 section 6; decision 0013). The one exit is text the
  player copies on a click (decision 0014). Any new endpoint stays on
  127.0.0.1 behind the per-start token.

Privacy classes for AshLight's own logs, ledgers and reports:

- Never on disk in a log or ledger: Client.txt lines or fragments, chat
  and whisper text, other players' character or account names, item
  text, build codes, the
  contact value, the API token, the Windows user name, absolute paths,
  game server addresses.
- Local only, never in a report: the player's own character names
  (already in the run-history files, decisions 0036 and 0038) and the
  Client.txt path.
- May be recorded and may enter a report: AshLight's own counts,
  timings and states; status codes of its own fetches per allow-listed
  host; exception class names with repo-relative file and line; version
  and build; OS build number, Python and Electron versions; line shapes
  that passed the mask and the two-sighting rule below.
- Memory dumps hold everything above. Dev only, never in a report.

## Design: the parse ledger (for R1)

Hook: `Core.feed_line` (core.py:664-668), the one place every tailed
line passes. Two parts, one bounded file `ops/runtime/logshapes.json`.

1. Hit ledger (no content). For each parsed event, count a pattern id
   with first and last sighting: the event type plus its sub-kind
   (chat channel, whisper with or without a guild tag, the 3 trade
   templates, AFK or DND on / off, death or self-inflicted, scene Set
   or Load, hideout word seen) and the class of each area id
   (campaign, cruel, interlude, map, hideout, other). Area ids are
   engine constants, so up to 100 distinct unknown ids are kept
   verbatim when they are plain identifier characters.
2. Shape ledger (masked). A line that produced no event, or an unknown
   system line, is put in one of these classes:
   - chat-like (first character is a channel or whisper mark): counted,
     never stored;
   - speech-like (`<up to 48 characters>: text`, no tag): counted, never
     stored. Research 0002 saw these as NPC lines; whether local chat
     looks the same is UNVERIFIED, so they are treated as chat;
   - tag line (`[TAG] ...`): counted per tag, the tag only;
   - unknown system line and plain line: stored as a masked shape;
   - trade near-miss: a whisper that starts with one of the 2 known
     template openings but fails all 3 template patterns: masked shape.
     No other whisper text is ever looked at;
   - long lines (over 512 characters) and lines with no prefix: counted.
3. The mask is an allow-list, not a scrubber. The text is split on
   white space (24 tokens at most). A token survives only when its
   lower-case form is one of about 80 function and system words shipped
   in the module (you, has, been, is, now, level, area, trade, party,
   joined, left ...). Every other token becomes a placeholder by form:
   number, address, path, host, hex run, or `<w>` for any other word;
   equal neighbours collapse. A name, a chat word or a path cannot be
   stored, by construction, unless the token is itself an allow-list
   word (verifier probe on the prototype, 2026-11-18: a character named
   "Trade" survives as `trade has been slain.`; a chat line whose speaker
   part exceeds 48 characters, or which has no space after the colon,
   escapes the speech class and keeps its allow-list words). Such a
   leak carries only common function words, but R1's acceptance adds
   both cases.
4. Bounds: 200 shapes (least recently seen goes first, with an evicted
   total), 64 tags, file under 64 KB, written at most once a minute and
   only when changed, by temp file and replace. Times are kept to the
   hour. A shape enters a report only after 2 sightings at least 60 s
   apart.
5. Consent: both parts run only when the stored consent lists the new
   use; revoking consent deletes the file. In-memory class counters run
   under the existing consent (they feed R4 and R5).
6. Prototype (L3, shape_proto.py): 20,000 hostile synthetic lines
   (random Unicode names, paths, address-like and mail-like tokens,
   160-bit hex runs, free text) gave 27 shapes and 0 tokens outside the
   allow-list and placeholders. A 6,183-line synthetic session
   (tools/synth_client.py) gave 3,747 events, 2,436 tag lines and 2
   stored entries. Cost: 1.5 microseconds a line on the session mix,
   7.0 on worst-case system lines, next to 1.4 for `parse_line`.
7. Not solved by this: localised clients. Their system words are not on
   the allow-list, so their shapes are all placeholders. Mining
   repeated tokens as constants (the DRAIN idea) would unmask the
   player's own character name, the most repeated "constant" there.

## Recommendations

R1. OBS-PARSE-LEDGER
- Action: add the parse ledger above, a `tools/live1_report.py` that
  prints VERIFIED live / NOT SEEN / NEW SHAPE per LIVE-1 item, and a
  loop-tick note (as the docs watch does) when a pattern gets its first
  live hit or a new shape passes the two-sighting rule.
- Impact: H. Closes LIVE-1 item by item from normal play (F2); raises
  the alarm within minutes if the 1.0 client on 2026-12-11
  (AL-NEXT-SESSION.txt:68) changes a line format. Effort: M.
- Risk: a mask gap. Held by the allow-list design and a property test;
  the tailer thread does one dict update per line.
- ToS check: Client.txt after opt-in only, read only, nothing sent
  anywhere; GGG's user-aware rule is met by a new consent line.
- Depends on: an adjudicator ruling on the consent scope (Open
  questions 1); R2 lets the file name the build that wrote it.
- Files: server/al/logshapes.py (new), core.py and web/index.html
  (hook, consent text), parser.py (expose Set or Load and the template
  kind), tools/live1_report.py (new), tools/al_loop.py, tests, a
  decision note.
- Acceptance: property test on 10,000 seeded hostile lines: every
  stored token is an allow-list word, a placeholder or punctuation; a
  chat, whisper or speech-like line never reaches the file, including a
  speaker part over 48 characters and a colon with no space after it;
  a death line for a character named like an allow-list word stores the
  name slot as a placeholder (so the mask must place-hold the name
  position of known templates, not judge the word); replaying
  tests/fixtures/client_live_shapes.txt yields the expected pattern ids;
  the file stays under 64 KB after 1,000,000 synthetic lines; with
  consent off or revoked no file exists; test_budgets.py stays green.
- ZERO-CLICK: after one Allow click on the new consent line (GGG's
  user-aware rule requires it) the ledger fills during normal play, the
  tick writes the note and a lane turns each verified item into a test.

R2. OBS-BUILD-STAMP
- Action: one `server/al/buildinfo.py` giving version plus a 12-hex
  commit id read from the .git files (no subprocess) and a `.dev` mark
  while hot reload is on; show it in /api/health, /api/version, the
  report header, a muted dashboard footer line, the overlay About and
  the tray tooltip, and as the first line of every log at start.
- Impact: H. Every record becomes attributable; today every commit
  reads the same (F3). Effort: S.
- Risk: none for play. The User-Agent stays as it is (decisions 0013,
  0015). Depends on: none; a non-git install needs a BUILD file from
  the release step (Open questions 3).
- ToS check: AshLight's own repo files only; no network; no GGG mark.
- Files: server/al/buildinfo.py (new), http.py, diag.py, __main__.py,
  keepalive.py, app/main.js, app/about.js, app/client/tray_menu.js,
  web/index.html, web/app.js, tests.
- Acceptance: one test per surface asserts the same build string; a
  node test asserts app/package.json version equals VERSION; the first
  core.log line after a start matches version plus 12 hex characters.
- ZERO-CLICK: computed at start, shown everywhere, no setting.

R3. OBS-CRASH
- Action: (a) Electron main: handlers for an uncaught exception and an
  unhandled rejection that write the stack to overlay.log, which also
  stops the default error box; one log line with reason and exit code
  for a lost renderer or child process, an unresponsive page and a
  failed load. (b) Core: `ops/runtime/last-exit.json` on every exit
  path (stop, reload, signal, crash with the exception class and
  repo-relative file and line); the next start logs how the last run
  ended. (c) Checks: the Reading row follows the thread's liveness; a
  Restarts note shows when the supervisor restarted the core in the
  last 24 hours. (d) Local Electron crash dumps only with AL_DEV=1
  (ELCRASH: collection without upload is supported).
- Impact: H. Removes a focus-taking dialog during play and three blind
  spots (F1, F4). Effort: M.
- Risk: swallowing a main-process error that should stop the app: log,
  then quit and let the client restart; never continue silently.
  Depends on: the reliability note's reader restart (Cut or merge).
- ToS check: AshLight's own processes only; no dialog, so no focus
  taken from the game; dumps never leave the machine.
- Files: app/main.js, app/client/window.js, app/overlay/overlay.js,
  server/al/__main__.py, core.py, diag.py, keepalive.py, logfile.py,
  tests/test_core_crash_log.py, tests/test_diag_self.py, app/test/.
- Acceptance: a node test loads the handlers and asserts a thrown
  error is logged and no dialog function is called; the L3 dead-reader
  scenario as a test: Checks reads fail or the reader restarts; a core
  killed in a test leaves "previous run ended: killed" in the next
  start's log; a design-reviewer pass on the new Checks words.
- ZERO-CLICK: all automatic; the note appears and clears by itself.

R4. OBS-COUNTERS
- Action: `server/al/metrics.py` (in-memory counters, gauges, small
  timing rings), `GET /api/debug` (token, loopback, pull only, never in
  the SSE snapshot, under 4 KB) and `python -m server.al.probe`, one
  line per item, for sessions and lanes. Set: loop tick milliseconds
  (last, p95, max, worst function); tailer lines, bytes, resets,
  dropped, backlog, thread alive; events by type and ignored lines by
  class; SSE clients now and peak, queue drops, frames, bytes; HTTP
  requests by route and status class, 401 count; hotkey presses with
  outcome kind and milliseconds; calc starts, restarts, timeouts,
  latency; fetches per allow-listed host by status class, errors,
  milliseconds; own uptime, RSS, CPU seconds, threads; the overlay's
  summed working set and CPU, sampled once a minute by its own main
  process (ELAPP) into `ops/runtime/overlay-state.json`.
- Impact: H for development, M for players. Sessions get one command
  in place of hand-rolled probes (F11); OVL-BUDGET's active RAM and CPU
  figure collects itself during normal play (F5); slow ticks show up.
  Effort: M.
- Risk: overhead; each update is O(1), 20 clock reads per 0.5 s tick.
  Depends on: R2 for the build line; R1's class counters.
- ToS check: numbers about AshLight's own processes only (its own
  process handle, Electron's metrics for its own process tree). It
  never lists or opens the game process, so decision 0029 holds. The
  FPS figure stays an operator reading (decision 0006).
- Files: server/al/metrics.py (new), probe.py (new), http.py,
  __main__.py, logfile.py, bus.py, webfetch.py, core.py,
  theorycraft/bridge.py, app/main.js, tests/test_metrics.py (new).
- Acceptance: lines read equals events plus ignored after a fixture
  replay; the SSE gauge goes 0, 1, 0 around a client; a 304 and a
  network error through the injected transport land in the right
  counters; /api/debug returns 401 without the token and no debug key
  is in the snapshot; 100,000 updates take under 50 ms; the probe
  exits 0 on a live test core and 1 on a stopped one.
- ZERO-CLICK: counted by itself; the probe is scripted into the
  session start and into lanes.

R5. OBS-EXPLAIN
- Action: extend Checks with 5 cause rows fed by R3 and R4: overlay on
  screen (shown, or hidden because you turned it off, or hidden because
  the game looks closed, or starting); item check key (last press, how
  long ago, outcome kind); calc at run time (last call or time-outs);
  log lines understood (events against lines in the last 10 minutes,
  failing when 500 lines gave 0 events); restarts. Single-source each
  card's empty-state sentence from the same module.
- Impact: M to H for players (F6); it is also the player-facing 1.0
  format alarm. Effort: M.
- Risk: a long Checks list; it stays folded and opens on failure.
  Depends on: R3, R4.
- ToS check: the overlay's state comes from AshLight's own window
  object, never from a screen read or a look at the game window; an
  exclusive-fullscreen cause can only be a fixed hint, never detected.
- Files: server/al/diag.py, core.py, app/main.js, app/overlay_gate.js,
  web/checks.js, tests/test_diag_self.py, app/test/checks.test.js.
- Acceptance: one test per new row and state; a seeded overlay-state
  file drives each overlay sentence; a design-reviewer pass.
- ZERO-CLICK: computed every 5 s; opens by itself on a new failure.

R6. OBS-REPORT
- Action: build the report on the click (`GET /api/report`) from an
  allow-list of structured fields: build, OS build number, Python and
  Electron versions, Checks rows, counters, last exit and restarts, and
  ledger shapes when the ledger is on. Show the exact text in a
  read-only preview before the copy. No log tails by default; an
  explicit second choice adds them through a hardened redactor (whole
  words, every known character name, UNC and quoted paths, POSIX home
  paths, addresses, hex runs of 32 or more, mail). Take the report text
  and its stamp out of the snapshot, and send the two age rows as
  absolute times that web/checks.js renders as ages (F8, verifier
  correction). At go-public add an issue
  form with a report text area and a required "I read it" checkbox
  (GHFORM, GHTPL).
- Impact: H once the repo is public; M now (F7, F8). Effort: M.
- Risk: the copy must stay inside the click's activation; test in the
  client window and a browser. Depends on: R2, R4; R1, R9 optional.
- ToS check: no upload (ruling J); the clipboard is written only on
  the player's click (decision 0014); nothing new is read.
- Files: server/al/diag.py, http.py, core.py, state.py, web/checks.js,
  web/index.html, app/overlay/overlay.js (only if it reads the age
  rows), tests, .github/ISSUE_TEMPLATE/ (at go-public).
- Acceptance: a fuzz test with the L3 strings and 1,000 seeded variants
  finds none of the seeded secrets in the output; the snapshot holds no
  report text and its version stays still over 3 idle minutes with web
  data on and a last line 5 minutes old (the case that moves today); the
  preview equals the copied text byte for byte.
- ZERO-CLICK: one click to copy (decision 0014 requires it); the
  preview costs no extra click.

R7. OBS-LOGS
- Action: rotate at start (over 1 MB moves to `.1`, one kept) for
  core.log, keepalive.log, overlay.log, run.log and tc-bridge.log, with
  a 2 MB in-run backstop for the core; one time-stamp format (UTC ISO)
  and a level word in all three app logs; pid in core.log lines; a
  banner line per start (R2), also before each calc bridge start.
- Impact: M (F10). Effort: S.
- Risk: PYLOG: rollover never happens when the backup count is 0;
  PYFAULT: the fault handler keeps its file descriptor, so it needs its
  own always-open file once the core log can roll over. Depends on: R2.
- ToS check: AshLight's own files in its sidecar only.
- Files: server/al/__main__.py, keepalive.py, theorycraft/bridge.py,
  app/main.js, scripts/run.ps1, tests.
- Acceptance: a 1.1 MB log becomes `.1` at the next start and the new
  file starts with the banner; a native-fault test writes to the crash
  file after a rollover; no log line holds an absolute path (test).
- ZERO-CLICK: at start, by itself.

R8. OBS-SSE-EVENTS
- Action: stop sending the "events" frame by default; keep it as a dev
  tap (`/events?tap=1`, honoured only in a source checkout) with text
  fields removed; move the 4 tests that read the frame to the tap.
- Impact: M (F9): chat, whisper text and server addresses stop leaving
  the core; one encode and write less per chat line. Effort: S.
- Risk: a hidden consumer; grep shows none in web/ or app/. Depends
  on: none.
- ToS check: reduces what is passed on; reads nothing new.
- Files: server/al/http.py, tests/test_fullstack.py,
  test_e2e_replay.py, test_soak.py, test_http_security.py.
- Acceptance: a default stream holds 0 "events" frames over a fixture
  replay and the state pushes still arrive within 250 ms.
- ZERO-CLICK: nothing to do.

R9. OBS-OPLOG
- Action: `server/al/oplog.py` writes one JSON line per own event to
  `<sidecar>\Logs\events.jsonl`: about 20 kinds (start with build and
  pid, stop reason, reader start / reset / death, consent and web data
  switches, fetch result per host, calc start / time-out / exit, press
  outcome and milliseconds, reload, first pattern hit, new shape). Each
  kind has typed fields: numbers, booleans or a word from a fixed set;
  no free-text field type exists.
- Impact: M: answers "what happened before it stopped showing".
  Effort: S.
- Risk: growth; rotated with R7. Depends on: R2, R7.
- ToS check: AshLight's own events only; no log text, by type.
- Files: server/al/oplog.py (new), call sites in core.py, logfile.py,
  webfetch.py, bridge.py, __main__.py, tests/test_oplog.py (new).
- Acceptance: a free-text value passed to any kind is dropped and
  counted; a replayed session writes the expected kinds in order.
- ZERO-CLICK: written by itself; read by the probe and the report.

R10. OBS-DEV-LEDGERS
- Action: add subagent_first to the rotation list; let the probe read
  the docs watch state.json and flag a last good read older than 3
  days; move one-off suite logs in `<sidecar>\Logs` to `Logs\dev\`.
- Impact: L (F11). Effort: S.
- Risk: none; rows are moved, never deleted (FLEET item 9). Depends
  on: R4 for the probe.
- ToS check: development files only.
- Files: tools/ledger_rotate.py, tests/test_ledger_rotate.py,
  server/al/probe.py.
- Acceptance: a seeded 40-day ledger keeps 30 days; a state.json with
  an old read prints a STALE line.
- ZERO-CLICK: the daily rotation pass does it.

## Cut or merge

- R7 and R9 touch the same files: one work package.
- R3's reader restart and the reliability note's fix for the same root
  cause (logfile.py:245-251) are one change; this note owns the Checks
  side only.
- Cut from the snapshot: `events_seen` once /api/debug exists
  (state.py:1831; no page reads it), the report text (R6); cut the
  "events" SSE frame (R8).
- Keep one player-facing health surface: extend the Checks card (R5),
  do not add a second status page; /api/debug stays a dev surface.
- LIVE-1 is one row for 11 remaining items (ROADMAP.md:13-18); split
  it so each closes when the ledger shows its first live hit.

## Rejected

- Automatic upload of a report, shapes, metrics or crash dumps: a
  network call outside the web-data opt-in (ruling J, decision 0013),
  and no first-party server exists.
- Storing raw unknown lines "for debugging", even locally: it would put
  chat, names and addresses on disk; the consent text says what is
  derived, not that the log is copied.
- Mining repeated tokens as shape constants (DRAIN style) to learn
  localised lines: the player's own character name repeats most.
- A screen capture, a look at the game window or process, or a game
  config read to explain a hidden overlay or name the display mode:
  outside the read floor (decisions 0003, 0029). Frame tracing for an
  FPS gauge: decision 0006.
- Logging a press's clipboard or item text: memory only (decision 0045).
- A health or metrics page on the LAN or a phone: 127.0.0.1 only.
- A third-party logging, metrics or crash library, or an exporter: the
  core is stdlib only (decision 0002).
- Machine-wide crash dump settings in the registry: needs admin, and a
  full dump holds the token, chat and item text.
- The build id in the User-Agent: changes a settled contract for no
  gain (decisions 0013, 0015).

## Open questions

1. Consent scope (adjudicator, at plan time): does the existing
   Client.txt consent cover the persisted hit ledger, or do both ledger
   parts wait for the new consent line? Recommended: both wait; the
   in-memory counters do not. Does revoking consent delete the ledger
   file? Recommended: yes.
2. Are speech-like lines without a channel mark ever local chat in
   PoE2? UNVERIFIED. The design treats them as chat either way.
3. The build id for an install without .git depends on the release
   pattern (notes 0052 and 0053).
4. Should players see the Restarts note, or only the dev details
   (design review)?
5. Should the public issue form ask for the shape list (operator
   decision at go-public)? Recommended: yes, for English clients.

## Verification

Independent verifier, 2026-11-18. Product code read, never changed; no
Client.txt line read; no core started; nothing touched the game.

Checked:

- Code (A): about 40 path:line citations opened, covering every finding and
  every recommendation's evidence (logfile, bus, core, state, diag,
  http, parser, __main__, keepalive, bridge, webfetch, procs, build.ps1,
  run.ps1, paths, web/checks.js, web/app.js, app/main.js,
  app/overlay_gate.js, app/eval_hotkey.js, app/client/link.js,
  overlay.js, al_loop.py, ledger_rotate.py, ROADMAP rows, the audit,
  research 0002, the hand-off). All held except the details corrected
  below. F1's mechanism confirmed in code: `Tailer._run` catches OSError
  only and listeners run synchronously in the tailer thread. 0 handlers
  for uncaught errors, lost renderers or failed loads in app/ (grep).
  The 4 tests that read the "events" frame confirmed (a fifth,
  test_trade_expire.py:105, asserts its absence).
- Numbers (Summary and findings): core.log 123 lines and its 44 / 39 /
  38 kinds re-counted; 16 Checks rows (diag.py:226-234); /api/health 74
  bytes; 5 unread counters; 10 tick calls in the 0.5 s loop
  (ensure_tailing plus 9 tick_*); report 15 lines; 12 tracked
  characters (state.py:63).
- Web (B): 9 of 11 sources re-fetched 2026-11-18 and matched the claims
  (GHTPL not re-fetched: it only names the go-public template folder)
  (GGG docs: user-aware rule, once-per-press reads, general privacy
  sentence, new applications still not processed; PYLOG backupCount 0
  means no rollover, page is 3.15.2; PYFAULT keeps the file descriptor;
  ELCRASH submitURL optional when uploadToServer is false, dumps under
  crashDumps; ELAPP getAppMetrics, child-process-gone,
  render-process-gone; ELWC render-process-gone, unresponsive,
  did-fail-load; ELGONE reason values; ELINIT on main and 45-x-y;
  GHFORM required checkboxes). DRAIN: title only (see Sources). The
  1.0 date is also in research 0018 and docs/plan/01-open-items.md.
- Probes: re-ran the synthetic Checks-view probe (diag.view with fixed
  facts, 60 s apart) and a 12-case edge probe against the author's
  allow-list prototype, both in the sidecar scratch area.
- ToS (C): each of R1 to R10 tested against every floor rule. All stay
  inside: no game process, window, screen or memory access; no input;
  Client.txt read only after opt-in; clipboard written only on a click;
  no network beyond existing opt-in paths; all endpoints on 127.0.0.1
  behind the token; no branding change; no revenue. Nothing moved to
  Rejected.
- Settled decisions (D): no reversal proposed. R1's file does not touch
  LIVE-RESUME's no-persisted-state rule (0008); the User-Agent stays
  (0013, 0015); report copy on a click stays (0040, 0014); no process
  check (0029); no frame tracing (0006); stdlib core (0002).
- Completeness (E): every brief point is covered (logs, DIAG-SELF,
  /api/health, Checks, progress, usage log, docs watch; parse ledger,
  counters, explainer, public report, crash records, build stamp, dev
  observation, privacy and ToS limits, ranking). Gap filled: account
  names added to the never-on-disk class.
- Recommendations (F): all 10 carry the required fields. Ranking kept;
  execution note: R3's error-box handler and the F1 Checks fix need no
  ruling and should ship before or with R1, which waits on Open
  question 1.

Corrected (9): commit count (356 at drafting, 381 now; wording made
count-free); build-stamp.json does record a source hash; F1 now names
the core.log trace the thread hook leaves; parser exit detail added;
tc-bridge.log and subagent_first.jsonl re-counts; F8 and R6: the age
rows also change each minute, so R6 now moves them to absolute times
and its acceptance test covers the moving case; the mask "by
construction" claim narrowed to its two edge gaps, with R1 acceptance
cases added; unhandled-rejection default marked UNVERIFIED; DRAIN
source note.

UNVERIFIED (3): Electron main-process default for an unhandled promise
rejection; whether PoE2 local chat looks like the speech-like NPC lines
(Open question 2); the live L2 / L4 figures (snapshot 6,384 bytes,
version 187 to 189) were not re-read, though the mechanism behind L4
was reproduced synthetically.
