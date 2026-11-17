# AshLight

A live, glanceable second-screen dashboard and quiet overlay for your play session.

A companion app for Path of Exile 2.

AshLight follows the game's own log file (`Client.txt`) and shows the few things
worth a glance: the zone you are in and how long you have been there, your
character level, deaths this session, session time, and incoming whispers and
trade requests. It runs on your own computer, on `127.0.0.1` only.

## What AshLight never does

- It never reads or writes game memory, injects anything, hooks graphics, or
  touches network traffic.
- It never modifies any game file.
- It never sends input to the game: no keys, no mouse, no chat, no macros, not
  even a synthesized copy shortcut. You play; AshLight only reads.
- It reads `Client.txt` only after you say yes, and shows a visible
  "reading Client.txt" indicator while it does. You can stop it at any time.
- Future price-check features read the clipboard once per press of an
  AshLight hotkey, never on a timer and never by watching the clipboard.
- It never asks for or stores your session cookie or account login.

## Quick start (Windows)

Needs Python 3.11 or newer. Node.js 20 or newer is only needed for the
optional overlay.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # checks, folders, overlay packages
powershell -ExecutionPolicy Bypass -File scripts\build.ps1   # runs the tests, writes a build stamp
powershell -ExecutionPolicy Bypass -File scripts\run.ps1     # core, supervisor, overlay (if installed), dashboard
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -NoOverlay   # same, without the overlay
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1    # stops every AshLight process
```

Every script is safe to run again: a finished step is skipped, and `run.ps1`
starts only the parts of AshLight that are not already running.

Without the scripts:

```text
python -m server.al                     # start; prints the dashboard link
python -m server.al --log PATH          # point at a Client.txt yourself
python -m server.al --no-tail --replay tests/fixtures/client_sample.txt   # demo data
```

Open the printed link (it carries a one-time access token after `#token=`).
The overlay toggles with Alt+Shift+A. Play in Windowed Fullscreen so the
overlay can sit on top of the game.

Optional per-computer settings live in `config/local.json` (not tracked):
`client_log` (path to Client.txt or the game folder), `character` (the name to
track), `poll_ms` (log poll interval, default 250), `overlay_toggle` (the
overlay shortcut), `web_data` (the web-data opt-in, default `false`) and
`league` (optional league for currency rates).

## Privacy and consent

- The first time, the dashboard asks before reading `Client.txt` and names the
  file and what is derived from it. Your answer is stored locally.
- Nothing leaves your computer unless you turn on web data (off by default).
  With it on, AshLight fetches currency rates from poe.ninja at most once an
  hour, a build share link (pobb.in, pastebin) once when you paste it, and
  price checks you ask for; every request names AshLight and its version and
  carries no cookie or account id. The server binds `127.0.0.1` only; every
  API call needs the per-start token; the Host and Origin headers are
  checked; the dashboard runs under a strict Content Security Policy.
- The log can hold chat text. AshLight keeps only a short in-memory list of
  recent whispers and events and writes none of it to disk.

## Budgets

AshLight must never cost you frames. The tested budgets:

- Core: parses 10,000 log lines in under 250 ms; a 1,000-line burst in under
  50 ms; idle tailing under 1 to 2 percent of one CPU core; memory stays flat
  (every buffer is bounded).
- Overlay: no animation and no render loop - it draws only when a shown value
  changes; hardware acceleration off; idle CPU under 1 percent of one core;
  under 250 MB for all its processes.

## How it works

The core is a small Python program using only the standard library. A tailer
polls the size of `Client.txt` four times a second and reads only the new
bytes, starting at the end of the file so an old session is never replayed. A
parser turns each line into an event (zone change, level up, death, whisper,
trade request, ...). Events go through an in-process event bus into a session
state, and a local HTTP server pushes that state to the dashboard over
Server-Sent Events, coalesced to at most four updates a second.

The dashboard is plain HTML, CSS and JavaScript served by the core. The
overlay is a separate Electron window that is transparent, always on top,
click-through and never takes focus; it shows the same feed in a tiny corner
box.

## Disclaimer

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.

Path of Exile is a trademark of Grinding Gear Games.

## License

Apache-2.0. See `LICENSE` and `NOTICE`.
