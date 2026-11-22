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

## Amendment 2026-11-20 (TC-CALC-VERIFY-PIN, plan unit F-139)

Pin contents, not bytes. GitHub generates commit archives on request and
does not promise byte-stable zips; a re-generated archive with the same
files would fail the archive SHA-256 and strand the calc. The Reverses-if
on byte stability is prepared for here, not met: no mismatch has been
seen on the current pin.

1. `config/tc_pins.json` gains, per component (pob2, luajit), a
   `content_sha256`: the `tools/tc_pin.py` `tree_digest` form (sorted
   relative path, size and SHA-256 of every file under the pinned top
   dir, the extract marker excluded) and, for PoB, a `lua_sha256`: the
   same digest over its runnable `.lua` files only. Both are required;
   a missing or malformed digest makes setup refuse. The values for the
   current pin were computed on 2026-11-20 from the cached pinned
   archives (their bytes still matched `archive_sha256`), and the
   zip-side digest equalled the digest of the extracted PoB checkout.
2. An archive whose bytes differ from `archive_sha256` (download or
   cache) is accepted only when its contents, read from the zip as data
   under the same member path guard (duplicate member paths refused),
   give the pinned `content_sha256`; the download is cut off at 2x the
   pinned size. Anything else is quarantined and refused as before.
3. Every extract is re-hashed before its marker is written; a tree that
   does not give `content_sha256` is removed and refused.
4. PoB's Lua files are re-hashed against `lua_sha256` on every setup
   re-run, the no-op included; the LuaJIT source tree is re-hashed
   against `content_sha256` right before each build. A mismatch
   re-extracts from the verified archive (no network when the cached
   archive verifies).
5. `tools/tc_drift.py` `candidate()` computes both digests from the
   downloaded candidate archive; a candidate without them does not
   validate, so `apply` cannot move the pin without them.
6. The toolchain (decision 0027) and the Electron zip (decision 0068) are
   GitHub release assets stored as uploaded, so they stay byte-strict
   with no content digest.

Alternatives: a git checkout verified by tree hash (the Reverses-if
route): needs git on the player's machine and a clone of the full
history; held until archives actually drift. Content digest only, no
archive hash: loses the cheap byte check and the record of what was
verified on the pin date. Rejected. Hash only the Lua files: misses
data files PoB reads (fonts, tree JSON). Rejected; the Lua digest is
the extra re-run check, the content digest the acceptance rule.

Reverses if: the content digest accepts a tree that later proves
different from the pinned commit, re-hashing PoB's Lua on each re-run
makes setup measurably slow on the target machine, or GitHub publishes
signed or digest-stable source archives.

## Amendment 2026-11-21 (TC-PIN-POLICY, plan unit F-180)

Pin policy, and the toolchain cleaned up after a verified build.

1. At most one PoB pin move per game patch cycle (the time between two
   game patches), unless a PoB release changes a reference output (a
   number in the decision 0028 reference build checks); then that release
   may move the pin within the same cycle. A move still runs only through
   `tools/tc_drift.py apply` after a live-green trial, committed by a
   session (decision 0025).
2. LuaJIT moves only together with a PoB move: never on its own, only
   when the PoB move needs it or in the same commit. A LuaJIT-only change
   would rebuild `luajit.exe` for every player with no calc gain.
3. After a verified build (`luajit.exe` built and its SHA-256 recorded,
   status `ready`, or a no-op run whose `luajit.exe` still verifies)
   `tools/tc_pin.py` deletes the portable toolchain tree and archive
   (decision 0027 amendment 2026-11-21). A re-run is still a no-op: the
   stamp, the PoB and LuaJIT trees and `luajit.exe` stay, and nothing is
   fetched or built.
4. The update flow re-runs calc setup when the pin digest changed (a new
   release carries a moved pin); that step is built by the REL update
   package, not here.

Alternatives: follow every PoB release (most current numbers, but a
large re-download and rebuild per player each time and more drift risk);
move only on a broken bridge (stale numbers for a whole league); move
LuaJIT on its own schedule (rebuilds with no calc gain). Rejected.

Why: PoB releases several times per patch cycle; one move per cycle
keeps players current for the patch while a reference-output change
still lands at once, and pinning LuaJIT to PoB moves keeps rebuilds rare.

Reverses if: PoB starts fixing calc bugs in releases that leave the
reference outputs unchanged and players miss them, GGG patches become so
frequent that one move per cycle means a move per release, or a LuaJIT
security fix must land without a PoB move.
