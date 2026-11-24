"""RUN-LEFTOVERS-CORE (finding F-188): small leftovers.

- Checks shows the advice 'Play in Windowed Fullscreen' as a note
  (server/al/plug/displaymode.py). Advice only: nothing reads a game file
  or detects the display mode.
- The dead 501 POST /api/clipboard-read stub is gone; the path now falls
  through to the plug lookup and answers 404 like any unknown /api/ path.
- scripts/run.ps1 no longer accepts the no-op -Overlay switch.

Synthetic cores in tmp dirs only; no network, no live log."""

import http.client
import re
import threading
from pathlib import Path

import pytest

from server.al import diag
from server.al import http as al_http
from server.al.core import Core
from server.al.plug import displaymode
from server.al.text import explain

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "t" * 32


@pytest.fixture
def core(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    try:
        yield c
    finally:
        c.close()


def test_windowed_fullscreen_note_shows_in_checks(core):
    rows = diag.checks(core.diag_facts(now=2000.0), 2000.0)
    row = next((r for r in rows if r["id"] == displaymode.ROW_ID), None)
    assert row is not None
    assert row["status"] == "note"
    assert row["label"] == displaymode.LABEL
    assert row["detail"] == ("Play in Windowed Fullscreen. An exclusive fullscreen "
                             "game covers every other window.")
    # word for word the tail of the overlay explain hint
    assert explain.OVERLAY_WORDS["shown"][1].endswith(
        "set the game to Windowed Fullscreen. An exclusive fullscreen game covers "
        "every other window.")
    assert row["detail"].isascii()
    # advice only: the plug reads no file and asks no process
    src = (ROOT / "server" / "al" / "plug" / "displaymode.py").read_text(encoding="ascii")
    for word in ("open(", "subprocess", "ctypes", "read_text", "urllib", "socket"):
        assert word not in src, word


@pytest.fixture
def srv(core):
    server = al_http.serve(core, TOKEN, port=0)
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    try:
        yield server
    finally:
        server.stop()


def test_clipboard_read_route_answers_404(srv):
    assert "/api/clipboard-read" not in al_http.POST_ROUTES
    assert not hasattr(al_http.Handler, "_post_clipboard_read")
    conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
    try:
        conn.request("POST", "/api/clipboard-read", body=b"{}", headers={
            "Host": f"127.0.0.1:{srv.port}", al_http.TOKEN_HEADER: TOKEN,
            "Content-Type": "application/json"})
        r = conn.getresponse()
        r.read()
    finally:
        conn.close()
    assert r.status == 404


def test_run_ps1_has_no_overlay_switch():
    text = (ROOT / "scripts" / "run.ps1").read_text(encoding="ascii")
    assert not re.search(r"\[switch\]\$Overlay\b", text)
    assert not re.search(r"^\.PARAMETER Overlay\s*$", text, re.M)
    assert not re.search(r"\$Overlay\b", text)
    # the opt-out stays
    assert re.search(r"\[switch\]\$NoOverlay\b", text)
