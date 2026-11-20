# 0063 - Installed-copy runtimes and launch

Date: 2026-11-19. Source: docs/plan/05-deployment.md (Design points 4, 6
and 13, decision D2), ruling Q-20, findings F-047 and F-038, packages
DEP-06 and REL-RUNTIME-PINS (split out of DEP-06); the runtime spike
record docs/ops/runtime-spike-record.md (DEP-01, verdict PASS).
Amends: decision 0002 (stack note), 0010 (the Electron folder an
installed copy proves its own), 0041 point 8 (shortcut target).

## Decision

1. An installed copy runs on two private runtimes: CPython at the exact
   version and sha256 in config/runtime_pins.json (the embeddable amd64
   zip; today 3.14.10, 12,619,664 bytes, SHA-256
   90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159,
   re-read from www.python.org on 2026-11-19 by downloading the zip with
   the AshLight User-Agent and hashing it), and the unmodified Electron
   zip at the exact version and sha256 in config/electron_pin.json
   (OVL-ELECTRON-PIN). Never a version range.
2. One source per pin: config/runtime_pins.json holds the CPython entry
   (version, arch, file, url, sha256, size, licence) and, for Electron,
   only `pin_file` and its licence; the Electron url, size and hash are
   read from config/electron_pin.json, whose version equals the electron
   entry of app/package.json (tests/test_runtime_pins.py).
3. Fetched at install, never bundled: `pinfetch.ensure_runtime(name, pin,
   dest, fetch)` runs only in the installer's own process (at install, at
   repair, and in an update whose release changes a pin). It checks the
   pin before any request, allows only the hosts www.python.org,
   github.com, release-assets.githubusercontent.com and
   objects.githubusercontent.com (every redirect hop, https, port 443,
   exact host), sends the AshLight User-Agent naming the runtime and no
   cookie, streams to a temp file beside the target while hashing, and
   refuses a wrong size or SHA-256 (HashMismatch) with the temp file
   deleted and nothing in the target. The zip is unpacked unmodified
   through a temp folder after a member path check (no absolute path, no
   `..`, no backslash or colon, no symlink), then gets AshLight's marker
   `ashlight-runtime.json` (name, version, url, sha256, size). A target
   with this pin's marker is a no-op; a target without AshLight's marker
   is never removed. The running core never imports pinfetch (static
   test in tests/test_pinfetch.py) and never fetches a runtime.
4. No AshLight artifact carries Electron or CPython. The offline route
   is the player's own publisher zips checked against the same pins
   (plan 05 Design point 5).
5. Launch: `boot.py` at the payload root plus one command builder
   (`paths.python_cmd`), as DEP-06 records; no Electron fuse is flipped
   on the unmodified exe (guards come from decision 0061).
6. The checkout keeps `npm ci` (or tools/electron_pin.py) and the system
   Python; nothing here changes the developer path.

## Licence record

Read 2026-11-19 from each publisher.

- CPython: Python Software Foundation License Version 2 (PSF-2.0), a
  permissive licence that allows use and redistribution with the notice
  kept. AshLight does not redistribute CPython: the player's machine
  fetches the publisher's own zip, which carries `LICENSE.txt` with the
  PSF text and the notices of the components it includes. Nothing of
  CPython is copied into this repository.
- Electron: MIT (Electron contributors, GitHub Inc.). The zip carries
  `LICENSE` and `LICENSES.chromium.html` (Chromium and its components,
  all licences that permit unmodified binary use). AshLight does not
  redistribute Electron: the player's machine fetches the release asset
  unmodified.
- Neither licence is GPL, AGPL or non-commercial; neither conflicts with
  AshLight's Apache-2.0 (decision 0047). THIRD-PARTY.md names both as
  "fetched at install, not bundled".
- A bundled full zip (a redistribution) is not decided here and would
  need its own licence decision (plan 05 Risks).

## Choices the package text left open (ruled)

- Electron's licence lives in runtime_pins.json beside `pin_file`, not
  in electron_pin.json: that file belongs to OVL-ELECTRON-PIN and its
  tool refuses unknown shapes; the licence is not a pin value, so one
  source per pin still holds. Alternative: a licence key in
  electron_pin.json. Reverses if: electron_pin.json gains a licence
  field.
- The CPython pin is amd64 only (`arch`): Windows on ARM is deferred
  (plan 05 Design point 12); an arm64 request refuses (PinError).
- The downloaded zip is deleted after unpacking, not kept in a cache:
  the marker records its hash, and a repair re-fetches. Alternative:
  keep it under the home's cache. Reverses if: repair without network
  is wanted (then keep it under `cache\downloads\`).
- A runtime target folder without AshLight's marker is never removed or
  overwritten (PinError): only AshLight-made folders are changed
  (decision 0051 spirit, FLEET item 9).

## Alternatives

- The player's own Python and `npm ci` on the player path: two heavy
  prerequisites, version drift, and a Node toolchain for players.
- A bundled full zip with both runtimes inside: redistributes third-party
  binaries, needs its own licence decision (Q-20 rules "never bundled").
- Fetching from a mirror or a CDN: not the publisher, not verifiable
  against the publisher's own hashes.

## Why

It removes both heavy prerequisites and redistributes nothing; each
runtime is the publisher's exact bytes, checked against a pinned hash
before use, fetched only by the installer, never by the running core
(Game ToS floor: public web data, truthful User-Agent, no cookie).

## Reverses if

The spike fails, a publisher drops hash-verifiable assets, or a licence
objection appears.
