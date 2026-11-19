"""Shared helpers of the full-stack tests (moved out of tests/test_fullstack.py
so other test helpers import a non-test module; TEST-LAYOUT-GUARD): the
local mock poe.ninja and the core's re-pointing transport, the synthetic
campaign and trades, and the waystone item text. Stdlib only.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import ninja, pricebook, webfetch  # noqa: E402

CONTACT = "fullstack-test-contact"
LEAGUE = "Example League"

WAYSTONE = """Item Class: Waystones
Rarity: Rare
Doom Trail
Waystone (Tier 15)
--------
Waystone Tier: 15
Item Quantity: +38% (augmented)
--------
Item Level: 79
--------
Monsters deal 28(20-30)% of Damage as Extra Fire
Players have 40% less Recovery Rate of Life and Energy Shield
--------
Can be used in a Map Device, allowing you to enter a Map. Waystones can only be used once.
"""

# Acts 1-4 (G<n>_ ids, research 0002 section 7); names invented.
CAMPAIGN = [("G1_1", 1, "The Riverbank"), ("G1_town", 15, "Clearfell Encampment"),
            ("G1_2", 2, "Clearfell"), ("G2_1", 16, "Vastiri Outskirts"),
            ("G2_town", 22, "The Ardura Caravan"), ("G3_1", 33, "Sandswept Marsh"),
            ("G3_town", 35, "Ziggurat Encampment"), ("G4_1", 45, "Isle of Kin")]
HIDEOUT = ("HideoutFelled", 65, "Felled Hideout")


# -- local mock poe.ninja ---------------------------------------------------

def _overview(path, kind):
    core = {"primary": "exalted",
            "items": [{"id": "exalted", "name": "Exalted Orb"}]}
    if path == ninja.OVERVIEW_PATH and kind == "Currency":
        return {"core": core,
                "items": [{"id": "exalted", "name": "Exalted Orb"},
                          {"id": "divine", "name": "Divine Orb"}],
                "lines": [{"id": "exalted", "primaryValue": 1},
                          {"id": "divine", "primaryValue": 180, "volumePrimaryValue": 900}]}
    if path == pricebook.ITEM_PATH and kind == "UniqueWeapons":
        return {"core": core,
                "lines": [{"name": "Example Unique", "baseType": "Example Quarterstaff",
                           "primaryValue": 42, "listingCount": 55,
                           "sparkLine": {"totalChange": 61.0}}]}
    return {"core": core, "lines": []}


class MockNinja:
    """poe.ninja's documented PoE2 endpoints, one ETag per URL, 304 on a
    matching If-None-Match. Every request is recorded."""

    def __init__(self):
        self.requests = []
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                u = urlsplit(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                mock.requests.append({"path": u.path, "query": q,
                                      "headers": {k.lower(): v for k, v in self.headers.items()}})
                if u.path == ninja.LEAGUES_PATH:
                    doc = [{"id": LEAGUE, "name": LEAGUE}, {"id": "Standard"}]
                elif u.path in (ninja.OVERVIEW_PATH, pricebook.ITEM_PATH):
                    doc = _overview(u.path, q.get("type"))
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                etag = '"v1-%08x"' % (hash(self.path) & 0xFFFFFFFF)
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.end_headers()
                    return
                body = json.dumps(doc).encode("ascii")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("ETag", etag)
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever,
                         kwargs={"poll_interval": 0.05}, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class Transport:
    """The core's injected fetch: the URL webfetch already checked
    (https://poe.ninja/...) goes to the local mock instead. Any other host
    reaching the transport is recorded as a defect."""

    def __init__(self, mock):
        self.mock = mock
        self.calls = []
        self.real = webfetch.make_transport(timeout=5.0)

    def __call__(self, method, url, headers, body=None):
        self.calls.append(url)
        assert url.startswith(ninja.BASE + "/"), url
        return self.real(method, self.mock.base + url[len(ninja.BASE):], headers, body)


def campaign_and_maps(s):
    """Acts 1-4 with level-ups and deaths, then two maps with a hideout
    portal trip and a re-entry into the first map (same seed)."""
    s.marker()
    s.raw("[WINDOW] Gained focus")
    for i, (aid, lvl, name) in enumerate(CAMPAIGN):
        s.zone_change(aid, lvl, name)
        s.noise(2)
        s.level_up()
        if i in (2, 5):
            s.death()
    s.zone_change(*HIDEOUT)
    s.zone_change("MapCrypt", 65, "Crypt", seed=111)
    s.level_up()
    s.death()  # in the map
    s.zone_change(*HIDEOUT)  # portal out ...
    s.zone_change("MapCrypt", 65, "Crypt", seed=111)  # ... and back in
    s.zone_change(*HIDEOUT)
    s.zone_change("MapSunTemple", 66, "Sun Temple", seed=222)


def trades(s):
    s.trade_whisper("Firstbuyer", "Grim Bane Ruby Ring", 5, "exalted")
    s.trade_whisper("Secondbuyer", "Example Unique", 40, "exalted")
