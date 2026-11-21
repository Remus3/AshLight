# 0022 - TC-BRIDGE: own stdio JSON bridge to the pinned PoB-PoE2 checkout

Date: 2026-11-17. Trigger: ROADMAP row TC-BRIDGE (decision 0004 item 3,
after TC-PIN / decision 0018). Adjudicated by the build lane itself, as the
row brief requires; no operator act was waited on.

## Decision

1. `server/al/theorycraft/bridge.lua` is AshLight's own Lua, written from
   scratch (no code from pob-mcp, pob2-mcp or any other bridge). It runs
   under the pinned `luajit.exe` with the pinned checkout's `src/` as its
   working directory and loads PoB through PoB's own, unmodified
   `src/HeadlessWrapper.lua`. Nothing in the checkout is edited.
2. Protocol: one JSON request per stdin line; one reply per request on
   stdout as `ALB1 <json>`. The prefix lets the client ignore anything PoB
   prints; the script also routes `print` to stderr, which the client
   appends to `<sidecar>\Logs\tc-bridge.log`. Commands: `ping`,
   `load_build {xml}`, `set_item {text, slot?}`, `outputs {keys?}`
   (PoB's `calcsTab.mainOutput`, numbers and booleans only), `quit`. The
   script's own minimal JSON codec avoids depending on a JSON library being
   present in PoB's runtime.
3. Client `server/al/theorycraft/bridge.py` (stdlib only): starts the
   process on the first call (ZERO-CLICK), kills it when a call runs past
   its timeout (`BridgeTimeout`; the next call starts a fresh one),
   restarts it once after a crash and replays the last build and its
   equipped items before retrying the call. `available()` / `status()`
   report the component; when it is absent every call raises
   `BridgeUnavailable` without spawning anything. The core imports nothing
   from it (a test enforces this), so it runs unchanged without the
   component. `shared()` gives callers (TC-DELTA) one lazy, lock-guarded
   instance.
4. Paths come from `server/al/paths.py` with the same layout as
   `tools/tc_pin.py` (a test pins the equality); TEMP / TMP for the child
   point at the sidecar `Temp\`.
5. Missing native module: when `require("lua-utf8")` fails under a plain
   luajit.exe, the script installs a string-library fallback so PoB can
   load; PoB's own module wins when present.

## Deviation from the row's ACCEPT

ACCEPT says "outputs on a fixture build match PoB GUI within 0.1 percent".
On this machine the component is absent: TC-PIN recorded "source-only"
(no C compiler, so no `luajit.exe`), and no PoB GUI is installed to read
reference numbers from. So:

- The 0.1 percent check is written (`tests/test_tc_bridge.py::
  test_live_outputs_match_pob_gui_within_0_1_percent`, `rel=1e-3`) and
  reads GUI reference values from `tests/fixtures/tc_bridge/
  gui_expected.json` or the gitignored `ops/runtime/tc_bridge/`; it SKIPS
  until both the component and a reference file exist. A live smoke test
  (load a minimal build, read numeric outputs) skips the same way.
- Every non-live behaviour (protocol, noise filtering, timeout kill, crash
  restart with replay, absent component, lazy start) is tested against a
  Python fake of the Lua side (`tests/fixtures/tc_bridge/fake_bridge.py`).
- The PoB internals the script calls (`loadBuildFromXML`,
  `mainObject.main.modes.BUILD`, `new("Item", text)`, `itemsTab:AddItem`,
  `slots[...]:SetSelItemId`, `calcsTab.mainOutput`) come from PoB's
  HeadlessWrapper / Items tab conventions and are UNVERIFIED against
  v0.23.1 here; the first run with the component is the check, and
  TC-DRIFT re-runs it on every PoB release.
- The row stays verifiable later with zero code change: once a compiler or
  a pinned LuaJIT binary exists and a GUI reference file is recorded, the
  skipped tests run.

## Alternatives

- Reuse an existing PoB MCP / bridge server: the row forbids it, and their
  licenses and code were not checked. Rejected.
- Patch PoB (e.g. add a JSON endpoint inside the checkout): breaks the
  "unmodified, hash-pinned" rule of decisions 0004 and 0018. Rejected.
- Load PoB per request (no long-lived process): PoB start-up takes seconds;
  TC-DELTA needs many evaluations per item. Rejected.
- Fail the row until a compiler is installed: the row's own ACCEPT also
  asks that tests skip cleanly when the component is absent, and every
  part that can be tested here is. Rejected; deviation recorded above.
- Restart forever on repeated crashes: a build that crashes PoB would spin.
  Rejected: one restart per call, then `BridgeError`.

## Why

It is the smallest piece that lets TC-DELTA ask PoB for real numbers while
keeping PoB unmodified, the core stdlib-only and independent of the
optional component, and the ToS floor untouched (inputs stay user-pasted
build XML and hotkey-read item text; nothing reaches the game).

## Reverses if

- PoB-PoE2 drops or reshapes `HeadlessWrapper.lua` or the internals above
  so the bridge breaks every release (then decision 0004's own reversal
  applies), or PoB ships an official headless API (use it instead).
- The live 0.1 percent test, once it can run, fails for a reason the
  script cannot fix without modifying PoB.
- The stdio prefix framing proves unreliable (PoB writing partial lines to
  stdout): move PoB output off stdout entirely or use a separate pipe.

## Amendment 2026-11-17 (AUDIT-BRIDGE-LOW, audit Pass 2 P2-B3)

- What the luajit.exe hash check guards: exepin writes the SHA-256 record
  (`luajit.exe.sha256`) beside the exe in the user-writable AL sidecar
  (`Build\`). Anyone who can replace the exe can rewrite the record, so the
  check stops a stale, half-built or foreign exe (a planted file, a
  different build left over in the folder) from being run; it is NOT
  tamper protection against a local process running as the same user.
  That attacker already runs code as the user, so a record elsewhere in a
  user-writable place (the repo's `ops/runtime/`) would add no real bar.
- Alternatives: keep the record in the repo runtime (same user, same bar;
  it would also need tools/tc_pin.py and setup changes the TC-LIVE lane
  owns); pin a hash in config/tc_pins.json (impossible: the exe is built
  locally, so no hash exists before the build; decision 0018). Rejected.
- Reverses if: a pinned LuaJIT release binary with a published hash
  becomes available (then pin it in config/tc_pins.json and verify against
  that, decision 0018's own reversal).

## Amendment 2026-11-19 (TC-CALC-CONFINE-PROC, F-138)

- Decision: every bridge start is confined in `Bridge._start`. The child
  gets only the allow-listed environment names `ENV_ALLOW` (SYSTEMROOT,
  WINDIR, TEMP, TMP, LUA_PATH, LUA_CPATH; matched case-insensitively, the
  component path builds its env from the same list), so LUA_INIT, the
  user's PATH and every other inherited name never reach luajit or PoB
  (PoB reads `CI` and `REGENERATE_MOD_CACHE`; both are now unset). On
  Windows the child starts with CREATE_SUSPENDED, is assigned to its own
  job object through stdlib ctypes (OpenProcess, AssignProcessToJobObject)
  and only then resumed (its thread found by a Toolhelp32 snapshot). The
  job sets kill on job close, an active process limit of 1 and a
  per-process memory limit of 1536 MB (`JOB_MEMORY_LIMIT`). `_stop` /
  `close` close the job handle after the process is reaped; a core that
  dies closes it too, so no luajit outlives the core. Job objects nest
  since Windows 8, so a core that already runs inside a job still works.
  A start whose job cannot be created or assigned kills the child and
  raises `BridgeUnavailable` (fail closed: no unconfined calc runs).
  Elsewhere than Windows no job is made (the env allow-list still holds).
- Alternatives: assign the job after a normal start (the child could
  start a process before the assignment); resume with the undocumented
  NtResumeProcess (one call, but not a documented API); keep the full
  environment and drop only LUA_INIT (a deny-list misses names added
  later); a memory limit at the 384 MB heap ceiling or the 768 MB budget
  (decision 0028 measured a 511 MB peak working set with the ceiling and
  ~900 MB without it, and committed memory runs above the working set, so
  either would kill normal calcs); run unconfined when the job fails
  (silent loss of the guard). Rejected.
- Why: PoB is third-party Lua fed with player text; the job bounds what a
  bug or a hostile build could do (no second process, bounded memory, no
  orphan after a core crash) at no runtime cost, and the allow-list keeps
  the child's behaviour independent of the user's shell environment.
- Tests: tests/test_tc_bridge.py (env names, a fake child refused a second
  process with ERROR_NOT_ENOUGH_QUOTA, kill on job close, confinement
  failure refuses the start); the live calc tests pass under the job.
- Reverses if: PoB-PoE2 needs another environment name or a helper
  process, a real build needs more than the memory limit, or job objects
  are refused in a supported install layout (then a Checks note and a
  per-user opt-out, never a silent unconfined start).

## Amendment 2026-11-20 (TC-CALC-VERIFY-USE, F-139)

- Decision: before every bridge start (the first and every restart after
  a crash or a time-out) `Bridge._start` re-checks PoB's runnable Lua
  files against the pinned `lua_sha256` of config/tc_pins.json (decision
  0018 amendment 2026-11-20). The digest is computed in bridge.py in the
  exact form of tools/tc_pin.py `tree_digest(select=is_lua)` (every `.lua`
  file under the checkout's top folder: sorted relative path, size and
  SHA-256), so the core imports nothing from tools/. A mismatch, an added
  or a removed Lua file raises `BridgeUnavailable("calc component changed,
  re-run setup")` before any process starts. A digest that matched is
  cached in memory with every Lua file's size and mtime: while those are
  unchanged the files are only stat-ed (about 1100 files, a few ms), and a
  mismatch is never cached. `status()` reports a mismatch as the missing
  part `pob-lua` (a pin file without a well-formed digest as `pins`, fail
  closed), so the Checks calc row reads "Missing or changed: pob-lua."
  with its existing fix line (run scripts\setup.ps1 -TcCalc).
  `from_component` refuses only the absent parts (luajit, pob, script,
  pins) and leaves the Lua check to the start, so the shared instance
  stays lazy and the refusal carries the fix words.
- Package loader guard (bridge.lua): before PoB loads, the native (C)
  loaders of `require` (package.loaders 3 and up) are wrapped to answer
  only for the allow-listed `lua-utf8` (PoB's one native module on the
  headless path; HeadlessWrapper already stubs lcurl) and, from the
  lockdown on, for nothing; any other native module fails with "refused by
  the AshLight calc bridge". The test-only probe tries two DLLs that sit
  in PoB's runtime (socket, lzip).
- Alternatives: check the digest in `from_component` only (a checkout
  edited while the core runs would be used by the next restart); hash
  every start without a cache (about 0.5 s cold on the dev host each
  start); persist the verified stat record in the sidecar (same-user
  writable, so no stronger than the in-memory cache, and needs a new path
  in paths.py); allow-list by file path instead of module name (PoB names
  modules, not files); clear package.cpath only (a module loaded before
  the lockdown, or a Croot loader hit, could still pull a DLL). Rejected.
- Why: the pin proved the archive at setup, but nothing proved the files
  the calc then runs; a stale extract, a partial update or a stray edit
  of PoB's Lua now stops the calc with one fix instead of feeding item
  checks numbers from unpinned code. The cache keeps the warm cost to a
  stat walk.
- Tests: tests/test_tc_bridge.py (an edited or added Lua file makes the
  component unavailable and the start refuses with the fix words, no
  spawn; the digest equals tc_pin's form; the cache re-hashes only on a
  size or mtime change; the loader guard sits before the PoB load; live:
  the probe's native requires fail inside the running bridge).
- Reverses if: PoB's headless path needs another native module, PoB
  starts generating Lua files at run time inside its checkout, or a pin
  move ships Lua outside the pinned digest's form.
