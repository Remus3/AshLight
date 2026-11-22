"""OVL-GLANCE-RULES (F-095, design 0001 sections 7.1 and 10).

1. Glance rule: every overlay card's first line starts with its answer
   inside the 26-character clip: the verdict word (item check), the price
   word (price card), the buyer (trade card) or one of the fixed status
   words of a card without a verdict.
2. Twins: every card kind the core can publish has a dashboard twin that
   stays (an id in web/index.html). The kinds come from the code
   (state.overlay_card, the trade card in render_gate.js, and
   server/al/overlayview.py CARD_HOLDERS once it exists), so a kind added
   later without a twin fails here.
3. Notification policy: no Windows toast, sound or taskbar flash during
   play. A raw-text scan of app/, web/, server/ and scripts/ finds no
   notification, flash or sound API except the one anchored allow entry.
"""

import ast
import importlib
import re
from pathlib import Path

import srcpaths
from server.al import state
from server.al.state import overlay_card

ROOT = Path(__file__).resolve().parents[1]
INDEX = srcpaths.path("index.html")
STATE_PY = ROOT / "server" / "al" / "text" / "overlaycard.py"
RENDER_GATE = ROOT / "app" / "shared" / "render_gate.js"
FORMAT_JS = ROOT / "app" / "shared" / "format.js"
DESIGN = ROOT / "docs" / "design" / "0001-design-system.md"

CLIP = 26  # design 0001 section 9 rule 6; format.js cardText / tradeCard

# Today's card kinds and their dashboard twins (ids in web/index.html).
# A later holder declares its own twin in overlayview.CARD_HOLDERS instead.
TWINS = {
    "eval": ("eval-result",),
    "price": ("price-result",),
    "merged": ("eval-result", "price-result"),
    "trade": ("play-t", "events"),
}

# Fixed status words of a card that has no verdict (design 0001 section 10).
STATUS_WORDS = ("No build loaded", "Not an item", "Can't compare this", "Build loaded",
                "Build not loaded", "Can't check this item", "Waystone unidentified",
                "Copy the item first")
# OVL-COPY-FIRST (F-054): status words the card already uses whose design
# 0001 section 10 text lands later (PLAY-TD-23-RECORDS; package notes:
# "Design 0001 text follows with TD-23"); only the design-text check skips
# them until then
DESIGN_TEXT_PENDING = ("Copy the item first",)
PRICE_WORD = "Price:"
TRADE_WORD = "Trade: "


def _clip(text, width=CLIP):
    """format.js clip(): over the width, cut to width - 3 plus "..."."""
    text = text or ""
    return text if len(text) <= width else text[:width - 3] + "..."


def _index_ids():
    return set(re.findall(r'\bid="([^"]+)"', INDEX.read_text(encoding="utf-8")))


# -- 1. the card kinds, read from the code ---------------------------------

def _state_kinds():
    """Every "kind" string overlay_card can return: dict literals with a
    "kind" key and kind="..." keywords inside the function."""
    tree = ast.parse(STATE_PY.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "overlay_card")
    kinds = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if (isinstance(k, ast.Constant) and k.value == "kind"
                        and isinstance(v, ast.Constant) and isinstance(v.value, str)):
                    kinds.add(v.value)
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (kw.arg == "kind" and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)):
                    kinds.add(kw.value.value)
    return kinds


def _render_gate_kinds():
    """The trade card the overlay builds itself, plus any card kind the
    render gate names (kind === "x", kind: "x")."""
    src = RENDER_GATE.read_text(encoding="utf-8")
    kinds = set(re.findall(r'\bkind\s*(?:===?|:)\s*"(\w+)"', src))
    if "fmt.tradeCard(" in src:
        kinds.add("trade")
    return kinds


def _card_holders():
    """overlayview.CARD_HOLDERS as {kind: entry}, or {} before it exists."""
    if not (ROOT / "server" / "al" / "overlayview.py").is_file():
        return {}
    holders = importlib.import_module("server.al.overlayview").CARD_HOLDERS
    if isinstance(holders, dict):
        return {k: v for k, v in holders.items()}
    out = {}
    for entry in holders:
        assert isinstance(entry, dict), entry
        kind = entry.get("kind") or entry.get("id") or entry.get("name")
        assert isinstance(kind, str) and kind, entry
        out[kind] = entry
    return out


def test_every_card_kind_has_a_dashboard_twin():
    ids = _index_ids()
    holders = _card_holders()
    kinds = _state_kinds() | _render_gate_kinds() | set(holders)
    assert {"eval", "price", "merged", "trade"} <= kinds, kinds
    missing = []
    for kind in sorted(kinds):
        if kind in holders:
            entry = holders[kind]
            assert isinstance(entry, dict), (kind, entry)
            twin, exempt = entry.get("twin"), entry.get("exempt")
            if isinstance(exempt, str) and exempt.strip():
                continue
            twins = (twin,) if isinstance(twin, str) else tuple(twin or ())
        else:
            twins = TWINS.get(kind, ())
        if not twins or any(t not in ids for t in twins):
            missing.append(f"{kind}: twin {twins!r} not in web/index.html")
    assert not missing, ("a card that leaves the overlay by itself needs a dashboard "
                         "twin (design 0001 section 10):\n" + "\n".join(missing))


def test_twins_table_has_no_stale_kind():
    kinds = _state_kinds() | _render_gate_kinds()
    assert set(TWINS) <= kinds, set(TWINS) - kinds


# -- 2. the glance rule on fixtures ------------------------------------------

NOW = 10000.0


def _comp(verdict, delta, slot="Gloves", **extra):
    c = {"slot": slot, "verdict": verdict, "score_delta": delta,
         "equipped": {"name": "Old Grip"},
         "stats": [{"key": "+# to maximum Life", "delta": 30, "weighted": True,
                    "score_delta": delta}]}
    c.update(extra)
    return c


def _ev(**kw):
    ev = {"at": NOW, "ok": True, "item": {"name": "Grim Grip", "base": "Ringmail Gauntlets"}}
    ev.update(kw)
    return ev


LONG_SLOT = "Weapon Swap Main Hand Slot Number Two"
EVAL_FIXTURES = [
    _ev(verdict="upgrade", slot="Gloves", score_delta=4.5,
        comparisons=[_comp("upgrade", 4.5)]),
    _ev(verdict="sidegrade", slot="Gloves", score_delta=0.2,
        comparisons=[_comp("sidegrade", 0.2)]),
    _ev(verdict="downgrade", slot="Gloves", score_delta=-3,
        comparisons=[_comp("downgrade", -3)]),
    _ev(verdict="upgrade", slot=LONG_SLOT, score_delta=12.25,
        comparisons=[_comp("upgrade", 12.25, slot=LONG_SLOT, empty=True)]),
    _ev(verdict="downgrade", slot="Weapon 1", score_delta=-50,
        calc={"source": "pob", "notice": "weapon_type"},
        comparisons=[_comp("downgrade", -50, slot="Weapon 1",
                           weapon_unusable={"skill": "Spark"})]),
    _ev(verdict="upgrade", slot="Gloves", score_delta=4.5, unidentified=True,
        comparisons=[_comp("upgrade", 4.5)]),
    _ev(ok=False, error="unheard of error"),
    _ev(ok=False, error="build loaded",
        parts={"buildload": {"status": "loaded", "class_name": "Monk", "level": 40}}),
    _ev(waystone={"tier": 15, "build_loaded": True,
                  "risky": [{"label": "Monsters deal extra Fire damage", "short": "Fire"}]}),
    _ev(waystone={"tier": 15, "build_loaded": False,
                  "risky": [{"label": "Players have reduced regeneration", "short": "Regen"}]}),
    _ev(waystone={"tier": 3, "build_loaded": True, "risky": []}),
    _ev(waystone={"tier": 3, "unidentified": True}),
] + [_ev(ok=False, error=err) for err in state.EVAL_ERROR_TEXT]


def _price(**kw):
    p = {"at": NOW, "item": {"name": "A Very Long Unique Item Name Of Doom"}}
    p.update(kw)
    return p


PRICE_FIXTURES = [
    _price(status="waiting", wait_s=7),
    _price(status="searching"),
    _price(status="done", count=12, listings=[{"amount": 1, "currency": "divine"},
                                              {"amount": 2, "currency": "divine"}]),
    _price(status="done", listings=[]),
    _price(status="link", league="Standard"),
    _price(status="link", league="Standard",
           ninja={"value": 3.5, "unit": "chaos", "league": "Standard", "listings": 40}),
    _price(status="off"),
    _price(status="off", error="contact not set"),
    _price(status="error", error="no league"),
    _price(status="error", error="something else"),
    _price(status="done", item={"base": "Gold Ring"}, listings=[]),
]


def _assert_eval_head(card, ev):
    line = _clip(card["head"])
    word = state.eval_card_text(ev)["word"]
    ok = (word and line.startswith(word) and len(word) <= CLIP) or \
        any(line.startswith(s) for s in STATUS_WORDS)
    assert ok, (f"first line {line!r} does not start with the verdict word {word!r} "
                f"or a status word (design 0001 section 10 glance rule)")


def test_eval_cards_start_with_the_verdict_word():
    for ev in EVAL_FIXTURES:
        card = overlay_card(ev, None, NOW)
        assert card and card["kind"] == "eval", ev
        _assert_eval_head(card, ev)


def test_price_cards_start_with_the_price_word():
    for pr in PRICE_FIXTURES:
        card = overlay_card(None, pr, NOW)
        assert card and card["kind"] == "price", pr
        assert _clip(card["head"]).startswith(PRICE_WORD), card["head"]


def test_merged_cards_start_with_the_verdict_word():
    done = PRICE_FIXTURES[2]
    seen = 0
    for ev in EVAL_FIXTURES:
        card = overlay_card(ev, done, NOW)
        if card["kind"] != "merged":
            continue
        seen += 1
        _assert_eval_head(card, ev)
    assert seen >= 4, seen


def test_fixtures_reach_every_state_kind():
    reached = {overlay_card(ev, None, NOW)["kind"] for ev in EVAL_FIXTURES}
    reached |= {overlay_card(None, pr, NOW)["kind"] for pr in PRICE_FIXTURES}
    reached |= {overlay_card(ev, PRICE_FIXTURES[2], NOW)["kind"] for ev in EVAL_FIXTURES}
    assert reached == _state_kinds(), (reached, _state_kinds())


def test_trade_card_starts_with_the_buyer():
    src = FORMAT_JS.read_text(encoding="utf-8")
    # the overlay's first trade line is "Trade: <buyer>", clipped to the card
    assert re.search(r'from:\s*clipText\("Trade: "\s*\+\s*\(req\.from', src), \
        "format.js tradeCard first line changed: re-check the glance rule"
    assert re.search(r"var max = maxLen \|\| 26;", src) and CLIP == state.CARD_LINE
    for buyer in ("Quietfox", "A_Really_Long_Character_Name_From_Wraeclast"):
        line = _clip(TRADE_WORD + buyer)
        assert line.startswith(TRADE_WORD + buyer[:CLIP - 3 - len(TRADE_WORD)]), line
        assert len(TRADE_WORD) + 1 <= CLIP


# -- 3. notification policy (no toast, sound or flash in play) -------------

SCAN_DIRS = ("app", "web", "server", "scripts")
SKIP_DIRS = {"node_modules", "__pycache__", ".pytest_cache", "dist", "out"}
TEXT_EXT = {".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".ps1", ".psm1", ".psd1",
            ".cmd", ".bat", ".html", ".htm", ".css", ".json", ".vbs", ".sh", ".cs"}
MAX_BYTES = 4 * 1024 * 1024
_I = re.IGNORECASE
BANNED = [
    ("notification", re.compile(r"\w*Notification\b|\bToast\w*|\bBurntToast\b")),
    ("tray balloon", re.compile(r"\bdisplayBalloon\b|\bShowBalloonTip\b|\bBalloonTip\w*")),
    ("taskbar flash", re.compile(r"\bflashFrame\b|\bFlashWindow(Ex)?\b"
                                 r"|\brequestUserAttention\b|\bdock\s*\.\s*bounce\b", _I)),
    ("beep", re.compile(r"beep\b", _I)),
    ("sound", re.compile(r"\bwinsound\b|\bplaysound\b|\bPlaySound\b|SoundPlayer"
                         r"|SystemSounds|\b(webkit)?AudioContext\b|\bnew\s+Audio\s*\("
                         r"|<audio\b|\bspeechSynthesis\b|\\x07|\\u0007")),
]

# (relpath, banned id, count, anchor within ANCHOR_LINES above the hit,
#  text that must follow on the hit line or the next 2 lines, reason)
ALLOW = [
    ("app/client/window.js", "tray balloon", 1, "function noteClosedToTray()",
     "noSound: true",
     "Decision 0041: one silent tray note per run, only after the player's own "
     "click on X closes the window; never during play by itself."),
]
ANCHOR_LINES = 5


def _files(root):
    for top in SCAN_DIRS:
        base = root / top
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(root)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            try:
                ok = (p.is_file() and p.suffix.lower() in TEXT_EXT
                      and p.stat().st_size <= MAX_BYTES)
            except OSError:
                continue
            if ok:
                yield p, rel.as_posix()


def scan(root):
    hits = []
    for path, rel in _files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        for bid, rx in BANNED:
            for m in rx.finditer(text):
                lno = text.count("\n", 0, m.start()) + 1
                hits.append((rel, bid, lno, lines))
    return hits


def violations(root, allow=ALLOW):
    by_key = {}
    for rel, bid, lno, lines in scan(root):
        by_key.setdefault((rel, bid), []).append((lno, lines))
    allowed = {(a[0], a[1]): a for a in allow}
    out = []
    for key, hs in sorted(by_key.items(), key=lambda kv: kv[0]):
        entry = allowed.get(key)
        if entry is None:
            out.extend(f"{key[0]}:{n}: {key[1]}: {ls[n - 1].strip()[:120]}" for n, ls in hs)
            continue
        _, _, count, anchor, follow, _ = entry
        if len(hs) != count:
            out.append(f"{key[0]}: {key[1]}: {len(hs)} hits, allow-list says {count}")
        for n, ls in hs:
            above = ls[max(0, n - 1 - ANCHOR_LINES):n]
            after = ls[n - 1:n + 2]
            if not any(anchor in w for w in above):
                out.append(f"{key[0]}:{n}: {key[1]}: outside its allowed place")
            if not any(follow in w for w in after):
                out.append(f"{key[0]}:{n}: {key[1]}: {follow!r} missing beside it")
    for key in allowed:
        if key not in by_key:
            out.append(f"stale allow entry {key}: no hit left, remove it")
    return out


def test_no_toast_sound_or_flash_in_the_tree():
    found = violations(ROOT)
    assert not found, ("notification policy (design 0001 section 7.1):\n"
                       + "\n".join(found))


def test_scan_covers_the_shipped_code():
    rels = {rel for _, rel in _files(ROOT)}
    for must in ("app/main.js", "app/client/window.js", "app/overlay/overlay.js",
                 "web/app.js", "server/al/state.py", "scripts/run.ps1"):
        assert must in rels, must
    assert not any("node_modules" in r for r in rels)


def test_scan_catches_planted_calls(tmp_path):
    planted = {
        "app/a.js": "new Notification('x');\n",
        "app/b.js": "win.flashFrame(true);\n",
        "app/c.js": "shell.beep();\n",
        "web/d.js": "const ctx = new AudioContext();\n",
        "server/e.py": "import winsound\n",
        "scripts/f.ps1": "[console]::Beep(440, 100)\n",
        "web/g.html": "<audio src=\"x.wav\"></audio>\n",
        "app/h.js": "tray.displayBalloon({ title: 'x' });\n",
    }
    for rel, text in planted.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    found = violations(tmp_path, allow=[])
    for rel in planted:
        assert any(f.startswith(rel + ":") for f in found), (rel, found)


def test_allow_entries_name_a_reason():
    ids = {b for b, _ in BANNED}
    for rel, bid, count, anchor, follow, reason in ALLOW:
        assert bid in ids and count >= 1 and anchor and follow, rel
        assert reason.isascii() and len(reason.split()) >= 5, rel


# -- the rules are written down where the reviewers read them ---------------

def test_design_0001_states_both_rules():
    text = DESIGN.read_text(encoding="ascii")
    s71 = text.split("### 7.1 ", 1)[1].split("### 7.2 ", 1)[0]
    s10 = text.split("## 10. Overlay rules", 1)[1].split("## 11. ", 1)[0]
    assert "Notification policy" in s71 and "toast" in s71 and "flash" in s71
    assert "Glance rule" in s10 and "26-character clip" in s10 and "twin" in s10
    for word in STATUS_WORDS:
        if word in DESIGN_TEXT_PENDING:
            continue
        assert word in s10.replace("\n  ", " "), word
