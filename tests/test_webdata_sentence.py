"""UX-WEBDATA-SENTENCE-TRUE (docs/reviews/ux/2026-11-28.md P1-2; decisions
0013, 0072): the web-data opt-in sentence lists every request the switch
allows, picked by the core from the copy kind, and its wording version is
bumped so an earlier opt-in acknowledges it once.

Both sentences are pinned exactly (copy sheet docs/design/copy/webdata.md).
The page holds no copy: web/index.html's #webdata-sentence is empty and
web/tc.js carries no sentence text.
"""
import http.client
import json
import re
import threading
from pathlib import Path

from server.al import core as core_mod
from server.al import ninja, updates
from server.al.http import serve
from server.al.text import webdata

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "t" * 32

INSTALLED = (
    "Off unless you turn it on. When on, AshLight downloads game data (item "
    "bases, gems, the passive tree) from public GitHub pages once a day. It "
    "opens a build link you paste, once. It checks GitHub once a day for a new "
    "AshLight. A new version downloads by itself while the game is closed and "
    "installs the next time you open AshLight. "
    "AshLight asks poe.ninja for nothing in this copy. Prices show as a trade "
    "link you open. It never asks the trade site anything. It sends no account, "
    "password or cookie, and never touches the game.")
CHECKOUT = (
    "Off unless you turn it on. When on, AshLight downloads game data (item "
    "bases, gems, the passive tree) from public GitHub pages once a day. It "
    "opens a build link you paste, once. It checks GitHub once a day for a new "
    "AshLight. A new version downloads by itself while the game is closed and "
    "installs the next time you open AshLight. "
    "It fetches currency and item prices from poe.ninja, currency hourly, the "
    "rest every 3 hours. It never asks the trade site anything. It sends no "
    "account, password or cookie, and never touches the game.")


def test_both_sentences_are_exact():
    assert webdata.SENTENCE_INSTALLED == INSTALLED
    assert webdata.SENTENCE_CHECKOUT == CHECKOUT
    assert webdata.sentence(True) == INSTALLED
    assert webdata.sentence(False) == CHECKOUT
    for s in (INSTALLED, CHECKOUT):
        assert s.isascii() and "  " not in s and "three things" not in s


def test_the_wording_version_moved_past_the_first_sentence():
    # an opt-in acknowledged under the old "three things only" wording (1)
    # makes no update request until the new sentence is acknowledged
    assert updates.WORDING_VERSION == 2
    assert updates.ack_ok(1) is False
    assert updates.ack_ok(2) is True


def _core(tmp_path, installed):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    cfg = tmp_path / "local.json"
    cfg.write_text(json.dumps({"web_data": False}), encoding="ascii")
    core = core_mod.Core(runtime=tmp_path / "rt", log_path=str(log), tail=False,
                         config_path=cfg, update_repo=None)
    core.rates.installed = lambda: installed
    return core


def _get(core):
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        conn.request("GET", "/api/web-data",
                     headers={"Authorization": "Bearer " + TOKEN,
                              "Host": "127.0.0.1:%d" % server.port})
        resp = conn.getresponse()
        body = json.loads(resp.read().decode("ascii"))
        conn.close()
        return resp.status, body
    finally:
        server.shutdown()
        server.server_close()


def test_the_core_picks_the_installed_sentence(tmp_path, monkeypatch):
    monkeypatch.setattr(ninja, "RELEASE_POLLING", False)
    core = _core(tmp_path, installed=True)
    assert core.web_data_sentence() == INSTALLED
    status, doc = _get(core)
    assert status == 200
    assert doc["sentence"] == INSTALLED
    assert doc["wording_version"] == updates.WORDING_VERSION


def test_the_core_picks_the_checkout_sentence(tmp_path, monkeypatch):
    monkeypatch.setattr(ninja, "RELEASE_POLLING", False)
    core = _core(tmp_path, installed=False)
    assert core.web_data_sentence() == CHECKOUT
    status, doc = _get(core)
    assert status == 200 and doc["sentence"] == CHECKOUT


def test_release_polling_on_names_the_prices_in_an_installed_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(ninja, "RELEASE_POLLING", True)
    assert _core(tmp_path, installed=True).web_data_sentence() == CHECKOUT


def test_the_page_holds_no_copy_of_the_sentence():
    html = (ROOT / "web" / "index.html").read_text(encoding="ascii")
    m = re.search(r'<p id="webdata-sentence"[^>]*>([\s\S]*?)</p>', html)
    assert m, "#webdata-sentence"
    assert m.group(1).strip() == ""
    tc = (ROOT / "web" / "tc.js").read_text(encoding="ascii")
    for words in ("three things", "Off unless you turn it on", "poe.ninja about once"):
        assert words not in tc
