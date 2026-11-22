"""PLAY-F-204A-SR-TOOL (F-204): the screen-reader pass tool and its refusals.

One real screen-reader pass over the dashboard records what the reader says
for five steps: page load, an item check, a trade request, a tab switch and
the Settings form. This tool drives the pass and turns the reader's own
speech log into a dated transcript.

    python tools/sr_pass.py run --operator-ok [--speech-log FILE] [--out FILE]
                                [--fixture DIR] [--browser EXE] [--reader NAME]
    python tools/sr_pass.py transcript --speech-log FILE [--timeline FILE]
                                       [--out FILE] [--date YYYY-MM-DD]
    python tools/sr_pass.py check FILE

run refuses (exit 2) unless the operator flag --operator-ok is given (the
operator's word that the game is closed, operator act OA-35), and refuses
(exit 3) unless the operator's running core reports game_idle true
(decision 0029: Client.txt staleness as the core sees it). game_idle is read
from that core over the token API on 127.0.0.1 (hello proof first, no
proxy); this tool never reads Client.txt itself. A core that does not answer
is unknown and refuses too. The flag is checked before anything is read.

After both checks run:
- copies the demo fixture (tests/fixtures/demo, decision 0049) into a
  scratch folder under the AL sidecar Temp dir and starts a demo core on it
  (`python -m server.al --demo <copy>`): the first free port of the demo
  block, never 8960, its own scratch runtime; the live runtime and
  config/local.json are not touched;
- opens a visible Chrome or Edge window on that demo core's dashboard with
  the DevTools protocol on a loopback port and renderer accessibility on;
- drives the five steps: navigate (page load); POST one fixture item text
  to the demo core's /api/eval (item check, no clipboard); append one trade
  whisper line to the scratch copy's Client.txt (trade request, AshLight's
  own fixture, never a game file); ArrowRight on the focused tab list
  (tab switch); Settings tab, then Tab through its form (Settings form).
  Every key goes to that one page through the DevTools protocol
  (Input.dispatchKeyEvent on the page target), never the OS input queue;
- writes the step timeline (local clock times) and, with --speech-log, the
  transcript from the reader's own speech log. Nothing captures the screen
  or audio, nothing touches the clipboard, nothing is sent to the game.

Deviation (recorded in the package result): the package names the CDP
harness of app/test/cdp; this package may create only tools/sr_pass.py, so
the same DevTools protocol commands are sent from here over a small stdlib
WebSocket client instead of a new .mjs driver.

transcript is offline: it reads one speech log (an NVDA log with its
"Speaking [...]" lines, or the plain form: optional "HH:MM:SS[.fff] " time,
then the text, one utterance a line, "# step <id>" marking a step) and
writes the transcript: a dated Markdown page with one section per step and
a findings block (unnamed and doubled announcements). Utterances are
placed in steps by the timeline when every utterance has a time and a
timeline is given, else by the step markers.

check verifies a transcript: dated, the five step sections in order, and
no unnamed or doubled announcement (exit 1 with the reasons otherwise).

Python stdlib only. Never started by the app, the core or the loop.
"""

import argparse
import ast
import base64
import datetime as _dt
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import hello, paths, ports  # noqa: E402

STEPS = (
    ("page-load", "Page load"),
    ("item-check", "Item check"),
    ("trade-request", "Trade request"),
    ("tab-switch", "Tab switch"),
    ("settings-form", "Settings form"),
)
STEP_IDS = tuple(s for s, _ in STEPS)
TITLE = "# Screen-reader pass"
FIXTURE = ROOT / "tests" / "fixtures" / "demo"
TRANSCRIPT_DOC = ROOT / "docs" / "design" / "screen-reader-pass.md"

EXIT_OK, EXIT_FAIL, EXIT_NO_FLAG, EXIT_NOT_IDLE = 0, 1, 2, 3
READ_TIMEOUT_S = 3.0
MAX_BODY = 4 * 1024 * 1024
MAX_LOG_BYTES = 32 * 1024 * 1024
SETTLE_S = 4.0
SETTINGS_TABS = 10

ITEM_TEXT = (
    "Item Class: Rings\nRarity: Rare\nGrim Bane\nRuby Ring\n--------\n"
    "Item Level: 40\n--------\n+12% to Fire Resistance\n--------\n"
    "+35 to maximum Life\n+18% to Cold Resistance\n")
TRADE_WHISPER = ("@From Quietfox: Hi, I would like to buy your Grim Bane Ruby Ring "
                 "listed for 5 exalted in Standard (stash tab \"Sale\"; position: "
                 "left 3, top 7)")

# Role words a reader says after a control's name; an utterance made only of
# these (or saying "unlabeled") names nothing.
ROLE_WORDS = frozenset((
    "button", "link", "edit", "editable", "text", "tab", "tab control",
    "combo box", "check box", "checkbox", "radio button", "list", "list item",
    "menu", "menu item", "group", "grouping", "region", "landmark", "clickable",
    "graphic", "image", "heading", "document", "section", "dialog", "slider",
    "spin button", "toggle button", "selected", "not selected", "checked",
    "not checked", "focused", "collapsed", "expanded", "unavailable", "blank",
    "level 1", "level 2", "level 3", "level 4", "level 5", "level 6",
))
UNNAMED_RE = re.compile(r"\bunlabel{1,2}ed\b", re.IGNORECASE)
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})(?:[.,](\d{1,6}))?$")
NVDA_HEAD_RE = re.compile(r"speech\.speech\.speak\s*\((\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?)\)")
NVDA_SPEAK_RE = re.compile(r"^\s*Speaking\s*\[(.*)\]\s*$")
QUOTED_RE = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
MARKER_RE = re.compile(r"^#\s*step\s+([a-z-]+)\s*$", re.IGNORECASE)


class PassError(RuntimeError):
    pass


def _say(text):
    print(text, flush=True)


# ---------------------------------------------------------------- refusals

def _token():
    try:
        return paths.token_file().read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        return ""


def read_idle(opener=None, timeout=READ_TIMEOUT_S):
    """game_idle of the operator's running core: True, False or None
    (unknown). Loopback only, no proxy, the hello proof before the token is
    sent; Client.txt is never read here."""
    opener = opener or hello.NO_PROXY_OPENER
    token = _token()
    try:
        port = ports.resolve(None, paths.load_local_config())
    except Exception:  # noqa: BLE001 - an unreadable config is "unknown"
        return None
    if not token or not hello.verify(port, token, opener=opener, timeout=timeout):
        return None
    req = urllib.request.Request(f"http://{ports.LOOPBACK}:{int(port)}/api/state",
                                 headers={"X-AL-Token": token})
    try:
        with opener.open(req, timeout=timeout) as r:
            if r.status != 200:
                return None
            data = r.read(MAX_BODY + 1)
        if len(data) > MAX_BODY:
            return None
        doc = json.loads(data)
    except (OSError, ValueError):
        hello.forget(port)
        return None
    idle = doc.get("game_idle") if isinstance(doc, dict) else None
    return idle if isinstance(idle, bool) else None


def refusal(operator_ok, idle_reader):
    """(exit code, reason) when the pass must not run, else None. The flag is
    checked first, so without it no core is asked."""
    if not operator_ok:
        return EXIT_NO_FLAG, ("refused: the operator flag --operator-ok is missing "
                              "(the operator's word that the game is closed, OA-35)")
    idle = idle_reader()
    if idle is not True:
        state = "unknown (no answer)" if idle is None else "false"
        return EXIT_NOT_IDLE, (f"refused: the running core reports game_idle {state}; "
                               "the pass runs only with the game closed")
    return None


# ---------------------------------------------------------------- speech log

def _secs(text):
    m = TIME_RE.match(str(text).strip())
    if not m:
        return None
    h, mi, s, frac = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + (float("0." + frac) if frac else 0.0)


def _nvda_items(body):
    out = []
    for q in QUOTED_RE.findall(body):
        try:
            val = ast.literal_eval(q)
        except (ValueError, SyntaxError):
            continue
        if isinstance(val, str) and val.strip():
            out.append(" ".join(val.split()))
    return out


def parse_speech_log(text):
    """List of entries: {"t": seconds or None, "items": [str], "text": str}
    and {"marker": step id}. Reads NVDA's log form and the plain form."""
    entries = []
    pending_t = None
    nvda = bool(NVDA_HEAD_RE.search(text))
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if nvda:
            head = NVDA_HEAD_RE.search(line)
            if head:
                pending_t = _secs(head.group(1))
                continue
            sp = NVDA_SPEAK_RE.match(line)
            if sp:
                items = _nvda_items(sp.group(1))
                if items:
                    entries.append({"t": pending_t, "items": items,
                                    "text": "  ".join(items)})
                pending_t = None
            continue
        mk = MARKER_RE.match(line.strip())
        if mk:
            entries.append({"marker": mk.group(1).lower()})
            continue
        t = None
        body = line.strip()
        first, _, rest = body.partition(" ")
        if _secs(first) is not None and rest.strip():
            t, body = _secs(first), rest.strip()
        items = [p.strip() for p in body.split("  ") if p.strip()]
        entries.append({"t": t, "items": items, "text": "  ".join(items)})
    return entries


def read_speech_log(path):
    p = Path(path)
    if p.stat().st_size > MAX_LOG_BYTES:
        raise PassError("the speech log is larger than 32 MB")
    return parse_speech_log(p.read_bytes().decode("utf-8", errors="replace"))


def split_steps(entries, timeline=None):
    """{step id: [utterance entries]} for the five steps. By the timeline's
    start times when it is given and every utterance has a time, else by the
    "# step" markers. Utterances before the first step are left out."""
    out = {s: [] for s in STEP_IDS}
    speech = [e for e in entries if "marker" not in e]
    starts = None
    if timeline:
        starts = []
        for st in timeline.get("steps", []):
            sec = _secs(st.get("start", ""))
            if st.get("id") in out and sec is not None:
                starts.append((sec, st["id"]))
        starts.sort()
    if starts and speech and all(e.get("t") is not None for e in speech):
        for e in speech:
            cur = None
            for sec, sid in starts:
                if e["t"] >= sec:
                    cur = sid
            if cur:
                out[cur].append(e)
        return out
    cur = None
    for e in entries:
        if "marker" in e:
            cur = e["marker"] if e["marker"] in out else None
        elif cur:
            out[cur].append(e)
    return out


def is_unnamed(items):
    words = [i.strip().lower() for i in items if i.strip()]
    if not words:
        return True
    if any(UNNAMED_RE.search(w) for w in words):
        return True
    return all(w in ROLE_WORDS for w in words)


def findings(steps):
    """(unnamed, doubled): lists of "<step>: <utterance>" lines. Doubled is
    the same utterance twice in a row inside one step."""
    unnamed, doubled = [], []
    for sid in STEP_IDS:
        prev = None
        for e in steps.get(sid, []):
            if is_unnamed(e["items"]):
                unnamed.append(f"{sid}: {e['text'] or '(empty)'}")
            key = e["text"].strip().lower()
            if prev is not None and key and key == prev:
                doubled.append(f"{sid}: {e['text']}")
            prev = key
    return unnamed, doubled


def _ascii(text):
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in str(text))


def render_transcript(steps, date, reader="NVDA"):
    """The transcript page (ASCII, LF)."""
    labels = dict(STEPS)
    lines = [TITLE, "", f"Date: {date}", f"Reader: {_ascii(reader)}",
             "Source: the reader's own speech log. Keys went to the page through "
             "the browser's DevTools protocol, never the OS input queue; no screen "
             "or audio was captured; the game was closed.", ""]
    for n, sid in enumerate(STEP_IDS, 1):
        lines.append(f"## {n}. {labels[sid]}")
        lines.append("")
        said = steps.get(sid, [])
        if not said:
            lines.append("- (nothing heard)")
        for e in said:
            lines.append(f"- \"{_ascii(e['text'])}\"")
        lines.append("")
    unnamed, doubled = findings(steps)
    lines.append("## Findings")
    lines.append("")
    lines.append("- unnamed: " + ("none" if not unnamed else str(len(unnamed))))
    lines.extend(f"  - {_ascii(u)}" for u in unnamed)
    lines.append("- doubled: " + ("none" if not doubled else str(len(doubled))))
    lines.extend(f"  - {_ascii(d)}" for d in doubled)
    return "\n".join(lines) + "\n"


def check_transcript(text):
    """Reasons the transcript fails (empty list = good): a Date line, the
    five step sections in order, each with at least one heard line, and
    'unnamed: none' / 'doubled: none' in the findings."""
    bad = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != TITLE:
        bad.append("the first line is not the title")
    dates = [ln for ln in lines if ln.startswith("Date: ")]
    if not dates:
        bad.append("no Date line")
    else:
        try:
            _dt.date.fromisoformat(dates[0][6:].strip())
        except ValueError:
            bad.append("the Date line is not YYYY-MM-DD")
    heads = [ln[3:].strip() for ln in lines if ln.startswith("## ")]
    want = [f"{n}. {label}" for n, (_, label) in enumerate(STEPS, 1)]
    if heads[:5] != want:
        bad.append("the step sections are not the five steps in order: " + ", ".join(want))
    sections, cur = {}, None
    for ln in lines:
        if ln.startswith("## "):
            cur = ln[3:].strip()
            sections[cur] = []
        elif cur is not None and ln.startswith("- "):
            sections[cur].append(ln)
    for head in want:
        heard = [ln for ln in sections.get(head, []) if ln != "- (nothing heard)"]
        if head in sections and not heard:
            bad.append(f"{head}: nothing heard")
    fin = sections.get("Findings", [])
    if "- unnamed: none" not in fin:
        bad.append("an unnamed announcement is listed (or the findings lack 'unnamed: none')")
    if "- doubled: none" not in fin:
        bad.append("a doubled announcement is listed (or the findings lack 'doubled: none')")
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        bad.append("the transcript is not ASCII")
    if "\r" in text:
        bad.append("the transcript has CR line ends")
    return bad


def write_text(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)


def build_transcript(speech_log, out, timeline=None, date=None, reader="NVDA"):
    entries = read_speech_log(speech_log)
    tl = None
    if timeline:
        tl = json.loads(Path(timeline).read_text(encoding="utf-8"))
    day = date or (tl or {}).get("date") or _dt.date.today().isoformat()
    text = render_transcript(split_steps(entries, tl), day, reader)
    write_text(out, text)
    return text


# ---------------------------------------------------------------- DevTools client

class DevTools:
    """A minimal WebSocket client for one DevTools page target (stdlib)."""

    def __init__(self, ws_url, timeout=30.0):
        m = re.match(r"^ws://127\.0\.0\.1:(\d+)(/.*)$", ws_url)
        if not m:
            raise PassError("the DevTools endpoint is not on 127.0.0.1")
        self.sock = socket.create_connection(("127.0.0.1", int(m.group(1))), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (f"GET {m.group(2)} HTTP/1.1\r\nHost: 127.0.0.1:{m.group(1)}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode("ascii"))
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise PassError("the DevTools endpoint closed the upgrade")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise PassError("the DevTools endpoint refused the upgrade")
        self.buf = head.split(b"\r\n\r\n", 1)[1]
        self.seq = 0

    def _recv_exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise PassError("the DevTools connection closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _send(self, text):
        self.sock.sendall(encode_frame(text.encode("utf-8")))

    def _recv(self):
        parts = []
        while True:
            b1, b2 = self._recv_exact(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if b2 & 0x80 else None
            data = self._recv_exact(n)
            if mask:
                data = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
            op = b1 & 0x0F
            if op == 0x8:
                raise PassError("the DevTools connection closed")
            if op in (0x9, 0xA):
                continue
            parts.append(data)
            if b1 & 0x80:
                return b"".join(parts).decode("utf-8", errors="replace")

    def call(self, method, params=None):
        self.seq += 1
        mid = self.seq
        self._send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self._recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise PassError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def key(self, key, code=None, vk=0, shift=False):
        """One key press to this page only (keyDown then keyUp)."""
        base = {"key": key, "code": code or key, "windowsVirtualKeyCode": vk,
                "nativeVirtualKeyCode": vk, "modifiers": 8 if shift else 0}
        self.call("Input.dispatchKeyEvent", dict(base, type="rawKeyDown"))
        self.call("Input.dispatchKeyEvent", dict(base, type="keyUp"))

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def encode_frame(payload, mask=None):
    """A masked, final text frame (client to server)."""
    mask = mask if mask is not None else os.urandom(4)
    n = len(payload)
    head = bytearray([0x81])
    if n < 126:
        head.append(0x80 | n)
    elif n < 65536:
        head.append(0x80 | 126)
        head += struct.pack(">H", n)
    else:
        head.append(0x80 | 127)
        head += struct.pack(">Q", n)
    body = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
    return bytes(head) + mask + body


# ---------------------------------------------------------------- the pass

def find_browser():
    env = os.environ.get("AL_CHROME", "").strip().strip('"')
    if env and Path(env).is_file():
        return env
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        for rel in (r"Google\Chrome\Application\chrome.exe",
                    r"Microsoft\Edge\Application\msedge.exe"):
            if base and (Path(base) / rel).is_file():
                return str(Path(base) / rel)
    for name in ("chrome", "msedge", "chromium"):
        hit = shutil.which(name)
        if hit:
            return hit
    return None


def _free_port():
    s = socket.socket()
    try:
        s.bind((ports.LOOPBACK, 0))
        return s.getsockname()[1]
    finally:
        s.close()


def _now():
    return _dt.datetime.now().strftime("%H:%M:%S.%f")[:12]


def _wait_line(proc, prefix, limit_s):
    end = time.monotonic() + limit_s
    while time.monotonic() < end:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            continue
        if prefix in line:
            return line.strip()
    raise PassError(f"the demo core gave no '{prefix}' line")


def _post_eval(port, token, text):
    if not hello.verify(port, token):
        raise PassError("the demo core failed the hello proof")
    body = json.dumps({"item": text}).encode("utf-8")
    req = urllib.request.Request(f"http://{ports.LOOPBACK}:{port}/api/eval", data=body,
                                 headers={"X-AL-Token": token,
                                          "Content-Type": "application/json"},
                                 method="POST")
    with hello.NO_PROXY_OPENER.open(req, timeout=10) as r:
        r.read(MAX_BODY)


def _append_log(log, line):
    stamp = _dt.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    with open(log, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{stamp} 99000 5380b6cc [INFO Client 5150] {line}\n")


def drive(fixture, browser, settle_s=SETTLE_S):
    """Run the five steps on a demo core in a visible browser; the timeline."""
    scratch_root = paths.sidecar_dir("Temp")
    scratch_root.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="sr-pass-", dir=str(scratch_root)))
    demo_dir = scratch / "fixture"
    shutil.copytree(fixture, demo_dir)
    core = subprocess.Popen(paths.python_cmd("server.al", "--demo", str(demo_dir)),
                            cwd=str(ROOT), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    chrome = tools = None
    timeline = {"date": _dt.date.today().isoformat(), "steps": []}
    try:
        line = _wait_line(core, " on http://", 60)
        url = line.split(" on ", 1)[1].strip()
        m = re.match(r"^http://127\.0\.0\.1:(\d+)/#token=([0-9A-Za-z_-]+)$", url)
        if not m or int(m.group(1)) == ports.AL_PORT:
            raise PassError("the demo core did not start on a demo port")
        port, token = int(m.group(1)), m.group(2)
        # keep reading the core's output so its pipe never fills
        threading.Thread(target=lambda: [None for _ in core.stdout],
                         daemon=True).start()
        dport = _free_port()
        chrome = subprocess.Popen(
            [browser, "--new-window", "--no-first-run", "--no-default-browser-check",
             "--disable-extensions", "--force-renderer-accessibility",
             f"--remote-debugging-port={dport}", f"--user-data-dir={scratch / 'profile'}",
             "about:blank"], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        targets = None
        for _ in range(150):
            try:
                with hello.NO_PROXY_OPENER.open(f"http://127.0.0.1:{dport}/json",
                                                timeout=2) as r:
                    targets = json.loads(r.read(MAX_BODY))
                break
            except (OSError, ValueError):
                time.sleep(0.1)
        page = next((t for t in targets or [] if t.get("type") == "page"), None)
        if not page:
            raise PassError("no DevTools page target")
        tools = DevTools(page["webSocketDebuggerUrl"])

        def step(sid, act):
            timeline["steps"].append({"id": sid, "start": _now()})
            _say(f"step {sid}")
            act()
            time.sleep(settle_s)
            timeline["steps"][-1]["end"] = _now()

        step("page-load", lambda: tools.call("Page.navigate", {"url": url}))
        step("item-check", lambda: _post_eval(port, token, ITEM_TEXT))
        step("trade-request", lambda: _append_log(demo_dir / "Client.txt", TRADE_WHISPER))

        def tab_switch():
            tools.call("Runtime.evaluate",
                       {"expression": "document.getElementById('tab-play').focus()"})
            tools.key("ArrowRight", vk=0x27)

        def settings_form():
            tools.call("Runtime.evaluate",
                       {"expression": "document.getElementById('tab-settings').focus()"})
            tools.key("Enter", vk=0x0D)
            for _ in range(SETTINGS_TABS):
                tools.key("Tab", vk=0x09)
                time.sleep(0.8)

        step("tab-switch", tab_switch)
        step("settings-form", settings_form)
        try:
            tools.call("Browser.close")
        except PassError:
            pass
    finally:
        if tools:
            tools.close()
        for proc in (chrome, core):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
    return timeline


def cmd_run(args, idle_reader=None, driver=None):
    refused = refusal(args.operator_ok, idle_reader or read_idle)
    if refused:
        code, reason = refused
        _say(reason)
        return code
    browser = args.browser or find_browser()
    if not browser:
        _say("failed: no Chrome or Edge found (set AL_CHROME)")
        return EXIT_FAIL
    try:
        timeline = (driver or drive)(Path(args.fixture), browser)
    except (PassError, OSError) as exc:
        _say(f"failed: {exc}")
        return EXIT_FAIL
    out = Path(args.out)
    tl_path = out.with_suffix(".timeline.json")
    write_text(tl_path, json.dumps(timeline, indent=1) + "\n")
    _say(f"timeline: {tl_path}")
    if args.speech_log:
        build_transcript(args.speech_log, out, tl_path, reader=args.reader)
        _say(f"transcript: {out}")
    return EXIT_OK


def cmd_transcript(args):
    try:
        text = build_transcript(args.speech_log, args.out, args.timeline, args.date,
                                args.reader)
    except (PassError, OSError, ValueError) as exc:
        _say(f"failed: {exc}")
        return EXIT_FAIL
    _say(f"transcript: {args.out}")
    bad = check_transcript(text)
    for b in bad:
        _say(f"check: {b}")
    return EXIT_OK


def cmd_check(args):
    try:
        text = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        _say(f"failed: {exc}")
        return EXIT_FAIL
    bad = check_transcript(text)
    for b in bad:
        _say(f"check: {b}")
    return EXIT_FAIL if bad else EXIT_OK


def parser():
    p = argparse.ArgumentParser(prog="sr_pass.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="drive the pass (operator flag and game_idle true)")
    r.add_argument("--operator-ok", action="store_true",
                   help="the operator's word that the game is closed (OA-35)")
    r.add_argument("--speech-log", help="the reader's own speech log")
    r.add_argument("--out", default=str(TRANSCRIPT_DOC), help="transcript path")
    r.add_argument("--fixture", default=str(FIXTURE), help="demo fixture folder")
    r.add_argument("--browser", help="Chrome or Edge executable")
    r.add_argument("--reader", default="NVDA", help="the screen reader's name")
    t = sub.add_parser("transcript", help="build a transcript from a speech log")
    t.add_argument("--speech-log", required=True)
    t.add_argument("--timeline")
    t.add_argument("--out", default=str(TRANSCRIPT_DOC))
    t.add_argument("--date")
    t.add_argument("--reader", default="NVDA")
    c = sub.add_parser("check", help="check a transcript")
    c.add_argument("file")
    return p


def main(argv=None, idle_reader=None, driver=None):
    args = parser().parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args, idle_reader, driver)
    if args.cmd == "transcript":
        return cmd_transcript(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
