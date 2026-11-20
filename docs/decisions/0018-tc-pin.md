# 0018 - TC-PIN: pinned PoB-PoE2 and LuaJIT, license check, opt-in setup

Date: 2026-11-17. Trigger: ROADMAP row TC-PIN (decision 0004 item 3, phase
A setup). This is also the third-party license-check record CLAUDE.md
requires before any third-party code is used. No adjudicator was needed:
every fork follows from decision 0004, CLAUDE.md (sidecar, stack, ToS
floor) and the row's acceptance.

## Verified values (all read 2026-11-17)

- PoB-PoE2 latest release: tag `v0.23.1`, published 2026-07-28, from
  https://api.github.com/repos/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases/latest.
  The tag is lightweight and points at commit
  `7d6f530cbdab20389ff8bc6ba97a37ac27f74e41`
  (https://api.github.com/repos/PathOfBuildingCommunity/PathOfBuilding-PoE2/git/ref/tags/v0.23.1).
- PoB source archive
  https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/archive/7d6f530cbdab20389ff8bc6ba97a37ac27f74e41.zip:
  390011097 bytes, SHA-256
  `67de3bbfe2bdbf43db3e138445e1dce56a58eb4302bac03605b4681ad46b5b9e`,
  identical over two independent downloads.
- LuaJIT has no releases (rolling model; the GitHub releases list is
  empty). Pinned: head of branch `v2.1`, commit
  `63c8f1a9b479ba5518cf6a170ff7729178bc3cfd` (committed
  2026-11-11T08:35:41Z), version `2.1.1794386141` (the archive's `.relver`
  holds `1794386141`, the commit epoch LuaJIT uses as its patch number).
- LuaJIT source archive
  https://github.com/LuaJIT/LuaJIT/archive/63c8f1a9b479ba5518cf6a170ff7729178bc3cfd.zip:
  1246780 bytes, SHA-256
  `9d1f1e5e4c7b91d7a047fb22a6bb0c1b074f6d29e011c7940c5b4000e7391bc1`,
  identical over two independent downloads.
- The archives were downloaded into an empty sidecar Cache dir, hashed and
  listed as data only; nothing from them was executed.

## License check

- PoB-PoE2: MIT, "Copyright (c) 2016 David Gowor", from LICENSE.md at the
  pinned commit
  (https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/7d6f530cbdab20389ff8bc6ba97a37ac27f74e41/LICENSE.md).
  The same file carries notices for the components PoB ships (list in
  THIRD-PARTY.md); they cover PoB's binaries, fonts and bundled Lua
  libraries. Compatible with AshLight's Apache-2.0: we neither copy nor
  modify PoB code, only fetch it on the user's machine and run it as a
  subprocess.
- LuaJIT: MIT, "Copyright (C) 2005-2026 Mike Pall", plus the Lua 5.1/5.2
  MIT notice and the public-domain dlmalloc notice, from COPYRIGHT at the
  pinned commit
  (https://raw.githubusercontent.com/LuaJIT/LuaJIT/63c8f1a9b479ba5518cf6a170ff7729178bc3cfd/COPYRIGHT).
  Compatible on the same terms.
- GitHub's license API reports "Other / NOASSERTION" for both repos (the
  files carry several notices); the texts above were read directly.
- Notices ship in `THIRD-PARTY.md` at the repo root.

## Decision

1. Pin file `config/tc_pins.json` (tracked, ASCII, no absolute paths):
   per component repo, commit, tag (PoB) or version (LuaJIT),
   commit-addressed archive URL, archive SHA-256 and size, top dir,
   license. `tools/tc_pin.py` validates it and REFUSES (exit 2) when any
   value is missing or malformed, including a URL or top dir not bound to
   the commit; it never guesses.
2. Setup step: `scripts/setup.ps1` always calls `tools/tc_pin.py setup`,
   which does nothing unless the user opted in (`-TcCalc` or
   `"tc_calc": true`, a real boolean, in the gitignored
   `config/local.json`). OFF by default. On opt-in it downloads each
   archive from github.com (redirects followed by hand, each hop checked
   against github.com / codeload.github.com with `webfetch.check_url`,
   truthful User-Agent, no cookie, cut off past the pinned size), verifies
   size and SHA-256, and on a mismatch moves the file aside as
   `<name>.rejected` and refuses; setup.ps1 then fails. A cached archive
   that no longer matches is refused the same way.
3. Layout (all via `server/al/paths.py`): `Cache\pob2\` holds the PoB
   archive and its extracted source checkout, `Cache\luajit\` the LuaJIT
   archive, `Build\luajit\` the LuaJIT source tree and `luajit.exe`,
   `Build\tc-pins-stamp.json` the stamp. Extraction refuses any member
   outside the pinned top dir, absolute, drive-qualified, with `..` or a
   symlink, and extracts via a temp dir plus rename.
4. LuaJIT is built from the verified source only when a compiler is on
   PATH (MSVC `cl` via `msvcbuild.bat`, else MinGW `mingw32-make` + `gcc`).
   Without one the step reports `source-only`, exits 0 and the core keeps
   working (the component is optional; TC-BRIDGE treats a missing
   `luajit.exe` as "component absent").
5. Re-run: a stamp with the same pin digest, status `ready`, matching
   extract markers and `luajit.exe` present is a no-op with no network and
   no writes. In `source-only`, trees whose marker matches the pin are
   skipped without network; only the compiler probe repeats.
6. This setup-time fetch is its own explicit opt-in; it is not the app's
   runtime `web_data` setting (decision 0013 governs the running core,
   which still fetches nothing from GitHub).

## Alternatives

- Pin PoB's Portable.zip release asset (GitHub publishes its digest): a
  binary GUI bundle, 383 MB, with prebuilt DLLs; decision 0004 calls for an
  unmodified SOURCE checkout. Rejected.
- Pin by tag URL (`archive/refs/tags/v0.23.1.zip`): a tag can move; the
  commit-addressed URL plus the commit sha in the pin cannot silently
  change. Rejected.
- Accept any local `luajit.exe` the user provides: not hash-pinnable, since
  builds are not byte-reproducible. Deferred: a pinned prebuilt binary can
  be added if a trustworthy, hashed upstream build appears.
- Download unconditionally during setup: breaks "off by default" and would
  pull 390 MB for users who never use theorycraft. Rejected.
- Re-download silently on a cache mismatch: hides tampering. Rejected:
  refuse once, quarantine, next run fetches afresh.

## Why

The phase A calc component needs PoB's Lua sources and a LuaJIT
interpreter. Pinning both by commit and SHA-256 makes the fetch
reproducible and tamper-evident, keeps everything in the sidecar, adds no
dependency to the core and changes nothing on the ToS floor (no game
process or file contact; the inputs stay user-pasted build text and
hotkey-read item text).

## Reverses if

- GitHub stops serving byte-stable commit archives (a hash mismatch on an
  unchanged pin): switch to a git checkout at the pinned commit verified by
  tree hash.
- PoB or LuaJIT changes license away from MIT / permissive.
- LuaJIT starts publishing hashed release binaries: pin one and drop the
  local build.
- The pin moves: only by a commit with the bridge tests green (decision
  0004 item 3), re-recording the values above.

## Amendment 2026-11-19 (DEP-16, decision 0065)

Item 6 wording: "which still fetches nothing from GitHub" now reads
"which fetches no component from GitHub". The running core makes one
GitHub read: the daily `releases/latest` check of the project's own
repository (decision 0065), inside the web-data opt-in and only after
the player has acknowledged the wording that names it. That read never
downloads PoB, LuaJIT or any runtime; component and runtime fetches stay
in setup and in the installer's own process (plan 05 design point 13).
