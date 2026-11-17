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
