"""PLAY-F-204A-SR-TOOL (F-204): tools/sr_pass.py, the screen-reader pass tool.

The tool refuses without the operator flag and while the running core does
not report game_idle true; it holds no OS input, screen, audio or clipboard
call; on a fixture speech log it writes a transcript with one section per
step. The transcript check of docs/design/screen-reader-pass.md skips while
that file is absent (it lands with PLAY-F-204B-SR-RUN).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "sr_pass.py"
sys.path.insert(0, str(ROOT / "tools"))

import sr_pass  # noqa: E402

# A fixture speech log in NVDA's log form: times on the header lines, one
# "Speaking [...]" list per utterance (command objects mixed in, as NVDA
# writes them). Synthetic text, no real session.
NVDA_LOG = """\
INFO - __main__ (17:00:00.000) - MainThread (100):
Starting NVDA
IO - speech.speech.speak (17:00:00.500) - MainThread (100):
Speaking ['about:blank', 'document']
IO - speech.speech.speak (17:00:01.200) - MainThread (100):
Speaking ['AshLight', 'document', CancellableSpeech (still valid)]
IO - speech.speech.speak (17:00:02.000) - MainThread (100):
Speaking ['Dashboard sections', 'tab control', 'Play', 'tab', 'selected']
IO - speech.speech.speak (17:00:06.300) - MainThread (100):
Speaking ['Grim Bane Ruby Ring: worth a look']
IO - speech.speech.speak (17:00:10.400) - MainThread (100):
Speaking ['Trade request from Quietfox: Grim Bane Ruby Ring, 5 exalted']
IO - speech.speech.speak (17:00:14.600) - MainThread (100):
Speaking ['Build', 'tab', 'selected', '2 of 4']
IO - speech.speech.speak (17:00:18.700) - MainThread (100):
Speaking ['Settings', 'tab', 'selected', '4 of 4']
IO - speech.speech.speak (17:00:19.500) - MainThread (100):
Speaking ['Game log path', 'edit', 'blank']
IO - speech.speech.speak (17:00:20.300) - MainThread (100):
Speaking ['Web data', 'check box', 'not checked']
"""

TIMELINE = {"date": "2026-11-22", "steps": [
    {"id": "page-load", "start": "17:00:01.000", "end": "17:00:05.000"},
    {"id": "item-check", "start": "17:00:06.000", "end": "17:00:10.000"},
    {"id": "trade-request", "start": "17:00:10.100", "end": "17:00:14.100"},
    {"id": "tab-switch", "start": "17:00:14.200", "end": "17:00:18.200"},
    {"id": "settings-form", "start": "17:00:18.300", "end": "17:00:30.000"},
]}

# The plain form, split by step markers, with one unnamed and one doubled
# announcement planted.
PLAIN_LOG = """\
# step page-load
AshLight  document
# step item-check
Grim Bane Ruby Ring: worth a look
# step trade-request
Trade request from Quietfox
Trade request from Quietfox
# step tab-switch
Build  tab  selected
# step settings-form
button
Web data  check box  not checked
"""


def _fixture(tmp_path, text=NVDA_LOG, name="speech.log"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


# -- refusals -------------------------------------------------------------------

def test_run_without_the_operator_flag_exits_non_zero():
    p = subprocess.run([sys.executable, str(TOOL), "run"], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == sr_pass.EXIT_NO_FLAG
    assert "operator flag" in p.stdout


def test_no_flag_asks_no_core():
    asked = []
    rc = sr_pass.main(["run"], idle_reader=lambda: asked.append(1) or True,
                      driver=lambda *a: pytest.fail("drove without the flag"))
    assert rc == sr_pass.EXIT_NO_FLAG and asked == []


@pytest.mark.parametrize("idle", [False, None, "true", 1])
def test_run_refuses_unless_game_idle_is_true(idle, tmp_path, capsys):
    rc = sr_pass.main(["run", "--operator-ok", "--out", str(tmp_path / "t.md")],
                      idle_reader=lambda: idle,
                      driver=lambda *a: pytest.fail("drove while not idle"))
    assert rc == sr_pass.EXIT_NOT_IDLE
    assert "game_idle" in capsys.readouterr().out
    assert not (tmp_path / "t.md").exists()


def test_read_idle_without_a_token_is_unknown(monkeypatch):
    monkeypatch.setattr(sr_pass, "_token", lambda: "")
    assert sr_pass.read_idle() is None


class _Reply:
    def __init__(self, doc):
        self.status = 200
        self._data = json.dumps(doc).encode()

    def read(self, n=-1):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Opener:
    def __init__(self, doc):
        self.doc = doc
        self.urls = []

    def open(self, req, timeout=None):
        self.urls.append(req.full_url)
        return _Reply(self.doc)


@pytest.mark.parametrize("doc,want", [({"game_idle": True}, True),
                                      ({"game_idle": False}, False),
                                      ({"game_idle": "yes"}, None), ({}, None)])
def test_read_idle_reads_the_token_api_on_loopback(monkeypatch, doc, want):
    monkeypatch.setattr(sr_pass, "_token", lambda: "t" * 32)
    monkeypatch.setattr(sr_pass.paths, "load_local_config", lambda: {})
    monkeypatch.setattr(sr_pass.hello, "verify", lambda *a, **k: True)
    op = _Opener(doc)
    assert sr_pass.read_idle(opener=op) is want
    assert op.urls and all(u.startswith("http://127.0.0.1:") and u.endswith("/api/state")
                           for u in op.urls)


def test_read_idle_refuses_a_core_failing_the_hello(monkeypatch):
    monkeypatch.setattr(sr_pass, "_token", lambda: "t" * 32)
    monkeypatch.setattr(sr_pass.paths, "load_local_config", lambda: {})
    monkeypatch.setattr(sr_pass.hello, "verify", lambda *a, **k: False)
    op = _Opener({"game_idle": True})
    assert sr_pass.read_idle(opener=op) is None and op.urls == []


# -- floor: no OS input, screen, audio or clipboard call ---------------------------

BANNED = [
    r"\bSendInput\b", r"\bkeybd_event\b", r"\bmouse_event\b", r"\bSendKeys\b",
    r"\bpyautogui\b", r"\bpynput\b", r"\bpydirectinput\b", r"\bsendInputEvent\b",
    r"\bWM_KEYDOWN\b", r"\bctypes\b", r"\bwin32api\b", r"\bwin32con\b",
    r"\bImageGrab\b", r"\bBitBlt\b", r"\bmss\b", r"\bcaptureScreenshot\b",
    r"\bstartScreencast\b", r"\bdesktopCapturer\b", r"\bgetDisplayMedia\b",
    r"\bwinsound\b", r"\bsounddevice\b", r"\bpyaudio\b", r"\bwaveIn\w*",
    r"\bgetUserMedia\b", r"\bplaysound\b",
    r"\bpyperclip\b", r"\bwin32clipboard\b", r"\bclipboard_get\b",
    r"\bGetClipboardData\b", r"\bOpenClipboard\b", r"\bGet-Clipboard\b",
    r"\bnavigator\.clipboard\b", r"\btkinter\b",
    r"Client\.txt['\"]\s*\)?\s*\.\s*(read|open)",
]


def test_the_tool_holds_no_input_screen_audio_or_clipboard_call():
    src = TOOL.read_text(encoding="utf-8")
    hits = [pat for pat in BANNED if re.search(pat, src)]
    assert hits == []


def test_keys_go_only_through_the_page_target():
    src = TOOL.read_text(encoding="utf-8")
    assert "Input.dispatchKeyEvent" in src
    assert "--headless" not in src  # a reader needs a visible window
    assert "--port" not in src  # the demo core picks its own demo-block port


def test_the_pass_reads_no_live_log_and_uses_the_demo_core():
    src = TOOL.read_text(encoding="utf-8")
    assert '"--demo"' in src
    assert "copytree" in src  # the fixture is copied; the trade line goes into the copy
    assert "paths.sidecar_dir(\"Temp\")" in src


# -- transcript -------------------------------------------------------------------

def test_nvda_log_parses_quoted_items_only():
    entries = sr_pass.parse_speech_log(NVDA_LOG)
    texts = [e["text"] for e in entries]
    assert texts[1] == "AshLight  document"
    assert all("CancellableSpeech" not in t for t in texts)
    assert entries[0]["t"] == pytest.approx(17 * 3600 + 0.5)


def test_fixture_speech_log_gives_one_section_per_step(tmp_path):
    log = _fixture(tmp_path)
    tl = tmp_path / "t.timeline.json"
    tl.write_text(json.dumps(TIMELINE), encoding="utf-8")
    out = tmp_path / "transcript.md"
    rc = sr_pass.main(["transcript", "--speech-log", str(log), "--timeline", str(tl),
                       "--out", str(out)])
    assert rc == 0
    text = out.read_text(encoding="ascii")
    heads = [ln for ln in text.splitlines() if ln.startswith("## ")]
    assert heads == ["## 1. Page load", "## 2. Item check", "## 3. Trade request",
                     "## 4. Tab switch", "## 5. Settings form", "## Findings"]
    assert "Date: 2026-11-22" in text
    assert "about:blank" not in text  # before the first step
    assert '- "Trade request from Quietfox' in text
    assert sr_pass.check_transcript(text) == []
    assert "\r" not in out.read_bytes().decode("ascii")


def test_markers_split_steps_and_findings_catch_unnamed_and_doubled(tmp_path):
    log = _fixture(tmp_path, PLAIN_LOG)
    out = tmp_path / "t.md"
    assert sr_pass.main(["transcript", "--speech-log", str(log), "--out", str(out),
                         "--date", "2026-11-22"]) == 0
    text = out.read_text(encoding="ascii")
    assert "- unnamed: 1" in text and "settings-form: button" in text
    assert "- doubled: 1" in text and "trade-request: Trade request from Quietfox" in text
    bad = sr_pass.check_transcript(text)
    assert any("unnamed" in b for b in bad) and any("doubled" in b for b in bad)
    assert sr_pass.main(["check", str(out)]) == sr_pass.EXIT_FAIL


def test_unnamed_rule():
    assert sr_pass.is_unnamed(["button"])
    assert sr_pass.is_unnamed(["tab", "selected"])
    assert sr_pass.is_unnamed(["unlabeled", "graphic"])
    assert not sr_pass.is_unnamed(["Play", "tab", "selected"])


def test_check_names_each_missing_part():
    assert "no Date line" in sr_pass.check_transcript("# Screen-reader pass\n")
    steps = {s: [{"items": ["x"], "text": "x"}] for s in sr_pass.STEP_IDS}
    good = sr_pass.render_transcript(steps, "2026-11-22")
    assert sr_pass.check_transcript(good) == []
    empty = sr_pass.render_transcript(dict(steps, **{"tab-switch": []}), "2026-11-22")
    assert sr_pass.check_transcript(empty) == ["4. Tab switch: nothing heard"]
    assert sr_pass.check_transcript(good.replace("Date: 2026-11-22", "Date: soon"))


def test_run_with_a_stub_driver_writes_timeline_and_transcript(tmp_path):
    log = _fixture(tmp_path)
    out = tmp_path / "pass.md"
    rc = sr_pass.main(["run", "--operator-ok", "--speech-log", str(log), "--out", str(out),
                       "--browser", sys.executable],
                      idle_reader=lambda: True, driver=lambda fixture, browser: TIMELINE)
    assert rc == 0
    assert json.loads(out.with_suffix(".timeline.json").read_text())["steps"][0]["id"] \
        == "page-load"
    assert sr_pass.check_transcript(out.read_text(encoding="ascii")) == []


def test_websocket_frame_is_masked_and_sized():
    f = sr_pass.encode_frame(b"abc", mask=b"\x01\x02\x03\x04")
    assert f[:2] == bytes([0x81, 0x83]) and f[2:6] == b"\x01\x02\x03\x04"
    assert bytes(c ^ f[2 + i % 4] for i, c in enumerate(f[6:])) == b"abc"
    big = sr_pass.encode_frame(b"x" * 300, mask=b"\0\0\0\0")
    assert big[1] == 0x80 | 126 and int.from_bytes(big[2:4], "big") == 300


def test_the_committed_transcript_passes_the_check():
    doc = sr_pass.TRANSCRIPT_DOC
    if not doc.is_file():
        pytest.skip("docs/design/screen-reader-pass.md lands with PLAY-F-204B-SR-RUN")
    assert sr_pass.check_transcript(doc.read_text(encoding="utf-8")) == []
