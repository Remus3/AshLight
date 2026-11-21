"""AUTO-15 (F-147): tools/shots.py render and check, the screenshot manifest.

- check compares the manifest's input hash with today's UI sources and
  fixture; it reads files only (no process, no socket, no browser);
- two renders of the same inputs give the same manifest (no time, no image
  bytes in it);
- render takes its port from the demo block (server.al.demo.pick_port,
  ports.DEMO_BLOCK) and refuses a core it did not start (another port in
  the URL line, a failed hello proof, a log outside the fixture);
- a demo start with a missing fixture log exits non-zero and opens no file
  outside the fixture folder, with a planted Steam root holding a decoy
  Client.txt (an audit hook records every open);
- the live runtime folder's mtime is unchanged;
- the browser command is capture.mjs's own headless set, nothing added;
- with node and a browser present, one real render from a real demo core.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import shots  # noqa: E402
from server.al import demo, hello, ports  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "demo"
TOKEN = "s" * 48
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 24
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ------------------------------------------------------------ helpers

def _tree(tmp_path):
    """A small root with UI sources and a demo fixture."""
    root = tmp_path / "root"
    (root / "web").mkdir(parents=True)
    (root / "web" / "index.html").write_text("<p>hi</p>\n", encoding="ascii")
    (root / "app" / "overlay").mkdir(parents=True)
    (root / "app" / "overlay" / "overlay.js").write_text("x = 1;\n", encoding="ascii")
    fx = root / "fixture"
    fx.mkdir()
    (fx / "Client.txt").write_text("line\n", encoding="ascii")
    (fx / demo.MARKER).write_text('{"ashlight_demo": 1}\n', encoding="ascii")
    return root, fx


class FakeChild:
    """Stands in for shots.DemoChild: a core that answers like a demo core."""

    started = []

    def __init__(self, root, fixture, port, url_port=None, log=None):
        FakeChild.started.append(port)
        self.port_asked = port
        self.port = url_port if url_port is not None else port
        self.token = TOKEN
        self.scratch = None
        self.log = str(log or Path(fixture) / "Client.txt")
        self.stopped = False

    def alive(self):
        return not self.stopped

    def get(self, path):
        if path == "/api/health":
            return {"ok": True, "port": self.port}
        return {"tailer": {"path": self.log, "reading": True, "consented": True,
                           "resume": {"recovered": ["zone", "level"]}}}

    def stop(self):
        self.stopped = True
        return 0


class Capture:
    def __init__(self):
        self.cmds = []

    def __call__(self, cmd, root):
        self.cmds.append(cmd)
        Path(cmd[5]).write_bytes(PNG)
        return 0, {"ok": True, "out": cmd[5]}


@pytest.fixture
def fake_world(monkeypatch, tmp_path):
    """No real core or browser: hello passes, ports are free, the sidecar
    and a planted live runtime folder live under tmp."""
    FakeChild.started = []
    monkeypatch.setattr(hello, "verify", lambda port, token, **kw: token == TOKEN)
    monkeypatch.setattr(demo, "_port_free", lambda port: True)
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(tmp_path / "sidecar"))
    live = tmp_path / "live_runtime"
    live.mkdir()
    (live / "token").write_text("live\n", encoding="ascii")
    monkeypatch.setenv("AL_RUNTIME_DIR", str(live))
    return live


def _render(out, start=FakeChild, capture=None, **kw):
    cap = capture or Capture()
    said = []
    rc = shots.render(ROOT, FIXTURE, out, start=start, capture=cap, node="node",
                      browser="browser.exe", say=said.append, **kw)
    return rc, cap, said


def _stat(p):
    st = p.stat()
    return (st.st_size, st.st_mtime_ns)


# ------------------------------------------------------------ check

def test_check_compares_the_manifest_hash(tmp_path):
    root, fx = _tree(tmp_path)
    out = root / "docs" / "shots"
    rc, msg = shots.check(root, fx, out)
    assert rc == 1 and "no manifest" in msg
    out.mkdir(parents=True)
    (out / shots.MANIFEST).write_text(shots.manifest_text(shots.manifest(root, fx)),
                                      encoding="ascii")
    assert shots.check(root, fx, out)[0] == 0
    # a UI source change makes it stale; so does a fixture change
    (root / "web" / "index.html").write_text("<p>changed</p>\n", encoding="ascii")
    assert shots.check(root, fx, out) == (
        1, "shots: stale (UI sources or fixture changed; run tools/shots.py render)")
    (out / shots.MANIFEST).write_text(shots.manifest_text(shots.manifest(root, fx)),
                                      encoding="ascii")
    assert shots.check(root, fx, out)[0] == 0
    (fx / "Client.txt").write_text("other\n", encoding="ascii")
    assert shots.check(root, fx, out)[0] == 1
    # a new file counts too, and a broken manifest is stale, not a crash
    (out / shots.MANIFEST).write_text(shots.manifest_text(shots.manifest(root, fx)),
                                      encoding="ascii")
    (root / "app" / "overlay" / "new.css").write_text("a{}\n", encoding="ascii")
    assert shots.check(root, fx, out)[0] == 1
    (out / shots.MANIFEST).write_text("{nope", encoding="ascii")
    assert shots.check(root, fx, out)[0] == 1


def test_check_starts_no_process_and_opens_no_socket(tmp_path, monkeypatch):
    root, fx = _tree(tmp_path)

    def boom(*a, **k):
        raise AssertionError("check started a process or opened a socket")

    import socket
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(socket, "socket", boom)
    assert shots.check(root, fx, root / "nowhere")[0] == 1
    assert shots.main(["check", "--fixture", str(fx), "--out", str(tmp_path / "o")]) == 1


def test_manifest_holds_no_machine_path_or_time(tmp_path):
    doc = shots.manifest(ROOT, FIXTURE)
    assert doc["fixture"] == "tests/fixtures/demo"
    text = shots.manifest_text(doc)
    text.encode("ascii")
    assert str(ROOT) not in text and ":\\" not in text
    assert set(doc) == {"schema", "tool", "inputs", "files", "fixture", "shots", "pending"}
    # a fixture outside the repo is named by its folder name only
    root, fx = _tree(tmp_path)
    assert shots.manifest(ROOT, fx)["fixture"] == "fixture"
    # every shot is a png of the page in a scheme and a size capture.mjs takes
    for s in doc["shots"]:
        assert s["file"].endswith(".png") and s["scheme"] in ("dark", "light")
        assert 200 <= s["width"] <= 4000 and 200 <= s["height"] <= 4000
    assert {(s["scheme"], s["width"]) for s in doc["shots"]} == {
        ("dark", 1440), ("light", 1440), ("dark", 360), ("light", 360)}


# ------------------------------------------------------------ render (fake core)

def test_two_renders_of_the_same_inputs_give_the_same_manifest(tmp_path, fake_world):
    a, b = tmp_path / "a", tmp_path / "b"
    assert _render(a)[0] == 0
    assert _render(b)[0] == 0
    ma = (a / shots.MANIFEST).read_bytes()
    assert ma == (b / shots.MANIFEST).read_bytes()
    assert b"\r" not in ma
    assert json.loads(ma)["inputs"] == shots.inputs_hash(ROOT, FIXTURE)[0]
    assert sorted(p.name for p in a.iterdir()) == sorted(
        [s["file"] for s in shots.SHOTS] + [shots.MANIFEST])
    # check agrees with a fresh render
    assert shots.check(ROOT, FIXTURE, a)[0] == 0


def test_render_takes_its_port_from_the_demo_block(tmp_path, fake_world, monkeypatch):
    lo, hi = sorted(ports.DEMO_BLOCK)
    monkeypatch.setattr(demo, "_port_free", lambda port: port != lo)  # first one taken
    rc, cap, _ = _render(tmp_path / "o")
    assert rc == 0
    assert FakeChild.started == [lo + 1]
    port = FakeChild.started[0]
    assert port in ports.block_range(ports.DEMO_BLOCK)
    assert port not in (ports.AL_PORT, ports.AL_DEV_PORT)
    assert all(f"http://127.0.0.1:{port}/#token=" in c[4] for c in cap.cmds)
    # every port taken: nothing starts
    FakeChild.started = []
    monkeypatch.setattr(demo, "_port_free", lambda port: False)
    rc, cap, said = _render(tmp_path / "p")
    assert rc == shots.FAILED and FakeChild.started == [] and cap.cmds == []
    assert "demo block" in said[-1]


@pytest.mark.parametrize("make, why", [
    (lambda r, f, p: FakeChild(r, f, p, url_port=ports.AL_PORT), "not the port"),
    (lambda r, f, p: FakeChild(r, f, p, url_port=p + 1), "not the port"),
    (lambda r, f, p: FakeChild(r, f, p, log=ROOT / "elsewhere" / "Client.txt"),
     "fixture's Client.txt"),
])
def test_render_refuses_a_core_it_did_not_start(tmp_path, fake_world, make, why):
    out = tmp_path / "o"
    rc, cap, said = _render(out, start=make)
    assert rc == shots.REFUSED, said
    assert why in said[-1]
    assert cap.cmds == []  # nothing was captured
    assert not (out / shots.MANIFEST).exists()


def test_render_refuses_a_listener_that_fails_the_hello_proof(tmp_path, fake_world,
                                                               monkeypatch):
    monkeypatch.setattr(hello, "verify", lambda port, token, **kw: False)
    rc, cap, said = _render(tmp_path / "o")
    assert rc == shots.REFUSED and "hello proof" in said[-1] and cap.cmds == []


def test_render_stops_on_a_helper_refusal_and_writes_no_manifest(tmp_path, fake_world):
    def refusing(cmd, root):
        return 2, {"refused": "not a demo core"}
    out = tmp_path / "o"
    children = []

    def start(r, f, p):
        children.append(FakeChild(r, f, p))
        return children[-1]
    rc, _, said = _render(out, start=start, capture=refusing)
    assert rc == shots.REFUSED and "not a demo core" in said[-1]
    assert not (out / shots.MANIFEST).exists()
    assert children and children[0].stopped  # its own core is stopped


def test_render_leaves_the_live_runtime_folder_untouched(tmp_path, fake_world):
    live = fake_world
    before = (_stat(live), sorted(p.name for p in live.iterdir()))
    repo_token = ROOT / "ops" / "runtime" / "token"
    repo_before = _stat(repo_token) if repo_token.is_file() else None
    assert _render(tmp_path / "o")[0] == 0
    assert (_stat(live), sorted(p.name for p in live.iterdir())) == before
    assert (_stat(repo_token) if repo_token.is_file() else None) == repo_before
    # the browser profiles went to the sidecar Temp folder, not the live one
    temp = tmp_path / "sidecar" / "Temp"
    assert [p.name.startswith("shots-") for p in temp.iterdir()] == [True]


def test_the_browser_command_is_the_helpers_headless_set(tmp_path, fake_world):
    rc, cap, _ = _render(tmp_path / "o")
    assert rc == 0 and len(cap.cmds) == len(shots.SHOTS)
    helper = (ROOT / shots.HELPER).read_text(encoding="utf-8")
    flags = helper[helper.index("BROWSER_FLAGS = Object.freeze(["):]
    flags = flags[:flags.index("]);")]
    assert '"--headless=new"' in flags and '"--disable-gpu"' in flags
    assert '"--remote-debugging-port=0"' in flags
    for cmd in cap.cmds:
        assert cmd[0] == "node" and Path(cmd[1]) == ROOT / shots.HELPER
        assert cmd[2] == "browser.exe"
        opts = [c for c in cmd if c.startswith("--")]
        assert [o.split("=")[0] for o in opts] == ["--width", "--height", "--scheme"]
        assert "--plan" not in cmd and not any("headless" in c for c in cmd)
    # the helper and the core run hidden at below-normal priority
    if os.name == "nt":
        assert shots.FLAGS & NO_WINDOW and shots.FLAGS & 0x00004000


# ------------------------------------------------------------ missing fixture log

AUDIT = r'''
import json, os, runpy, sys
out = open(sys.argv[1], "w", encoding="utf-8")
seen = []
WATCH = ("subprocess.Popen", "os.system", "os.startfile", "os.spawn", "os.exec",
         "socket.connect", "socket.bind")
def hook(ev, args):
    if ev == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        seen.append(os.path.abspath(os.fsdecode(args[0])))
    elif ev in WATCH:
        seen.append("EVENT:" + ev)
sys.addaudithook(hook)
mode, rest = sys.argv[2], sys.argv[3:]
rc = 0
try:
    if mode == "shots":
        sys.argv = ["tools/shots.py"] + rest
        runpy.run_path("tools/shots.py", run_name="__main__")
    else:
        sys.path.insert(0, ".")
        from server.al.__main__ import main
        rc = main(rest)
except SystemExit as exc:
    rc = exc.code if isinstance(exc.code, int) else 1
json.dump({"rc": rc, "seen": seen}, out)
out.close()
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
'''


def _audited(tmp_path, mode, args, env):
    script = tmp_path / "audit.py"
    script.write_text(AUDIT, encoding="ascii")
    record = tmp_path / f"seen-{mode}.json"
    r = subprocess.run([sys.executable, str(script), str(record), mode, *args],
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120,
                       creationflags=NO_WINDOW)
    assert record.is_file(), r.stdout + r.stderr
    doc = json.loads(record.read_text(encoding="utf-8"))
    return doc["rc"], doc["seen"], r.stdout + r.stderr


def test_missing_fixture_log_exits_non_zero_and_opens_nothing_outside(tmp_path):
    # a planted Steam root with a decoy Client.txt where the scan would look
    pf = tmp_path / "pf"
    logs = pf / "Steam" / "steamapps" / "common" / "Path of Exile 2" / "logs"
    logs.mkdir(parents=True)
    decoy = logs / "Client.txt"
    decoy.write_text("decoy\n", encoding="ascii")
    (pf / "Steam" / "steamapps" / "libraryfolders.vdf").write_text(
        '"libraryfolders"\n{\n "0"\n {\n  "path" "%s"\n }\n}\n'
        % str(pf / "Steam").replace("\\", "\\\\"), encoding="ascii")
    fx = tmp_path / "demo_no_log"
    fx.mkdir()
    (fx / demo.MARKER).write_text('{"ashlight_demo": 1}\n', encoding="ascii")
    sidecar = tmp_path / "sidecar"
    live = tmp_path / "live_runtime"
    live.mkdir()
    live_mtime = live.stat().st_mtime_ns
    out = tmp_path / "out"
    env = {k: v for k, v in os.environ.items() if k not in ("AL_PORT",)}
    env.update({"ProgramFiles": str(pf), "ProgramFiles(x86)": str(pf),
                "AL_SIDECAR_ROOT": str(sidecar), "AL_RUNTIME_DIR": str(live),
                "PYTHONDONTWRITEBYTECODE": "1"})
    runs = [("shots", ["render", "--fixture", str(fx), "--out", str(out)]),
            ("core", ["--demo", str(fx), "--port", "0"])]
    for mode, args in runs:
        rc, seen, text = _audited(tmp_path, mode, args, env)
        assert rc not in (0, None), (mode, rc, text)
        assert "Client.txt" in text, text
        opened = [s for s in seen if not s.startswith("EVENT:")]
        assert not [s for s in opened if str(pf) in s], (mode, opened)
        stray = [s for s in opened if Path(s).name.lower() == "client.txt"
                 and not s.startswith(str(fx))]
        assert stray == [], (mode, stray)
        events = [s for s in seen if s.startswith("EVENT:")]
        assert events == [], (mode, events)  # no process, no socket
    assert not out.exists() and not sidecar.exists()
    assert live.stat().st_mtime_ns == live_mtime and list(live.iterdir()) == []
    assert decoy.read_text(encoding="ascii") == "decoy\n"


def test_check_cli_exits_0_or_1_with_no_process_or_socket(tmp_path):
    rc, seen, text = _audited(tmp_path, "shots", ["check"], dict(os.environ))
    assert rc in (0, 1), text
    assert text.startswith("shots: ")
    assert [s for s in seen if s.startswith("EVENT:")] == []


# ------------------------------------------------------------ real render

def test_real_render_from_a_real_demo_core(tmp_path, monkeypatch):
    node, browser = shots.find_node(), shots.find_browser()
    if not node or not browser:
        pytest.skip("node or a Chrome / Edge browser not found")
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(tmp_path / "sidecar"))
    live = tmp_path / "live_runtime"
    live.mkdir()
    monkeypatch.setenv("AL_RUNTIME_DIR", str(live))
    live_mtime = live.stat().st_mtime_ns
    out = tmp_path / "shots"
    said = []
    rc = shots.render(ROOT, FIXTURE, out, say=said.append)
    assert rc == 0, said
    for s in shots.SHOTS:
        data = (out / s["file"]).read_bytes()
        assert data[1:4] == b"PNG"
        assert int.from_bytes(data[16:20], "big") == s["width"]
    fake_out = tmp_path / "fake"
    monkeypatch.setattr(hello, "verify", lambda port, token, **kw: token == TOKEN)
    assert _render(fake_out)[0] == 0
    assert (out / shots.MANIFEST).read_bytes() == (fake_out / shots.MANIFEST).read_bytes()
    assert live.stat().st_mtime_ns == live_mtime and list(live.iterdir()) == []
    assert sorted(p.name for p in FIXTURE.iterdir()) == ["Client.txt", demo.MARKER]
