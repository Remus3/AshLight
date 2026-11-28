# 0064 - Release artifact and tool

Date: 2026-11-19. Source: docs/plan/05-deployment.md (decision D3,
section "Release procedure", "What `release.py build` writes"), research
0053 (F7, F16), finding F-048, ruling Q-22, package DEP-08; adjudicator
LE-53 (close-out 2026-11-18); ruling Q-20 (no bundled runtimes).

## Decision

1. A release is a fixed file set built from one git ref: the app zip
   `AshLight-<ver>-app.zip`, `install.ps1` (the bootstrap with the
   version stamped in), `release.json`, `SHA256SUMS.txt`,
   `AshLight-<ver>-notes.md` and an SBOM. No installer framework, no
   packaged .exe, no signing at first (decision 0041 point 9 stands). No
   Electron, CPython, game data, PoB source or LuaJIT is in any artifact
   (decisions 0009, 0018; Q-20: the offline full zip of F-048 is not
   built; the offline route is `install.ps1 -Zip ... -RuntimeDir ...`).
2. One command builds it: `python tools/release.py build [--ref REF |
   --tag vX.Y.Z] [--out DIR]` (module tools/rel_build.py, loaded by the
   DEP-03 dispatcher). Default output: `<sidecar>/Build/release/<ver>/`.
   It never uploads, tags, commits or pushes and makes no network call.
   DEP-08 writes the app zip and SHA256SUMS.txt; REL-BUILD-ASSETS adds
   the other assets through one call at the end of `build()`.
3. The app zip: one top folder `AshLight-<ver>/`; entries are the ship
   list over `git ls-tree -r` at the ref, bytes read from git blobs
   (`git cat-file --batch`), never from the working copy; sorted by
   path; every time field is the ref's commit time (UTC); fixed entry
   metadata (create system 0, external attributes 0). Two files are
   generated inside: `BUILD`, one JSON line `{"commit": <12 hex>,
   "created": "<YYYY-MM-DDTHH:MM:SSZ>", "version": <VERSION>}` (the
   build-stamp reader of F-027 reads it), and `MANIFEST.json`
   `{"commit", "files": {path: {"sha256", "size"}}, "schema": 1,
   "version"}` listing every entry but itself. Entries are deflated at
   level 9: the payload is about 1.9 MB raw and the zip has a 2,000,000
   byte budget, so a stored zip does not fit.
4. The ship list is tracked config/ship_list.json, read at the ref: an
   allow-list of path patterns (`*` inside one segment, `**` across
   segments) plus excludes, so a later package that adds files under
   server/, web/, app/, scripts/ or config/ never edits it. It ships
   server/, web/, app/ without app/test/, scripts/*.ps1 and *.vbs,
   config/*.json without *.example.json and the ship list itself,
   tools/tc_pin.py, ops/fleet_kit/tokens.css and the kit LICENSE and
   NOTICE, boot.py, README.md, CHANGELOG.md, LICENSE, NOTICE and
   THIRD-PARTY.md. Not shipped: tests/, docs/, other tools, ops/loop,
   .claude, .githooks, .github, the hand-off, ROADMAP.md, CLAUDE.md.
5. Refusals, each before anything is written (the output folder is not
   even created): a dirty tree (tracked changes or untracked files);
   `--tag` naming a tag that is missing or is not `v` + VERSION at its
   commit; a VERSION that is not SemVer; a missing or malformed ship
   list at the ref; a shipped path that is unsafe (not plain ASCII
   segments, `..`, a drive, a backslash, a Windows reserved name, a
   trailing dot), not a plain file blob (symlink, submodule), or named
   like a generated file; a shipped path matching a `cache_deny` pattern
   (cache-shaped folders and archive or binary suffixes); a shipped file
   of 256 bytes or more whose bytes equal a file under the sidecar Cache
   (a local read; skipped when the folder is absent, as on CI); a zip
   over the budget. The leak sweep and the poe.ninja release-switch
   refusals of the staged tree come with REL-BUILD-ASSETS.
6. Tags (LE-53): the "final version without a tag" refusal of plan 05
   applies to `build --tag` only. `--ref` builds any version, tagged or
   not, and no artifact records the tag (BUILD, MANIFEST.json and
   release.json hold no tag field). The release procedure stages with
   `--ref` before the tag exists; the tag binds the staged SHA256SUMS at
   publish; CI rebuilds with `--tag` and must match byte for byte, which
   holds because a `--ref` build and a `--tag` build of one commit are
   identical.
7. Checks for the installer: `verify_tree(dir)` reports a changed,
   missing or unlisted file and an unsafe listed path of a laid-out
   version folder against its MANIFEST.json; `verify_zip(zip)` does the
   same for the zip and also refuses unsafe or duplicate member names and
   more than one top folder.
8. Reproducible: nothing reads the clock, the host name or a random
   source. tests/test_release_tool.py builds twice with those patched to
   differ and compares the bytes.

## Alternatives

- An installer framework (MSI, Inno Setup, NSIS) or a packaged .exe.
  Rejected (plan 05 D3, 0053): build dependencies and signing friction
  for no gain over a zip plus a stdlib bootstrap.
- Code signing now. Deferred: no signing identity yet (Q-22).
- A deny-list of paths. Rejected: a new dev file would ship by default;
  the allow-list fails safe.
- Reading the working copy. Rejected: a build must equal the ref's
  blobs, or CI's rebuild could never match.
- A stored (uncompressed) zip, the 0053 F16 fallback for deflate drift
  between Python builds. Not taken: it breaks the 2 MB budget today.
  The ship list's `compression` field switches it in one data edit; CI
  builds with the builder's exact Python version so its zlib matches.
- The tag check for every final version (plan 05 as first written).
  Rejected by LE-53: `stage` must build the final version before the tag
  exists.
- The offline full zip with CPython and Electron (F-048). Rejected by
  Q-20: never bundled.

## Why

A zip from git blobs with fixed metadata is the smallest artifact that
an operator can rebuild and compare byte for byte, that CI can attest,
and that a stdlib installer can verify file by file. The allow-list and
the refusals keep dev files, secrets and cache data (game data, PoB,
LuaJIT, Electron) out of every release.

## Reverses if

The operator gets a signing identity, or SmartScreen friction measurably
blocks installs (then a signed artifact replaces the plain zip route).
The deflate choice reverses to stored if a CI `--tag` rebuild with the
pinned Python differs from the staged zip and the payload fits the
budget stored. The tag rule reverses if the operator wants final
versions buildable only from a tag (then `stage` builds with a pre-tag
flag).

## Amendment 2026-11-28 (REL-BUILD-PYTHON-PIN)

Cause: the v0.2.0-rc.1 tag (commit 962437ec) failed CI's release run at
"compare SHA256SUMS.txt with the tag message sums-sha256" (tag 1fd13235...,
rebuild 361218b4...). The local stage ran on the dev host's default CPython
3.14.4, whose zlib is zlib-ng (`zlib.ZLIB_RUNTIME_VERSION` 1.3.1.zlib-ng);
CI rebuilt on CPython 3.11.9 with stock zlib 1.3.1, so the app zip's deflate
bytes differed. A local build of the tag on 3.11.9 reproduces CI's sums.
The tag stays as it is (a tag is never moved or deleted); 0.2.0-rc.2 is the
next candidate.

Decision: the release build is pinned to one exact CPython version, the
`python-version:` of .github/workflows/release.yml (the one source;
rel_build.pinned_python() reads it, tests/test_release_tool.py asserts the
two agree and tests/test_workflows.py keeps it one exact X.Y.Z).
`release.py build` on another interpreter re-runs itself under the
matching `py -X.Y` launcher entry when that entry reports exactly the pin,
else refuses naming both versions. `release.py stage` keeps its suite and
node steps on the dev interpreter and runs its two builds (and the round
trip's N-1 build) on the pin: in process when it is the pin, else as a
`release.py build` child under `py -X.Y`, else the builds step fails with
the named refusal. stage.json records `build_python`; publish and the
pre-push tag check refuse a stage report whose `build_python` is not the
pin. build() itself carries no guard (tests call it in process), and
AL_REL_ANY_PYTHON=1 lifts the command-line guard only inside a pytest run.

Alternatives:
- Stored (uncompressed) entries: refused again; the zip would pass the
  2 MB max_zip_bytes budget (above), and a format change to dodge a
  toolchain pin hides the real dependency.
- A pure-Python deflate in the tool: byte-stable by construction but a
  large, slow, new piece of code to own; rejected.
- Pinning on zlib.ZLIB_RUNTIME_VERSION instead of the Python version:
  narrower, but zipfile's own header and deflate call paths also move
  between Python versions; the exact interpreter that CI uses is the
  whole toolchain and is what release.yml already states.
- Re-running the whole stage under 3.11.9: the dev host's 3.11 has no
  pytest, and the suite's interpreter is not what the sums depend on.

Why: CI's rebuild is the release's trust anchor; a local stage that
cannot match it can never publish. One pinned interpreter, read from the
workflow, makes a mismatch a named refusal before the tag instead of a
red release run after it.

Reverses if: CI moves to another interpreter (the pin follows release.yml
by itself), a pure-stdlib deflate becomes byte-stable across CPython
versions (then drop the pin), or the dev host cannot keep a `py -X.Y`
entry of the pin (then stage on a CI-built artifact).
