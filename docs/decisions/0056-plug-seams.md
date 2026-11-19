# 0056 - Plug-in folder for ticks, Checks rows and routes

Date: 2026-11-18. Source: package RUN-SEAMS (wave 5); finding F-090
(docs/plan/02-findings.md), its throttle part C22; decision 0040
(DIAG-SELF, the Checks card); decision 0042 (HOT-RELOAD, the loop's data
ticks); SEC-SURFACE-PIN (the route table in tests/test_security_surface.py).

## Decision

1. Folder. `server/al/plug/` is a package whose modules are found by
   name (`pkgutil.iter_modules` over the package `__path__`; a name
   starting with `_` is skipped), imported once per process and kept in
   (`ORDER`, name) order. Every hook is optional:
   - `ORDER` (number, default 100): the sort key for ticks, facts and rows.
   - `attach(core)`: called once at the tail of `Core.__init__`; a module
     adds a loop tick with `core.add_tick(name, fn)`.
   - `facts(core, now)`: a dict merged into `Core.diag_facts`; a built-in
     key always wins, and an earlier module's key wins over a later one's.
   - `rows(f, now)`: a Checks row, a list of rows or None; rows follow the
     built-in rows in module order. A row with a bad shape or an id
     already taken is dropped; `fix` is kept only on a `fail` row, as for
     the built-ins. `web/checks.js` paints any row, so no web edit.
   - `ROUTES = {(verb, path): fn}`: `fn(req, query, extra)` with `req` the
     `http.Handler`. Only GET or POST, only an exact path under `/api/`
     (no query, no fragment, not `/api/` itself) and only a callable;
     anything else is refused at discovery and logged, never served and
     never listed. Two modules naming one route: the first in order keeps
     it.
2. Tick list. `Core.ticks` holds the loop ticks in the order the old
   `__main__` loop called them (`core.TICK_ORDER`: ensure_tailing,
   tick_build, tick_summary, tick_calc, tick_sources, tick_guide,
   tick_history, tick_watch, tick_diag, tick_reload), then each plug's
   ticks. A built-in tick is looked up by name on every pass, so a
   subclass (demo.DemoCore) or a test override is honoured. A name is in
   the list once. `Core.tick_all(log)` runs one pass; `__main__` calls it
   every 0.5 s in place of the ten try / except blocks. It records
   `loop_at` (monotonic, the pass start) and `tick_ms` (each tick's last
   duration in ms).
3. Throttle (C22). A tick that raises never stops the loop or the ticks
   after it. Its first failure is logged with the traceback; after that
   one line at most every 60 s per tick, with the count of failures since
   the last line and a one-line error summary (`plug.ErrorThrottle`). A
   tick failing on all 600 passes of a 5-minute run writes one traceback
   and four lines, well under 50 KB. A broken plug import, attach, facts
   or rows hook goes through the same throttle and is skipped.
4. Routes and the guard. `do_GET` and `do_POST` end with
   `return self._plug(verb, path, query, extra)`: it runs only after
   `_guard` (Host, Sec-Fetch-Site, Origin, token) and after every built-in
   route, so a built-in route of the same path wins. `plug.route` answers
   only a path under `/api/`, and `Handler._needs_token` covers every
   `/api/` path, so a plug route always needs the token value (the hello
   proof opens no plug route; `?token=` opens none). Reply headers (CSP
   and the rest) come from the same `_send` / `_json`. PUT and every other
   verb keep their 405.
5. Surface pin. `tests/test_security_surface.py` reads
   `plug.all_routes()` next to the ast reading of http.py
   (`served_routes()`), so a plug route without its row in ROUTES fails
   the pin like a built-in one.

## Choices the package text left open (ruled by the builder)

- Discovery is cached per process, not re-scanned. Alternatives: scan on
  every lookup; watch the folder. Why: a new module is a code change, and
  code changes already restart the core (decision 0042), so a rescan buys
  nothing and costs a directory read per request. Reverses if: plug
  modules must load without a restart.
- Handler signature `fn(req, query, extra)`. Alternatives: `fn(core,
  body)` returning a JSON doc. Why: a route needs the handler's own body
  reader and reply helpers (`_read_json` with its caps, `_json`,
  `_send`), which keeps the body caps and headers in one place. Reverses
  if: F-193's route table defines another contract.
- `loop_at` is the pass start. Alternatives: the pass end. Why: a hung
  tick then shows as an ever older `loop_at`, which a later watchdog can
  read. Reverses if: a consumer needs the end time.
- The throttle does not reset after a success. Alternatives: a fresh
  traceback after each recovery. Why: a tick flapping between success and
  failure would otherwise write a traceback every half second, which is
  the flood C22 removes. Reverses if: a recovered-then-new error is
  missed in play because its traceback never shows.
- tests/test_tc_wire.py follows the change (adjudicator ruling, wave 5):
  its source check for the literal `core.tick_calc()` in `__main__` now
  asserts tick_calc sits in Core's tick list in its old place, that
  `tick_all` reaches it, and that the loop calls `core.tick_all`.
  Alternatives: keep a comment naming the old calls; drop the check. Why:
  a literal a comment satisfies pins nothing. Reverses if: another wave-5
  package owns that test file, or tick_all is replaced by another
  dispatch.

## Alternatives

- Keep editing core.py, __main__.py, diag.py and http.py for each new
  tick, row or route: rejected, every later package would collide on the
  same four files (one editor a wave).
- A central registry module each feature appends to: rejected, still one
  shared file per addition.
- Entry points or a config list of module names: rejected, the stdlib-only
  core has no packaging step, and a list is a shared edit again.

## Why

Later packages wire themselves by adding one file, so waves stop
serialising on the shared core files; the security surface stays where it
was because a plug route can only be reached through the existing guard
and only under the token-gated `/api/` prefix. The throttle stops a
repeating tick error from filling core.log. Checked by
tests/test_plug_seams.py, tests/test_security_surface.py,
tests/test_core_crash_log.py, tests/test_http_security.py and
tests/test_diag_self.py.

## Reverses if

The F-193 route table replaces the lookup, discovery fails in the
installed layout, or a plug module is found to bypass the token, Host /
Origin or CSP checks.
