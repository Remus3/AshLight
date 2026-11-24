"""PLAY-TD-01B: the Play fit harness, red first (plan 03 section 11: G1, G2,
G4, G5, G6, G7, G9).

One headless Chrome and one page (app/test/cdp/play_fit.mjs) measure Play
and the other tab panels in every state of tests/play_states.py at the 5
cockpit sizes and the 2 flow sizes. Each state runs on its own fresh
core pinned to a temp Client.txt (discover off; the live log is never
found), all on one free test port in 8961-8979 (never 8960), so the page
keeps one URL while the state is swapped under it.

Every failed budget belongs to a scope: a Play region (#play-g, #play-c,
#play-t, #play-n, #play-b, #play-i, #play-u), a tab panel, the page, or the
skeleton (the placeholder-mode G2 proof of PLAY-TD-09B-SKELETON). A
failure is tolerated only while its pending marker exists: one one-line
reason file per region or tab in tests/play_fit_pending/. Region C has two
markers, c-setup (setup, idle and error modes: states a, d, e) and c-zone
(every other mode). A missing region is a failure of that region, so it
is pending exactly while its marker is. Page-wide budgets (word, element
and control totals, text styles) are pending while any region marker is;
page overflow (G1 on the page) is never pending since WEB-PLAY-FOOT-ONE-ROW
(the one-row footer took its last 13 px). The package that lands a region or a tab deletes its
marker; from then on that scope must hold in every state and size.

Skips cleanly without Chrome (or Edge) or node. Never touches the game,
the live Client.txt or port 8960.

    python tests/test_play_fit.py --figures   # the measured figures
"""

import contextlib
import html as htmllib
import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tools", ROOT / "tests", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import play_states as ps  # noqa: E402
import srcpaths  # noqa: E402
import synth_client  # noqa: E402
import fullstack_mocks as fs  # noqa: E402
from ci_timing import ci_scale  # noqa: E402
from server.al import VERSION, buildinfo, runs  # noqa: E402

pytestmark = pytest.mark.server

SCRIPT = ROOT / "app" / "test" / "cdp" / "play_fit.mjs"
PENDING_DIR = ROOT / "tests" / "play_fit_pending"
REGIONS = ("g", "c", "t", "n", "b", "i", "u")
REGION_MARKERS = ("g", "c-zone", "c-setup", "t", "n", "b", "i", "u")
TAB_MARKERS = ("tab-build", "tab-run", "tab-settings")
MARKERS = REGION_MARKERS + TAB_MARKERS
C_SETUP_STATES = frozenset({"a", "d", "e"})  # setup, idle, error (plan 03 3.4)

COCKPIT = ((1280, 760), (1920, 950), (1264, 821), (1024, 700), (1920, 875))
FLOW = ((1366, 650), (320, 640))
SIZES = COCKPIT + FLOW
# plan 03 3.2 / 3.8 track tables at s = 1 (px); C and I take the extra height
TRACKS = {"full": {"g": 100, "c": 228, "t": 204, "n": 96, "b": 68, "i": 360, "u": 100},
          "compact": {"g": 100, "c": 212, "t": 204, "n": 52, "b": 68, "i": 348, "u": 52}}
FRAME_H = {"full": 760, "compact": 700}
GROWS = ("c", "i")
SLACK_MIN = {1: 2, 1.25: 3}           # G4
I_SLACK_MIN = {"full": 16, "compact": 6}
WORD_CAPS = {"g": 20, "c": 52, "t": 50, "n": 22, "b": 16, "i": 60, "u": 24}  # G5
WORDS_MAX = 250
WORDS_STATE_MAX = {"b": 150, "a": 110}  # plain campaign zone, first run
ELEMENTS_MAX = 100
CONTROL_CAPS = {"g": 0, "c": 1, "n": 1, "b": 1, "i": 4, "u": 0}  # G6; t by trades
CONTROLS_BASE = 7
TARGET_MIN = 24
TYPE_RATIOS = (0.8125, 0.875, 1.0, 1.25, 1.75, 2.0)  # G7
FOOTER_ONLY = 0.8125
PLAY_STYLES_MAX = 9
TAB_STYLES_MAX = 8
STEP_TITLE, STEP_GLANCE, STEP_HERO = 1.25, 1.75, 2.0  # G9
TIMER_RE = r"\d{1,2}:\d{2}(:\d{2})?"
RED_FIRST_MIN_PX = 300  # plan 03 3.2: state c at 1280x760 is 380 px over today
# web/app.js reads the fragment token as hex only; play_states.TOKEN ("p" x 48)
# is not hex, so the page would never connect. The sweep swaps in a hex token
# for its own stacks and puts the recipe token back afterwards.
PAGE_TOKEN = "f" * 48
# WEB-PLAY-FIT-SETTINGS: the footer's version line names the checkout's HEAD
# commit (and ", dev" while hot reload is on), set in a proportional face, so
# its width moved with the commit: at 1024x700 one hash fit the footer on one
# row (32 px) and another wrapped it to two (45 px), and the harness gave a
# different Settings result per checkout. The sweep's cores answer one fixed
# build string instead, the long form (a commit and the dev mark). Since
# WEB-PLAY-FOOT-ONE-ROW the footer shows that build cut to 7 hex (always
# 7 characters, so its width moves by at most one letter), so even the long
# form keeps one 32 px row at 1024 px (FOOT_PX); the static Kindler page
# below still writes the full line.
PIN_COMMIT = "0123456789ab"
PIN_BUILD = buildinfo.compose(VERSION, PIN_COMMIT, True)
FOOT_PX = 32  # design 0001's footer budget: one row in compact and full


# -- markers ------------------------------------------------------------------

def read_pending(folder=PENDING_DIR):
    """The pending marker names (file stems) in the folder."""
    if not Path(folder).is_dir():
        return set()
    return {p.stem for p in Path(folder).glob("*.txt")}


def marker_for(scope, state):
    if scope == "c":
        return "c-setup" if state in C_SETUP_STATES else "c-zone"
    return scope


def covered(f, pending):
    scope = f["scope"]
    if scope == "page":
        if f["check"] == "G1":
            return False  # WEB-PLAY-FOOT-ONE-ROW: page overflow is enforced
        return any(m in pending for m in REGION_MARKERS)
    if scope == "skeleton":
        return False
    return marker_for(scope, f["state"]) in pending


def uncovered(fails, pending):
    return [f for f in fails if not covered(f, pending)]


def tab_scope(panel_id):
    pid = (panel_id or "").lower()
    if "run" in pid:
        return "tab-run"
    if "build" in pid or "item" in pid:
        return "tab-build"
    if "setting" in pid:
        return "tab-settings"
    return "page"


# -- sizes ----------------------------------------------------------------------

def size_class(w, h):
    """(class, s) by the scale rule of plan 03 3.1 at a 16 px default."""
    steps = [s for s in (1, 1.25, 1.5, 2) if w >= 1024 * s and h >= 700 * s]
    if not steps:
        return "flow", 1
    s = max(steps)
    return ("full" if w >= 1200 * s and h >= 760 * s else "compact"), s


def size_key(w, h):
    return f"{w}x{h}"


def parse_key(key):
    w, h = key.split("x")
    return int(w), int(h)


def expected_height(region, w, h):
    cls, s = size_class(w, h)
    track = TRACKS[cls][region] * s
    if region in GROWS:
        track += max(0.0, h - FRAME_H[cls] * s)
    return track


def control_cap(region, trades):
    if region == "t":
        return trades + (1 if trades >= 2 else 0)
    return CONTROL_CAPS[region]


# -- the 12 answers (G9) ----------------------------------------------------------

def build_word(snap):
    build = snap.get("build") or {}
    alert = snap.get("build_alert")
    if not build.get("loaded"):
        return "No build"
    if alert:
        return "Wrong class" if alert.get("kind") == "class" else "Old build"
    return "Build fits"


def answers_for(snap):
    """The answers this state can show, each with its region and its step
    (plan 03 section 11, G9). The driver finds each in its region."""
    out = [{"id": "what-to-do", "region": "c", "kind": "first", "min": STEP_TITLE},
           {"id": "build-right", "region": "b", "kind": "contains",
            "text": build_word(snap), "min": STEP_TITLE}]
    if snap.get("zone"):
        out += [{"id": "zone", "region": "g", "kind": "contains", "text": snap["zone"],
                 "min": STEP_GLANCE},
                {"id": "zone-time", "region": "g", "kind": "exact", "re": TIMER_RE,
                 "min": STEP_TITLE}]
    if snap.get("level") is not None:
        out.append({"id": "level", "region": "g", "kind": "exact", "text": str(snap["level"]),
                    "min": STEP_HERO})
    under = snap.get("underlevel") or {}
    if under.get("word"):
        out.append({"id": "under-level", "region": "g", "kind": "contains",
                    "text": under["word"], "min": STEP_TITLE})
    tailer = snap.get("tailer") or {}
    if tailer.get("consented"):
        out += [{"id": "deaths", "region": "g", "kind": "exact",
                 "text": str(snap.get("deaths") or 0), "min": STEP_HERO},
                {"id": "session", "region": "g", "kind": "exact", "re": TIMER_RE,
                 "min": STEP_HERO}]
    if tailer.get("reading"):
        out.append({"id": "reading", "region": "g", "scope": "bar", "kind": "contains",
                    "text": "reading", "min": STEP_TITLE})
    ev = snap.get("eval")
    if ev:
        # the Play card's own word once region I has it ("Not an item" for
        # a press error, where eval.text.word says "Not checked")
        item = (snap.get("play") or {}).get("item") or {}
        word = (item.get("word") or (ev.get("text") or {}).get("word")
                or (snap.get("card") or {}).get("head"))
        if word:
            out.append({"id": "upgrade", "region": "i", "kind": "contains", "text": word,
                        "min": STEP_GLANCE})
        price = (ev.get("value") or {}).get("price") or {}
        if price.get("amount") is not None and price.get("currency"):
            out.append({"id": "worth", "region": "i", "kind": "contains",
                        "re": r"\b%s\s*%s" % (price["amount"], price["currency"][:2]),
                        "flags": "i", "min": STEP_TITLE})
    trades = snap.get("trade_requests") or []
    if trades:
        newest = max(trades, key=lambda t: t.get("at") or 0)
        out.append({"id": "who-wants", "region": "t", "kind": "contains",
                    "text": newest["from"], "min": STEP_TITLE})
    return out


# -- verdicts ---------------------------------------------------------------------

def _scroll_fails(add, scope_of, scroll, state, key, flow):
    if flow:
        for sc in scroll.get("scrollers") or ():
            add(scope_of(sc.get("region")), "G1", state, key,
                f"nested scroll box {sc['el']} ({sc['sh']}x{sc['sw']} in {sc['ch']}x{sc['cw']})")
        return
    for o in scroll.get("over") or ():
        add(scope_of(o.get("region")), "G1", state, key,
            f"{o['el']} scrollHeight {o['sh']} > clientHeight {o['ch']}")


def _type_fails(add, scope_of, styles, state, key, max_styles):
    pairs = set()
    for t in styles:
        scope = scope_of(t.get("region"))
        ratio = t["ratio"]
        pairs.add((ratio, t["weight"]))
        if not any(abs(ratio - r) < 0.002 for r in TYPE_RATIOS) or abs(ratio - FOOTER_ONLY) < 0.002:
            add(scope, "G7", state, key, f"{t['el']} font {t['px']}px = {ratio} rem "
                f"({t['text']!r})")
        if t["weight"] >= 600 and t["px"] < 14:
            add(scope, "G7", state, key, f"{t['el']} weight {t['weight']} at {t['px']}px")
    if len(pairs) > max_styles:
        add(scope_of(None), "G7", state, key, f"{len(pairs)} text styles (max {max_styles})")


def fit_failures(sweep):
    """Every failed budget of a sweep as {scope, check, state, size, detail}."""
    fails = []

    def add(scope, check, state, size, detail):
        fails.append({"scope": scope, "check": check, "state": state, "size": size,
                      "detail": detail})

    play_scope = lambda r: r or "page"  # noqa: E731
    boxes = {}
    for state, st in sweep["states"].items():
        trades = st.get("trades", 0)
        if not st.get("live"):
            add("page", "load", state, "-", "the page never came live")
        for key, m in st["sizes"].items():
            w, h = parse_key(key)
            cls, s = size_class(w, h)
            flow = cls == "flow"
            play = m.get("play")
            if not play:
                add("page", "G1", state, key, "no #panel-play")
                continue
            d = m["doc"]
            if flow:
                if d["sw"] > d["cw"]:
                    add("page", "G1", state, key, f"horizontal scroll {d['sw'] - d['cw']} px")
            elif d["sh"] > d["ch"]:
                add("page", "G1", state, key, f"page {d['sh'] - d['ch']} px over")
            _scroll_fails(add, play_scope, play["scroll"], state, key, flow)
            for pid, p in (m.get("panels") or {}).items():
                ts = tab_scope(pid)
                pd = p["doc"]
                if flow:
                    if pd["sw"] > pd["cw"]:
                        add(ts, "G1", state, key, f"{pid}: horizontal scroll {pd['sw'] - pd['cw']} px")
                elif pd["sh"] > pd["ch"]:
                    add(ts, "G1", state, key, f"{pid}: page {pd['sh'] - pd['ch']} px over")
                _scroll_fails(add, lambda r, ts=ts: ts, p["scroll"], state, key, flow)
                if not flow:
                    _type_fails(add, lambda r, ts=ts: ts, p.get("type") or (), state, key,
                                TAB_STYLES_MAX)
            if flow:
                continue
            for r in REGIONS:
                rg = (play.get("regions") or {}).get(r)
                if rg is None:
                    add(r, "missing", state, key, f"#play-{r} is not on the page")
                    continue
                boxes.setdefault((key, r), []).append(
                    (state, round(rg["top"]), round(rg["left"]), round(rg["width"])))
                want = expected_height(r, w, h)
                if abs(rg["height"] - want) > 1:
                    add(r, "G2", state, key, f"height {rg['height']:.1f} px, track {want:g}")
                slack = math.floor(rg["inner"]) - math.ceil(rg["content"])
                need = I_SLACK_MIN[cls] if r == "i" else SLACK_MIN.get(s, 3)
                if slack < need:
                    add(r, "G4", state, key, f"slack {slack} px (min {need})")
                if rg["words"] > WORD_CAPS[r]:
                    add(r, "G5", state, key, f"{rg['words']} words (cap {WORD_CAPS[r]})")
                cap = control_cap(r, trades)
                if len(rg["controls"]) > cap:
                    add(r, "G6", state, key, f"{len(rg['controls'])} controls (cap {cap})")
            words_max = min(WORDS_MAX, WORDS_STATE_MAX.get(state, WORDS_MAX))
            if play["words"] > words_max:
                add("page", "G5", state, key, f"{play['words']} words on Play (max {words_max})")
            if play["elements"] > ELEMENTS_MAX:
                add("page", "G5", state, key,
                    f"{play['elements']} visible elements (max {ELEMENTS_MAX})")
            ctl_max = CONTROLS_BASE + control_cap("t", trades)
            if len(play["controls"]) > ctl_max:
                add("page", "G6", state, key, f"{len(play['controls'])} controls (max {ctl_max})")
            for c in play["controls"]:
                if c["w"] < TARGET_MIN or c["h"] < TARGET_MIN:
                    add(play_scope(c.get("region")), "G6", state, key,
                        f"{c['el']} is {c['w']:.0f}x{c['h']:.0f} px (min {TARGET_MIN})")
            _type_fails(add, play_scope, play.get("type") or (), state, key, PLAY_STYLES_MAX)
            for a in play.get("answers") or ():
                if not a.get("ok"):
                    region = next((x["region"] for x in st.get("answers", ())
                                   if x["id"] == a["id"]), "page")
                    add(region, "G9", state, key, f"{a['id']}: {a.get('why')} "
                        f"({a.get('el', '-')}, {a.get('ratio', '-')} rem, word {a.get('pos', '-')})")
    for (key, r), seen in boxes.items():
        ref = Counter(b[1:] for b in seen).most_common(1)[0][0]
        for state, *pos in seen:
            if any(abs(a - b) > 1 for a, b in zip(pos, ref)):
                add(r, "G2", state, key, f"box at {tuple(pos)}, other states at {ref}")
    for key, m in (sweep.get("placeholder") or {}).items():
        w, h = parse_key(key)
        for r in REGIONS:
            rg = ((m.get("play") or {}).get("regions") or {}).get(r)
            if rg is None:
                add(r, "missing", "placeholder", key, f"#play-{r} is not on the page")
                continue
            want = expected_height(r, w, h)
            if abs(rg["height"] - want) > 1:
                add("skeleton", "G2", "placeholder", key,
                    f"#play-{r} height {rg['height']:.1f} px, track {want:g}")
    return fails


def over_px(m):
    """How far the Play panel runs over at one size: the page overflow or
    the worst element under the panel (today's columns scroll inside)."""
    play = m.get("play") or {}
    return max(m["doc"]["sh"] - m["doc"]["ch"], (play.get("scroll") or {}).get("overMax", 0))


def today_layout(sweep):
    """True while no measured page holds any Play region (the layout
    before PLAY-TD-09B-SKELETON)."""
    for st in sweep["states"].values():
        for m in st["sizes"].values():
            regions = (m.get("play") or {}).get("regions") or {}
            if any(regions.get(r) for r in REGIONS):
                return False
    return True


# -- the sweep ----------------------------------------------------------------------

_BROWSERS = (r"Google\Chrome\Application\chrome.exe",
             r"Microsoft\Edge\Application\msedge.exe")


def find_browser():
    """A private copy of the dashboard console test's browser finder."""
    env = os.environ.get("AL_CHROME", "").strip().strip('"')
    if env and Path(env).is_file():
        return env
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        for rel in _BROWSERS if base else ():
            p = Path(base) / rel
            if p.is_file():
                return str(p)
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        hit = shutil.which(name)
        if hit:
            return hit
    return None


class Driver:
    """The play_fit.mjs process: one JSON command in, one JSON line out."""

    def __init__(self, node, browser, profile):
        self.proc = subprocess.Popen(
            [node, str(SCRIPT), browser, str(profile)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.lines = queue.Queue()
        self.err = []
        threading.Thread(target=self._pump, args=(self.proc.stdout, self.lines.put),
                         daemon=True).start()
        threading.Thread(target=self._pump, args=(self.proc.stderr, self.err.append),
                         daemon=True).start()
        self._read(ci_scale(60))

    @staticmethod
    def _pump(stream, put):
        for line in stream:
            put(line)

    def _read(self, timeout):
        try:
            line = self.lines.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError(f"play_fit.mjs gave no answer in {timeout} s; "
                               f"stderr: {''.join(self.err)[-1500:]}") from None
        doc = json.loads(line)
        if "error" in doc:
            raise RuntimeError(f"play_fit.mjs: {doc['error']}")
        return doc

    def call(self, cmd, timeout=90):
        self.proc.stdin.write(json.dumps(cmd) + "\n")
        self.proc.stdin.flush()
        return self._read(ci_scale(timeout))  # decision 0080: 3x under AL_CI=1

    def close(self):
        try:
            if self.proc.poll() is None:
                self.proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=15)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            self.proc.kill()
            self.proc.wait(timeout=15)


METRIC_ROWS = (  # plan 03 3.4 character budgets: (key, px, weight)
    ("context_title", 20, 600), ("context_row", 16, 400), ("notice_row", 16, 400),
    ("event_sentence", 16, 400), ("build_row", 16, 400), ("item_sentence", 16, 400),
    ("kept_row", 14, 400), ("notice_word", 20, 600), ("notice_title", 16, 600),
    ("notice_action", 16, 400))


def metric_rows():
    rows = []
    for key, px, weight in METRIC_ROWS:
        text = ps.LONG_ROWS[key]
        text = text[0] if isinstance(text, tuple) else text
        rows.append({"key": key, "text": text, "px": px, "weight": weight})
    return rows


# -- RUN-CARDS-PAGE-FIT: the 10-row fit state -------------------------------------
#
# The Run tab's Acts, Maps and Deaths cards page their lists; a page must fit
# its card when it is full. No recipe of tests/play_states.py fills a page:
# the core sends at most RECENT_MAPS finished maps and RECENT_DEATHS deaths
# (5 each), so this harness-only state lifts both caps to ROWS_FILL for its
# own core (in this process, restored on close) and drives a synthetic run
# through 11 acts and 12 maps with a death in each (two in the last, so the
# Deaths card's most deaths line shows). Every list then holds more rows
# than a page, so each card shows a full first page.

ROWS_STATE = "rows10"
ROWS_FILL = 12
ROWS_MIN = 10  # the rows each list must hold (more than any page)
ROWS_ACTS = (("G1_1", 1, "The Riverbank"), ("G2_1", 16, "Vastiri Outskirts"),
             ("G3_1", 33, "Sandswept Marsh"), ("G4_1", 45, "Isle of Kin"),
             ("P1_1", 46, "Example Interlude One"), ("P2_1", 47, "Example Interlude Two"),
             ("P3_1", 48, "Example Interlude Three"), ("C_G1_1", 50, "Example Cruel One"),
             ("C_G2_1", 52, "Example Cruel Two"), ("C_G3_1", 54, "Example Cruel Three"),
             ("C_G4_1", 56, "Example Cruel Four"))
FIT_STATES = ps.STATES + (ROWS_STATE,)


def rows_counts(snap):
    """(act rows, map rows, death rows) the Run cards list for a snapshot
    (web/acts.js splitRows, web/runs.js mapRows and the death recap)."""
    maps = snap.get("maps") or {}
    acts_part = snap.get("acts") or {}
    recap = snap.get("death_recap") or {}
    return (len(acts_part.get("splits") or ()),
            len(maps.get("recent") or ()) + (1 if maps.get("current") else 0),
            len(recap.get("recent") or ()))


def _rows_recipe(st):
    ps._consent(st)
    s = synth_client.Session(seed=47, character="Rowdemo", klass="Ranger")
    s.marker()
    s.raw("[WINDOW] Gained focus")
    for aid, lvl, name in ROWS_ACTS:
        s.zone_change(aid, lvl, name)
        s.level_up()
    for i in range(ROWS_FILL):
        s.zone_change(*fs.HIDEOUT)
        s.zone_change(f"MapRow{i}", 65 + i % 10, f"Example Map {i}", seed=470 + i)
        s.death()
    s.death()  # a second death in the open map: the most deaths line shows too
    st.append(s)
    return st.wait_for(lambda x: min(rows_counts(x)) >= ROWS_MIN
                       and (x.get("death_recap") or {}).get("worst_text"),
                       "10 rows on each Run card")


@contextlib.contextmanager
def open_rows_state(root, port=None):
    """The 10-row fit state on its own PlayStack; the core's recent caps are
    lifted for its life and put back afterwards."""
    saved = runs.RECENT_MAPS, runs.RECENT_DEATHS
    runs.RECENT_MAPS = runs.RECENT_DEATHS = ROWS_FILL
    try:
        st = ps.PlayStack(Path(root), port=port)
        try:
            _rows_recipe(st)
            st.pinned()
            yield st
        finally:
            st.close()
    finally:
        runs.RECENT_MAPS, runs.RECENT_DEATHS = saved


def _opener(name):
    if name == ROWS_STATE:
        return open_rows_state
    return lambda root, port=None: ps.open_state(name, root, port=port)


@contextlib.contextmanager
def _open_state(name, root, port):
    """The state on the previous state's port (one page URL for the whole
    sweep); a fresh free test port when another test took that one."""
    for i, want in enumerate((port, None) if port else (None,)):
        stack = contextlib.ExitStack()
        try:
            st = stack.enter_context(_opener(name)(root / f"{name}-{i}", port=want))
        except OSError:
            stack.close()
            if want is None:
                raise
            continue
        with stack:
            yield st
        return


def run_sweep(root, browser, node):
    """Every state at every size, then the placeholder mode and the
    character-budget metrics, on one page. Returns the sweep document."""
    root = Path(root)
    drv = Driver(node, browser, root / "chrome")
    sweep = {"states": {}, "placeholder": {}, "metrics": [], "seconds": 0.0}
    t0 = time.monotonic()
    port = None
    recipe_token, ps.TOKEN = ps.TOKEN, PAGE_TOKEN
    real_build_id = buildinfo.build_id
    buildinfo.build_id = lambda *a, **k: PIN_BUILD
    try:
        for name in FIT_STATES:
            with _open_state(name, root, port) as st:
                port = st.port
                snap = st.state()
                answers = answers_for(snap)
                r = drv.call({"cmd": "state", "url": st.url, "name": name,
                              "sizes": [list(x) for x in SIZES], "answers": answers})
                sweep["states"][name] = {"live": r["live"], "sizes": r["sizes"],
                                         "trades": len(snap.get("trade_requests") or ()),
                                         "answers": answers, "rows": rows_counts(snap)}
                if name == FIT_STATES[-1]:
                    ph = drv.call({"cmd": "placeholder", "sizes": [list(x) for x in COCKPIT]})
                    sweep["placeholder"] = ph["sizes"]
                    sweep["metrics"] = drv.call({"cmd": "metrics", "rows": metric_rows()})["rows"]
    finally:
        ps.TOKEN = recipe_token
        buildinfo.build_id = real_build_id
        drv.close()
    sweep["seconds"] = round(time.monotonic() - t0, 1)
    return sweep


@pytest.fixture(scope="module")
def sweep(tmp_path_factory):
    browser = find_browser()
    node = shutil.which("node")
    if not browser or not node:
        pytest.skip("headless Chrome / Edge or node not found")
    return run_sweep(tmp_path_factory.mktemp("play_fit"), browser, node)


def _report(fails, limit=40):
    lines = [f"[{f['scope']}] {f['check']} {f['state']} {f['size']}: {f['detail']}"
             for f in fails[:limit]]
    if len(fails) > limit:
        lines.append(f"... {len(fails) - limit} more")
    return "\n".join(lines)


# -- tests without a browser ---------------------------------------------------------

def test_pending_markers_are_known_one_line_reasons():
    assert PENDING_DIR.is_dir()
    for p in sorted(PENDING_DIR.iterdir()):
        assert p.suffix == ".txt" and p.stem in MARKERS, f"unknown pending marker {p.name}"
        raw = p.read_bytes()
        assert raw.isascii() and b"\r" not in raw, p.name
        text = raw.decode("ascii")
        assert text.endswith("\n") and text.count("\n") == 1 and text.strip(), \
            f"{p.name}: one line of reason, LF-terminated"


def test_size_classes_follow_the_scale_rule():
    assert size_class(1280, 760) == ("full", 1)
    assert size_class(1920, 950) == ("full", 1.25)
    assert size_class(1264, 821) == ("full", 1)
    assert size_class(1024, 700) == ("compact", 1)
    assert size_class(1920, 875) == ("compact", 1.25)
    assert size_class(1366, 650)[0] == "flow"
    assert size_class(320, 640)[0] == "flow"
    # the extra height of the client default goes to C and I only
    assert expected_height("c", 1264, 821) == 228 + 61
    assert expected_height("i", 1264, 821) == 360 + 61
    assert expected_height("t", 1264, 821) == 204
    assert expected_height("u", 1920, 875) == 52 * 1.25
    # the track tables sum to the grid (plan 03 3.2, 3.8)
    for cls, gap in (("full", 8), ("compact", 8)):
        tr = TRACKS[cls]
        left = tr["g"] + gap + tr["c"] + gap + tr["t"] + gap + tr["n"]
        right = tr["g"] + gap + tr["b"] + gap + tr["i"] + gap + tr["u"]
        assert left == right == FRAME_H[cls] - 108


def _fake_region(height, words=1, controls=0, top=100, slack=20):
    return {"top": top, "left": 16, "width": 500, "height": height,
            "inner": top + height - 10, "content": top + height - 10 - slack,
            "words": words, "controls": [{"el": "button", "w": 40, "h": 32}] * controls,
            "fit": "yes"}


def _fake_sweep(regions=True, over=0, state="c", size=(1280, 760), region_patch=None):
    w, h = size
    cls, _s = size_class(w, h)
    regs = {r: (_fake_region(expected_height(r, w, h)) if regions else None) for r in REGIONS}
    regs.update(region_patch or {})
    m = {"doc": {"sh": h + over, "ch": h, "sw": w, "cw": w}, "panels": {},
         "play": {"words": 50, "elements": 40, "controls": [], "type": [],
                  "scroll": {"over": [], "scrollers": []}, "regions": regs, "answers": []}}
    return {"states": {state: {"live": True, "trades": 0, "answers": [],
                               "sizes": {size_key(w, h): m}}}}


def test_a_fitting_page_has_no_failure():
    assert fit_failures(_fake_sweep()) == []


def test_missing_regions_and_overflow_are_pending_only_while_marked():
    sw = _fake_sweep(regions=False, over=380)
    fails = fit_failures(sw)
    assert {f["scope"] for f in fails} == {"page", *REGIONS}
    # WEB-PLAY-FOOT-ONE-ROW: page overflow is never pending
    over = [f for f in fails if f["scope"] == "page" and f["check"] == "G1"]
    assert over and uncovered(fails, set(MARKERS)) == over
    fails = [f for f in fails if f not in over]
    sw["states"]["c"]["sizes"]["1280x760"]["play"]["words"] = 999
    fails += [f for f in fit_failures(sw) if f["scope"] == "page" and f["check"] == "G5"]
    assert any(f["scope"] == "page" for f in fails)
    assert uncovered(fails, set(MARKERS)) == []
    # deleting a marker while its region is still missing turns it red
    for marker in REGION_MARKERS:
        if marker == "c-setup":
            continue  # state c is a zone state: c-zone owns its region C
        left = uncovered(fails, set(MARKERS) - {marker})
        assert left and all(marker_for(f["scope"], f["state"]) == marker for f in left), marker
    # page-wide budgets stay pending while any region marker is left
    page = [f for f in fails if f["scope"] == "page"]
    assert uncovered(page, {"u"}) == []
    assert uncovered(page, set(TAB_MARKERS)) == page


def test_region_c_has_one_marker_per_mode_group():
    for state, marker in (("a", "c-setup"), ("d", "c-setup"), ("e", "c-setup"),
                          ("a2", "c-zone"), ("b", "c-zone"), ("c", "c-zone"),
                          ("f", "c-zone"), ("map", "c-zone"), ("long", "c-zone")):
        assert marker_for("c", state) == marker, state
        f = {"scope": "c", "state": state}
        assert covered(f, {marker}) and not covered(f, set(MARKERS) - {marker})


def test_each_budget_fails_on_its_own_region():
    big = _fake_region(228, words=99, controls=3, slack=0)
    fails = fit_failures(_fake_sweep(region_patch={"c": big}))
    assert {f["check"] for f in fails} == {"G4", "G5", "G6"}
    assert {f["scope"] for f in fails} == {"c"}
    tall = _fake_region(300)
    fails = fit_failures(_fake_sweep(region_patch={"t": tall}))
    assert [(f["scope"], f["check"]) for f in fails] == [("t", "G2")]
    # region I keeps 16 px in the full class
    thin = _fake_region(360, slack=10)
    fails = fit_failures(_fake_sweep(region_patch={"i": thin}))
    assert [(f["scope"], f["check"]) for f in fails] == [("i", "G4")]


def test_placeholder_g2_is_the_skeleton_proof_and_never_pending():
    sw = _fake_sweep()
    sw["placeholder"] = {"1280x760": {"play": {"regions": {
        r: _fake_region(expected_height(r, 1280, 760) + (5 if r == "n" else 0))
        for r in REGIONS}}}}
    fails = fit_failures(sw)
    assert [(f["scope"], f["check"]) for f in fails] == [("skeleton", "G2")]
    assert uncovered(fails, set(MARKERS)) == fails


def test_tab_panels_map_to_their_markers():
    assert tab_scope("panel-run") == "tab-run"
    assert tab_scope("panel-build") == "tab-build"
    assert tab_scope("panel-items") == "tab-build"
    assert tab_scope("panel-settings") == "tab-settings"


def test_answers_name_their_regions_and_steps():
    snap = {"zone": "Clearfell", "level": 4, "deaths": 1, "underlevel": {"word": "2 lv under"},
            "tailer": {"consented": True, "reading": True},
            "build": {"loaded": True}, "build_alert": {"kind": "class"},
            "eval": {"text": {"word": "Upgrade"},
                     "value": {"price": {"amount": 5, "currency": "exalted"}}},
            "trade_requests": [{"from": "Old", "at": 1}, {"from": "Newest", "at": 2}]}
    got = {a["id"]: a for a in answers_for(snap)}
    assert set(got) == {"zone", "zone-time", "what-to-do", "upgrade", "worth", "who-wants",
                        "level", "under-level", "deaths", "session", "reading",
                        "build-right"}
    assert got["who-wants"]["text"] == "Newest"
    assert got["build-right"]["text"] == "Wrong class"
    assert {a["min"] for a in got.values()} <= {STEP_TITLE, STEP_GLANCE, STEP_HERO}
    assert {k for k, a in got.items() if a["min"] == STEP_HERO} == {"level", "deaths", "session"}
    assert build_word({"build": {}}) == "No build"
    assert build_word({"build": {"loaded": True}, "build_alert": {"kind": "level"}}) == "Old build"


# -- the browser sweep ------------------------------------------------------------------

def test_every_state_and_size_was_measured(sweep):
    assert tuple(sweep["states"]) == FIT_STATES
    for name, st in sweep["states"].items():
        assert st["live"], f"state {name}: the page never came live"
        assert set(st["sizes"]) == {size_key(w, h) for w, h in SIZES}, name
        for key, m in st["sizes"].items():
            assert (m["vw"], m["vh"]) == parse_key(key), (name, key)
            assert m["play"] is not None, (name, key)
    assert set(sweep["placeholder"]) == {size_key(w, h) for w, h in COCKPIT}


def test_the_rows_state_fills_every_run_list(sweep):
    """RUN-CARDS-PAGE-FIT: Acts, Maps and Deaths each hold at least 10 rows
    in the fit state, so their first page is full while it is measured."""
    acts_n, maps_n, deaths_n = sweep["states"][ROWS_STATE]["rows"]
    assert min(acts_n, maps_n, deaths_n) >= ROWS_MIN, (acts_n, maps_n, deaths_n)


def test_the_rows_state_puts_the_core_caps_back(tmp_path):
    before = runs.RECENT_MAPS, runs.RECENT_DEATHS
    with open_rows_state(tmp_path / "rows") as st:
        assert min(rows_counts(st.state())) >= ROWS_MIN
    assert (runs.RECENT_MAPS, runs.RECENT_DEATHS) == before


def test_the_footer_is_the_same_in_every_checkout(sweep):
    """WEB-PLAY-FIT-SETTINGS: the sweep's cores answer the pinned build, so
    the footer has one height per size in every state, whatever the
    checkout's commit; WEB-PLAY-FOOT-ONE-ROW: it is one 32 px row at every
    cockpit size at s = 1, 1024x700 included."""
    assert buildinfo.build_id.__module__ == buildinfo.__name__  # put back after the sweep
    for key in (size_key(w, h) for w, h in COCKPIT):
        feet = {name: round(st["sizes"][key]["play"]["frame"]["foot"])
                for name, st in sweep["states"].items()}
        assert len(set(feet.values())) == 1, (key, feet)
    for key in ("1280x760", "1264x821", "1024x700"):
        foot = round(sweep["states"][FIT_STATES[0]]["sizes"][key]["play"]["frame"]["foot"])
        assert foot == FOOT_PX, (key, foot)


def test_play_fits_or_is_pending(sweep):
    pending = read_pending()
    left = uncovered(fit_failures(sweep), pending)
    assert not left, ("budgets failed outside every pending marker "
                      f"(pending: {', '.join(sorted(pending)) or 'none'}):\n" + _report(left))


def test_red_first_on_todays_layout(sweep):
    """While no region has landed, state c at 1280x760 is far over the page
    and deleting any pending marker turns the harness red."""
    pending = read_pending()
    if not today_layout(sweep) or not set(REGION_MARKERS) <= pending:
        pytest.skip("a Play region has landed: the red-first proof is done")
    over = over_px(sweep["states"]["c"]["sizes"]["1280x760"])
    assert over > RED_FIRST_MIN_PX, f"state c at 1280x760 is only {over} px over"
    fails = fit_failures(sweep)
    for marker in sorted(pending):
        left = uncovered(fails, pending - {marker})
        assert left, f"deleting {marker} would leave the harness green"


def figures(sweep):
    """The measured figures of today's Play as Markdown lines."""
    out = [f"Sweep: {len(sweep['states'])} states x {len(SIZES)} sizes in "
           f"{sweep['seconds']} s.", ""]
    for state in ("c", "c2", "d", "long", "c5"):
        for key in ("1280x760", "1920x950", "1264x821", "1024x700", "1920x875"):
            m = sweep["states"][state]["sizes"][key]
            p, fr = m["play"], m["play"]["frame"]
            cols = ", ".join(f"{c['el']} {c['height']:.0f} (scroll {c['sh']})"
                             for c in fr["cols"])
            styles = len({(t["ratio"], t["weight"]) for t in p["type"]})
            out.append(f"- {state} {key}: root {m['root']:g} px, Play "
                       f"{over_px(m)} px over, bar {fr['bar']:.0f}, "
                       f"main padding {fr['mainPad'][0]:g} + {fr['mainPad'][1]:g}, footer "
                       f"{fr['foot']:.0f}; words {p['words']}, elements {p['elements']}, "
                       f"controls {len(p['controls'])}, text styles {styles}; columns: {cols}")
    out.append("")
    for r in sweep["metrics"]:
        out.append(f"- {r['key']}: {r['chars']} chars at {r['px']} px / {r['weight']}: "
                   f"{r['width']} px, {r['spaced']} px with the 1.4.12 override")
    return out


# -- PLAY-PAGER-SCALE-24: the 24 px floor below UI scale 1 -----------------------
#
# The scale step --al-s is 1 or more at the cockpit sizes, but the root is
# 100% of the viewer's default font size times s, so a smaller default font
# (or a lowered --al-s) shrinks every rem. The pager buttons and the compact
# weight inputs keep a 24 px target there (WCAG 2.2 SC 2.5.8): a static page
# on the real stylesheets, web/pager.js and the Item scoring card of the
# assembled page, measured by the browser's own --dump-dom run (no core, no
# network, no port). At s = 1 the floor changes nothing (1.5rem is 24 px).

SCALES = (0.75, 0.875, 1)
SCALE_SIZES = ((1280, 760), (1024, 700), (320, 640))
SCALE_OUT = "al-scale-out"

_SCALE_JS = r"""
(function () {
  var out = {}, de = document.documentElement;
  var rows = [];
  for (var i = 0; i < 30; i++) { rows.push("Row " + i); }
  var pg = window.ALPager.build(document, { rows: rows, label: "rows", sizeClass: "full" });
  document.getElementById("al-pager-slot").appendChild(pg.node);
  var list = document.getElementById("weights-list");
  for (var j = 0; j < 9; j++) {
    var li = document.createElement("li"), lab = document.createElement("label");
    var inp = document.createElement("input");
    lab.htmlFor = "w-" + j; lab.textContent = "Stat " + j;
    inp.type = "number"; inp.step = "any"; inp.id = "w-" + j; inp.value = "1.5";
    inp.setAttribute("data-key", "k" + j); inp.setAttribute("inputmode", "decimal");
    li.appendChild(lab); li.appendChild(inp); list.appendChild(li);
  }
  var wp = document.getElementById("weights-pager");
  ["Prev", "Next"].forEach(function (t) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "al-pager-btn"; b.textContent = t; wp.appendChild(b);
  });
  Array.prototype.forEach.call(document.querySelectorAll("#weightsbox .card-page[hidden]"),
    function (p) { p.removeAttribute("hidden"); });
  var box = function (e) { var r = e.getBoundingClientRect(); return [r.width, r.height]; };
  var SCALES = __SCALES__;
  SCALES.forEach(function (s) {
    de.style.setProperty("--al-s", String(s));
    var m = { root: parseFloat(getComputedStyle(de).fontSize), pager: [], inputs: [], rows: [] };
    Array.prototype.forEach.call(document.querySelectorAll("button.al-pager-btn"), function (b) {
      if (b.hidden) { return; }
      var off = b.getAttribute("aria-disabled") === "true", cs = getComputedStyle(b);
      var e = { text: b.textContent, off: off, box: box(b),
                edge: [cs.borderTopStyle, parseFloat(cs.borderTopWidth)] };
      if (off) {
        b.removeAttribute("aria-disabled");
        e.onBox = box(b);
        b.setAttribute("aria-disabled", "true");
      }
      m.pager.push(e);
    });
    Array.prototype.forEach.call(document.querySelectorAll("#weightsbox .weights-form input"),
      function (inp) { m.inputs.push({ id: inp.id, box: box(inp) }); });
    Array.prototype.forEach.call(document.querySelectorAll("#weights-list li"), function (li) {
      var r = li.getBoundingClientRect(), ir = li.querySelector("input").getBoundingClientRect();
      m.rows.push({ h: r.height, over: Math.max(0, r.top - ir.top, ir.bottom - r.bottom) });
    });
    out[String(s)] = m;
  });
  document.getElementById("__OUT__").textContent = JSON.stringify(out);
}());
"""


def _file_url(path):
    return Path(path).resolve().as_uri()


def scale_page(scales=SCALES):
    """The static measuring page: every stylesheet of the assembled page
    (tokens from the fleet kit), a pager from web/pager.js and the Item
    scoring card, then the script that measures at each scale."""
    html = srcpaths.index_html(encoding="utf-8")
    links = []
    for href in re.findall(r'<link rel="stylesheet" href="([^"]+)">', html):
        if href == "/tokens.css":
            links.append(ROOT / "ops" / "fleet_kit" / "tokens.css")
        elif href.startswith("/web/"):
            links.append(srcpaths.path(href[len("/web/"):]))
    i = html.index('<section id="weightsbox"')
    weights = html[i:html.index("</section>", i) + len("</section>")]
    js = _SCALE_JS.replace("__SCALES__", json.dumps(list(scales))).replace("__OUT__", SCALE_OUT)
    head = "".join(f'<link rel="stylesheet" href="{_file_url(p)}">\n' for p in links)
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>scale floor</title>\n{head}</head>\n<body>\n<main>\n"
            "<section id=\"al-pagerbox\" class=\"card grid-card\">"
            "<div id=\"al-pager-slot\" class=\"pager-slot\"></div></section>\n"
            f"{weights}\n</main>\n<pre id=\"{SCALE_OUT}\"></pre>\n"
            f"<script src=\"{_file_url(srcpaths.path('pager.js'))}\"></script>\n"
            f"<script>{js}</script>\n</body>\n</html>\n")


def measure_scales(browser, folder, size):
    """{scale: measures} for the page at one window size, read back from
    the browser's --dump-dom output."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    page = folder / "scale.html"
    page.write_text(scale_page(), encoding="utf-8")
    w, h = size
    cmd = [browser, "--headless=new", "--disable-gpu", "--in-process-gpu", "--no-first-run",
           "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars",
           "--force-device-scale-factor=1",
           f"--user-data-dir={folder / 'profile'}", f"--window-size={w},{h}",
           "--dump-dom", page.as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=ci_scale(90))
    m = re.search(r'<pre id="' + SCALE_OUT + r'">(.*?)</pre>', r.stdout, re.S)
    assert m and m.group(1).strip(), f"no measures at {w}x{h}; stderr: {r.stderr[-1500:]}"
    return json.loads(htmllib.unescape(m.group(1)))


def scale_failures(measures, size):
    """Every target under 24 px, every disabled pager button whose box
    differs from its enabled box or whose dashed edge is under 2 px, and
    every weight row its input overflows."""
    fails = []
    key = size_key(*size)
    for s, m in measures.items():
        where = f"s={s} {key} (root {m['root']:g} px)"
        if not m["pager"] or not m["inputs"]:
            fails.append(f"{where}: nothing measured")
        for b in m["pager"]:
            bw, bh = b["box"]
            if bw < TARGET_MIN - 0.01 or bh < TARGET_MIN - 0.01:
                fails.append(f"{where}: pager button {b['text']!r} is {bw:.1f}x{bh:.1f} px")
            if b["off"]:
                if b["edge"][0] != "dashed" or b["edge"][1] < 2:
                    fails.append(f"{where}: disabled {b['text']!r} edge {b['edge']}")
                if any(abs(a - c) > 0.01 for a, c in zip(b["box"], b["onBox"])):
                    fails.append(f"{where}: disabled {b['text']!r} box {b['box']} "
                                 f"against {b['onBox']} enabled")
        for inp in m["inputs"]:
            iw, ih = inp["box"]
            if ih < TARGET_MIN - 0.01:
                fails.append(f"{where}: weight input {inp['id']} is {iw:.1f}x{ih:.1f} px")
        for row in m["rows"]:
            if row["over"] > 0.01:
                fails.append(f"{where}: a weight input runs {row['over']:.1f} px out of its row")
    return fails


def test_scale_failures_catch_small_and_shifting_targets():
    ok = {"1": {"root": 16, "pager": [{"text": "Prev", "off": True, "box": [44, 24],
                                       "onBox": [44, 24], "edge": ["dashed", 2]}],
                "inputs": [{"id": "w-0", "box": [84, 24]}], "rows": [{"h": 24, "over": 0}]}}
    assert scale_failures(ok, (1280, 760)) == []
    bad = json.loads(json.dumps(ok))
    m = bad["1"]
    m["pager"][0].update(box=[30, 18], onBox=[32, 18], edge=["dashed", 1])
    m["inputs"][0]["box"] = [63, 19]
    m["rows"][0]["over"] = 3
    fails = scale_failures(bad, (1280, 760))
    assert len(fails) == 5, fails


@pytest.fixture(scope="module")
def scale_measures(tmp_path_factory):
    browser = find_browser()
    if not browser:
        pytest.skip("headless Chrome / Edge not found")
    root = tmp_path_factory.mktemp("scale_floor")
    return {size: measure_scales(browser, root / size_key(*size), size) for size in SCALE_SIZES}


def test_pager_and_weight_inputs_keep_24px_below_scale_1(scale_measures):
    fails = []
    for size, measures in scale_measures.items():
        assert set(measures) == {str(s) for s in SCALES}, measures.keys()
        for s in SCALES:
            if s < 1:
                assert measures[str(s)]["root"] < 16, (size, s)
        fails += scale_failures(measures, size)
    assert not fails, "\n".join(fails[:40])


def test_floor_leaves_scale_1_unchanged(scale_measures):
    """At s = 1 max(24px, 1.5rem) is 1.5rem: the pager buttons and the
    weight inputs stay 24 px tall, so the cockpit fit is untouched."""
    for size, measures in scale_measures.items():
        m = measures["1"]
        assert m["root"] == 16, size
        for b in m["pager"]:
            assert abs(b["box"][1] - TARGET_MIN) < 0.01, (size, b)
        for inp in m["inputs"]:
            assert abs(inp["box"][1] - TARGET_MIN) < 0.01, (size, inp)


# -- CP-1: the Characters card picker line keeps its select at narrow sizes ----
#
# The picker line (#char-pick-box: label, the pin chip web/chars.js adds,
# select) used to stay on one line, so at 320 px the select shrank to 24 px
# wide and the pin's words broke over four lines. Now it wraps: the label
# and the pin keep one line each, and the select keeps at least its widest
# name or the whole line, so its shown choice reads in full and it stays a
# 24 px target. At the two tightest cockpit sizes the picker at its tallest
# (the pin's failure line showing) plus web/chars.js ROWS rows of 22 px and
# the pager row fit the Characters card. Measured on a static page (the real
# stylesheets and the Run panel of the assembled page) inside srcdoc
# iframes, so the viewport is the exact size (a headless window cannot go
# below about 500 px wide), read back by the browser's own --dump-dom run
# (no core, no network, no port).

PICK_SIZES = ((320, 640), (1024, 700), (1280, 760))
PICK_OUT = "al-pick-out"
PICK_NAMES = ("Rowdemo (playing now)", "Wanderingblademaster")  # web/chars.js PLAYING
PIN_WORDS = "This is my character"  # web/chars.js PIN_LABEL
# room under the Characters title (web/chars.js ROWS comment): size class, px
CHARS_ROOM = {(1280, 760): ("full", 244), (1024, 700): ("compact", 204)}
CHARS_ROW_PX, CHARS_GAP_PX, CHARS_PAGER_PX = 22, 4, 24
SAID = " said"  # the measure key suffix of a frame whose failure line shows


def chars_consts():
    """(ROWS {size class: rows}, PIN_FAILED) read from web/chars.js, so a
    stale constant fails the fit check."""
    src = srcpaths.path("chars.js").read_text(encoding="utf-8")
    m = re.search(r"var ROWS = \{ full: (\d+), compact: (\d+) \};", src)
    f = re.search(r'var PIN_FAILED = "([^"]+)";', src)
    assert m and f, "web/chars.js ROWS or PIN_FAILED moved"
    return {"full": int(m.group(1)), "compact": int(m.group(2))}, f.group(1)

_PICK_JS = r"""
(function () {
  var box = document.getElementById("char-pick-box"), sel = document.getElementById("char-pick");
  box.hidden = false;
  __NAMES__.forEach(function (n) {
    var o = document.createElement("option"); o.textContent = n; sel.appendChild(o);
  });
  var pin = document.createElement("button");
  pin.type = "button"; pin.id = "char-pin"; pin.className = "chip";
  pin.setAttribute("data-label", __PIN__); pin.setAttribute("aria-pressed", "false");
  pin.textContent = __PIN__; box.insertBefore(pin, sel);  // web/chars.js pinButton
  var said = document.createElement("span");
  said.id = "char-pin-said"; said.className = "muted"; box.appendChild(said);
  var say = !!(window.frameElement && window.frameElement.getAttribute("data-say"));
  if (say) { said.textContent = __SAID__; }
  var rect = function (e) { var r = e.getBoundingClientRect();
    return { l: r.left, r: r.right, w: r.width, h: r.height }; };
  var lines = function (e) { var g = document.createRange(); g.selectNodeContents(e);
    var tops = []; Array.prototype.forEach.call(g.getClientRects(), function (q) {
      if (q.width > 0 && tops.indexOf(Math.round(q.top)) < 0) { tops.push(Math.round(q.top)); } });
    return tops.length; };
  var natural = function (texts) {
    var c = document.createElement("select");
    c.style.cssText = "flex: none; width: auto; min-width: 0; max-width: none";
    texts.forEach(function (t) { var o = document.createElement("option");
      o.textContent = t; c.appendChild(o); });
    box.appendChild(c); var w = c.getBoundingClientRect().width; box.removeChild(c); return w;
  };
  var lab = box.querySelector("label");
  var out = { vw: innerWidth, box: rect(box), label: rect(lab), labelLines: lines(lab),
              labelClip: lab.scrollWidth - lab.clientWidth, select: rect(sel),
              shown: natural([sel.options[sel.selectedIndex].textContent]),
              widest: natural(__NAMES__), pin: rect(pin), pinLines: lines(pin),
              say: say, said: rect(said) };
  parent.document.getElementById(__OUT__).textContent += JSON.stringify(out) + "\n";
}());
"""


def pick_page(sizes=PICK_SIZES):
    """The outer page: two srcdoc iframes per size (the pin's failure line
    empty, then showing), each holding every stylesheet of the assembled
    page and its Run panel, then the script that fills the picker and
    measures it."""
    html = srcpaths.index_html(encoding="utf-8")
    links = []
    for href in re.findall(r'<link rel="stylesheet" href="([^"]+)">', html):
        if href == "/tokens.css":
            links.append(ROOT / "ops" / "fleet_kit" / "tokens.css")
        elif href.startswith("/web/"):
            links.append(srcpaths.path(href[len("/web/"):]))
    i = html.index('<div id="panel-run"')
    run = html[i:html.index('<div id="panel-settings"', i)].replace(" hidden>", ">", 1)
    js = (_PICK_JS.replace("__NAMES__", json.dumps(list(PICK_NAMES)))
          .replace("__PIN__", json.dumps(PIN_WORDS)).replace("__OUT__", json.dumps(PICK_OUT))
          .replace("__SAID__", json.dumps(chars_consts()[1])))
    head = "".join(f'<link rel="stylesheet" href="{_file_url(p)}">\n' for p in links)
    inner = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
             "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
             f"<title>picker</title>\n{head}</head>\n<body>\n<main>\n{run}</main>\n"
             f"<script>{js}</script>\n</body>\n</html>\n")
    frames = "".join(f'<iframe{say} width="{w}" height="{h}" style="border: 0; display: block" '
                     f'srcdoc="{htmllib.escape(inner, quote=True)}"></iframe>\n'
                     for w, h in sizes for say in ("", ' data-say="1"'))
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            f"<title>picker sizes</title>\n</head>\n<body style=\"margin: 0\">\n"
            f"<pre id=\"{PICK_OUT}\"></pre>\n{frames}</body>\n</html>\n")


def measure_pick(browser, folder):
    """{"<w>x<h>": measures, "<w>x<h> said": measures} for every PICK_SIZES
    frame."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    page = folder / "pick.html"
    page.write_text(pick_page(), encoding="utf-8")
    cmd = [browser, "--headless=new", "--disable-gpu", "--in-process-gpu", "--no-first-run",
           "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars",
           "--force-device-scale-factor=1", f"--user-data-dir={folder / 'profile'}",
           "--window-size=1400,2400", "--dump-dom", page.as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=ci_scale(90))
    m = re.search(r'<pre id="' + PICK_OUT + r'">(.*?)</pre>', r.stdout, re.S)
    assert m and m.group(1).strip(), f"no picker measures; stderr: {r.stderr[-1500:]}"
    rows = [json.loads(line) for line in htmllib.unescape(m.group(1)).splitlines() if line]
    heights = dict(PICK_SIZES)  # frames report in load order; match by width
    return {size_key(row["vw"], heights[row["vw"]]) + (SAID if row["say"] else ""): row
            for row in rows}


def pick_failures(measures):
    """Every picker part that is cut, squeezed, under 24 px or out of its line."""
    fails = []
    for key, m in measures.items():
        line, sel, pin, lab = m["box"], m["select"], m["pin"], m["label"]
        if m["labelLines"] != 1 or m["labelClip"] > 0:
            fails.append(f"{key}: the label takes {m['labelLines']} lines, "
                         f"{m['labelClip']} px cut")
        if sel["w"] < TARGET_MIN - 0.01 or sel["h"] < TARGET_MIN - 0.01:
            fails.append(f"{key}: the select is {sel['w']:.1f}x{sel['h']:.1f} px")
        if sel["w"] < min(m["widest"], line["w"]) - 0.5:
            fails.append(f"{key}: the select is squeezed to {sel['w']:.1f} px "
                         f"(widest name {m['widest']:.1f}, line {line['w']:.1f})")
        if sel["w"] < m["shown"] - 0.5:
            fails.append(f"{key}: the shown name needs {m['shown']:.1f} px, "
                         f"the select is {sel['w']:.1f}")
        if pin["h"] < TARGET_MIN - 0.01 or m["pinLines"] != 1:
            fails.append(f"{key}: the pin is {pin['h']:.1f} px tall on {m['pinLines']} lines")
        parts = [("label", lab), ("select", sel), ("pin", pin)]
        if m.get("say"):
            parts.append(("failure line", m["said"]))
            if m["said"]["h"] <= 0:
                fails.append(f"{key}: the failure line does not show")
        for name, part in parts:
            if part["l"] < line["l"] - 0.5 or part["r"] > line["r"] + 0.5:
                fails.append(f"{key}: the {name} runs out of its line")
    return fails


def room_failures(measures, rows):
    """Every cockpit size where the picker, ROWS rows and the pager row do
    not fit the room under the Characters title."""
    fails = []
    for size, (cls, room) in CHARS_ROOM.items():
        for key in (size_key(*size), size_key(*size) + SAID):
            if key not in measures:
                fails.append(f"{key}: not measured")
                continue
            need = (measures[key]["box"]["h"] + CHARS_GAP_PX + rows[cls] * CHARS_ROW_PX
                    + CHARS_PAGER_PX)
            if need > room + 0.01:
                fails.append(f"{key}: picker {measures[key]['box']['h']:.1f} + "
                             f"{rows[cls]} rows needs {need:.1f} of {room} px ({cls})")
    return fails


def test_pick_failures_catch_a_squeezed_picker():
    ok = {"320x640": {"vw": 320, "box": {"l": 25, "r": 295, "w": 270, "h": 87},
                      "label": {"l": 25, "r": 154, "w": 129, "h": 22}, "labelLines": 1,
                      "labelClip": 0, "select": {"l": 25, "r": 295, "w": 270, "h": 33},
                      "shown": 190, "widest": 295,
                      "pin": {"l": 25, "r": 168, "w": 143, "h": 24}, "pinLines": 1}}
    assert pick_failures(ok) == []
    bad = json.loads(json.dumps(ok))
    m = bad["320x640"]
    m.update(labelLines=2, pinLines=4)
    m["select"].update(l=162, w=20, h=33)
    m["pin"].update(r=300)
    fails = pick_failures(bad)
    assert len(fails) == 6, fails
    said = json.loads(json.dumps(ok["320x640"]))
    said.update(say=True, said={"l": 25, "r": 295, "w": 270, "h": 0})
    assert pick_failures({"320x640 said": said}) == ["320x640 said: the failure line does not show"]


def test_room_failures_catch_too_many_rows():
    fit = {k: {"box": {"h": 85}} for k in ("1280x760", "1280x760 said",
                                           "1024x700", "1024x700 said")}
    assert room_failures(fit, {"full": 5, "compact": 4}) == []
    fails = room_failures(fit, {"full": 8, "compact": 6})
    assert len(fails) == 4, fails
    del fit["1024x700 said"]
    assert room_failures(fit, {"full": 5, "compact": 4}) == ["1024x700 said: not measured"]


@pytest.fixture(scope="module")
def pick_measures(tmp_path_factory):
    browser = find_browser()
    if not browser:
        pytest.skip("headless Chrome / Edge not found")
    return measure_pick(browser, tmp_path_factory.mktemp("char_pick"))


def test_the_picker_keeps_its_select_and_labels_at_narrow_sizes(pick_measures):
    assert set(pick_measures) == {size_key(*s) + say for s in PICK_SIZES for say in ("", SAID)}, \
        pick_measures.keys()
    narrow = pick_measures["320x640"]
    # at 320 px the label and the select cannot share a line: the select wraps
    assert narrow["label"]["w"] + narrow["widest"] > narrow["box"]["w"], narrow
    fails = pick_failures(pick_measures)
    assert not fails, "\n".join(fails)


def test_the_characters_card_fits_its_rows_under_the_tallest_picker(pick_measures):
    rows, _said = chars_consts()
    for size in CHARS_ROOM:
        m = pick_measures[size_key(*size) + SAID]
        assert m["say"] and m["said"]["h"] > 0, m  # the failure line made it taller
        assert m["box"]["h"] > pick_measures[size_key(*size)]["box"]["h"], m
    fails = room_failures(pick_measures, rows)
    assert not fails, "\n".join(fails)


# -- KINDLER-FIT-MEASURE: the Kindler editor card on Build and items ------------
#
# The Play sweep never opens a Kindler sub-tab (the shown sub-tab is the
# store's and the page's own memory), so the editor card web/kindler.js
# builds was never measured. This part opens one on a static page: the
# whole assembled page (every stylesheet, header, panels and the two-row
# pinned footer line of WEB-PLAY-FIT-SETTINGS) with Build and items shown,
# and the real web/kindler.js attached to a fake core that answers the
# store document and the result read at once (no core, no network, no
# port). Each size is a srcdoc iframe, as CP-1's picker, read back by the
# browser's own --dump-dom run.
#
# Two documents per size: "new" (one tab, no result: the card spans the
# grid) and "worst" (6 tabs of 32 characters, the full note, a stale and
# partial unscored result with the longest template name, so the plan card
# takes columns 2 and 3 and the editor sits in column 1, and the longest
# status words). The worst document is measured in each card mode (tools,
# rename, confirm). In the cockpit the card clips (overflow hidden), so a
# cut row would never show as page overflow: the check is the card's own
# slack, its content box bottom less the bottom of its last shown child,
# which must keep the G4 minimum, and no clipped content. The plan card
# beside it (the engine's calc-off plan of that template) is held to the
# same rule on every stage, plan page and part. Flow sizes check
# horizontal scroll only (flow scrolls the page).
#
# First measure (before the web/panels/kindler.css fix): at 1024x700 the
# worst editor card was 300 to 350 px short in its one column, at 1280x760
# 39 to 71 px short, at 1264x821 6 to 10 px and at 1920x875 13 px short in
# rename mode; the "new" card fitted everywhere (221 px slack at 1024x700).
#
#     python tests/test_play_fit.py --kindler   # the measured figures

KINDLER_OUT = "al-kindler-out"
KINDLER_SIZES = COCKPIT + FLOW
KINDLER_MODES = ("tools", "rename", "confirm")
KINDLER_LABEL = "Wanderingblademaster's long tab"[:32]  # genstore.MAX_LABEL
KINDLER_TABS = 6  # genstore MAX_TABS: the bar at its fullest

_KINDLER_JS = r"""
(function () {
  var fe = window.frameElement, doc = document, out = [];
  var kind = fe.getAttribute("data-kind");
  var send = function (o) {
    o.vw = innerWidth; o.vh = innerHeight; o.kind = kind;
    parent.document.getElementById(__OUT__).textContent += JSON.stringify(o) + "\n";
  };
  try {
    Array.prototype.forEach.call(doc.querySelectorAll("[role=tabpanel]"), function (p) {
      p.hidden = p.id !== "panel-build";
    });
    Array.prototype.forEach.call(doc.querySelectorAll("[role=tab]"), function (t) {
      t.setAttribute("aria-selected", String(t.getAttribute("aria-controls") === "panel-build"));
    });
    var line = doc.getElementById("build-line");
    line.textContent = __BUILD__; line.hidden = false;
    var worst = kind === "worst";
    var tabs = [];
    for (var i = 0; i < (worst ? __TABS__ : 1); i++) {
      var t = { id: "t" + i, label: worst ? __LABEL__ : "Kindler", custom_label: worst,
                "class": worst ? "Mercenary" : "", league: worst ? "Standard" : "",
                toggles: {}, follow: true, result: null };
      if (worst) {
        t.result = { template: __TEMPLATE__, scored: false, partial: true, stale: true,
                     at: 1, key: "k" };
      }
      tabs.push(t);
    }
    var store = { tabs: tabs, shown: tabs[0].id, max: __TABS__ };
    var read = { result: { best: { template: __TEMPLATE__, label: __TEMPLATE_LABEL__ },
                           note: "calc_off" } };
    var answer = function (method, path, body) {
      if (path === "/api/gen-builds") { return { status: 200, body: store }; }
      if (body && body.op === "read") { return { status: 200, body: read }; }
      if (body && body.op === "plan") { return { status: 200, body: __PLAN__ }; }
      return { status: 404, body: null };
    };
    var K = window.ALKindler;
    var noop = function () {};
    K.attach(doc, {
      request: function (m, p, b) { return Promise.resolve(answer(m, p, b)); },
      store: { getItem: function () { return "kindler"; }, setItem: noop },
      later: noop, leagues: function () { return null; }, say: noop
    });
    K.follow(__HERE__);  // the plan is read once the store answer paints the tab
    window.addEventListener("load", function () {
      try {
        if (worst) {
          var full = doc.getElementById("kindler-full");
          full.textContent = K.view(store).fullText; full.hidden = false;
          var longest = "";
          Object.keys(K.WORDS).forEach(function (k) {
            if (k !== "partial" && K.WORDS[k].length > longest.length) { longest = K.WORDS[k]; }
          });
          doc.getElementById("kindler-status").textContent = longest;
        }
        var de = doc.documentElement;
        var rect = function (e) { var r = e.getBoundingClientRect();
          return { t: r.top, b: r.bottom, l: r.left, r: r.right, w: r.width, h: r.height }; };
        var shown = function (e) { return e.getClientRects().length > 0; };
        var fit = function (card) {
          var cs = getComputedStyle(card), cr = card.getBoundingClientRect();
          var inner = cr.bottom - parseFloat(cs.paddingBottom) - parseFloat(cs.borderBottomWidth);
          var last = cr.top;
          Array.prototype.forEach.call(card.children, function (k) {
            if (shown(k)) { last = Math.max(last, k.getBoundingClientRect().bottom); }
          });
          return { slack: Math.floor(inner) - Math.ceil(last),
                   clip: card.scrollHeight - card.clientHeight };
        };
        var planFit = function () {
          var plan = doc.getElementById("kindler-plan");
          if (!plan || plan.hidden) { return null; }
          var st = K.state(), worstFit = null, seen = 0;
          var tab = st.model.tabs[0], pv = st.plans[tab.id];
          if (!pv || !pv.plan) { return { error: "no plan painted" }; }
          for (var b = 0; b < pv.stages.length; b++) { K.stage(-1); }
          for (var i = 0; i < pv.stages.length; i++) {
            K.PLAN_PAGES.forEach(function (pg) {
              K.planPage(pg[0]);
              for (var j = 0; j < 20 && j < (st.parts || 1); j++) {
                var f = fit(plan);
                f.at = "stage " + i + " " + pg[0] + " part " + j;
                seen += 1;
                if (!worstFit || f.slack < worstFit.slack) { worstFit = f; }
                K.part(1);
              }
              for (var k = 0; k < 20; k++) { K.part(-1); }
            });
            K.stage(1);
          }
          worstFit.seen = seen;
          return worstFit;
        };
        var measure = function (mode) {
          var card = doc.getElementById("kindlerbox");
          if (!card || card.hidden) { return { mode: mode, error: "no editor card" }; }
          var cs = getComputedStyle(card), cr = card.getBoundingClientRect();
          var inner = cr.bottom - parseFloat(cs.paddingBottom) - parseFloat(cs.borderBottomWidth);
          var last = cr.top, kids = 0, parts = [];
          Array.prototype.forEach.call(card.children, function (k) {
            if (!shown(k)) { return; }
            var kr = k.getBoundingClientRect();
            kids += 1; last = Math.max(last, kr.bottom);
            parts.push((k.id || k.className.split(" ")[0] || k.tagName.toLowerCase()) + " " +
                       Math.round(kr.height));
          });
          var small = [];
          Array.prototype.forEach.call(card.querySelectorAll("button, input, select"), function (c) {
            if (!shown(c)) { return; }
            var r = c.getBoundingClientRect();
            if (r.width < 24 - 0.01 || r.height < 24 - 0.01) {
              small.push((c.id || c.tagName.toLowerCase()) + " " + r.width.toFixed(1) + "x" +
                         r.height.toFixed(1));
            }
          });
          var bar = doc.getElementById("kindler-bar");
          var plan = doc.getElementById("kindler-plan");
          return { mode: mode, root: parseFloat(getComputedStyle(de).fontSize),
                   card: rect(card), inner: inner, last: last, kids: kids,
                   clip: card.scrollHeight - card.clientHeight, parts: parts,
                   bar: rect(bar), plan: plan && !plan.hidden ? rect(plan) : null,
                   foot: rect(doc.querySelector("footer")),
                   doc: { sh: de.scrollHeight, ch: de.clientHeight, sw: de.scrollWidth,
                          cw: de.clientWidth },
                   small: small };
        };
        out.push(measure("tools"));
        var planned = null;
        if (worst) {
          K.openRename(); out.push(measure("rename"));
          K.openConfirm(); out.push(measure("confirm"));
          K.keep();
          planned = planFit();
        }
        send({ modes: out, plan: planned });
      } catch (e) { send({ error: String(e && e.stack || e) }); }
    });
  } catch (e) { send({ error: String(e && e.stack || e) }); }
}());
"""


def kindler_template():
    """(id, label) of the template with the longest label in the authored
    archetypes, so the worst result line is the longest one."""
    doc = json.loads((ROOT / "server" / "al" / "data" / "archetypes.json")
                     .read_text(encoding="utf-8"))
    t = max(doc["templates"], key=lambda x: len(x.get("label") or ""))
    return t["id"], t["label"]


KINDLER_HERE = {"area_id": "G1_1", "area_level": 1, "level": 2}


def kindler_plan(template_id):
    """(the op plan answer, the Play values) for the authored template: the
    plan the engine builds with the calc off, its stage for KINDLER_HERE."""
    from server.al.theorycraft import archetypes, kindlerplan
    view = archetypes.resolve(archetypes.load())
    template = next(t for t in view["templates"] if t["id"] == template_id)
    plan = kindlerplan.build_plan(template, note=kindlerplan.FOCUS_CALC_OFF)
    return ({"state": "ready", "plan": plan, "focus": kindlerplan.FOCUS_CALC_OFF,
             "current": kindlerplan.current_stage(plan, KINDLER_HERE)}, KINDLER_HERE)


def kindler_page(sizes=KINDLER_SIZES):
    """The outer page: a "new" and a "worst" srcdoc iframe per size, each
    the assembled page without its scripts, plus web/kindler.js and the
    script that opens a Kindler tab and measures its editor card."""
    html = srcpaths.index_html(encoding="utf-8")
    links = []
    for href in re.findall(r'<link rel="stylesheet" href="([^"]+)">', html):
        if href == "/tokens.css":
            links.append(ROOT / "ops" / "fleet_kit" / "tokens.css")
        elif href.startswith("/web/"):
            links.append(srcpaths.path(href[len("/web/"):]))
    body = html[html.index("<body>") + len("<body>"):html.index("</body>")]
    body = re.sub(r"<script\b[^>]*>.*?</script>\s*", "", body, flags=re.S)
    tid, tlabel = kindler_template()
    plan_answer, here = kindler_plan(tid)
    build_text = f"Version {VERSION}, build {PIN_COMMIT}, dev"  # web/panels/version.js
    js = (_KINDLER_JS.replace("__OUT__", json.dumps(KINDLER_OUT))
          .replace("__BUILD__", json.dumps(build_text))
          .replace("__TABS__", str(KINDLER_TABS)).replace("__LABEL__", json.dumps(KINDLER_LABEL))
          .replace("__TEMPLATE__", json.dumps(tid))
          .replace("__TEMPLATE_LABEL__", json.dumps(tlabel))
          .replace("__PLAN__", json.dumps(plan_answer)).replace("__HERE__", json.dumps(here)))
    head = "".join(f'<link rel="stylesheet" href="{_file_url(p)}">\n' for p in links)
    inner = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
             "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
             f"<title>kindler card</title>\n{head}</head>\n<body>\n{body}\n"
             f"<script src=\"{_file_url(srcpaths.path('kindler.js'))}\"></script>\n"
             f"<script>{js}</script>\n</body>\n</html>\n")
    frames = "".join(f'<iframe data-kind="{kind}" width="{w}" height="{h}" '
                     f'style="border: 0; display: block" '
                     f'srcdoc="{htmllib.escape(inner, quote=True)}"></iframe>\n'
                     for w, h in sizes for kind in ("new", "worst"))
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            f"<title>kindler sizes</title>\n</head>\n<body style=\"margin: 0\">\n"
            f"<pre id=\"{KINDLER_OUT}\"></pre>\n{frames}</body>\n</html>\n")


def measure_kindler(browser, folder, sizes=KINDLER_SIZES):
    """{"<w>x<h> <kind>": {mode: measures}} for every frame."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    page = folder / "kindler.html"
    page.write_text(kindler_page(sizes), encoding="utf-8")
    cmd = [browser, "--headless=new", "--disable-gpu", "--in-process-gpu", "--no-first-run",
           "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars",
           "--force-device-scale-factor=1", f"--user-data-dir={folder / 'profile'}",
           "--window-size=2000,2400", "--dump-dom", page.as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=ci_scale(120))
    m = re.search(r'<pre id="' + KINDLER_OUT + r'">(.*?)</pre>', r.stdout, re.S)
    assert m and m.group(1).strip(), f"no Kindler measures; stderr: {r.stderr[-1500:]}"
    out = {}
    for line in htmllib.unescape(m.group(1)).splitlines():
        if not line:
            continue
        row = json.loads(line)
        h = next(hh for ww, hh in sizes if ww == row["vw"] and hh == row["vh"])
        key = f"{size_key(row['vw'], h)} {row['kind']}"
        if "error" in row:
            out[key] = {"error": row["error"]}
        else:
            out[key] = {mm["mode"]: mm for mm in row["modes"]}
            if row.get("plan"):
                out[key]["tools"]["plan_fit"] = row["plan"]
    return out


def kindler_failures(measures):
    """Every Kindler editor card that is missing, cut, short of the G4
    slack, holds a target under 24 px, or makes the page scroll."""
    fails = []
    for key, modes in sorted(measures.items()):
        if "error" in modes:
            fails.append(f"{key}: {modes['error'][:300]}")
            continue
        w, h = parse_key(key.split()[0])
        cls, s = size_class(w, h)
        need = SLACK_MIN.get(s, 3)
        for mode, m in modes.items():
            where = f"{key} {mode}"
            if "error" in m:
                fails.append(f"{where}: {m['error']}")
                continue
            d = m["doc"]
            if cls == "flow":
                if d["sw"] > d["cw"]:
                    fails.append(f"{where}: horizontal scroll {d['sw'] - d['cw']} px")
                continue
            if d["sh"] > d["ch"]:
                fails.append(f"{where}: page {d['sh'] - d['ch']} px over")
            slack = math.floor(m["inner"]) - math.ceil(m["last"])
            if slack < need:
                fails.append(f"{where}: editor card slack {slack} px (min {need})")
            if m["clip"] > 1:
                fails.append(f"{where}: editor card clips {m['clip']} px")
            for c in m["small"]:
                fails.append(f"{where}: target {c} px (min {TARGET_MIN})")
            pf = m.get("plan_fit")
            if pf is None:
                continue
            if "error" in pf:
                fails.append(f"{where}: plan card: {pf['error']}")
            elif pf["slack"] < need or pf["clip"] > 1:
                fails.append(f"{where}: plan card slack {pf['slack']} px, clips {pf['clip']} px "
                             f"at {pf['at']} (min {need})")
    return fails


def kindler_figures(measures):
    """One line per measured card: size, document, mode, card height and slack."""
    out = []
    for key, modes in sorted(measures.items()):
        if "error" in modes:
            out.append(f"- {key}: error")
            continue
        for mode, m in modes.items():
            if "error" in m:
                out.append(f"- {key} {mode}: {m['error']}")
                continue
            slack = math.floor(m["inner"]) - math.ceil(m["last"])
            pf = m.get("plan_fit")
            if pf:
                out.append(f"- {key} plan: worst slack {pf.get('slack')} at {pf.get('at')}, "
                           f"clip {pf.get('clip')}, {pf.get('seen')} views"
                           + (f", {pf['error']}" if "error" in pf else ""))
            out.append(f"- {key} {mode}: root {m['root']:g}, card {m['card']['w']:.0f}x"
                       f"{m['card']['h']:.0f}, slack {slack}, clip {m['clip']}, bar "
                       f"{m['bar']['h']:.0f}, footer {m['foot']['h']:.0f}, page over "
                       f"{m['doc']['sh'] - m['doc']['ch']}; parts {', '.join(m.get('parts', ()))}")
    return out


def _fake_kindler(slack=10, clip=0, over=0, small=(), sw=0, plan=None):
    def mode(name):
        return {"mode": name, "root": 16, "card": {"w": 400, "h": 300}, "inner": 400.0,
                "last": 400.0 - slack, "clip": clip, "bar": {"h": 24}, "foot": {"h": 45},
                "doc": {"sh": 700 + over, "ch": 700, "sw": 1024 + sw, "cw": 1024},
                "small": list(small), "parts": []}
    out = {name: mode(name) for name in KINDLER_MODES}
    if plan is not None:
        out["tools"]["plan_fit"] = plan
    return out


def test_kindler_failures_catch_a_cut_card():
    assert kindler_failures({"1024x700 worst": _fake_kindler()}) == []
    fails = kindler_failures({"1024x700 worst": _fake_kindler(slack=1, clip=30, over=4,
                                                              small=("kindler-left 20x20",))})
    assert len(fails) == 4 * len(KINDLER_MODES), fails
    # a flow size checks horizontal scroll only
    assert kindler_failures({"320x640 new": _fake_kindler(slack=-50, over=900)}) == []
    assert len(kindler_failures({"320x640 new": _fake_kindler(sw=7)})) == len(KINDLER_MODES)
    assert kindler_failures({"1280x760 new": {"error": "boom"}}) == ["1280x760 new: boom"]
    # the plan card beside the editor keeps the same minimum and never clips
    ok = {"slack": 40, "clip": 0, "at": "stage 0 skills part 0", "seen": 3}
    assert kindler_failures({"1024x700 worst": _fake_kindler(plan=ok)}) == []
    for bad in (dict(ok, slack=1), dict(ok, clip=12), {"error": "no plan painted"}):
        fails = kindler_failures({"1024x700 worst": _fake_kindler(plan=bad)})
        assert len(fails) == 1 and "plan card" in fails[0], fails


@pytest.fixture(scope="module")
def kindler_measures(tmp_path_factory):
    browser = find_browser()
    if not browser:
        pytest.skip("headless Chrome / Edge not found")
    return measure_kindler(browser, tmp_path_factory.mktemp("kindler_fit"))


def test_the_kindler_card_was_measured_in_every_mode(kindler_measures):
    want = {f"{size_key(w, h)} {kind}" for w, h in KINDLER_SIZES for kind in ("new", "worst")}
    assert set(kindler_measures) == want, sorted(kindler_measures)
    for key, modes in kindler_measures.items():
        assert "error" not in modes, (key, modes)
        assert set(modes) == ({"tools"} if key.endswith(" new") else set(KINDLER_MODES)), key
    # the worst document puts the plan card beside the editor in the cockpit
    views = 3 * len(kindler_plan(kindler_template()[0])[0]["plan"]["stages"])
    for w, h in COCKPIT:
        worst = kindler_measures[f"{size_key(w, h)} worst"]["tools"]
        new = kindler_measures[f"{size_key(w, h)} new"]["tools"]
        assert worst["plan"] is not None and new["plan"] is None, (w, h)
        assert worst["card"]["w"] < new["card"]["w"], (w, h)
        # every stage, every plan page, every part of it was looked at
        assert worst["plan_fit"]["seen"] >= views, (w, h, worst["plan_fit"])


def test_the_kindler_editor_card_fits_at_compact_and_full_size(kindler_measures):
    fails = kindler_failures(kindler_measures)
    assert not fails, "\n".join(fails[:40]) + "\n\n" + "\n".join(kindler_figures(kindler_measures))


if __name__ == "__main__":
    if "--kindler" in sys.argv[1:]:
        _browser = find_browser()
        if not _browser:
            sys.exit("headless Chrome / Edge not found")
        with tempfile.TemporaryDirectory(prefix="al-kindler-fit-",
                                         ignore_cleanup_errors=True) as tmp:
            _km = measure_kindler(_browser, tmp)
        print("\n".join(kindler_figures(_km)))
        _kf = kindler_failures(_km)
        print(f"\n{len(_kf)} failures" + ("".join("\n  " + f for f in _kf)))
        sys.exit(0)
    if "--figures" not in sys.argv[1:]:
        sys.exit("usage: python tests/test_play_fit.py --figures | --kindler")
    _browser, _node = find_browser(), shutil.which("node")
    if not _browser or not _node:
        sys.exit("headless Chrome / Edge or node not found")
    with tempfile.TemporaryDirectory(prefix="al-play-fit-", ignore_cleanup_errors=True) as tmp:
        _sweep = run_sweep(tmp, _browser, _node)
    print("\n".join(figures(_sweep)))
    _fails = fit_failures(_sweep)
    print(f"\n{len(_fails)} failed budgets; by check: "
          + ", ".join(f"{k} {v}" for k, v in sorted(Counter(f['check'] for f in _fails).items())))
    if os.environ.get("AL_PLAY_FIT_DUMP"):
        Path(os.environ["AL_PLAY_FIT_DUMP"]).write_text(json.dumps(_sweep), encoding="ascii")
