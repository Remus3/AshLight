# 0027 - TC-LIVE: pinned portable C toolchain for the LuaJIT build

Date: 2026-11-17. Trigger: ROADMAP row AUDIT-TC-BRIDGE-LIVE (audit pass 2,
P2-C1). The machine has no C compiler, listed as operator act i. The
operator is away and authorized full computer use; ruled by the adjudicator
agent (FLEET item 1), no operator act waited on.

## Decision

1. `config/tc_pins.json` gains an OPTIONAL `toolchain` entry: one WinLibs
   MinGW-w64 release asset (GCC 16.2.0, UCRT, posix-seh, no LLVM), pinned by
   GitHub release tag, asset name, release download URL, size and SHA-256.
   The SHA-256 equals the digest GitHub publishes for the asset and was
   re-computed from two independent downloads on 2026-11-17.
2. `tools/tc_pin.py` uses it ONLY when no system compiler (MSVC `cl`, or
   `mingw32-make` + `gcc`) is on PATH, and only on the calc opt-in (`-TcCalc`, or `"tc_calc": true` in config/local.json; tools/tc_pin.py opted_in, wording fixed by AREA-AUDIT pass 3). It
   downloads with the same host-allowlisted, size-capped, hash-verified
   stream as the other pins (the allowlist widens to the GitHub release
   asset hosts for this entry only), extracts with stdlib `zipfile` under the
   same path guard into `<sidecar>\Cache\toolchain\mingw64\`, and runs
   `mingw32-make BUILDMODE=static` in the LuaJIT source with a minimal env
   (toolchain `bin`, then System32 and the Windows dir; no MSYS / TERM).
3. No system install, no registry change, no user or machine PATH change;
   the PATH edit exists only inside the build subprocess. The toolchain is
   never vendored, bundled or redistributed; the built `luajit.exe` (MIT
   source) stays in the sidecar and is hash-recorded by `exepin` as before.
4. A `.zip` asset is required (stdlib extraction); a 7z / self-extracting
   asset is never used. If WinLibs stops shipping a `.zip`, the row goes
   `BLOCKED:` rather than switching format.

License check: GCC is GPL-3.0-or-later with the GCC Runtime Library
Exception; the MinGW-w64 runtime is ZPL / public domain. AshLight only runs
the toolchain as an unmodified build tool on the user's machine and ships
none of it, so no license term reaches AshLight's code. No game ToS floor
change: build time only, nothing touches the game.

## Alternatives

- Leave "no C compiler" as an operator act: safe, but stalls TC-BRIDGE-LIVE
  while the operator is away (FLEET item 1: act, don't ask).
- A prebuilt LuaJIT binary: no hashed official Windows release exists
  (decision 0018); trusting an unverified binary is refused.
- w64devkit: ships as a 7z self-extracting exe, not stdlib-extractable.
- PoB's own `runtime/lua51.dll`: a DLL, not a standalone interpreter, and
  the static build exists so the one hashed exe covers everything that runs
  (audit pass 2, P2-B2).

## Why

The only route to an automated, verifiable `luajit.exe` that keeps
stdlib-only extraction and the decision 0018 pin-and-fetch model.

## Result (read back 2026-11-17)

`setup.ps1 -TcCalc`: toolchain archive verified (sha256 ok), extracted,
`luajit: built (sha256 recorded)`, `tc calc component: ready`; a re-run is
a no-op. `luajit.exe -v` reads `LuaJIT 2.1.1794386141`; static, no DLL.

## Reverses if

WinLibs drops `.zip` assets or the pin goes stale with no successor; a
license objection to running GCC as a build tool appears; LuaJIT ships
hashed Windows binaries (then use those and drop this entry); or the
operator installs MSVC / MinGW and wants this entry removed.
