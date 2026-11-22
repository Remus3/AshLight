"""HOT-RELOAD (decision 0042): stat-only change watching for AshLight's own
files, so data, web and code edits reach a running app with no click.

Three parts, all polled from loops that already run (never a new thread,
never an OS file-change API, stat calls only):

- Watched / register(): one data file (a tracked data/ JSON, a cached
  snapshot). get() stats the file and re-reads it only when its (mtime,
  size) moved. A file that fails to parse keeps the LAST GOOD value and
  sets `error`, a one-line health note; a removed file reads as the
  default (as the old per-module caches did). A read that hits an OSError
  (a lock, a share violation) is tried 3 times and, if still failing,
  leaves the signature unmoved so the next poll tries again; a bad content
  is not re-read until the file moves; a stat error other than "missing"
  keeps the last good value with a note. Every Watched joins the
  module REGISTRY (weakly), whose poll() the core runs on its 0.5 s tick
  and whose notes() the Checks card shows.

  Other work calls the public API:

      from server.al import hotreload
      notes = hotreload.register(PATH, load_fn, name="zone guide",
                                 default=dict, check=hotreload.check_json())
      doc = notes.get()          # cheap: one stat, a read only on change

  load_fn(path) returns the parsed value or raises; `check` (optional)
  raises on a malformed file before load_fn runs, for loaders that turn a
  bad file into {} instead of raising. With from_doc=fn the value is
  fn(document check returned), so a change is parsed once; share=True
  lets several tables of one file (world_areas, base_items) use one
  parse per change through a SharedDoc, each keeping its own last good
  copy (RUN-PERF-PARSE-ONCE).

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


def check_json(max_bytes=32 * 1024 * 1024, kind=dict, encoding="utf-8"):
    """A `check` for Watched: raise ValueError unless the file is at most
    max_bytes and parses as JSON of `kind` in `encoding`. It returns the
    parsed document, which a Watched with `from_doc` builds its value from
    (RUN-PERF-PARSE-ONCE: one parse per change, never a check parse and a
    second loader parse)."""
    def check(path):
        p = Path(path)
        if p.stat().st_size > max_bytes:
            raise ValueError(f"larger than {max_bytes} bytes")
        doc = json.loads(p.read_text(encoding=encoding))
        if kind is not None and not isinstance(doc, kind):
            raise ValueError(f"not a JSON {getattr(kind, '__name__', 'value')}")
        return doc
    return check


def load_json(path):
    """A strict JSON loader for Watched (raises on any problem)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


RETRY_TRIES = 3          # reads of one changed file on an OSError
RETRY_GAP_S = 0.05       # pause between those reads (at most 0.1 s)
SHARE_KEEP_S = 10.0      # a shared parsed document serves late joiners this long


def _stat_sig(path):
    """(mtime_ns, size), or None when the file is missing. Any other stat
    error (a denied or locked path) raises OSError: that is not a removed
    file, so the caller keeps its last good copy."""
    try:
        st = os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None
    return (st.st_mtime_ns, st.st_size)


def _with_retries(read, sleep, gap_s):
    """(result, None, False) on success, (None, reason, False) when the
    content is bad, (None, reason, True) when every read hit an OSError.
    Reasons are short_error text: no exception object is kept, so no
    traceback cycle holds a Watched past its last user."""
    reason = None
    for attempt in range(RETRY_TRIES):
        if attempt:
            sleep(min(gap_s, 0.1))
        try:
            return read(), None, False
        except OSError as exc:  # a transient lock or share violation
            reason = short_error(exc)
        except Exception as exc:  # noqa: BLE001 - keep the last good copy
            return None, short_error(exc), False
    return None, reason, True


class Watched:
    """One file, re-read on change, the last good value kept on a bad one.

    from_doc (optional): the value is from_doc(document), where the
    document is what `check` returned (load_json when there is no check or
    the check returns None), so a change is parsed once. share=True (needs
    from_doc): every Watched with share=True on the same path uses one
    SharedDoc, so one parse per change feeds all their tables; each table
    still keeps its own last good copy and note (decision 0042)."""

    def __init__(self, path, loader, name=None, default=None, check=None,
                 registry=None, on_change=None, from_doc=None, share=False):
        self.path = Path(path)
        self.loader = loader
        self.name = name or self.path.name
        self._default = default if callable(default) else (lambda: default)
        self.check = check
        self.on_change = on_change
        self.from_doc = from_doc
        self.error = None
        self.loads = 0           # successful (re)loads, for tests and notes
        self._sig = None
        self._stat_failed = False
        self._held_error = None  # the note a stat error covers, restored after
        self.retry_gap_s = RETRY_GAP_S
        self._sleep = time.sleep
        self._value = self._default()
        self._share = None
        if share and from_doc is not None:
            self._share = SharedDoc.of(self.path, check)
            self._lock = self._share.lock
            self._share.add(self)
        else:
            self._lock = threading.RLock()
        reg = REGISTRY if registry is None else registry
        if reg is not False:
            reg.add(self)

    def _note(self, text):
        """Set the note; log it only when its text changes, so a file that
        stays unreadable does not log on every poll."""
        if text != self.error:
            LOG.warning("hot reload: %s", text)
        self.error = text

    def _read(self):
        if self.from_doc is not None:
            doc = self.check(self.path) if self.check is not None else None
            return self.from_doc(load_json(self.path) if doc is None else doc)
        if self.check is not None:
            self.check(self.path)
        return self.loader(self.path)

    def _load(self):
        """(value, reason, transient) as _with_retries gives them."""
        return _with_retries(self._read, self._sleep, self.retry_gap_s)

    def _stat_error(self):
        """A stat that failed for a reason other than "missing"."""
        with self._lock:
            if not self._stat_failed:
                self._stat_failed = True
                self._held_error = self.error
            self._note(f"{self.name} could not be checked for changes. "
                       f"The last good copy stays in use.")
            return self._value

    def _stat_ok(self):
        """Caller holds the lock: a working stat restores the held note."""
        if self._stat_failed:
            self._stat_failed = False
            self.error, self._held_error = self._held_error, None

    def _settle(self, sig, value, reason, transient):
        """Caller holds the lock: take one load outcome for `sig`. True when
        a new value went in (and the listener is due)."""
        if sig is None:
            self._sig = sig
            self._value, self.error = self._default(), None
            return False
        if reason is not None:
            if not transient:
                self._sig = sig      # bad content: no re-read until it moves
            # transient: the signature stays old, so the next poll retries
            self._note(f"{self.name} did not load ({reason}). "
                       f"The last good copy stays in use.")
            return False
        self._sig = sig
        self._value, self.error = value, None
        self.loads += 1
        return True

    def _notify(self, value):
        if self.on_change is not None and self.loads > 1:
            try:
                self.on_change(value)
            except Exception:  # noqa: BLE001 - a listener never breaks a load
                LOG.exception("hot reload listener failed for %s", self.name)

    def get(self):
        if self._share is not None:
            return self._share.sync(self)
        try:
            sig = _stat_sig(self.path)
        except OSError:
            return self._stat_error()
        with self._lock:
            self._stat_ok()
            if sig == self._sig:
                return self._value
            if sig is None:
                self._settle(sig, None, None, False)
                return self._value
            value, reason, transient = self._load()
            fresh = self._settle(sig, value, reason, transient)
            current = self._value
        if fresh:
            self._notify(value)
        return current


class SharedDoc:
    """One data file read by several tables (RUN-PERF-PARSE-ONCE): one
    stat per get, one parse per change for every member whose table is
    behind, each member's value from its own from_doc. A bad file, or a
    from_doc that raises, keeps that member's last good copy only. The
    parsed document is kept SHARE_KEEP_S for a member that joins late
    (the core builds its caches one after another at start), then
    dropped, so the parsed tree does not stay in memory."""

    _SHARES = weakref.WeakValueDictionary()
    _SHARES_LOCK = threading.Lock()

    def __init__(self, path, check, clock=time.monotonic):
        self.path = Path(path)
        self.check = check
        self.lock = threading.RLock()
        self.parses = 0          # parses of the file, for tests
        self._members = weakref.WeakSet()
        self._clock = clock
        self._doc = None
        self._doc_sig = None
        self._doc_at = 0.0

    @classmethod
    def of(cls, path, check):
        """The SharedDoc for `path` (made on first use; the first member's
        check is the share's parse)."""
        key = os.path.normcase(os.path.abspath(str(path)))
        with cls._SHARES_LOCK:
            share = cls._SHARES.get(key)
            if share is None:
                share = cls(path, check)
                cls._SHARES[key] = share
            return share

    def add(self, member):
        with self.lock:
            self._members.add(member)

    def members(self):
        with self.lock:
            return list(self._members)

    def _parse(self):
        doc = self.check(self.path) if self.check is not None else None
        return load_json(self.path) if doc is None else doc

    def _drop_stale(self, sig):
        """Caller holds the lock: forget a document past its keep time or
        for another file signature."""
        if self._doc is not None and (self._doc_sig != sig or
                                      self._clock() - self._doc_at > SHARE_KEEP_S):
            self._doc = None

    def _document(self, sig, sleep, gap_s):
        """Caller holds the lock: (doc, reason, transient) for `sig`,
        parsing at most once while the kept document serves."""
        self._drop_stale(sig)
        if self._doc is not None:
            return self._doc, None, False
        doc, reason, transient = _with_retries(self._parse, sleep, gap_s)
        self.parses += 1
        if reason is None:
            self._doc, self._doc_sig, self._doc_at = doc, sig, self._clock()
        return doc, reason, transient

    def sync(self, caller):
        """Bring every member up to the file; returns caller's value."""
        try:
            sig = _stat_sig(self.path)
        except OSError:
            for m in self.members():
                m._stat_error()
            return caller._value
        fresh = []
        with self.lock:
            self._drop_stale(sig)
            behind = []
            for m in list(self._members):
                m._stat_ok()
                if m._sig != sig:
                    behind.append(m)
            if behind and sig is None:
                for m in behind:
                    m._settle(None, None, None, False)
            elif behind:
                doc, reason, transient = self._document(
                    sig, caller._sleep, caller.retry_gap_s)
                for m in behind:
                    if reason is not None:
                        m._settle(sig, None, reason, transient)
                        continue
                    try:
                        value, why = m.from_doc(doc), None
                    except Exception as exc:  # noqa: BLE001 - this table only
                        value, why = None, short_error(exc)
                    if m._settle(sig, value, why, False):
                        fresh.append((m, value))
                doc = None
            current = caller._value
        for m, value in fresh:
            m._notify(value)
        return current


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


def register(path, loader, name=None, default=None, check=None, on_change=None,
             from_doc=None, share=False):
    """The public entry point: watch `path` with `loader`; returns the
    Watched (call .get() for the current value)."""
    return Watched(path, loader, name=name, default=default, check=check,
                   registry=REGISTRY, on_change=on_change, from_doc=from_doc,
                   share=share)


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
    from . import jsonfile
    try:
        jsonfile.write_text(Path(runtime) / TOKEN_REUSE_FILE,
                            json.dumps({"at": time.time() if now is None else now}) + "\n")
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
