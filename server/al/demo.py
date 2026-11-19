"""Demo mode core (decision 0049): an isolated AshLight instance on a fixture
folder.

`prepare(fixture_dir)` checks the folder (AshLight's demo marker
ashlight-demo.json and a Client.txt; a path with a `steamapps` or
`Path of Exile 2` part is refused from its text alone, before any stat),
makes a scratch folder under the sidecar Temp dir (resolved before any
override), points AL_RUNTIME_DIR, AL_SIDECAR_ROOT and the local config at
it, turns hot reload off (AL_HOT_RELOAD=0) and writes the demo consent
record, which covers the fixture's Client.txt only.

`DemoCore(demo)` is a Core on that scratch runtime: the fixture's Client.txt
is the only log, the Steam scan is off, web data is off and its fetcher
refuses every request, the consent API cannot name another log, and a log
path outside the fixture folder ends the process with exit code 97 before
anything opens it.

`pick_port()` returns the first free port of ports.DEMO_BLOCK, never the
core port 8960.

The entry point (`python -m server.al --demo <fixture dir>`) is
SEC-DEMO-ENTRY's; this module never starts a server by itself.
"""

import datetime as _dt
import json
import os
import re
import socket
import stat as _stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import VERSION, paths, ports, webfetch
from .core import Core, write_private

MARKER = "ashlight-demo.json"  # AshLight's demo marker in the fixture folder
MARKER_MAX_BYTES = 64 * 1024
LOG_NAME = "Client.txt"
EXIT_LOG_OUTSIDE = 97  # a log outside the fixture folder would be opened
SCRATCH_PREFIX = "demo-"
GAME_PARTS = ("steamapps", "path of exile 2")  # compared case-insensitively
HOT_RELOAD_ENV = "AL_HOT_RELOAD"


class DemoError(ValueError):
    """The fixture folder cannot back a demo instance; nothing was made."""


@dataclass(frozen=True)
class Demo:
    """A prepared demo instance: every path it may touch."""
    fixture: Path   # the fixture folder (resolved)
    log: Path       # fixture/Client.txt, the only log
    scratch: Path   # <sidecar Temp>/demo-*
    runtime: Path   # scratch/runtime (AL_RUNTIME_DIR)
    sidecar: Path   # scratch/sidecar (AL_SIDECAR_ROOT)
    config: Path    # scratch/runtime/local.json (paths.local_config_file)
    consent: Path   # scratch/runtime/consent.json


def _utc_now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def game_path_part(text):
    """The first path part of text that names a game folder (`steamapps`,
    `Path of Exile 2`, any case), else None. Text only: no stat."""
    for part in re.split(r"[\\/]+", str(text)):
        if part.strip().lower() in GAME_PARTS:
            return part
    return None


def _refuse_game_text(text):
    part = game_path_part(text)
    if part is not None:
        raise DemoError(f"a demo folder is never inside a game folder ({part!r} in the path)")


def _is_reparse(path):
    """True for a symlink or junction (lstat only; the target is not read)."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if _stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & getattr(_stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def check_fixture(fixture_dir):
    """(fixture folder, its Client.txt) after every check, else DemoError.
    The game-folder test runs on the text first, so a game folder is never
    stat'ed; links are refused so the log cannot lead out of the folder."""
    if not isinstance(fixture_dir, (str, os.PathLike)):
        raise DemoError("the demo folder must be a path")
    text = os.fspath(fixture_dir)
    if not text or "\x00" in text:
        raise DemoError("the demo folder must be a path")
    _refuse_game_text(text)
    absolute = os.path.abspath(text)  # lexical, no stat
    _refuse_game_text(absolute)
    folder = Path(absolute)
    if not folder.is_dir():
        raise DemoError(f"demo folder not found: {folder}")
    if _is_reparse(folder):
        raise DemoError("the demo folder must not be a link or junction")
    real = folder.resolve()
    _refuse_game_text(str(real))
    marker = real / MARKER
    if not marker.is_file():
        raise DemoError(f"not a demo folder: {MARKER} is missing")
    try:
        if marker.stat().st_size > MARKER_MAX_BYTES:
            raise DemoError(f"{MARKER} is too large")
        doc = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DemoError(f"{MARKER} is not readable JSON: {exc}") from None
    if not isinstance(doc, dict):
        raise DemoError(f"{MARKER} must hold a JSON object")
    log = real / LOG_NAME
    if _is_reparse(log):
        raise DemoError(f"the demo {LOG_NAME} must not be a link")
    if not log.is_file():
        raise DemoError(f"the demo folder has no {LOG_NAME}")
    return real, log


def consent_record(log, consented=True):
    """The demo consent record: it covers the fixture's Client.txt only."""
    return {"consented": bool(consented), "at": _utc_now(), "app_version": VERSION,
            "file": LOG_NAME, "derives": ["zone", "level", "deaths", "whispers",
                                          "session times"],
            "demo": True, "scope": "demo fixture file only", "path": str(log)}


def prepare(fixture_dir, environ=None):
    """Check the fixture folder, make the scratch folder and point this
    process at it (environ, default os.environ). Returns a Demo. Raises
    DemoError before anything is made when the folder is unusable."""
    env = os.environ if environ is None else environ
    fixture, log = check_fixture(fixture_dir)
    temp = paths.sidecar_dir("Temp", env)  # resolved before any override
    temp.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=SCRATCH_PREFIX, dir=str(temp))).resolve()
    runtime = scratch / "runtime"
    sidecar = scratch / "sidecar"
    runtime.mkdir()
    for name in paths.SIDECAR_SUBDIRS:
        (sidecar / name).mkdir(parents=True)
    env[paths.RUNTIME_ENV] = str(runtime)
    env[paths.SIDECAR_ENV] = str(sidecar)
    env[HOT_RELOAD_ENV] = "0"
    config = runtime / "local.json"
    paths.set_demo_config(config)
    consent = runtime / "consent.json"
    write_private(consent, json.dumps(consent_record(log), indent=1) + "\n")
    return Demo(fixture=fixture, log=log, scratch=scratch, runtime=runtime,
                sidecar=sidecar, config=config, consent=consent)


def refuse_fetch(method, url, headers, body=None):
    """The demo core's web transport: every request is refused, unsent."""
    raise webfetch.WebDataOff("demo mode: web data is off; no request is made")


def _hard_exit(code):
    sys.stderr.write(f"AshLight demo: a log outside the demo folder would be opened; "
                     f"exit {code}\n")
    sys.stderr.flush()
    os._exit(code)


class DemoCore(Core):
    """A Core that can only ever read the fixture's Client.txt."""

    FIXED = ("runtime", "log_path", "discover", "web_fetch", "config_path")

    def __init__(self, demo, exit_fn=None, **kwargs):
        fixed = sorted(set(kwargs) & set(self.FIXED))
        if fixed:
            raise TypeError(f"a demo core sets {', '.join(fixed)} itself")
        self.demo = demo
        self._exit = exit_fn or _hard_exit
        super().__init__(runtime=demo.runtime, log_path=str(demo.log), discover=False,
                         web_fetch=refuse_fetch, config_path=demo.config, **kwargs)

    def log_allowed(self, path):
        """True when path is a file inside the fixture folder (text first;
        a lexically inside path is resolved to catch a link out)."""
        if path is None:
            return True
        fixture = self.demo.fixture
        candidate = Path(os.path.abspath(os.fspath(path)))
        try:
            candidate.relative_to(fixture)
        except ValueError:
            return False
        try:
            candidate.resolve().relative_to(fixture)
        except (ValueError, OSError):
            return False
        return True

    def _guard_log(self, path):
        if not self.log_allowed(path):
            self._exit(EXIT_LOG_OUTSIDE)
            raise SystemExit(EXIT_LOG_OUTSIDE)  # an injected exit_fn returned

    def locate_log(self):
        found = super().locate_log()
        self._guard_log(found)
        return found

    def start_tailing(self):
        self._guard_log(self.log_path)
        return super().start_tailing()

    def record_consent(self, consented, path=None):
        """The consent API may turn reading on or off, never name a log."""
        if path:
            raise ValueError("demo mode: the log is the demo folder's Client.txt; "
                             "a consent path is refused")
        super().record_consent(consented)
        rec = consent_record(self.demo.log, consented)
        write_private(self.consent_path, json.dumps(rec, indent=1) + "\n")
        return rec

    def web_data_enabled(self):
        """Web data is always off in a demo instance."""
        return False


def _port_free(port):
    """True when 127.0.0.1:port can be bound now (closed again at once)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind((ports.LOOPBACK, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def pick_port(probe=None):
    """The first free port of ports.DEMO_BLOCK (probe(port) -> bool, default
    a loopback bind); DemoError when every port is taken. Never 8960."""
    probe = probe or _port_free
    for port in ports.block_range(ports.DEMO_BLOCK):
        if port == ports.AL_PORT:
            continue
        if probe(port):
            return port
    lo, hi = sorted(ports.DEMO_BLOCK)
    raise DemoError(f"no free port in the demo block {lo}-{hi}")
