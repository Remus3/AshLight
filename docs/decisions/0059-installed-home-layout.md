# 0059 - Installed-mode home and layout

Date: 2026-11-19. Source: package DEP-05 (wave 7); finding F-049
(docs/plan/02-findings.md); docs/plan/05-deployment.md "Design" items 2
and 3 and "Installed-mode layout" (plan 05 D1); ruling Q-19 (decision
0078); the port table of server/al/ports.py (SEC-DEMO-CORE). Builds on
DEP-02 (the kit default counts only while its folder exists) and
RUN-DURABLE-JSONFILE (the hardened JSON reader, F-014).

## Decision

1. One resolver, two modes. server/al/paths.py stays the one path
   resolver. `paths.install_mode()` is "installed" when the env variable
   `AL_HOME` is set or the marker `install.json` lies two levels above
   the payload root (`<home>/app/<version>/`), else "checkout". In a
   checkout nothing changes.
2. The home. A player install lives in a per-user home, by default
   `%LOCALAPPDATA%\Programs\AshLight` (`paths.default_home()`); the
   installer's `-InstallDir` or `AL_HOME` moves it. On this machine the
   installed copy uses `-InstallDir` under the AL sidecar (`Install\`).
   Code sits in `<home>\app\<version>\` plus the marker
   `<home>\install.json`.
3. All player state in `<home>\data\`. In an install `runtime_dir()` is
   `<home>\data` (consent, token, pid, run history, settings) and
   `local_config_file()` is `<home>\data\local.json`, so every version
   folder reads the same consent file and settings. The sidecar folders
   become `<home>\cache`, `logs`, `temp` and `build` (`sidecar_root()` is
   the home); Worktree, Scratch and ClaudeHistory do not exist
   (`sidecar_dir` raises ValueError for them, `worktree_dir()` is None,
   `all_runtime_paths()` leaves them out and adds `home`, `marker` and
   `local_config`). `ensure_dirs()` makes data, cache, logs and temp;
   build only exists once the optional calc component is set up.
4. Path-shape refusal. `paths.install_home()` raises `HomeRefused` for a
   home whose path text has a `steamapps` or `Path of Exile 2` component
   (case-insensitive, Windows' ignored trailing dots and spaces
   stripped). The check is text only: no registry read, no library file,
   no listing or stat of any folder (floor audit on F-049). The core's
   `main()` checks it first and exits 2 with a one-line reason before
   anything is made or logged.
5. Electron. In an install `procs.electron_dir()` is
   `<home>\runtime\<marker "electron">`, the pinned runtime folder (amends
   decision 0010's proven-ours folder for installs); a marker without a
   plain folder name turns the overlay scan off.
6. Reporting. The core's first log line names the mode and the marker's
   previous version; `/api/health` and `/api/version` carry `mode` and
   `previous` (null in a checkout).
7. Ports: nothing new. `AL_DEV_PORT` (8961) and `SELFTEST_PORTS`
   (8970-8975, the same block as `DEMO_BLOCK`) are the constants of the
   one port table SEC-DEMO-CORE defined; DEP-05 uses them and redefines
   nothing.

## Choices the package text left open (ruled by the builder)

- An explicit `AL_SIDECAR_ROOT` wins in an install too and keeps the
  sidecar layout (`<root>\Cache` and so on). Why: a demo core (decision
  0049) points its scratch there, and the install self-test runs a demo
  core from the new version folder; ignoring the variable would put demo
  caches and logs into the player's home. Likewise `AL_RUNTIME_DIR` still
  wins over `<home>\data` (tests, demo).
- The marker counts only when the payload's parent folder is named
  `app` (`<home>\app\<version>\`). Why: a stricter reading of "two levels
  above the payload root"; a checkout that happens to sit two levels
  under an unrelated `install.json` stays a checkout.
- The marker is read with `jsonfile.read_json(..., backup=True)` (64 KB
  cap, dict only), so a torn marker is restored from its one `.bak`.
- Marker presence is cached per payload root (one stat per process); a
  payload folder never moves.
- `AL_HOME` is made absolute with `os.path.abspath`, never `resolve()`,
  so the text check runs before any file system access.

## Alternatives

- Keep player state inside the version folder: an update would lose or
  have to copy consent and settings, and a rollback would split them.
- Refuse a game folder by looking for the game (registry, Steam's
  libraryfolders.vdf, a listing): rejected by the floor audit on F-049.
- A second resolver module for installs: two sources of truth for paths,
  against the one-resolver rule of CLAUDE.md "Sidecar".
- Mode from a command-line flag: the launcher would have to pass it on
  every start path (core, supervisor, stop); the marker is found alone.

## Why

ZERO-CLICK: the mode is resolved from the marker by itself; nothing to
set, and a checkout behaves as before. One shared `data\` folder is what
makes build-beside updates and rollback safe (plan 05 Design item 3).

## Reverses if

The installed copy cannot serve daily dev use, or the AL_HOME / sidecar
override breaks the sidecar path test (tests/test_sidecar_paths.py).
