"""PLAY-TD-01A: the Play state recipes and the long-string fixture.

One recipe per evidence-pack state (research 0043, PACK README "STATES"),
plus the trade burst (c and 3 more whispers: 5 open trades), the mapping
state and the long-string worst case, for the fit harness
(PLAY-TD-01B), the play view tests (PLAY-TD-07A) and the in-browser
accessibility pass (PLAY-TD-22C).

Every recipe builds on a fresh in-process core and its real HTTP / SSE
server (the stack fixture of tests/test_dash_console.py):
- the runtime, the config and Client.txt live under the root the caller
  gives (a pytest tmp_path); the log file is created BEFORE the core
  starts and the core is pinned to it (discover=False, SEC-NO-DISCOVERY):
  a recipe can never find or tail the live Client.txt (evidence pack
  incident, plan 03 risk R12);
- a free test port in 8961-8979 (tests/tc_live_util.free_test_port) or
  the port the caller names; 8960 is refused;
- web data stays off, except state g, which turns it on against the
  loopback mock poe.ninja of tests/fullstack_mocks.py (no external request);
- lines come from tools/synth_client.py, builds and items from
  tests/tc_eval_fixtures.py; nothing is sent to the game, no clipboard or
  screen is read.

Each recipe's docstring ends in a "Fields:" block: one check per line on
the /api/state snapshot the recipe leaves (`path`, `path <op> literal` or
`len(path) <op> n`; a dotted path walks dicts, a number indexes a list).
check_fields() evaluates that block, so the docstring is the contract.

    with play_states.open_state("c", tmp_path) as st:
        snap = st.state()        # the /api/state document
        url = st.url             # http://127.0.0.1:<port>/#token=...
"""

import ast
import contextlib
import http.client
import json
import operator
import os
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tools", ROOT / "tests", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import synth_client  # noqa: E402
import tc_eval_fixtures as fx  # noqa: E402
import fullstack_mocks as fs  # noqa: E402
from tc_live_util import free_test_port  # noqa: E402

from server.al import acts, ninja, ports, summary, zoneguide  # noqa: E402
from server.al import state as state_mod  # noqa: E402
from server.al.core import Core  # noqa: E402
from server.al.http import serve  # noqa: E402
from server.al.theorycraft import codec  # noqa: E402

TOKEN = "p" * 48
WAIT_S = 8.0
HOLD_CARD_S = 6 * 3600  # the item card stays up while a harness measures

# -- caps (plan 03 section 3.4, character budgets [D]) ----------------------
# TD-07 composes under them; the fit harness measures them with real strings.
CAP_CONTEXT_TITLE = 38
CAP_CONTEXT_ROW = 52
CAP_NOTICE_ROW = 52
CAP_EVENT_SENTENCE = 38
CAP_BUILD_ROW = 36
CAP_ITEM_SENTENCE = 36  # per row
ITEM_SENTENCE_ROWS = 2
CAP_KEPT_ROW = 42
CAP_NOTICE_WORD = 12
CAP_NOTICE_TITLE = 20
CAP_NOTICE_ACTION = 12
CAPS = {"context_title": CAP_CONTEXT_TITLE, "context_row": CAP_CONTEXT_ROW,
        "notice_row": CAP_NOTICE_ROW, "event_sentence": CAP_EVENT_SENTENCE,
        "build_row": CAP_BUILD_ROW, "item_sentence": CAP_ITEM_SENTENCE,
        "kept_row": CAP_KEPT_ROW, "notice_word": CAP_NOTICE_WORD,
        "notice_title": CAP_NOTICE_TITLE, "notice_action": CAP_NOTICE_ACTION}
NAME_LEN = 40  # names are data, never capped: the fixture's are this long
LONG_TRADES = state_mod.TRADE_REQUESTS  # 5 open trades, every server slot

# -- long-string fixture ----------------------------------------------------
_WORDS = ("Remember", "the", "waypoint", "beside", "Clearfell", "Encampment",
          "before", "you", "fight", "through", "Grelwood", "and", "check",
          "resistance", "upgrades", "against", "your", "current", "build",
          "level", "while", "trading", "experience", "lightning", "quarterstaff")


def text_at(n, words=_WORDS, start=0, stop=True):
    """An ASCII text of exactly n characters made of real words (the budget
    per character is an average over real text, plan 03 3.4): capital
    first letter, no leading, trailing or doubled space, and a full stop
    at the end when stop is true (a name when it is false)."""
    if n <= 0:
        return ""
    out = ""
    i = start
    while len(out) < n + 1:
        w = words[i % len(words)]
        out = (out + " " + w) if out else w
        i += 1
    chars = list(out[:n])
    chars[0] = chars[0].upper()
    if stop and n >= 2:
        chars[-1] = "."
        if chars[-2] == " ":
            chars[-2] = "s"
    elif chars[-1] == " ":
        chars[-1] = "s"
    return "".join(chars)


def name_at(n, stem):
    """A name of exactly n characters: letters only, no space (player and
    item names are data and take the ellipsis, plan 03 3.4)."""
    s = (stem * (n // max(1, len(stem)) + 1))[:n]
    return s[:1].upper() + s[1:]


LONG_CHARACTER = name_at(NAME_LEN, "Emberwhisperoftheashenvale")
LONG_BUYERS = tuple(name_at(NAME_LEN, stem) for stem in (
    "Firstbuyerwithaverylongaccountname", "Secondbuyerwhonevershortenshisname",
    "Thirdbuyerfromthenorthernmarches", "Fourthbuyerofrareandmagicitems",
    "Fifthbuyerwaitinginthehideout"))
LONG_ITEMS = tuple(text_at(NAME_LEN, start=i * 3, stop=False)
                   for i in range(LONG_TRADES))
# One composed row per kind at exactly its cap (TD-07 tests and the
# harness paint these where the composed rows will go).
LONG_ROWS = {
    "context_title": text_at(CAP_CONTEXT_TITLE, start=0),
    "context_row": text_at(CAP_CONTEXT_ROW, start=1),
    "notice_row": text_at(CAP_NOTICE_ROW, start=2),
    "event_sentence": text_at(CAP_EVENT_SENTENCE, start=3),
    "build_row": text_at(CAP_BUILD_ROW, start=4),
    "item_sentence": tuple(text_at(CAP_ITEM_SENTENCE, start=5 + r)
                           for r in range(ITEM_SENTENCE_ROWS)),
    "kept_row": text_at(CAP_KEPT_ROW, start=7),
    "notice_word": name_at(CAP_NOTICE_WORD, "Attention"),
    "notice_title": text_at(CAP_NOTICE_TITLE, start=8, stop=False),
    "notice_action": name_at(CAP_NOTICE_ACTION, "Opensettings"),
}


def _guide_size(entry, act):
    if not isinstance(entry, dict):
        return 0
    parts = [entry.get("objective") or (act or {}).get("default"),
             entry.get("layout"), entry.get("next")]
    parts += [o.get("text") for o in entry.get("optional") or () if isinstance(o, dict)]
    return sum(len(p) for p in parts if isinstance(p, str))


def longest_guide_entry(doc=None):
    """(act key, zone name, size) of the campaign guide entry with the most
    text (objective or act default, layout, next, every optional line) in
    the bundled zone_guide.json; ties go to the first in file order."""
    doc = zoneguide.load() if doc is None else doc
    best = None
    for key, act in (doc.get("acts") or {}).items():
        zones = (act or {}).get("zones") or {}
        for name, entry in zones.items():
            size = _guide_size(entry, act)
            if best is None or size > best[2]:
                best = (key, name, size)
    return best


def guide_area_id(act_key, n=99):
    """A synthetic area id of that act (acts.act_of accepts it)."""
    if act_key.startswith("C"):
        return f"C_G{act_key[1:]}_{n}"
    return f"{act_key}_{n}"


# -- the stack ----------------------------------------------------------------

class RecipeError(AssertionError):
    pass


class PlayStack:
    """One core pinned to <root>/Client.txt and its HTTP / SSE server.

    The log file is made before the core starts, also for state e (its
    recipe removes it afterwards). hold_card keeps the 20 s item card up
    for the life of the stack (state.EVAL_CARD_S, restored on close).
    gamedata writes a small synthetic world_areas.json (zone levels and
    waypoints) into the runtime. contact puts the test contact in the
    config (state g's User-Agent); web data stays off until a recipe
    turns it on."""

    def __init__(self, root, port=None, hold_card=True, gamedata=True, contact=True):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.rt = self.root / "rt"
        self.rt.mkdir(exist_ok=True)
        self.log = self.root / "Client.txt"
        self.log.write_bytes(b"")  # before the core starts (PACK incident)
        self.cfg = self.rt / "local.json"
        self.cfg.write_text(json.dumps({"contact": fs.CONTACT} if contact else {}) + "\n",
                            encoding="ascii")
        if gamedata:
            write_world_areas(self.rt / "gamedata" / acts.FILE_NAME)
        self.notes = []
        self.server = self.core = None
        self.mock = fs.MockNinja()
        self.fetch = fs.Transport(self.mock)
        self._card_s = state_mod.EVAL_CARD_S
        if hold_card:
            state_mod.EVAL_CARD_S = HOLD_CARD_S
        try:
            self._start(port)
        except BaseException:
            self.close()
            raise

    def _start(self, port):
        self.core = Core(runtime=self.rt, log_path=str(self.log), poll_s=0.02,
                         config_path=self.cfg, web_fetch=self.fetch, discover=False)
        # The GGG docs flag lives under the real runtime dir; a recipe core
        # never looks there (tick_diag reads it through this method).
        self.core._ggg_reg_open = lambda: False
        self.pinned()
        if port is None:
            port = free_test_port()
        if int(port) == ports.AL_PORT:
            raise RecipeError(f"port {ports.AL_PORT} is the running AshLight's")
        self.server = serve(self.core, TOKEN, port=port, web_root=ROOT / "web",
                            tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
        self.port = self.server.port
        self.core.port = self.port
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True).start()
        self.url = f"http://127.0.0.1:{self.port}/#token={TOKEN}"

    def pinned(self):
        """The core's log and its tailer's are this stack's Client.txt."""
        for p in (self.core.log_path, getattr(self.core.tailer, "path", None)):
            if p is not None and Path(p).resolve() != self.log.resolve():
                raise RecipeError(f"core points at a log outside the recipe: {p}")
        if self.core.discover:
            raise RecipeError("core may scan for the live Client.txt")

    def req(self, method, path, body=None, timeout=10):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        h = {"Host": f"127.0.0.1:{self.port}", "X-AL-Token": TOKEN}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        try:
            conn.request(method, path, body=data, headers=h)
            r = conn.getresponse()
            raw = r.read()
        finally:
            conn.close()
        try:
            return r.status, json.loads(raw) if raw else None
        except ValueError:
            return r.status, None

    def post(self, path, body):
        status, doc = self.req("POST", path, body)
        self.notes.append(f"POST {path} -> {status}")
        if status != 200:
            raise RecipeError(f"POST {path} -> {status}: {doc}")
        return doc

    def state(self):
        status, doc = self.req("GET", "/api/state")
        if status != 200:
            raise RecipeError(f"GET /api/state -> {status}")
        return doc

    def wait_for(self, pred, what, timeout=WAIT_S):
        end = time.monotonic() + timeout
        snap = None
        while time.monotonic() < end:
            snap = self.state()
            try:
                if pred(snap):
                    self.pinned()
                    return snap
            except (KeyError, TypeError, IndexError):
                pass
            time.sleep(0.02)
        raise RecipeError(f"timed out waiting for {what}; last: "
                          f"{ {k: (snap or {}).get(k) for k in ('zone', 'level', 'tailer')} }")

    def append(self, s):
        with open(self.log, "ab") as fh:
            fh.write(s.text().encode("utf-8"))
        s.lines.clear()

    def close(self):
        try:
            if self.server is not None:
                self.server.stop()
        finally:
            try:
                if self.core is not None:
                    self.core.close()
            finally:
                self.mock.close()
                state_mod.EVAL_CARD_S = self._card_s


def write_world_areas(path):
    """A small synthetic world_areas.json (the repoe-fork fields acts and
    zoneguide read): the zones the recipes enter plus the longest guide
    entry's zone, which has no waypoint (the longer waypoint line)."""
    key, name, _size = longest_guide_entry()
    long_id = guide_area_id(key)
    doc = {}
    for aid, lvl, zname in fs.CAMPAIGN:
        doc[aid] = {"name": zname, "area_level": lvl, "is_town": "town" in aid,
                    "has_waypoint": True, "connections": []}
    doc["G1_3"] = {"name": "Mud Burrow", "area_level": 3, "is_town": False,
                   "has_waypoint": False, "connections": ["G1_2"]}
    doc["G1_2"]["connections"] = ["G1_town", "G1_3"]
    doc.setdefault(long_id, {"name": name, "area_level": 2, "is_town": False,
                             "has_waypoint": False, "connections": []})
    hub = next((a for a, z in doc.items() if acts.act_of(a)["key"] == key
                and a != long_id and z["has_waypoint"]), None)
    if hub is None:
        hub = guide_area_id(key, 98)
        doc[hub] = {"name": "Waystation", "area_level": 2, "is_town": False,
                    "has_waypoint": True, "connections": []}
    doc[long_id]["connections"] = [hub]
    doc[hub]["connections"] = list(doc[hub]["connections"]) + [long_id]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="ascii")


# -- shared drive steps -------------------------------------------------------

def _consent(st):
    st.post("/api/consent", {"consent": True})
    return st.wait_for(lambda x: x["tailer"]["consented"] and x["tailer"]["reading"],
                       "tailer reading")


def _campaign_start(st, character="Emberdemo", klass="Sorceress"):
    """PACK b: marker, The Riverbank, level 2, Clearfell Encampment,
    Clearfell, levels 3-4, one death."""
    s = synth_client.Session(seed=7, character=character, klass=klass)
    s.marker()
    s.raw("[WINDOW] Gained focus")
    s.zone_change("G1_1", 1, "The Riverbank")
    s.level_up()
    s.zone_change("G1_town", 15, "Clearfell Encampment")
    s.zone_change("G1_2", 2, "Clearfell")
    s.noise(2)
    s.level_up()
    s.level_up()
    s.death()
    st.append(s)
    st.wait_for(lambda x: x["zone"] == "Clearfell" and x["level"] == 4 and x["deaths"] == 1,
                "campaign zone")
    return s


def _build(st):
    st.post("/api/build-code", {"code": codec.encode(fx.EVAL_BUILD_XML)})
    return st.wait_for(lambda x: x["build"]["loaded"], "build")


def _trades(st, s, pairs):
    want = len(st.state()["trade_requests"]) + len(pairs)
    for who, item, amount in pairs:
        s.trade_whisper(who, item, amount, "exalted")
    st.append(s)
    return st.wait_for(lambda x: len(x["trade_requests"]) == want, f"{want} trade cards")


C_TRADES = (("Firstbuyer", "Grim Bane Ruby Ring", 5),
            ("Secondbuyer_WithALongAccountName", "Example Unique Quarterstaff of Many Words", 40))
BURST_TRADES = (("Thirdbuyer", "Example Amber Amulet", 12),
                ("Fourthbuyer", "Example Leather Boots", 3),
                ("Fifthbuyer", "Example Iron Ring", 1))


def _c2(st):
    _consent(st)
    s = _campaign_start(st)
    _build(st)
    _trades(st, s, C_TRADES)
    return s


def _eval(st, item):
    st.post("/api/eval", {"item": item})


def _full_session(st, web_data=False, checks=True, character="Ashdemo"):
    """PACK f: the test_fullstack session (seed 31, Ranger): acts 1-4, two
    maps with a portal re-entry, 3 deaths, two trade whispers (one
    accepted), the build, three item checks (staff, waystone, gloves)."""
    _consent(st)
    s = synth_client.Session(seed=31, character=character, klass="Ranger")
    fs.campaign_and_maps(s)
    fs.trades(s)
    st.append(s)
    st.wait_for(lambda x: x["maps"]["count"] == 2 and len(x["trade_requests"]) == 2,
                "campaign, maps, trades")
    s.whisper_out("Firstbuyer", "invite sent")
    s.trade_accepted()
    st.append(s)
    st.wait_for(lambda x: len(x["trade_requests"]) == 1, "one trade closed")
    if web_data:
        past = time.time() - ninja.MIN_INTERVAL_S - 100
        st.core.rates.clock = lambda: past
        st.post("/api/web-data", {"enabled": True})
        end = time.monotonic() + WAIT_S
        while time.monotonic() < end and (st.core.rates._busy
                                           or not st.core.rates.doc.get("checked_at")):
            time.sleep(0.05)
        st.core.rates.clock = time.time
    _build(st)
    if checks:
        for item in (fx.UNIQUE_STAFF, fs.WAYSTONE, fx.RARE_GLOVES):
            _eval(st, item)
    for tick in ("tick_history", "tick_watch", "tick_sources"):
        getattr(st.core, tick)()
    st.core.tick_diag(force=True)
    return s


# -- the recipes ----------------------------------------------------------------

def state_a(st):
    """First run: fresh runtime, no consent, empty log, no build.

    Fields:
        tailer.consented is False
        tailer.reading is False
        game_idle is False
        zone is None
        character is None
        build.loaded is False
        eval is None
        len(trade_requests) == 0
    """


def state_a2(st):
    """Opted in, no line yet: consent recorded, the log exists and is empty.

    Fields:
        tailer.consented is True
        tailer.reading is True
        zone is None
        level is None
        character is None
        build.loaded is False
    """
    _consent(st)


def state_b(st):
    """Campaign zone: Emberdemo (Sorceress) in Clearfell, level 4, one
    death, the zone guide filled, no build saved.

    Fields:
        character == 'Emberdemo'
        class == 'Sorceress'
        zone == 'Clearfell'
        area_id == 'G1_2'
        level == 4
        deaths == 1
        in_hideout is False
        zone_guide.kind == 'campaign'
        zone_guide.objective
        build.loaded is False
        len(trade_requests) == 0
        eval is None
    """
    _consent(st)
    _campaign_start(st)


def state_c(st):
    """Worst case Play: b, then a Ranger build (class mismatch: build
    alert), two trade whispers (one long name and item) and an item check
    (rare gloves) whose card is up.

    Fields:
        zone == 'Clearfell'
        zone_guide.kind == 'campaign'
        build.class_name == 'Ranger'
        build_alert
        len(trade_requests) == 2
        trade_requests.1.from == 'Secondbuyer_WithALongAccountName'
        eval.ok is True
        card
    """
    _c2(st)
    _eval(st, fx.RARE_GLOVES)
    st.wait_for(lambda x: x["eval"] is not None and x["card"] is not None, "item card")


def state_c2(st):
    """c without the item check: zone guide, build alert, two trade cards
    (the overlay shows its trade card).

    Fields:
        zone == 'Clearfell'
        build_alert
        len(trade_requests) == 2
        eval is None
        card is None
    """
    _c2(st)


def state_d(st):
    """Game idle: c2, then 20 minutes of quiet (time-injected): idle and
    the session summary card.

    Fields:
        game_idle is True
        tailer.idle is True
        session_summary
        session_summary.reason == 'idle'
        len(trade_requests) == 2
        build_alert
    """
    _c2(st)
    quiet = time.time() + summary.IDLE_S + 5
    saved = st.core.tick_summary(now=quiet)
    st.notes.append(f"tick_summary(+{int(summary.IDLE_S) + 5}s) -> "
                    f"{saved.get('reason') if saved else None}")
    st.wait_for(lambda x: x["game_idle"] and x["session_summary"], "idle")


def state_e(st):
    """Error: consent with the recipe's Client.txt gone (the core keeps
    its configured path, never scans) and an item check of junk text: the
    Checks row for the log and the "Not an item" card.

    Fields:
        tailer.consented is True
        tailer.reading is False
        zone is None
        eval.ok is False
        diag.checks.0.id == 'log'
        diag.checks.0.status == 'fail'
        card.head == 'Not an item'
    """
    st.log.unlink()
    st.post("/api/consent", {"consent": True})
    st.wait_for(lambda x: x["tailer"]["consented"], "consent")
    _eval(st, "this is not an item text\n")
    st.core.tick_diag(force=True)
    st.wait_for(lambda x: x["eval"] is not None and x["diag"], "error card and checks")


def state_f(st):
    """Typical filled: acts 1-4, two maps, 3 deaths, one of two trades
    accepted, the Ranger build (it fits: no alert), three item checks
    (unique staff, waystone, gloves; the gloves card is up). Web data off.

    Fields:
        character == 'Ashdemo'
        zone == 'Sun Temple'
        maps.count == 2
        deaths == 3
        len(trade_requests) == 1
        build.class_name == 'Ranger'
        build_alert is None
        eval.ok is True
        card
        sources.rates_checked_at is None
        price.league == 'Standard'
    """
    _full_session(st)


def state_g(st):
    """f with web data on against the loopback mock poe.ninja (no external
    request): price book filled, the gloves card priced.

    Fields:
        character == 'Ashdemo'
        maps.count == 2
        len(trade_requests) == 1
        build.class_name == 'Ranger'
        eval.ok is True
        sources.rates_checked_at
        sources.book_checked_at
        price.league == 'Example League'
    """
    _full_session(st, web_data=True)


def state_c5(st):
    """Trade burst: c and three more trade whispers, every one of the 5
    trade slots open, the item card up.

    Fields:
        zone == 'Clearfell'
        build_alert
        len(trade_requests) == 5
        eval.ok is True
        card
    """
    s = _c2(st)
    _eval(st, fx.RARE_GLOVES)
    _trades(st, s, BURST_TRADES)


def state_map(st):
    """Mapping: the Ranger session in its second map (Sun Temple) with two
    open trades, the build fits, no item check.

    Fields:
        zone == 'Sun Temple'
        area_id == 'MapSunTemple'
        in_hideout is False
        maps.count == 2
        zone_guide.kind == 'endgame'
        len(trade_requests) == 2
        build.class_name == 'Ranger'
        build_alert is None
        eval is None
    """
    _consent(st)
    s = synth_client.Session(seed=31, character="Ashdemo", klass="Ranger")
    fs.campaign_and_maps(s)
    fs.trades(s)
    st.append(s)
    st.wait_for(lambda x: x["maps"]["count"] == 2 and len(x["trade_requests"]) == 2,
                "maps and trades")
    _build(st)


def state_long(st):
    """Long strings: a 40-character character name in the zone with the
    longest guide entry (no waypoint there), 5 open trades from
    40-character buyers for 40-character items, a level-up and a death in
    the feed, the class-mismatch build alert and the item card up. The
    composed rows at their caps are LONG_ROWS (data for TD-07 / TD-01B).

    Fields:
        len(character) == 40
        zone_guide.kind == 'campaign'
        zone_guide.objective
        zone_guide.waypoint
        len(trade_requests) == 5
        len(trade_requests.0.from) == 40
        len(trade_requests.0.item) == 40
        build_alert
        eval.ok is True
        card
        deaths == 1
    """
    key, zone, _size = longest_guide_entry()
    _consent(st)
    s = synth_client.Session(seed=11, character=LONG_CHARACTER, klass="Sorceress")
    s.marker()
    s.raw("[WINDOW] Gained focus")
    s.zone_change("G1_1", 1, "The Riverbank")
    s.level_up()
    s.zone_change(guide_area_id(key), 2, zone)
    s.level_up()
    s.death()
    st.append(s)
    st.wait_for(lambda x: x["zone"] == zone and x["deaths"] == 1, "longest guide zone")
    _build(st)
    _trades(st, s, [(LONG_BUYERS[i], LONG_ITEMS[i], 100 + i) for i in range(LONG_TRADES)])
    _eval(st, fx.RARE_GLOVES)
    st.wait_for(lambda x: x["card"] is not None, "item card")


RECIPES = {"a": state_a, "a2": state_a2, "b": state_b, "c": state_c, "c2": state_c2,
           "d": state_d, "e": state_e, "f": state_f, "g": state_g, "c5": state_c5,
           "map": state_map, "long": state_long}
STATES = tuple(RECIPES)
PACK_STATES = ("a", "a2", "b", "c", "c2", "d", "e", "f", "g")


@contextlib.contextmanager
def open_state(name, root, port=None, hold_card=True):
    """A PlayStack driven to the named state; closed on exit. Pass the
    previous state's port to swap states under one page URL."""
    if name not in RECIPES:
        raise KeyError(f"unknown play state {name!r}; known: {', '.join(STATES)}")
    st = PlayStack(Path(root), port=port, hold_card=hold_card)
    try:
        RECIPES[name](st)
        st.pinned()
        yield st
    finally:
        st.close()


# -- the Fields: contract -------------------------------------------------------

_OPS = {"==": operator.eq, "!=": operator.ne, ">=": operator.ge, "<=": operator.le,
        ">": operator.gt, "<": operator.lt, "is": operator.is_, "is not": operator.is_not}
_LINE = re.compile(r"^(len\()?([A-Za-z0-9_.]+)\)?(?:\s+(==|!=|>=|<=|>|<|is not|is)\s+(.+))?$")


def fields_of(recipe):
    """The checks of a recipe's docstring "Fields:" block, as (text, is_len,
    path, op, value) tuples."""
    doc = recipe.__doc__ or ""
    if "Fields:" not in doc:
        return []
    out = []
    for raw in doc.split("Fields:", 1)[1].splitlines():
        line = raw.strip()
        if not line:
            if out:
                break
            continue
        m = _LINE.match(line)
        if not m:
            raise ValueError(f"{recipe.__name__}: bad Fields line {line!r}")
        is_len, path, op, lit = m.groups()
        out.append((line, bool(is_len), path, op, ast.literal_eval(lit) if lit else None))
    return out


_MISSING = object()


def lookup(snap, path):
    cur = snap
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part, _MISSING)
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return _MISSING
        if cur is _MISSING:
            return _MISSING
    return cur


def check_fields(recipe, snap):
    """Failures (one text per failed line) of the recipe's Fields: block
    against a snapshot; [] when every line holds."""
    bad = []
    for text, is_len, path, op, value in fields_of(recipe):
        got = lookup(snap, path)
        if got is _MISSING:
            bad.append(f"{text}: {path} missing")
            continue
        if is_len:
            try:
                got = len(got)
            except TypeError:
                bad.append(f"{text}: {path} has no length ({got!r})")
                continue
        ok = bool(got) if op is None else _OPS[op](got, value)
        if not ok:
            bad.append(f"{text}: got {got!r}"[:300])
    return bad


# -- what a recipe opens --------------------------------------------------------

_AUDIT = {"rec": None}
_WATCHED = ("open", "os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.listdir",
            "os.scandir", "os.truncate", "shutil.copyfile", "shutil.rmtree")


def _hook(event, args):
    rec = _AUDIT["rec"]
    if rec is None or event not in _WATCHED:
        return
    if threading.get_ident() in rec["skip"]:
        return
    path = args[0] if args else None
    mode = args[1] if event == "open" and len(args) > 1 else None
    flags = args[2] if event == "open" and len(args) > 2 else 0
    rec["events"].append((event, path, mode, flags))


@contextlib.contextmanager
def watch_opens():
    """Every file system path the code opens, lists, makes or removes while
    the block runs, from this thread and every thread started inside the
    block (threads that were running before are other tests' leftovers).
    Yields the list of (event, path, mode, flags). Python's audit hook is
    process-wide and cannot be removed: it is installed once and is a
    no-op outside this block."""
    if not _AUDIT.get("installed"):
        sys.addaudithook(_hook)
        _AUDIT["installed"] = True
    me = threading.get_ident()
    rec = {"events": [], "skip": {t.ident for t in threading.enumerate() if t.ident != me}}
    _AUDIT["rec"] = rec
    try:
        yield rec["events"]
    finally:
        _AUDIT["rec"] = None


_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_LIVE_STATE = ("ops/runtime", "ops/loop", "config/local.json", "moon_sync_inbox",
               "moon_sync_outbox")
_READ_ONLY_ROOTS = ("server", "web", "tools", "tests", "ops/fleet_kit")


def _norm(p):
    return os.path.normcase(os.path.abspath(p))


def _under(path, root):
    root = _norm(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def outside(events, tmp_root):
    """The events that touch a path outside tmp_root, except read-only
    opens of AshLight's own code and bundled data (server/, web/, tools/,
    tests/, ops/fleet_kit/) and of the Python installation, and the
    bytecode cache. Any write outside tmp_root, any repo live state
    (ops/runtime, ops/loop, config/local.json, the inbox / outbox) and any
    other Client.txt is reported."""
    bad = []
    py_roots = {sys.prefix, sys.base_prefix, sys.exec_prefix}
    for event, path, mode, flags in events:
        if isinstance(path, int) or path is None:
            continue
        try:
            p = _norm(os.fsdecode(path))
        except (TypeError, ValueError):
            bad.append((event, repr(path), mode))
            continue
        if _under(p, tmp_root):
            continue
        if os.path.basename(os.path.dirname(p)) == "__pycache__" and _under(p, ROOT):
            continue
        write = event != "open" and event not in ("os.listdir", "os.scandir")
        if event == "open":
            write = (any(c in (mode or "") for c in "wax+")
                     or bool((flags or 0) & _WRITE_FLAGS))
        if write:
            bad.append((event, p, mode))
            continue
        if os.path.basename(p) == "client.txt":
            bad.append((event, p, mode))
            continue
        if any(_under(p, ROOT / rel) for rel in _LIVE_STATE):
            bad.append((event, p, mode))
            continue
        if any(_under(p, ROOT / rel) for rel in _READ_ONLY_ROOTS):
            continue
        if any(_under(p, r) for r in py_roots):
            continue
        bad.append((event, p, mode))
    return bad
