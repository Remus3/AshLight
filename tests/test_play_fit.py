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
is pending exactly while its marker is. Page-wide budgets (page overflow,
word, element and control totals, text styles) are pending while any
region marker is. The package that lands a region or a tab deletes its
marker; from then on that scope must hold in every state and size.

Skips cleanly without Chrome (or Edge) or node. Never touches the game,
the live Client.txt or port 8960.

    python tests/test_play_fit.py --figures   # the measured figures
"""

import contextlib
import json
import math
import os
import queue
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
        word = (ev.get("text") or {}).get("word") or (snap.get("card") or {}).get("head")
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
        self._read(60)

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
        return self._read(timeout)

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


@contextlib.contextmanager
def _open_state(name, root, port):
    """The state on the previous state's port (one page URL for the whole
    sweep); a fresh free test port when another test took that one."""
    for i, want in enumerate((port, None) if port else (None,)):
        stack = contextlib.ExitStack()
        try:
            st = stack.enter_context(ps.open_state(name, root / f"{name}-{i}", port=want))
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
    try:
        for name in ps.STATES:
            with _open_state(name, root, port) as st:
                port = st.port
                snap = st.state()
                answers = answers_for(snap)
                r = drv.call({"cmd": "state", "url": st.url, "name": name,
                              "sizes": [list(x) for x in SIZES], "answers": answers})
                sweep["states"][name] = {"live": r["live"], "sizes": r["sizes"],
                                         "trades": len(snap.get("trade_requests") or ()),
                                         "answers": answers}
                if name == ps.STATES[-1]:
                    ph = drv.call({"cmd": "placeholder", "sizes": [list(x) for x in COCKPIT]})
                    sweep["placeholder"] = ph["sizes"]
                    sweep["metrics"] = drv.call({"cmd": "metrics", "rows": metric_rows()})["rows"]
    finally:
        ps.TOKEN = recipe_token
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
    assert tuple(sweep["states"]) == ps.STATES
    for name, st in sweep["states"].items():
        assert st["live"], f"state {name}: the page never came live"
        assert set(st["sizes"]) == {size_key(w, h) for w, h in SIZES}, name
        for key, m in st["sizes"].items():
            assert (m["vw"], m["vh"]) == parse_key(key), (name, key)
            assert m["play"] is not None, (name, key)
    assert set(sweep["placeholder"]) == {size_key(w, h) for w, h in COCKPIT}


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


if __name__ == "__main__":
    if "--figures" not in sys.argv[1:]:
        sys.exit("usage: python tests/test_play_fit.py --figures")
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
