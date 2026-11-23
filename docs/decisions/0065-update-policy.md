# 0065 - Update policy

Date: 2026-11-19. Source: docs/plan/05-deployment.md (design points 9
and 13, "Checksums and what a client trusts", decision D5), ruling Q-21
(decision 0078 ledger), findings F-055 and F-077, package DEP-16 (the
release check client). Amends decision 0013 (the web-data opt-in now
also covers the update read; the wording text itself lands with
REL-UPDATE-WIRE) and the wording of decision 0018 item 6 (dated
amendment there).

## Decision

1. One read of the project's GitHub `releases/latest` per 24 h, made by
   `server/al/updates.py` (`UpdateClient.tick`). It runs only while all
   three hold: the web-data opt-in is on (decision 0013; with it off the
   transport is never called); the player has acknowledged the opt-in
   wording that names the update check and the automatic apply
   (`WORDING_VERSION`, now 1; an opt-in given before that wording makes
   no update request until the player has seen it once, Q-21); and the
   repository constant is set. The constant is the `repo` value of the
   tracked `config/public_repo.json` written by the go-public address
   package (GP-10); a missing file, an empty value or one that is not
   `<owner>/<name>` in GitHub's character set means off, so nothing is
   requested before the address exists.
2. The read goes through `server/al/webfetch` only: https, host
   allow-list `api.github.com` (a redirect off it is refused, never
   followed), the truthful AshLight User-Agent with no contact value
   (GitHub does not ask for one; nothing personal leaves the machine),
   no cookie, no token, a 1 MB answer cap. Every attempt uses the day's
   one read, whatever its outcome. A 304 against the cached ETag keeps
   the cached answer and parses nothing. Retry-After and a rate-limit
   reset (`X-RateLimit-Remaining: 0` with `X-RateLimit-Reset`) are
   honoured: the next read waits for the later of them and the daily
   slot; a wait past 7 days is capped at 7 days.
3. The trimmed answer (tag, pre-release flag, publish date, release
   page, and per asset its name, size, `digest` and download URL, at
   most 32 assets) is cached as `update_check.json` in the cache folder
   (the sidecar `Cache` in a checkout, `<home>\cache` in an install) for
   the installer process. An answer cached for another repository value
   is never reused.
4. A pre-release never counts as newer than a release: a tag with a
   SemVer pre-release part, or an answer whose `prerelease` flag is
   true, is never offered (SemVer 2.0.0 precedence otherwise).
5. `view()` is the one snapshot shape: installed, latest, newer,
   prerelease, notes (the newest 3 version sections of the shipped
   CHANGELOG.md, the hand-written lead or the bullet lines, 600
   characters each), releases_url (none while the constant is empty),
   checked_at, next_at, error and ack_needed (true only when the
   constant is set, web data is on and the wording is not acknowledged).
6. Verification, staging and apply belong to the installer process
   (DEP-17, server/al/install/update.py), never to the core: size,
   SHA-256 against SHA256SUMS.txt of the same immutable release and the
   API `digest` field; a verified update is staged and applied at the
   next client start after a 24 h hold, the previous version kept and
   restored by itself when the new one fails its self-test; a Settings
   switch gives click-only. The Sigstore build attestation is verified
   by CI and by people (`gh attestation verify`), not by the installed
   updater: the Python standard library cannot verify it, so the
   updater does not claim to.
7. Runtime fetches in an installed copy stay in the installer's own
   process (plan 05 design point 13); the core never fetches a runtime.
   The core's one GitHub read is this release check.

## Alternatives

- Click-only by default (Q-21 option b). Not taken: the operator's
  minimal-interaction order; the hold, the hash checks and the rollback
  bound the risk. Kept as the Settings switch.
- No check, a notice from the release page only. Rejected: a player on
  an old version never learns of fixes.
- Shipping a signature verifier binary for the attestation. Rejected:
  breaks the stdlib-only core (decision 0002) and adds a binary to trust.
- Sending the configured contact in the User-Agent as for poe.ninja and
  GGG. Rejected: GitHub does not ask for it and the read needs no
  personal value.
- Treating a newer pre-release as an update for every player. Rejected:
  release candidates are for the private test round (plan 05 DEP-18).

## Why

It mirrors the settled TC-DRIFT daily read (decision 0025) and the single
opt-in of decision 0013: one small, anonymous, rate-limit-respecting read
a day, inside the switch the player already chose, with no request at
all before the address exists or before the player has seen the wording.

## Reverses if

GitHub or GGG terms bar the daily read, a bad release auto-applies in
practice, the operator wants click-only, or a stdlib-verifiable
signature becomes available.

## Amendment 2026-11-22 (REL-UPDATE-APPLY-NOW, F-077)

Decision: one 'Update now' click finishes the update. When the click's
update run ends with a version staged (or the release was staged
already), the core writes <runtime>/apply_now.request holding only the
version (core._ask_apply; an automatic idle run never writes it, so that
update still applies at the next client start after the 24 h hold). The
desktop client's main process takes the file on its 30 s watch
(launcher.takeApplyRequest: at most 4 KB, removed on every read, a plain
SemVer only) and runs launcher.applyNow: it writes stop.request (the
user-stop file of scripts/stop.ps1, so the supervisor exits too), waits
up to 20 s for the hello check to fail and core.alive to go, runs
`installer apply-staged --home <home>` without --if-due (the click skips
the hold, as switch.apply already allowed), then relaunches from the new
marker version (exit 10) or starts the core again through run.ps1. A
core that does not stop is never switched under; the version applies at
the next start. The first health answer still confirms and a failed
start still rolls back (unchanged).

Alternatives: a new preload action from the dashboard button (rejected:
decision 0041 keeps the preload set fixed, and the renderer cannot see
when the staging run ends); the client reading the snapshot over the
token (rejected: the main process holds no feed, and a file in the
private runtime dir is the existing stop.request pattern); the installer
itself stopping the core (rejected: only the client may relaunch the
client, and the installer never kills processes).

Why: the operator's minimal-interaction order; the click already states
the player's consent to update now, so the hold adds nothing.

Reverses if: the stop then apply cuts a press or a calc in play, the
30 s watch delay proves too slow, or the operator wants the click to wait
for the next start again.
