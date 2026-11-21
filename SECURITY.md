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
feed), the dashboard, the overlay shell, and the setup / build / run scripts.

AshLight's design floor: it binds `127.0.0.1` only, requires a per-start
token on every API call, never sends input to the game, and never reads game
memory. A way around any of these is a vulnerability.
