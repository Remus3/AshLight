#!/usr/bin/env python3
"""AshLight screenshots from a demo core (AUTO-15, F-147).

    shots.py check  [--fixture DIR] [--out DIR]
    shots.py render [--fixture DIR] [--out DIR]
    shots.py hash   [--fixture DIR]

check compares the input hash recorded in <out>/manifest.json with the hash
of today's UI sources and demo fixture. It reads files only: no browser, no
process, no socket. Exit 0 = fresh, 1 = stale or no manifest.

render starts its OWN demo core (`python -m server.al --demo <fixture>`,
decision 0049) on the first free port of ports.DEMO_BLOCK
(server.al.demo.pick_port; never the core port or the dev port), waits until
the core has read the fixture's Client.txt, and saves each shot of SHOTS
through the one capture helper app/test/cdp/capture.mjs (headless browser,
software rendering, below-normal priority, no window). It then writes
<out>/manifest.json. Exit 0 = rendered, 2 = refused (nothing captured),
3 = a start, wait or capture failed.

render refuses any core it did not start: it takes no port or URL from
outside; the URL line must come from its own child process and name the port
it chose; the listener must pass the hello proof (decision 0054) for the
child's token; /api/health must name that port; the tailed log must be the
fixture's Client.txt. capture.mjs repeats its own checks before the browser
starts. Nothing here touches the live core, the live runtime folder,
config/local.json or the live Client.txt, and no web request is made (a demo
core has web data off).

The manifest holds no time and no image bytes, so two renders of the same
inputs give the same manifest. Defaults: --fixture tests/fixtures/demo,
--out docs/shots. Scratch files (browser profiles) go under the sidecar Temp
folder. Standard library only.
"""

import argparse
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = 1
MANIFEST = "manifest.json"
DEFAULT_FIXTURE = Path("tests") / "fixtures" / "demo"
DEFAULT_OUT = Path("docs") / "shots"
HELPER = Path("app") / "test" / "cdp" / "capture.mjs"

# The UI sources whose change makes the images stale (folders are walked).
UI_SOURCES = ("web", "app/overlay", "app/shared", "ops/fleet_kit/tokens.css",
              "app/test/cdp/capture.mjs", "tools/shots.py")

# The shot plan: what the helper can render truthfully today. capture.mjs
# opens each page in a new, empty browser profile, so the dashboard shows
# its opening tab (Play); it has no tab option, and the core serves web/
# only (the overlay is a file:// page of the client). PENDING names the
# shots that wait for those two seams.
SIZES = ((1440, 900), (360, 800))
SCHEMES = ("dark", "light")
SHOTS = tuple({"file": f"play-{scheme}-{w}.png", "page": "/", "tab": "play",
               "scheme": scheme, "width": w, "height": h}
              for scheme in SCHEMES for (w, h) in SIZES)
PENDING = (
    {"shot": "build, run and settings tabs",
     "needs": "a tab option in app/test/cdp/capture.mjs"},
    {"shot": "overlay page on a plain ground",
     "needs": "the overlay page served by the demo core"},
)

URL_RE = re.compile(r"http://127\.0\.0\.1:(\d+)/#token=([0-9A-Za-z_\-]+)")
SCRATCH_RE = re.compile(r"^demo mode: fixture .+; scratch (.+)$")
BROWSERS = (r"Google\Chrome\Application\chrome.exe",
            r"Microsoft\Edge\Application\msedge.exe")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BELOW_NORMAL = 0x00004000 if os.name == "nt" else 0  # BELOW_NORMAL_PRIORITY_CLASS
FLAGS = NO_WINDOW | BELOW_NORMAL
START_S = 60.0
LOAD_S = 30.0
STOP_S = 20.0
CAPTURE_S = 90.0
REFUSED, FAILED = 2, 3


class Refused(Exception):
    """render will not capture: the target is not its own demo core."""


class Failed(Exception):
    """a start, wait or capture failed."""


# ------------------------------------------------------------------ hashing

def _rel(path, root):
    return path.relative_to(root).as_posix()


def source_files(root):
    """Sorted (relpath, Path) of every UI source file that exists."""
    root = Path(root)
    out = {}
    for item in UI_SOURCES:
        p = root / item
        if p.is_file():
            out[_rel(p, root)] = p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts:
                    out[_rel(f, root)] = f
    return sorted(out.items())


def fixture_files(fixture):
    fixture = Path(fixture)
    if not fixture.is_dir():
        return []
    return sorted(("fixture/" + _rel(f, fixture), f)
                  for f in fixture.rglob("*") if f.is_file())


def inputs_hash(root, fixture):
    """(sha256 hex, number of files) over the UI sources and the fixture:
    each file's relative path and content hash, in sorted order."""
    h = hashlib.sha256()
    files = source_files(root) + fixture_files(fixture)
    for rel, path in files:
        h.update(rel.encode("utf-8") + b"\0"
                 + hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return h.hexdigest(), len(files)


def fixture_label(root, fixture):
    """The fixture as a repo-relative path, else its folder name only (a
    tracked manifest never holds a machine path)."""
    try:
        return Path(fixture).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(fixture).name


def manifest(root, fixture):
    digest, count = inputs_hash(root, fixture)
    return {"schema": SCHEMA, "tool": "tools/shots.py", "inputs": digest,
            "files": count, "fixture": fixture_label(root, fixture),
            "shots": [dict(s) for s in SHOTS], "pending": [dict(p) for p in PENDING]}


def manifest_text(doc):
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def check(root, fixture, out):
    """(exit code, message): 0 when the manifest's input hash is today's."""
    path = Path(out) / MANIFEST
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return 1, "shots: stale (no manifest yet; run tools/shots.py render)"
    except (OSError, ValueError) as exc:
        return 1, f"shots: stale (manifest unreadable: {type(exc).__name__})"
    digest, _ = inputs_hash(root, fixture)
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return 1, "shots: stale (manifest schema changed; run tools/shots.py render)"
    if doc.get("inputs") != digest:
        return 1, "shots: stale (UI sources or fixture changed; run tools/shots.py render)"
    return 0, f"shots: fresh ({digest[:12]})"


# ------------------------------------------------------------------ tools

def find_node():
    env = os.environ.get("AL_NODE", "").strip().strip('"')
    if env and Path(env).is_file():
        return env
    return shutil.which("node")


def find_browser():
    env = os.environ.get("AL_CHROME", "").strip().strip('"')
    if env and Path(env).is_file():
        return env
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        for rel in BROWSERS if base else ():
            p = Path(base) / rel
            if p.is_file():
                return str(p)
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        hit = shutil.which(name)
        if hit:
            return hit
    return None


def _al():
    """server.al modules, imported only by render (check stays file-only)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from server.al import demo, hello, paths, ports
    return demo, hello, paths, ports


# ------------------------------------------------------------------ demo core

def child_env():
    """The environment of the demo child: no live runtime or port override
    (demo.prepare sets its own runtime, sidecar and config), no bytecode."""
    _, _, paths, ports = _al()
    env = {k: v for k, v in os.environ.items()
           if k not in (paths.RUNTIME_ENV, ports.PORT_ENV)}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


class DemoChild:
    """This tool's own `python -m server.al --demo <fixture> --port <port>`."""

    def __init__(self, root, fixture, port):
        self.port_asked = port
        self.port = self.token = self.scratch = None
        self.lines = []
        self._q = queue.Queue()
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "server.al", "--demo", str(fixture), "--port", str(port)],
            cwd=str(root), env=child_env(), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", creationflags=FLAGS)
        threading.Thread(target=self._read, daemon=True).start()
        deadline = time.monotonic() + START_S
        while (self.port is None or self.scratch is None) and time.monotonic() < deadline:
            try:
                line = self._q.get(timeout=0.5)
            except queue.Empty:
                if self.proc.poll() is not None:
                    break
                continue
            m = URL_RE.search(line)
            if m:
                self.port, self.token = int(m.group(1)), m.group(2)
            m = SCRATCH_RE.match(line.strip())
            if m:
                self.scratch = Path(m.group(1))
        if self.port is None or self.scratch is None:
            self.stop()
            tail = " | ".join(self.lines[-5:])
            raise Failed(f"the demo core did not start (exit {self.proc.poll()}): {tail}")

    def _read(self):
        for line in self.proc.stdout:
            self.lines.append(line.rstrip("\n"))
            self._q.put(line)

    def alive(self):
        return self.proc.poll() is None

    def get(self, path):
        _, _, _, ports = _al()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(f"http://{ports.LOOPBACK}:{self.port}{path}",
                                     headers={"X-AL-Token": self.token})
        with opener.open(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def stop(self):
        """A clean stop through the scratch stop.request, else a kill."""
        if self.proc.poll() is not None:
            return self.proc.returncode
        if self.scratch is not None:
            try:
                (self.scratch / "runtime" / "stop.request").write_text("stop\n",
                                                                         encoding="ascii")
            except OSError:
                pass
        try:
            return self.proc.wait(STOP_S if self.scratch is not None else 0.1)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            return self.proc.wait(STOP_S)


def _inside(path, folder):
    try:
        Path(os.path.abspath(path)).resolve().relative_to(Path(folder).resolve())
        return True
    except (ValueError, OSError):
        return False


def verify_own(child, port, fixture):
    """Refused unless the core on port is this tool's child: same port as
    asked, still running, the hello proof for its token, health on that
    port, and the fixture's Client.txt as its log."""
    _, hello, _, ports = _al()
    if child.port != port or child.port_asked != port:
        raise Refused(f"the core answered on port {child.port}, not the port {port} "
                      "this run chose; not its own core")
    if port in (ports.AL_PORT, ports.AL_DEV_PORT) or port not in ports.block_range(
            ports.DEMO_BLOCK):
        raise Refused(f"port {port} is not a demo block port")
    if not child.alive():
        raise Refused("the demo core this run started has exited")
    if not hello.verify(port, child.token):
        raise Refused("the listener failed the hello proof for this run's token")
    health = child.get("/api/health")
    if not isinstance(health, dict) or health.get("port") != port:
        raise Refused("the listener is not an AshLight core on the chosen port")
    log = ((child.get("/api/state") or {}).get("tailer") or {}).get("path")
    if not log or not _inside(log, fixture) or Path(log).name != "Client.txt":
        raise Refused("the core does not read the fixture's Client.txt")


def wait_loaded(child, timeout=LOAD_S):
    """Wait until the core tails the fixture log and its resume scan (the
    fixture session) has been read."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        if not child.alive():
            break
        try:
            tl = (child.get("/api/state") or {}).get("tailer") or {}
            last = tl
            # reading the fixture log and its start-up resume scan is done
            if tl.get("reading") and tl.get("path") and isinstance(tl.get("resume"), dict):
                return tl
        except (OSError, ValueError) as exc:
            last = type(exc).__name__
        time.sleep(0.25)
    raise Failed(f"the demo core never read the fixture session (last {last!r})")


# ------------------------------------------------------------------ capture

def capture_cmd(node, root, browser, profile, url, out_png, shot):
    """The helper command for one shot. The browser flags are capture.mjs's
    own frozen headless set; nothing here adds or changes one."""
    return [node, str(Path(root) / HELPER), browser, str(profile), url, str(out_png),
            f"--width={shot['width']}", f"--height={shot['height']}",
            f"--scheme={shot['scheme']}"]


def run_capture(cmd, root):
    """Run one helper command hidden, at below-normal priority: (rc, last
    JSON line as a dict)."""
    r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=CAPTURE_S,
                       stdin=subprocess.DEVNULL, creationflags=FLAGS)
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    try:
        doc = json.loads(lines[-1]) if lines else {}
    except ValueError:
        doc = {"error": lines[-1][:200]}
    return r.returncode, doc


def render(root=ROOT, fixture=None, out=None, *, start=DemoChild, capture=run_capture,
           pick_port=None, node=None, browser=None, say=print):
    """Render every shot of SHOTS from this run's own demo core into out and
    write the manifest. Returns the exit code."""
    root = Path(root)
    fixture = Path(fixture) if fixture else root / DEFAULT_FIXTURE
    out = Path(out) if out else root / DEFAULT_OUT
    demo, _, paths, _ = _al()
    try:
        fixture, _ = demo.check_fixture(fixture)  # no process before this holds
    except demo.DemoError as exc:
        say(f"shots: refused: {exc}")
        return REFUSED
    node = node or find_node()
    browser = browser or find_browser()
    if not node or not browser:
        say("shots: failed: " + ("node" if not node else "a Chrome or Edge browser")
            + " was not found")
        return FAILED
    try:
        port = (pick_port or demo.pick_port)()
    except demo.DemoError as exc:
        say(f"shots: failed: {exc}")
        return FAILED
    child = None
    try:
        child = start(root, fixture, port)
        verify_own(child, port, fixture)
        wait_loaded(child)
        verify_own(child, port, fixture)
        temp = paths.sidecar_dir("Temp")
        temp.mkdir(parents=True, exist_ok=True)
        scratch = Path(tempfile.mkdtemp(prefix="shots-", dir=str(temp)))
        out.mkdir(parents=True, exist_ok=True)
        url = f"http://127.0.0.1:{port}/#token={child.token}"
        for i, shot in enumerate(SHOTS):
            if not child.alive():
                raise Refused("the demo core this run started has exited")
            cmd = capture_cmd(node, root, browser, scratch / f"profile-{i}", url,
                              out / shot["file"], shot)
            rc, doc = capture(cmd, root)
            if rc == REFUSED or "refused" in doc:
                raise Refused(f"capture.mjs refused {shot['file']}: {doc.get('refused')}")
            if rc != 0 or not doc.get("ok"):
                raise Failed(f"capture of {shot['file']} failed (exit {rc}): {doc}")
        text = manifest_text(manifest(root, fixture))
        tmp = out / (MANIFEST + ".tmp")
        tmp.write_bytes(text.encode("ascii"))
        os.replace(tmp, out / MANIFEST)
        say(f"shots: rendered {len(SHOTS)} shot(s); {len(PENDING)} pending")
        return 0
    except Refused as exc:
        say(f"shots: refused: {exc}")
        return REFUSED
    except (Failed, OSError, ValueError, subprocess.SubprocessError) as exc:
        say(f"shots: failed: {exc}")
        return FAILED
    finally:
        if child is not None:
            child.stop()


# ------------------------------------------------------------------ cli

def build_parser():
    p = argparse.ArgumentParser(prog="shots.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "render", "hash"):
        s = sub.add_parser(name)
        s.add_argument("--fixture", default=None, help="demo fixture folder")
        if name != "hash":
            s.add_argument("--out", default=None, help="shots folder")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    fixture = Path(args.fixture) if args.fixture else ROOT / DEFAULT_FIXTURE
    if args.cmd == "hash":
        digest, count = inputs_hash(ROOT, fixture)
        print(f"{digest} {count}")
        return 0
    out = Path(args.out) if args.out else ROOT / DEFAULT_OUT
    if args.cmd == "check":
        rc, msg = check(ROOT, fixture, out)
        print(msg)
        return rc
    return render(ROOT, fixture, out)


if __name__ == "__main__":
    sys.exit(main())
