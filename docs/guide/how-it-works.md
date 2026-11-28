# How AshLight works

For developers and the curious. Players do not need this page; start with
the [Quick start](quick-start.md).

## How it works

The core is a small Python program using only the standard library. A tailer
polls the size of `Client.txt` four times a second and reads only the new
bytes. At start it looks back through the log only to pick up the current
run (zone, level, deaths), so an old session is never replayed. A parser
turns each line into an event (zone change, level up, death, whisper, trade
request, ...). Events go through an in-process event bus into a session
state, and a local HTTP server pushes that state to the dashboard over
Server-Sent Events, coalesced to at most four updates a second.

The dashboard is plain HTML, CSS and JavaScript served by the core. The
overlay is a separate Electron window that is transparent, always on top,
click-through and never takes focus; it shows the same feed in a tiny corner
box. Build numbers come from Path of Building PoE2: the ones saved in your
build code, and more when the optional calc component runs it unmodified as a
separate process. AshLight has no damage calculator of its own.

The core binds `127.0.0.1` only. Every API call needs the per-start token,
the Host and Origin headers are checked, and the dashboard runs under a
strict Content Security Policy. A keepalive supervisor restarts the core if
it dies; a stop from the tray or `scripts\stop.ps1` is one it respects.

## Budgets

The numbers are in the README's
[Budgets](../../README.md#budgets) section. `tests/test_budgets.py` asserts
each one, and `tools/docs_fresh.py` fails the suite when the README quotes a
number the tests no longer assert. The reasoning and the measured values are
in [decision 0002](../decisions/0002-stack.md).

## How this repository is run

AshLight is built by one maintainer with AI coding assistants. The files
`CLAUDE.md`, `AL-NEXT-SESSION.txt` and `ROADMAP.md` and the folders `ops/` and
`docs/` are that development process: the assistants' rules, the hand-off
between work sessions, the work list, research notes and decision records. You
can ignore them to use AshLight or to read its code.

The process is AI-assisted and operator-reviewed: the maintainer reviews every
change, and every commit is gated by the test suite, an identity check (no bot
author and no AI co-author line) and a leak sweep (no machine path, account id
or e-mail address in any tracked file).

The development loop, not the app, reads a few public web pages unattended:
once a day the Path of Building PoE2 releases list (decision 0025) and GGG's
developer documentation pages (decision 0044). The app itself fetches nothing
unless you turn web data on.

Releases: none yet, install from source (see the
[Quick start](quick-start.md)).

Next: [Download](download.md).

---

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.
