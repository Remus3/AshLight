"""HOT-RELOAD (decision 0042): stat-only change watching for AshLight's own
files, so data, web and code edits reach a running app with no click.

Three parts, all polled from loops that already run (never a new thread,
never an OS file-change API, stat calls only):

- Watched / register(): one data file (a tracked data/ JSON, a cached
  snapshot). get() stats the file and re-reads it only when its (mtime,
  size) moved. A file that fails to parse keeps the LAST GOOD value and
  sets `error`, a one-line health note; a removed file reads as the
  default (as the old per-module caches did). Every Watched joins the
  module REGISTRY (weakly), whose poll() the core runs on its 0.5 s tick
  and whose notes() the Checks card shows.

  Other work calls the public API:

      from server.al import hotreload
      notes = hotreload.register(PATH, load_fn, name="zone guide",
                                 default=dict, check=hotreload.check_json())
      doc = notes.get()          # cheap: one stat, a read only on change

  load_fn(path) returns the parsed value or raises; `check` (optional)
  raises on a malformed file before load_fn runs, for loaders that turn a
  bad file into {} instead of raising.

- TreeWatch: a bounded stat scan of whole directories (web/ for the
  dashboard, server/ *.py for the supervisor). poll() is rate limited and
  says only "something changed".

- dev_enabled(): web and code reload are on when running from a source
  checkout (a .git entry at the repo root); config/local.json
  "hot_reload": true / false or env AL_HOT_RELOAD=1 / 0 override. Data
  file reload is always on.

Nothing here reads anything outside AshLight's own repo, runtime dir and
sidecar cache; it never touches the game (ToS floor).
"""

import json
import logging
import os
import threading
import time
import weakref
from pathlib import Path

from . import paths

LOG = logging.getLogger("al.hotreload")

CONFIG_KEY = "hot_reload"
ENV = "AL_HOT_RELOAD"
STATUS_FILE = "hotreload.json"       # supervisor -> core: code reload status
RESTART_FILE = "restart.request"     # supervisor -> core: exit for new code
TOKEN_REUSE_FILE = "token.reuse"     # old core -> new core: keep the token
TOKEN_REUSE_S = 120.0
TREE_MAX_FILES = 4000                # bound on one directory scan
NOTE_MAX = 160

_TRUE = ("1", "true", "on", "yes")
_FALSE = ("0", "false", "off", "no")


def dev_enabled(cfg=None, environ=None, root=None):
    """True when web / code hot reload should run: env AL_HOT_RELOAD,
    then config "hot_reload" (a bool), then "is this a source checkout"."""
    environ = os.environ if environ is None else environ
    value = str(environ.get(ENV) or "").strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    if isinstance(cfg, dict) and isinstance(cfg.get(CONFIG_KEY), bool):
        return cfg[CONFIG_KEY]
    root = paths.repo_root() if root is None else Path(root)
    return (root / ".git").exists()


def short_error(exc):
    """A one-line reason without a path (OSError text carries one)."""
    if isinstance(exc, OSError):
        return "could not be read"
    if isinstance(exc, json.JSONDecodeError):
        return f"not valid JSON at line {exc.lineno}"
    if isinstance(exc, UnicodeDecodeError):
        return "not plain text"
    text = " ".join(str(exc).split()) or type(exc).__name__
    return text[:NOTE_MAX]


def check_json(max_bytes=32 * 1024 * 1024, kind=dict):
    """A `check` for Watched: raise ValueError unless the file is at most
    max_bytes and parses as JSON of `kind`."""
    def check(path):
        p = Path(path)
        if p.stat().st_size > max_bytes:
            raise ValueError(f"larger than {max_bytes} bytes")
        doc = json.loads(p.read_text(encoding="utf-8"))
        if kind is not None and not isinstance(doc, kind):
            raise ValueError(f"not a JSON {getattr(kind, '__name__', 'value')}")
        return doc
    return check


def load_json(path):
    """A strict JSON loader for Watched (raises on any problem)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _stat_sig(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


class Watched:
    """One file, re-read on change, the last good value kept on a bad one."""

    def __init__(self, path, loader, name=None, default=None, check=None,
                 registry=None, on_change=None):
        self.path = Path(path)
        self.loader = loader
        self.name = name or self.path.name
        self._default = default if callable(default) else (lambda: default)
        self.check = check
        self.on_change = on_change
        self.error = None
        self.loads = 0           # successful (re)loads, for tests and notes
        self._sig = None
        self._value = self._default()
        self._lock = threading.RLock()
        reg = REGISTRY if registry is None else registry
        if reg is not False:
            reg.add(self)

    def get(self):
        sig = _stat_sig(self.path)
        with self._lock:
            if sig == self._sig:
                return self._value
            self._sig = sig
            if sig is None:
                self._value, self.error = self._default(), None
                return self._value
            try:
                if self.check is not None:
                    self.check(self.path)
                value = self.loader(self.path)
            except Exception as exc:  # noqa: BLE001 - keep the last good copy
                self.error = (f"{self.name} did not load ({short_error(exc)}). "
                              f"The last good copy stays in use.")
                LOG.warning("hot reload: %s", self.error)
                return self._value
            self._value, self.error = value, None
            self.loads += 1
        if self.on_change is not None and self.loads > 1:
            try:
                self.on_change(value)
            except Exception:  # noqa: BLE001 - a listener never breaks a load
                LOG.exception("hot reload listener failed for %s", self.name)
        return value


class Registry:
    """The data files the core re-checks on its tick (held weakly)."""

    def __init__(self):
        self._items = weakref.WeakSet()
        self._lock = threading.Lock()

    def add(self, watched):
        with self._lock:
            self._items.add(watched)
        return watched

    def watches(self):
        with self._lock:
            return sorted(self._items, key=lambda w: w.name)

    def poll(self):
        """Stat every registered file; re-read the changed ones."""
        for w in self.watches():
            try:
                w.get()
            except Exception:  # noqa: BLE001 - one bad watch never stops the tick
                LOG.exception("hot reload poll failed for %s", w.name)

    def notes(self):
        """One line per file that is holding a last good copy."""
        return [w.error for w in self.watches() if w.error]


REGISTRY = Registry()


def register(path, loader, name=None, default=None, check=None, on_change=None):
    """The public entry point: watch `path` with `loader`; returns the
    Watched (call .get() for the current value)."""
    return Watched(path, loader, name=name, default=default, check=check,
                   registry=REGISTRY, on_change=on_change)


class TreeWatch:
    """A rate-limited stat scan of directories; poll() is True once per
    change. `suffixes` limits the files looked at (None: all)."""

    def __init__(self, roots, suffixes=None, every_s=1.0, clock=time.monotonic,
                 max_files=TREE_MAX_FILES):
        self.roots = [Path(r) for r in roots]
        self.suffixes = tuple(s.lower() for s in suffixes) if suffixes else None
        self.every_s = float(every_s)
        self._clock = clock
        self.max_files = int(max_files)
        self._next = 0.0
        self._sig = None

    def _scan(self, root, out):
        try:
            entries = list(os.scandir(root))
        except OSError:
            return
        for e in entries:
            if len(out) >= self.max_files:
                return
            name = e.name
            if name.startswith(".") or name in ("__pycache__", "node_modules"):
                continue
            try:
                if e.is_dir(follow_symlinks=False):
                    self._scan(e.path, out)
                    continue
                if self.suffixes and not name.lower().endswith(self.suffixes):
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            out.append((e.path, st.st_mtime_ns, st.st_size))

    def signature(self):
        out = []
        for r in self.roots:
            self._scan(r, out)
        return tuple(sorted(out))

    def poll(self):
        now = self._clock()
        if now < self._next:
            return False
        self._next = now + self.every_s
        sig = self.signature()
        if self._sig is None:
            self._sig = sig
            return False
        if sig != self._sig:
            self._sig = sig
            return True
        return False


# -- code reload hand-off between the supervisor and the core

def write_status(runtime, code_error=None, now=None):
    """The supervisor's code reload status for the core's Checks card."""
    from . import jsonfile
    data = {"code_error": code_error, "updated": time.time() if now is None else now}
    try:
        jsonfile.write_text(Path(runtime) / STATUS_FILE, json.dumps(data) + "\n")
    except (OSError, UnicodeEncodeError):
        pass


def read_code_error(doc):
    value = doc.get("code_error") if isinstance(doc, dict) else None
    return value if isinstance(value, str) and value.strip() else None


def mark_token_reuse(runtime, now=None):
    """The old core, exiting for a code reload, lets the next start keep
    its token so the open dashboard and overlay reconnect on their own."""
    try:
        (Path(runtime) / TOKEN_REUSE_FILE).write_text(
            json.dumps({"at": time.time() if now is None else now}) + "\n", encoding="ascii")
    except OSError:
        pass


def take_token_reuse(runtime, token_file, now=None):
    """The token to keep (str) when a fresh reuse mark and a well-formed
    token file exist; the mark is always consumed. Else None."""
    mark = Path(runtime) / TOKEN_REUSE_FILE
    try:
        at = float(json.loads(mark.read_text(encoding="ascii")).get("at"))
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    finally:
        try:
            mark.unlink()
        except OSError:
            pass
    now = time.time() if now is None else now
    if not 0 <= now - at <= TOKEN_REUSE_S:
        return None
    try:
        token = Path(token_file).read_text(encoding="ascii").strip()
    except OSError:
        return None
    if len(token) == 48 and all(c in "0123456789abcdef" for c in token):
        return token
    return None
