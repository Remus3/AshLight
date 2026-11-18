# 0045 - Security of the local surface

Date: 2026-11-17. For the ultraplan (docs/plan/README.md), dimension B9
hardening: local surface. Scope: the core's HTTP server on 127.0.0.1, its
token, runtime files, supervisor, hot reload, scheduled tasks and every
input it parses (log, item text, build codes, settings, filters, web
replies), read at HEAD b8fda80; plus what a phone view would need.
Electron hardening and the supply chain are note 0046.
Status: draft

## Sources (all accessed 2026-11-17)

- LNA-C: https://developer.chrome.com/blog/local-network-access
- LNA-F: https://www.firefox.com/firefox/151.0/releasenotes/
- SFS: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Site
- SC: https://w3c.github.io/webappsec-secure-contexts/
- FM: https://web.dev/articles/fetch-metadata
- CORP: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Resource-Policy
- T1187: https://attack.mitre.org/techniques/T1187/
- EXPAT: https://libexpat.github.io/doc/api/latest/
- PYXML: https://docs.python.org/3/library/xml.html
- PYHTTP: https://docs.python.org/3/library/http.server.html
- PYOS: https://docs.python.org/3/library/os.html
- PYURL: https://docs.python.org/3/library/urllib.request.html
- EXCL: https://learn.microsoft.com/en-us/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse
- JOB: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- ICACLS: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls
- TS: https://tailscale.com/kb/1312/serve
- AUD: docs/audit/2026-11-17-audit.md (passes 1 to 8, up to main 1e73774).
- RES8: docs/research/0008-dashboard-tech.md (the original security design).
- PROBE: throwaway scripts run on 2026-11-17 against the repo code in a
  scratch process, never the live core: an isolated server on an ephemeral
  loopback port with a dummy core, pure-function calls, stdlib
  introspection, a read of three folder ACLs. Nothing left the machine.
  Untracked, under `<sidecar>\Scratch\up-0045-sec\scripts\`. Python
  3.14.4, bundled Expat 2.7.5, OpenSSL 3.0.19.

## Summary

The design holds against its main threat: a hostile web page can neither
read nor change anything; five independent layers stand in the way (Host
allow-list, Origin check, a 192-bit header token, JSON-only bodies with no
preflight answered, strict CSP with textContent rendering). The audit left
two security lows open (P8-3, P8-4). This note adds 13 findings, scored
exploitability x impact (1-3 each). Top: F1 (6) the token-free static
route resolves a URL-supplied path before checking containment, so one GET
makes the core open an SMB connection to a host the requester names; F2
(4) a 16-bit encoded build payload passes the "no DTD" text guard; F3 (3)
token, code and calc binaries are private only when the install folder
is; F5 / F6 (2) local clients send the token to whatever answers on the
port. F1 and F2 are confirmed by probe. R1-R8 (S or M each) close every
finding scored 2 or more except F4 and F8 (R9, R10). Nothing touches the
ToS floor. The phone view is three designs for the operator's decision.

## Threat model

Assets: (a) the per-start token, which is full control of the API (read
zone, character, whispers, trades and the Client.txt path; flip consent
and web data; load builds; clear history); (b) the player's Windows
credentials and files, reachable only through a bug; (c) the game session
(frame rate, focus), never the game process; (d) the contact string in
config/local.json.

Attackers, most likely first:

- T1 a hostile web page in the player's browser while AshLight runs:
  CSRF, DNS rebinding, cross-origin reads, no-cors requests to the
  token-free static routes. Chrome from 142 and Firefox from 151 (still
  rolling out) ask the player before a public page may reach loopback
  (LNA-C, LNA-F); embedded browsers, older builds and an "Allow" click
  remain, so the server's own checks stay the primary defence.
- T2 hostile content the player feeds in: a pasted build code or share
  link (builds from strangers are the normal input), item text on the
  clipboard at a hotkey press, an imported settings file, an uploaded
  filter.
- T3 hostile lines in Client.txt: other players choose their whisper and
  chat text and their character names.
- T4 a hostile or broken reply from a web source (poe.ninja, the paste
  sites, repoe-fork, GitHub, the GGG docs pages).
- T5 other local accounts and lower-privileged processes on the same PC:
  loopback ports are shared, and so are files when the folder ACL allows.
- Out of scope: malware already running as the player, and physical
  access; both can read everything AshLight can.

## Current state

- Listener: binds 127.0.0.1 only (server/al/http.py:94,
  server/al/ports.py:8); port held to 8960-8979 (ports.py:28-47) except
  by `--port`, which only warns (server/al/__main__.py:154-155; audit
  P8-4). `SO_EXCLUSIVEADDRUSE` stops a second socket taking the port
  (http.py:99-102; EXCL); IPv6 loopback is not bound. Stdlib
  `ThreadingHTTPServer`, HTTP/1.0 (http.py:79-80), which Python documents
  as doing only basic security checks (PYHTTP).
- Token: 192 random bits as 48 hex chars (http.py:75-76), compared in
  constant time, accepted as `X-AL-Token`, `Authorization: Bearer`, or
  `?token=` on /events only (http.py:183-198).
- Token holders: the server; `<runtime>/token` (__main__.py:174-175),
  written by `write_private`, whose 0600 mode has no effect on Windows
  (server/al/core.py:38-50; PYOS); the dashboard's sessionStorage
  (web/app.js:24-35); the overlay page through its preload
  (app/preload.js:16-17, app/main.js:338-343); the Electron main
  process, the supervisor and run.ps1, which read the file
  (app/main.js:78, server/al/keepalive.py:197, scripts/run.ps1:104-107).
- Token path to the page: the URL fragment (app/client/link.js:24-28,
  run.ps1:192), stored and stripped at once (web/app.js:28-30); in
  `-Browser` / `-EdgeApp` mode the URL is also on the browser's command
  line (run.ps1:231-240).
- Token lifetime: one core run, no expiry or rotation, one scope for
  reading and for every POST; the file is removed on a clean exit
  (__main__.py:279-284) and left behind by a crash.
- Token reuse (decision 0042): a core leaving for a code reload writes
  `<runtime>/token.reuse`; the next start keeps the token when the mark
  is under 120 s old and the file holds 48 hex chars
  (server/al/hotreload.py:279-311, __main__.py:164-165, 277-278). The
  only proof of origin is write access to the runtime dir.
- Host must be `127.0.0.1:<port>` or `localhost:<port>`, else 400
  (http.py:96, 168-169): a rebinding name fails here. Origin, when sent,
  must be one of the two (http.py:97, 171-178); `null` / `file://`
  passes only for GET on /events, /api/state and /api/health, with
  `Access-Control-Allow-Origin: null` (http.py:66-67, 179-180). No other
  CORS header exists and OPTIONS is a 405 (http.py:409-411), so no
  preflight succeeds. Both checks run on every route before the token
  (http.py:200-212).
- Headers on every reply (PROBE): `Content-Security-Policy: default-src
  'self'; script-src 'self'; style-src 'self'; img-src 'self' data:;
  connect-src 'self'; font-src 'self'; object-src 'none'; base-uri
  'none'; form-action 'none'; frame-ancestors 'none'` (http.py:38-41);
  `X-Content-Type-Options: nosniff`; `Referrer-Policy: no-referrer`;
  `X-Frame-Options: DENY`; `Cache-Control: no-store` (http.py:143-146);
  `Server: AshLight/<version>` (http.py:122-123). Not sent:
  `Cross-Origin-Resource-Policy`, `Cross-Origin-Opener-Policy`,
  `Permissions-Policy`. `Sec-Fetch-Site` is not read.

### Route inventory (complete; http.py:219-411)

- No token, GET / HEAD (Host and Origin checks only): `/`, `/index.html`,
  `/web/<file>`, `/favicon.ico`, `/tokens.css`: files under web/ plus one
  kit file (http.py:225-233, 682-697).
- Token, GET / HEAD, no input: /api/health, /api/version, /api/state,
  /api/overlay-layout, /api/build, /api/weights, /api/gfx, /api/web-data,
  /api/rates (may start a background refresh while web data is on),
  /api/filter, /api/buildfile, /api/settings-export (downloads), /events
  (SSE, GET only, the one route taking `?token=`).
- Token, POST, a JSON object as `application/json`, 4,096 bytes unless
  stated (http.py:464-496): /api/clipboard-read (a 501 stub,
  http.py:311-317); /api/consent `{consent, path?}` (lexical path check,
  server/al/logfile.py:106-132; F9); /api/overlay-layout (strict fields
  and ranges, server/al/layout.py:51-96); /api/trade-dismiss,
  /api/web-data, /api/run-history, /api/price-watch, /api/hints (one
  typed flag or id each); /api/build-code `{code}` or `{character}`
  (256 KiB; code, JSON or share link, http.py:595-628); /api/eval
  `{item, slot?}` (80 KiB, http.py:630-654); /api/settings-import
  (16 KiB, allow-list, server/al/settingsio.py:84-108);
  /api/filter-merge (raw bytes as `application/octet-stream`, 2 MiB,
  `?name=` reduced to a safe base name, http.py:498-534).
- Token, PUT /api/weights, 64 KiB: at most 500 ASCII keys, finite
  numbers (server/al/theorycraft/weights.py:28-33, 146-176).
- DELETE, PATCH, OPTIONS: 405. Anything else: 404. Routes match the raw,
  un-decoded path and the token rule reads the same string
  (http.py:214-216), so no encoding trick separates them.

### Limits, static files, errors

- Request line 65,536 bytes, 100 header lines (stdlib; PROBE); body caps
  as listed; a refused body is drained up to 1 MiB within 2 s
  (http.py:46-54). 10 s per socket read or write (http.py:58, 126); no
  whole-request deadline; handler threads uncapped except SSE.
- SSE: 16 streams, at most 4 pushes a second, 15 s heartbeat, a closed
  client noticed within about a second (http.py:43-44, 62, 699-712,
  787-798); events go out without their raw log line (http.py:755).
- `/web/<rel>`: `(root / rel).resolve()`, then `is_relative_to(root)`,
  then `is_file()` (http.py:682-697); `rel` is the raw path tail
  (http.py:227-228). Tests cover `..` and `%2e%2e`
  (tests/test_http_security.py:122-125).
- Handler exceptions go to the log, the client gets a closed socket
  (http.py:109-118); the query string is never logged (http.py:132-134).
  Three token-gated JSON errors can carry lower-level text: the XML
  parser's message (server/al/theorycraft/model.py:201), urllib's error
  (server/al/webfetch.py:164), an OS error naming the config path
  (layout.py:121).

### Files and control channel

- Plain files in the runtime dir drive the lifecycle: heartbeat
  `core.alive` with pid, port and creation time (__main__.py:133-142);
  `stop.request` ends core and supervisor (scripts/stop.ps1:77,
  __main__.py:216-218, keepalive.py:301-307); `restart.request` makes
  the core exit and keep its token (keepalive.py:419,
  __main__.py:219-225). The supervisor terminates only a python image
  whose creation time equals the one in the heartbeat file
  (keepalive.py:139-150, 343-352).
- At rest: `<repo>/ops/runtime/` (token, consent, control files, build
  codes, weights, run history; server/al/paths.py:35-41, 87-97),
  `config/local.json` (contact, Client.txt path, opt-ins;
  paths.py:119-121), the sidecar (logs, caches, luajit.exe, the PoB
  checkout; paths.py:61-71, 124-155). No file gets an ACL of its own.
  PROBE (icacls): here the token file, the repo root and the sidecar
  root all inherit Modify for the Authenticated Users group.

### Inputs

- Client.txt: lines over 64 KiB dropped (logfile.py:26, 338-342), over
  8,192 chars ignored, trade templates tried only up to 1,024 chars
  (server/al/parser.py:73-74); game events come only from system lines,
  so chat cannot fake them (parser.py:162-165); character names become
  file names only as a hash or hex slug
  (server/al/theorycraft/store.py:51-58).
- Item text: 64 KB client cap, 80 KiB body cap; regexes linear since
  audit P2-I2.
- Build code: inflate bounded at 8 MiB
  (server/al/theorycraft/codec.py:23, 102-115), a DTD text guard, then
  ElementTree (model.py:190-194); a code that parses is saved per
  character (store.py:280-298) and, with the calc on, sent to PoB.
- Share link: two hosts; URL rebuilt from a fixed template around an id
  of at most 64 safe chars; the reply (2 MiB) must itself be a build
  (server/al/theorycraft/shareurl.py:32-46, 49-94).
- Settings import: 12 allow-listed keys; never contact, paths, port or
  token; never switches web data or the calc on (settingsio.py:84-108,
  150-158). Filter merge: UTF-8, no NUL or control bytes, in memory
  only; generated lines hold `[A-Za-z0-9 ',-]` names only
  (server/al/theorycraft/lootfilter.py:49, 227-246, 280-289).
- Web replies: 2 MiB cap, 4 MiB for poe.ninja (webfetch.py:32,
  server/al/ninja.py:59); JSON with type checks; text reaches the DOM
  through textContent only (web/app.js:5).

### PoB bridge and outbound fetch

- Bridge: fixed argv, no shell; luajit.exe hash checked before every
  start against a record beside the exe; one ASCII JSON line per
  request; 60 s timeout, then kill; replies need a fixed prefix; 1 MiB
  line cap (server/al/theorycraft/bridge.py:38, 47, 144-157, 204-207,
  283-286; server/al/exepin.py:11-13). The child inherits the whole
  environment and an unrestricted Lua: io, os, LuaJIT ffi, native
  modules on LUA_CPATH (bridge.py:136, 143).
- Core fetch, webfetch.py only: https, exact host allow-list, no user
  info, port 443, no IP literal, at most 2,048 ASCII chars
  (webfetch.py:99-127); at most 3 redirects, each re-checked
  (webfetch.py:183-210); User-Agent required, Cookie refused
  (webfetch.py:190-193); 10 s per socket operation, no total deadline
  (webfetch.py:30, 148-153). TLS is urllib's default: chain and host
  name verified, TLS 1.2 or newer (PROBE). Environment and registry
  proxy settings are honoured (PYURL).
- Build-time snapshot: own opener, two hosts, a path prefix on the
  GitHub raw host, redirects re-checked, 60 s per read, up to 256 MiB
  in memory (server/al/theorycraft/snapshot.py:58-63, 103-134). Tools:
  tc_pin.py (pinned SHA-256 and size, at most 3 redirects, member path
  and symlink guard; tools/tc_pin.py:55-61, 253-286, 339-351);
  tc_drift.py and ggg_docs_watch.py go through webfetch.
- Loopback: the supervisor's health check uses plain `urlopen`
  (keepalive.py:194-206).

### Hot reload and scheduled tasks

- Web and code reload are on when `.git` exists at the repo root, unless
  env `AL_HOT_RELOAD` or config "hot_reload" says otherwise
  (hotreload.py:64-76). A changed server .py settles 1.5 s, then
  `python -m server.al --check` runs in a child (keepalive.py:404-426,
  493-514); the check imports the core and compiles every file
  (__main__.py:44-66), so it already executes the changed modules.
- "AshLight Autostart" (opt-in, off by default): at logon, run level
  Limited; wscript runs scripts/autostart_launch.vbs with the repo as
  working directory (scripts/autostart.ps1:68-87, 148-157); that script
  starts `powershell.exe` by bare name (autostart_launch.vbs:11-13).
- `\AshLightOps\LaneLoop` (the dev loop): every 15 minutes,
  LeastPrivilege, pythonw by absolute path on tools/al_loop.py
  (tools/loop_task.py:72-77, 174-186). Neither task is elevated; both
  run repo code as the player.

## What the audit already found (AUD)

- Fixed, each with a regression test: held-hotkey clipboard repeat (audit
  F1); HEAD /events stream, missing socket timeout, `?token=` on every
  route, any or UNC consent path (S1-S4); bare `powershell.exe` /
  `cmd.exe` and an unhashed luajit.exe (S5); tree link to any https host
  (S8); snapshot fetched by default (T1); Infinity in JSON (P2-V1);
  bridge replay list, Lua DLL hash, EOF and line caps (P2-B1 to B5);
  quadratic item regexes (P2-I2); overlong log lines (P2-L1); huge JSON
  integers (P3-2); luajit kept after opt-out (P3-6); pin file moved by
  an env var (P3-8); unattended drift trial (P3-9); toolchain re-hash
  (P3-10); config overwritten when broken (P5-1); import switching the
  calc on (P5-2); hotkeys without a modifier (P5-3); filter marker
  without an end (P5-5); `$` before a newline (P6-2); JSON reader
  recursion and size caps (P7-3, P7-8). S6 and S7 belong to note 0046.
- Open: AUDIT-P8-LOW. P8-3: the client's port rule takes any number
  (app/main.js:67-76), so token and item text can go to a port the core
  never binds. P8-4: `--port` outside the block still binds. P8-5 to
  P8-8 are not security items.
- Not covered (merged after pass 8): the desktop client (decision 0041),
  hot reload and token reuse (0042), the zone guide (0043), the docs
  watch (0044), per-character builds (0045).
- Where this note differs: AUD records static serving as clean (see F1)
  and the token file as written 0600 (no effect on Windows; see F3).

## Findings

Score = exploitability x impact, each 1 (low) to 3 (high).

- F1 (2 x 3 = 6) The static route opens network paths. `/web/<rel>` joins
  the URL tail to the web root and calls `Path.resolve()` before the
  containment check (http.py:227-228, 686-687). A tail that begins with
  two slashes is a UNC name on Windows, and resolving it opens that path.
  PROBE: one token-free GET made the handler resolve
  `\\<host>\<share>\x` (10.1 ms against the loopback SMB service, about
  0.1 ms for local names) before answering 404; opening the same name
  directly failed with Windows error 67, which only an SMB server
  answers. Why it matters: Windows logs on to an SMB server by itself
  and so hands it the player's credential hash (T1187) wherever outbound
  SMB is not filtered. No token is needed and a no-cors GET carries no
  Origin, so any page that can reach loopback is enough (T1), as is any
  local process; each request also parks a handler thread for the SMB
  timeout. AUD fixed this class only on the token-gated consent path
  (S4).
- F2 (2 x 2 = 4) The DTD guard misses 16-bit encodings. `_root` refuses
  XML whose text holds `<!DOCTYPE` or `<!ENTITY` (model.py:190-192),
  reading the bytes as UTF-8; the codec only wants the payload to start
  with `<` (codec.py:141). A UTF-16LE document without a byte order mark
  passes both, and Expat detects its encoding alone. PROBE: a share code
  holding such a document with one harmless entity parsed with the
  entity expanded; its UTF-8 twin was refused. Expat stops expansion only
  past 100 times the input once output exceeds 8 MiB (EXPAT; the bundled
  2.7.5 has that guard, PYXML). No expansion test was run. Why it
  matters: with the 8 MiB XML cap the worst case is hundreds of megabytes
  of text built inside the core while the game runs, and a code that
  parses is saved (store.py:287-291) and parsed again at every start.
  Expat opens no file and no connection (PYXML): a stall, not a leak.
- F3 (1 x 3 = 3) Private files are only as private as the install
  folder. Nothing sets an ACL and `write_private` cannot (core.py:38-50,
  PYOS). With the ACL found here (PROBE) any other local account or
  service account can: read the token and use the whole API; replace it
  and plant `token.reuse` so the next core adopts a chosen token
  (hotreload.py:289-311); write the stop and restart files, or a forged
  heartbeat that points the supervisor's terminate at another python
  process (keepalive.py:343-352); edit repo code, which hot reload runs
  within about 2 s and the two scheduled tasks start later; swap
  luajit.exe together with its hash record (exepin.py:11-13). The logon
  launcher's bare `powershell.exe` with the repo as working directory
  (autostart_launch.vbs:11-13) is one more such path, the class
  AUDIT-EXE-PATH fixed elsewhere. Why it matters: nil on a one-account
  PC; on a shared PC it is code execution as the player, and a public
  release cannot know where people unpack it.
- F4 (1 x 3 = 3) The calc child is unconfined: full environment, no job
  object, every Lua library (bridge.py:136, 143, 171-175). Build XML and
  item text go straight into PoB's parsers, so a PoB bug that evaluates
  input is code execution as the player. Needs the opt-in calc and a
  hostile build. Decision 0025 already lists "a no-admin OS sandbox" as
  something that would change its ruling.
- F5 (1 x 2 = 2) No client checks who answers on the port. The Electron
  main process posts the hotkey's clipboard text with the token
  (app/eval_hotkey.js:51-70) and loads the dashboard once any listener
  answers 200 (app/client/link.js:128-145); the supervisor and run.ps1
  send the token the same way (keepalive.py:194-206, run.ps1:109-119).
  Loopback ports are shared by all accounts, and the exclusive bind only
  protects a port the core already holds (EXCL). A wrong port (P8-3) or
  a process that bound first receives the token and whatever is on the
  clipboard, and can show a fake dashboard.
- F6 (1 x 2 = 2) One loopback call follows the proxy settings. The
  health check uses urllib's default opener (keepalive.py:200-204).
  PROBE: with a registry proxy and the usual "bypass local addresses"
  entry, urllib does not treat `127.0.0.1` as local, and with a proxy
  from environment variables and no `no_proxy` it does not bypass either
  (PYURL). On such a PC the request, token header included, goes to the
  proxy and the check fails, so a core with a late heartbeat is
  terminated as hung. The PowerShell check in run.ps1 was not tested
  (UNVERIFIED); Node and Chromium are not affected.
- F7 (2 x 1 = 2) Static routes answer every site. No token and no Origin
  on a no-cors GET: any page that can reach loopback can load
  `/favicon.ico` or `/web/app.js` (PROBE: 200, 48 KB) and learn that
  AshLight runs and which build. Neither `Cross-Origin-Resource-Policy`
  nor `Sec-Fetch-Site` is used. It is also the browser's road to F1.
- F8 (1 x 2 = 2) One token, one scope, in a URL. The stream credential
  also authorises every POST, never expires within a run, and rides in
  the /events URL (web/app.js:1126, app/overlay/overlay.js:77-78) where
  browser extensions with wide host access can read it; the overlay page
  holds it though it only reads (app/preload.js:16-17).
- F9 (1 x 1 = 1) The consent path accepts any dot-free file.
  `consent_path_ok` allows a name without a dot, meant for a folder
  (logfile.py:131-132), and `discover_client_log` returns a configured
  path that is a file (logfile.py:138-143). PROBE:
  `%USERPROFILE%\.ssh\config` and the hosts file pass. Only log-shaped
  lines become events, so the leak is small, but it is not "Client.txt
  only".
- F10 (1) Allowances nobody uses: the `null` origin on /api/state and
  /api/health (a file page cannot send the token header without a
  preflight; the overlay uses /events alone, overlay.js:77-78);
  `localhost` in the Host and Origin lists while every AshLight URL uses
  127.0.0.1; `Authorization: Bearer` and the 501 stub, which have no
  caller in the repo.
- F11 (1) Missing ceilings: handler threads uncapped, timeouts per read
  (http.py:58, 79-80); outbound fetch without a total deadline
  (webfetch.py:148-153); snapshot bodies of up to 256 MiB in memory and
  a URL check that ignores user info and port (snapshot.py:58, 103-109).
- F12 (1) Hot reload is on in every git checkout and its check runs the
  new code (see Current state). Same precondition as F3, so it adds
  speed, not reach; it matters for the shape of the public install.
- F13 (1) Small leaks: version in the `Server` header on token-free
  replies; a config path in one API error; the token on the browser's
  command line in `-Browser` mode.

Checked again and clean: CSRF (Origin check, header token, JSON content
type, no preflight); DNS rebinding (Host list); cross-origin reads;
deflate bombs (bounded inflate); header injection (download names
reduced, lootfilter.py:280-289); SSRF through share links; log spoofing
by chat; DOM sinks and link targets (web/tc.js:52, web/prices.js:218);
settings import; filter merge; TLS verification.

## Recommendations

- R1 Serve static files from a fixed name list.
  - Action: build a map of the files under web/ at start and on each web
    hot-reload scan; answer `/web/<name>` by exact lookup only, with no
    filesystem call on request text.
  - Impact H: closes F1 and every path-shape variant (stream suffix,
    trailing dot, device name). Effort S. Risk: low; a new web file is
    served after the next scan. Depends on: nothing.
  - ToS check: no floor rule touched; it removes an unintended outbound
    connection. ZERO-CLICK: code change, nothing for the player to do.
  - Files likely touched: server/al/http.py, tests/test_http_security.py.
    Acceptance test: tails with two leading slashes, a drive name, a
    stream suffix, a trailing dot and a device name each get 404 while a
    spy on Path.resolve, os.stat and open sees no request text; every
    file in web/ still loads.
- R2 Strict build XML intake.
  - Action: refuse a payload that holds a NUL byte or is not valid UTF-8
    before the guard runs, and refuse a DOCTYPE inside the parser (an
    Expat doctype handler that raises); keep the text search as a second
    layer.
  - Impact M: closes F2. Effort S. Risk: a PoB export in UTF-16, if one
    ever existed, would be refused with a clear message. Depends on:
    nothing.
  - ToS check: floor untouched; build text stays user-pasted input
    parsed locally (decision 0004). ZERO-CLICK: code change.
  - Files likely touched: server/al/theorycraft/model.py,
    server/al/theorycraft/codec.py, tests/test_tc_code.py. Acceptance
    test: share codes holding UTF-16 documents (both byte orders, with
    and without a mark) with an entity get 400 from POST /api/build-code
    and nothing is saved; the real-export fixtures of decision 0021
    still round-trip byte-exact.
- R3 Refuse cross-site requests on every route; trim unused allowances.
  - Action: answer 403 when `Sec-Fetch-Site` is present and is neither
    `same-origin` nor `none`, with one exception (`Origin: null`, GET
    /events, for the overlay); send `Cross-Origin-Resource-Policy:
    same-origin` and `Vary: Sec-Fetch-Site`; cut /api/state and
    /api/health from the null-origin list; send `Server` without the
    version; keep OS error text out of API errors.
  - Impact M: closes F7, F13 and half of F10, and puts a second barrier
    before any F1-class bug. Browsers set the header themselves, send it
    to loopback (SFS, SC) and page script cannot forge it (SFS); the
    rule is the resource isolation recipe, made stricter (FM); CORP
    blocks no-cors loads from other origins (CORP). Effort S. Risk:
    clients that send no such header behave as today; the overlay's file
    page sends `cross-site`, hence the exception. Depends on: R1.
  - ToS check: floor untouched. ZERO-CLICK: code change.
  - Files likely touched: server/al/http.py,
    tests/test_http_security.py, app/test. Acceptance test: with
    `Sec-Fetch-Site: cross-site` every route answers 403 except GET
    /events with `Origin: null`; with `same-origin`, `none` or no header
    the existing suites pass; the overlay smoke run still reports its
    feed live.
- R4 Make AshLight's files private, and say so when they are not.
  - Action: (a) create the runtime dir with an explicit ACL (the player,
    SYSTEM and the local admin group; inheritance off) through the
    system icacls by absolute path (ICACLS) and write config/local.json
    the same way;
    (b) at core start compare the ACLs of runtime dir, repo root and
    sidecar root with that rule and publish a Checks note with a
    one-line fix when anyone else can write; (c) setup.ps1 applies the
    ACL to the sidecar; (d) the logon launcher starts PowerShell by its
    System32 path; (e) notes 0052 / 0053 make a per-user folder the
    default install and data location.
  - Impact H on shared PCs and public installs: closes F3 and removes
    the precondition of F12; nil on a one-account PC. Effort M. Risk:
    changing ACLs on a folder the player shares on purpose, so only
    AshLight-made folders are changed and the repo only gets the note.
    Depends on: nothing; wording with DIAG-SELF (decision 0040).
  - ToS check: floor untouched; AshLight's own folders only, never a
    game file or folder. ZERO-CLICK: (a) to (d) run by themselves; the
    note for a shared repo folder asks for one command, because
    rewriting ACLs on the player's own checkout unasked would be
    intrusive (no floor rule involved).
  - Files likely touched: server/al/core.py, server/al/paths.py,
    server/al/diag.py, scripts/setup.ps1, scripts/autostart_launch.vbs,
    tests. Acceptance test: a test core's runtime dir and token file
    list exactly three principals when read back; a dir prepared with
    one more writer yields the Checks note; no launcher starts a program
    by bare name.
- R5 Loopback calls never use a proxy.
  - Action: build the health-check opener with an empty ProxyHandler
    (PYURL); test the PowerShell health check the same way.
  - Impact M on PCs with a proxy: closes F6. Effort S. Risk: none
    known. Depends on: nothing.
  - ToS check: floor untouched. ZERO-CLICK: code change.
  - Files likely touched: server/al/keepalive.py, scripts/run.ps1,
    tests/test_keepalive.py. Acceptance test: with `http_proxy` set to a
    closed local port and no `no_proxy`, the health check is true
    against a test core and the fake proxy port sees no connection.
- R6 Clients verify the core before they send anything.
  - Action: add GET /api/hello?nonce=<32 hex> (no token) answering an
    HMAC-SHA256 keyed with the token over nonce and port; the Electron
    main process checks it once per token value, and again after any
    request error, before it posts item text or loads the dashboard;
    apply the 8960-8979 rule in app/main.js and refuse `--port` outside
    the block.
  - Impact M: closes F5, P8-3 and P8-4; clipboard text can no longer
    reach a foreign listener. Effort M. Risk: anyone can ask for MACs
    over chosen nonces; with a 192-bit key that reveals nothing, and the
    API still wants the token. Depends on: R3; the Electron side is
    shared with note 0046.
  - ToS check: the clipboard is still read once per manual press
    (decision 0003); this only narrows where that text may go.
    ZERO-CLICK: code change.
  - Files likely touched: server/al/http.py, server/al/__main__.py,
    app/main.js, app/eval_hotkey.js, app/client/link.js, tests,
    app/test. Acceptance test: a fake server answering 200 to everything
    receives neither token nor item text; a wrong-port config leaves the
    client on its starting page; `--port 9000` exits non-zero.
- R7 A consent path that is a file must be named Client.txt.
  - Action: `discover_client_log` returns a configured file only under
    that name (any case); dot-free names stay valid for folders only.
  - Impact L: closes F9 and makes the consent text literally true.
    Effort S. Risk: none known. Depends on: nothing.
  - ToS check: strengthens "READ ONLY ... Client.txt". ZERO-CLICK: code
    change.
  - Files likely touched: server/al/logfile.py,
    tests/test_audit_http_harden.py. Acceptance test: POST /api/consent
    with the path of an existing dot-free file leaves the tailer path
    unchanged and tails nothing; folder and Client.txt paths still work.
- R8 One test file that pins the surface.
  - Action: tests/test_security_surface.py holds a pinned table of every
    route (method, token rule, body cap) compared with the routes read
    from http.py, a pinned reply header set, and the R1-R7 cases.
  - Impact M: a new route or a dropped header cannot ship unreviewed.
    Effort S. Risk: none. Depends on: R1 to R3.
  - ToS check: floor untouched. ZERO-CLICK: runs in the suite.
  - Files likely touched: tests only. Acceptance test: adding a route
    without a table row fails the test; every token route answers 401
    without the token.
- R9 Confine the calc child.
  - Action: (a) start luajit with a short environment (system root,
    temp, the two Lua paths); (b) place it in a job object: kill on
    close, one active process, a memory limit above the 384 MB Lua heap
    ceiling (JOB); (c) once PoB has loaded, bridge.lua drops what the
    calc does not use (os.execute, io.popen, os.remove, os.rename,
    package.loadlib, ffi if unused) and makes io.open read-only.
  - Impact M: turns a PoB parser bug from "runs anything as the player"
    into "can read files"; closes most of F4. Effort M. Risk: PoB may
    need something (c) removes; the live bridge tests decide. Job
    objects nest since Windows 8 (JOB). Depends on: the calc component
    installed for the tests.
  - ToS check: PoB stays an unmodified, hash-pinned subprocess
    (decisions 0004, 0018, 0022); only AshLight's own bridge files
    change. ZERO-CLICK: code change.
  - Files likely touched: server/al/theorycraft/bridge.py,
    server/al/theorycraft/bridge.lua, tests/test_tc_bridge.py.
    Acceptance test: the 17 reference outputs still agree within 0.1
    percent; a test command trying os.execute or a write-mode io.open
    fails inside the bridge; the child's environment holds only the
    allowed names; a second process started by the child is refused.
- R10 A read-only stream key.
  - Action: derive a second credential from the token (an HMAC over a
    fixed label), accept it on GET /events only, and use it instead of
    the token in both EventSource URLs; the overlay preload hands its
    page that key and no token.
  - Impact M: closes F8; nothing in a URL can change state and the
    overlay page loses control rights; the base for any phone view.
    Effort M. Risk: amends the "API token" section of decision 0002
    (`?token=` on /events); the stack decision itself stands. Depends
    on: R3; the Electron side with note 0046.
  - ToS check: floor untouched. ZERO-CLICK: code change.
  - Files likely touched: server/al/http.py, web/app.js, app/preload.js,
    app/main.js, app/overlay/overlay.js, docs/decisions/0002-stack.md,
    tests. Acceptance test: the stream key opens /events and gets 401 on
    every /api route; `?token=` on /events gets 401; the overlay page's
    config object has no token field.
- R11 Ceilings.
  - Action: cap handler threads (64, refuse beyond); give webfetch and
    snapshot a total deadline per request; stream snapshot bodies to
    disk under a per-source cap; make snapshot's URL check equal to
    webfetch's.
  - Impact L: closes F11. Effort S. Risk: low. Depends on: nothing.
  - ToS check: floor untouched; opt-in, User-Agent and host lists do not
    change. ZERO-CLICK: code change.
  - Files likely touched: server/al/http.py, server/al/webfetch.py,
    server/al/theorycraft/snapshot.py, tests. Acceptance test:
    connection 65 is refused while 64 idle ones are open and the
    dashboard loads again once they time out; a fake transport sending
    one byte a second is dropped at the deadline.

## Phone view: what it would need (operator decision, not made here)

Today: bind 127.0.0.1 only, LAN access off (CLAUDE.md), and the footer
promises "This page can't be opened from another device"
(web/index.html:617). Any design that sends data to a phone needs:

1. A read-only credential (R10), never the control token, shown as a QR
   code on the dashboard, revocable, dead at core exit.
2. A phone route set with no POST at all, its own small page and a
   trimmed snapshot (no Client.txt path, no build code; whispers only if
   the operator wants them).
3. Exactly one more configured name in the Host and Origin lists, never
   a wildcard, so the rebinding guard stays.
4. Opt-in per start, a visible "phone view on" mark on dashboard and
   overlay, off again at exit (RES8 asked for this), new footer words.
5. R1, R3 and R11 first: the server would face more than the player's
   own browser.
6. ToS check, all designs: a read-only display of what the dashboard
   shows; nothing is sent to the game and no new source is read, so no
   floor rule is touched.

- Design A, no network path: use the phone or tablet as a wireless
  second display and put the companion window on it. AshLight changes:
  none. Residual risk: only that of the display tool the operator picks
  (which tools do this well: UNVERIFIED).
- Design B, loopback bind kept, operator-run private tunnel with device
  identity and TLS that ends on 127.0.0.1. Example: a tailnet proxy
  forwards a local port to the operator's own devices over HTTPS, the
  service stays on localhost, identity headers are added by the proxy
  and stripped from incoming requests (TS). AshLight changes: items 1 to
  4. Residual risk: the tunnel software and its account join the trust
  base; every device the tunnel admits reaches the phone routes; a proxy
  in front of an HTTP/1.0 stdlib server (PYHTTP) makes request-framing
  bugs matter; the Host value that arrives is not confirmed
  (UNVERIFIED). The bind rule holds to the letter; whether "LAN access
  stays off" allows it is the operator's reading.
- Design C, a second read-only listener on one LAN address (never all
  interfaces), own port in the block, plain HTTP. AshLight changes: the
  most. Residual risk: everything on the LAN can probe a stdlib server
  (PYHTTP); data and the read-only key cross the Wi-Fi in clear, so
  anyone on that network can read zone, level and trade whispers; a
  firewall rule is an operator act; a laptop on a public network exposes
  it unless the listener refuses non-private networks; TLS would need a
  certificate the phone trusts, and a self-signed one trains the player
  to click through warnings. This reverses the bind rule.

Residual risk rises from A to B to C; doing none keeps today's surface.

## Cut or merge

- Cut the two unused null-origin paths (R3). Cut `localhost` from the
  Host and Origin lists, or answer it with a redirect to 127.0.0.1.
- Cut `Authorization: Bearer` unless a script outside the repo uses it
  (Open question 6); it would amend decision 0002's "API token" section.
- Cut the 501 stub POST /api/clipboard-read: no caller; the source scan
  in tests/test_floor_static.py is the better pin of "the core never
  reads the clipboard". Low priority.
- Merge AUDIT-P8-LOW P8-3 and P8-4 into R6's package and the
  token.reuse hardening into R4; put all new security cases in R8's one
  test file.

## Rejected

- Binding the LAN by default, or all interfaces ever: against the bind
  rule; only the operator can change it, and then only as an opt-in.
- A cloud relay for the phone view: it would send log-derived data off
  the PC and add an account, against the local-only promise
  (web/index.html:617) and the "public web data" scope of decision 0013.
- Cookie login for the dashboard: an ambient credential re-opens CSRF;
  the header token is the stronger design.
- TLS on loopback: no gain against T1 or T5, and certificate warnings
  break zero-click.
- Dropping token reuse (decision 0042): its reverse condition, reuse
  "ruled unsafe", is not met once R4 makes the runtime dir private.
- Finding and stopping whatever holds the port: AshLight stops only its
  own processes (decision 0010).
- Proving the listener by a process or handle lookup: R6 proves it with
  the token and looks at no process (well clear of decision 0029).
- Pre-granting the browsers' local-network permission by policy: it
  weakens a protection the player's browser gives, and the same-origin
  dashboard never needs it.

## Open questions

1. OPERATOR DECISION: phone view A, B, C or none.
2. ADJUDICATOR, once the install shape is known (notes 0052 / 0053):
   should hot reload stay on by default in a public git checkout (F12)?
   Decision 0042 says yes for a source checkout and the evidence here
   meets none of its reverse conditions.
3. Does PoB's headless path need LuaJIT ffi or native modules (R9)? Only
   the live bridge tests can tell.
4. Does Windows PowerShell 5.1 skip a system proxy for 127.0.0.1 (R5)?
   UNVERIFIED.
5. With the WebClient service running, does a UNC name also go out over
   HTTP (F1)? Not tested (the service is stopped here); R1 makes it
   moot.
6. Does any script of the operator use the Bearer form?
7. Does replaceState keep the fragment out of a synced browser history
   in `-Browser` mode? UNVERIFIED; low stakes, the token dies with the
   core.
