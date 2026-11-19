"""F-131: the one status vocabulary (server/al/data/status_words.json).

One table names every reading and connection state: the dashboard bar
word, the overlay status word, the Checks detail and the player's next
step. diag.py takes its consent, Client.txt, reading and last-line wording
from here, and the play view takes its state words from here. The two JS
surfaces (web/status.js, app/shared/render_gate.js) cannot import a server
file, so each holds a copy of the table between its STATUS_WORDS marker
lines; tests/test_status_words.py compares both copies with this file.

The table is tracked code data: read once, never hot-reloaded (a reload
would part it from the JS copies). Wording only; idle still comes only
from Client.txt staleness (decision 0029).
"""

import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parent / "data" / "status_words.json"

# The marker lines around the copy in each JS file.
BEGIN = "/* STATUS_WORDS BEGIN: copy of server/al/data/status_words.json */"
END = "/* STATUS_WORDS END */"
JS_COPIES = ("web/status.js", "app/shared/render_gate.js")


@lru_cache(maxsize=1)
def table():
    """The whole document (raises on a malformed tracked file)."""
    return json.loads(PATH.read_text(encoding="ascii"))


def state(sid):
    """The row of one state id (KeyError for an unknown id)."""
    return table()["states"][sid]


def check(sid):
    return state(sid)["check"]


def next_step(sid):
    return state(sid)["next"]


def bar(sid):
    return state(sid)["bar"]


def overlay(sid):
    return state(sid)["overlay"]


def reading_state(tailer, live=True):
    """The reading state id of a snapshot's tailer dict, the same rule as
    web/status.js readingState: unknown while the feed is down or the core
    sends no tailer; idle (decision 0029) before reading; then reading,
    waiting (path known), missing (no path) or off (not opted in)."""
    if not live or not isinstance(tailer, dict):
        return "unknown"
    if tailer.get("consented") and tailer.get("idle"):
        return "idle"
    if tailer.get("reading"):
        return "reading"
    if tailer.get("consented"):
        return "waiting" if tailer.get("path") else "missing"
    return "off"


def copy_doc():
    """The document a JS copy must equal: the table without _README."""
    return {k: v for k, v in table().items() if k != "_README"}


def js_copy(text):
    """The table copy parsed from a JS file's text, or None without
    markers. The copy is `var STATUS_WORDS = <json>;` between them."""
    if BEGIN not in text or END not in text:
        return None
    body = text.split(BEGIN, 1)[1].split(END, 1)[0].strip()
    prefix = "var STATUS_WORDS ="
    if not body.startswith(prefix) or not body.endswith(";"):
        return None
    return json.loads(body[len(prefix):-1])


def js_block(indent="  "):
    """The marker block text for a JS file (what a table edit pastes)."""
    lines = json.dumps(copy_doc(), indent=2).splitlines()
    out = [indent + BEGIN, indent + "var STATUS_WORDS = " + lines[0]]
    out += [indent + ln for ln in lines[1:-1]]
    out += [indent + lines[-1] + ";", indent + END]
    return "\n".join(out)


if __name__ == "__main__":
    print(js_block())
