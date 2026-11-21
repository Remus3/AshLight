# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's "Report a
vulnerability" button (private security advisory) on the repository's
Security tab (https://github.com/Remus3/AshLight/security/advisories/new). Do not open a public issue for a security
problem.

Include what you found, how to reproduce it, and the AshLight version
(`GET /api/version` or the `python -m server.al --help` banner).

## Scope

In scope: the local core server (token, Host / Origin checks, CSP, the SSE
feed), the dashboard, the overlay shell, the setup / build / run scripts,
and the installer, updater and uninstaller of an installed copy.

AshLight's design floor: it binds `127.0.0.1` only, requires a per-start
token on every API call, never sends input to the game, and never reads game
memory. A way around any of these is a vulnerability.

## Release provenance

Releases are not code-signed. What stands in for a signature:

- Immutable releases. A published release's files and tag cannot be
  changed or replaced; a fix is always a new version.
- Two hash sources. Every release carries `SHA256SUMS.txt`, and GitHub
  records its own SHA-256 digest for each release file. The installer
  checks the size and SHA-256 of every file it downloads against
  `SHA256SUMS.txt`, and the updater (once it ships) also checks GitHub's
  digest. The two
  runtimes (Python and Electron) are checked against the size and SHA-256
  pinned in the release. A file that fails any check is not unpacked.
- Build attestation. The release workflow builds the files from the
  tagged source and publishes a build attestation for them (a statement
  of how the files were built, signed through GitHub). CI
  verifies it on every release, and anyone can check it with
  `gh attestation verify` and `gh release verify-asset` (README, Verify
  your download).

What the installer and the installed updater do not do: they do not
verify the attestation. They cannot check it with the tools they ship
with (the Python standard library), so they make no claim about it and
rely on the immutable release and the two hash sources. The pasted install line fetches the installer over HTTPS
from the immutable release; anyone who wants to check before anything runs
can use the release-files route in the README.
