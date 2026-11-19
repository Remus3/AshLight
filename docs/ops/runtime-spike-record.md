# Runtime spike record (DEP-01, F-038)

Date: 2026-11-19. Package: DEP-01 (plan 05, Design points 4 and 6).
Verdict: PASS. The private-runtime design holds: the embeddable CPython
and the unmodified Electron zip run AshLight with no Python and no Node on
PATH. Both launch forms work; the boot shim (`boot.py`) is the one
recorded, with the re-spawn sites listed below moving to it in DEP-06.

## Setup

- Work folder: `<sidecar>\Scratch\dep-spike\` only.
- `python-3.14.10-embed-amd64.zip`: fetched from www.python.org with the
  AshLight User-Agent (`AshLight/0.1.0 (local Path of Exile 2 companion;
  dev: runtime spike download)`), no cookie. Read back: 12,619,664 bytes,
  SHA-256 90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159,
  both equal to plan 05 Design point 4. Reports 3.14.10.
- `electron-v45.3.3-win32-x64.zip`: the copy F-044 had already fetched
  into the sidecar Cache was used (no second download). Read back:
  158,325,836 bytes, SHA-256
  49dd2d3875944f08de03d34595cd30093c588b9edcabb41a0ac481028a3a5a8a, both
  equal to the pin.
- Tree: `git archive` of main at b6ab91e unpacked to `dep-spike\tree`.
- Environment of every check: PATH = the Windows folders only (plus the
  Windows PowerShell 5.1 folder for the script tests); no python, py or
  node resolvable. `AL_SIDECAR_ROOT` = a scratch sidecar, except the calc
  check, which reads the installed calc component in the AL sidecar.
- pytest and its five dependencies: placed by the system pip with
  `--target dep-spike\site --require-hashes -r requirements-dev.txt`
  (the repo's hash pins), and named in the scratch `._pth`.
- Every child ran with no window and below-normal priority. Demo cores
  only, one at a time, on the demo block (they picked 8970); never 8960,
  8961 or the live Client.txt. No process was left running.

Two runtime folders were made from the one zip:

- pth variant: `python314._pth` = `python314.zip`, `.`, the tree, the
  site folder.
- boot variant: `python314._pth` = `python314.zip`, `.`, the site folder
  (the site line is dev-only; an installed runtime keeps the stock
  file). The tree is found only through `boot.py` at the tree root: it
  puts its own folder first on sys.path and runs the named module with
  `runpy.run_module(..., run_name="__main__", alter_sys=True)`.

Observed: with any `._pth` present the interpreter runs isolated
(`sys.flags.isolated` 1, `safe_path` True): neither the current
directory nor the script folder nor PYTHON* variables reach sys.path.
So `-m server.al` from the checkout as cwd fails under the boot variant
(`No module named 'server'`), as plan 05 Design point 6 predicted.

## Checks

- Demo core `/api/health` on a port in 8970-8975: PASS (both variants).
  `python -m server.al --demo tests\fixtures\demo` (pth) and
  `python boot.py server.al --demo ...` (boot) printed the URL line;
  `/api/health` with the token answered 200 on port 8970.
- One supervisor restart: PASS (both variants). keepalive.Keepalive with
  its real `_Launcher` and `core_command` adopted the demo core's
  runtime; the core was killed; the supervisor logged "no core running;
  restart 1/5" and "core launched"; the relaunched core (pythonw.exe of
  the embeddable runtime) answered `/api/health` 200 on the same port.
  Under the boot variant the relaunch command had to be the boot form
  (see re-spawn sites). Note: a supervised demo core makes a new scratch
  folder per start, so the supervisor cannot follow it across restarts
  by itself; the spike pointed it at the first core's runtime. This is a
  demo-mode property, not a runtime finding.
- One calc on the reference build (calc installed): PASS. Bridge status
  available; pobb.in Nqt6FK5lIc6F loaded in 2.0 s; TotalDPS 27729.38,
  Life 1887, TotalEHP 32072.01 against the GUI reference 27729.4, 1887,
  32072. The bridge is a luajit child, so the Python runtime only spawns
  it.
- The five tests under the embeddable python:
  - pth variant, tree unchanged: PASS. tests/test_sidecar_paths.py,
    tests/test_keepalive.py, tests/test_procs.py, tests/test_jsonfile.py,
    tests/test_http_security.py plus tests/test_test_layout.py: 104
    passed, 1 skipped.
  - boot variant, tree unchanged: FAIL as expected, 103 passed, 2 failed
    (test_keepalive::test_end_to_end_real_core_restart_and_user_stop,
    test_procs::test_stop_script_leaves_no_ashlight_process: "core
    never wrote a heartbeat", because the supervisor and core are
    spawned with `-m`).
  - boot variant, re-spawn sites switched to `boot.py` (scratch copy
    only): PASS, 104 passed, 1 skipped.
  - The one skip in both passing runs is
    test_procs::test_stop_script_leaves_no_ashlight_process at its fake
    Electron helper ("renamed interpreter does not start here"): the
    helper copies python.exe and its DLLs as a fake electron.exe, and
    the embeddable python.exe does not start without its stdlib zip
    beside it. A test-fixture limit, not an AshLight fault; the stop
    path itself is covered under "re-spawn sites" (stop.ps1).
- Boot shim versus `._pth`: both tried, both PASS. Recorded: `boot.py`.
  See the ruling below.
- Electron zip version without Node: PASS. The unpacked folder's
  `version` file reads 45.3.3, `electron.exe --version` prints v45.3.3
  (no window), and the exe's file ProductVersion is 45.3.3.

## Re-spawn sites that need a change

Under `._pth` (tree named in the runtime file) none needed a change for
the checks above. Under `boot.py`, and in both variants wherever a
script finds Python by name on PATH, these sites change (DEP-06's one
command builder `paths.python_cmd` and its PowerShell twin):

1. server/al/keepalive.py `core_command`: `[exe, "-m", "server.al", ...]`
   (changed in the scratch copy; proven by the restart check and the
   tests).
2. server/al/keepalive.py `run_preflight`: `[exe, "-m", "server.al",
   "--check"]` (changed in the scratch copy).
3. scripts/run.ps1: bare-name python lookup; `-m server.al.paths`,
   `-m server.al.procs plan`, `-m server.al` (core),
   `-m server.al.keepalive` (supervisor), `-m server.al.procs
   record-overlay`.
4. scripts/stop.ps1: `Get-AlPython` throws "Python 3.11 or newer was not
   found on PATH." with no python on PATH (read back in the spike); then
   `-m server.al.paths` and `-m server.al.procs status / stop`.
5. app/client/launcher.js: bare-name `python` / `py` lookup for
   `-m server.al.paths`, then a hidden `scripts\run.ps1 -NoBrowser`.
6. scripts/autostart.ps1: bare-name lookup, `-m server.al.paths`.
7. Test sites (switched in the scratch copy): tests/test_keepalive.py
   and tests/test_procs.py spawn `[sys.executable, "-m",
   "server.al.keepalive", ...]`.

Checkout-only, not on the installed path (no change needed for the
runtime design): scripts/setup.ps1 and scripts/build.ps1 (`-m` with the
system Python), tools/al_loop.py and tools/loop_task.py (pythonw beside
sys.executable), tools/tc_drift.py and tools/state_equiv.py.

## Ruling (boot shim versus ._pth)

- Decision: `boot.py` at the payload root, one command builder returning
  `<python> <app>\boot.py <module> ...` in installed mode and today's
  `-m` form in a checkout; the runtime's `._pth` stays the publisher's
  file.
- Alternatives: the `._pth` variant (one line naming the app folder; it
  passed with no code change); a `-c` bootstrap per spawn.
- Why: the `._pth` names one app version inside a runtime shared by
  versions, so version N+1 cannot self-test while N runs without
  rewriting the runtime or a `-c` path; `boot.py` keeps the runtime
  byte-identical to the pinned zip and lets each version start itself.
  Both passed every check, so the cheaper-to-ship option is not needed.
- Reverses if: a `boot.py` start breaks a module that relies on `-m`
  semantics (`__spec__`, relative imports at top level), or DEP-06 finds
  a re-spawn site that cannot take the builder; then the `._pth` line
  plus a `-c` self-test (plan 05 Design point 6 fallback).

No fallback to the player's own Python is needed (plan 05 Order); Q-20
stands.
