"""AREA-TEST batch 6: the one helper for AshLight's small JSON / text files
(runtime state under ops/runtime or the sidecar, caches, config/local.json).

read_json() never raises: a missing, unreadable, oversized or corrupt file
reads as None (or `default`), so a hand-broken or half-written file never
stops the core. write_json() / write_text() / write_bytes() are atomic and
durable (RUN-DURABLE-JSONFILE, finding F-014, research 0050 R4):

- the data goes to a unique sibling temp file (`<name>.<pid>.<hex>.tmp`,
  created exclusively, so two writers never share one), is flushed and
  os.fsync'ed (sync=False skips the fsync, for the heartbeat), then
  os.replace swaps it in, so a reader sees the old file or the new one,
  never a torn one;
- os.replace is retried on PermissionError (a reader, the indexer or an
  antivirus holding the target without delete sharing) 5 times over
  250 ms; on a final failure the temp file is removed and the error
  raised, and the target keeps its old content;
- backup=True also keeps `<name>.bak`, a second atomic copy of the last
  good (fully written) content; read_json(..., backup=True) restores the
  main file from it when the main file exists but does not parse (empty,
  half written, wrong kind) and records the path for pop_restored().

Written text is ASCII + LF (json.dumps(ensure_ascii=True)); a non-ASCII
text raises UnicodeEncodeError before any file is touched.

Saver is the small save scheduler for stores: mark() sets a dirty flag,
flush() runs the store's save callable and on a failure waits 1, 5, 30,
then 60 s before the next attempt.
"""

import json
import os
import threading
import time
from pathlib import Path

# AREA-AUDIT P7-8: read_json's cap when the caller names none (config,
# displays.json, summaries, poe.ninja caches); a bigger file reads as default
DEFAULT_MAX_BYTES = 32 * 1024 * 1024

# F-014: waits between os.replace attempts on PermissionError: 1 try plus 5
# retries, 250 ms of waiting in all
REPLACE_DELAYS = (0.01, 0.02, 0.04, 0.08, 0.10)

# Saver back-off after 1, 2, 3 and 4+ failed saves, in seconds
SAVER_DELAYS = (1.0, 5.0, 30.0, 60.0)

_sleep = time.sleep  # tests patch this to keep the retry path fast
_restored = []
_restored_lock = threading.Lock()


def _parse(path, cap, encoding, kind):
    """(ok, doc) for one file; ok is False when it is missing, unreadable,
    over `cap`, not JSON in `encoding` or not an instance of `kind`."""
    try:
        p = Path(path)
        if p.stat().st_size > cap:
            return False, None
        doc = json.loads(p.read_text(encoding=encoding))
    except (OSError, ValueError, RecursionError):  # AREA-AUDIT P7-3: deep nesting
        return False, None
    if kind is not None and not isinstance(doc, kind):
        return False, None
    return True, doc


def read_json(path, max_bytes=None, encoding="utf-8", kind=None, default=None,
              backup=False):
    """The parsed JSON of `path`, or `default` when the file is missing,
    unreadable, larger than `max_bytes` (None: DEFAULT_MAX_BYTES, AREA-AUDIT
    P7-8; a caller that needs more passes it), not valid JSON in
    `encoding`, or (with `kind`, a type or tuple of types) not an instance
    of `kind`.

    backup=True: when the main file exists but fails those checks and
    `<name>.bak` passes them, the backup's content is written back to the
    main file, the path is recorded for pop_restored() and the backup's
    document returned. A missing main file is not restored (a cleared
    store removes both)."""
    cap = DEFAULT_MAX_BYTES if max_bytes is None else max_bytes
    ok, doc = _parse(path, cap, encoding, kind)
    if ok:
        return doc
    if not backup:
        return default
    p = Path(path)
    try:
        if not p.is_file():
            return default
    except OSError:
        return default
    bak = bak_path(p)
    ok, doc = _parse(bak, cap, encoding, kind)
    if not ok:
        return default
    try:
        write_bytes(p, bak.read_bytes())
    except OSError:
        pass  # the document is still good; the next save rewrites the file
    with _restored_lock:
        _restored.append(str(p))
    return doc


def pop_restored():
    """The paths read_json(..., backup=True) restored from their .bak since
    the last call, oldest first; the list is cleared."""
    with _restored_lock:
        out = list(_restored)
        del _restored[:]
    return out


def tmp_path(path, tag=None):
    """The sibling temp name of `path`: `<name>.tmp`, or `<name>.<tag>.tmp`
    with a tag. Writes use a unique tag per call (_unique_tmp)."""
    path = Path(path)
    if tag is None:
        return path.with_name(path.name + ".tmp")
    return path.with_name("%s.%s.tmp" % (path.name, tag))


def bak_path(path):
    """The sibling `.bak` file a backup=True write keeps."""
    path = Path(path)
    return path.with_name(path.name + ".bak")


def _unique_tmp(path):
    return tmp_path(path, "%d.%s" % (os.getpid(), os.urandom(6).hex()))


def _replace(src, dst):
    """os.replace with the F-014 retry on PermissionError."""
    for delay in REPLACE_DELAYS:
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            _sleep(delay)
    os.replace(src, dst)


def _atomic(path, data, sync):
    tmp = _unique_tmp(path)
    try:
        with open(tmp, "xb") as fh:
            fh.write(data)
            fh.flush()
            if sync:
                os.fsync(fh.fileno())
        _replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_bytes(path, data, backup=False, sync=True):
    """Write `data` to `path` atomically and durably, making its parents
    (unique temp, flush, fsync unless sync=False, retried replace).
    backup=True also writes the same bytes to `<name>.bak`."""
    path = Path(path)
    data = bytes(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic(path, data, sync)
    if backup:
        _atomic(bak_path(path), data, sync)


def write_text(path, text, backup=False, sync=True):
    """Write `text` (ASCII, LF) to `path` atomically, making its parents.
    A non-ASCII text raises UnicodeEncodeError before any file is touched."""
    write_bytes(path, text.encode("ascii"), backup=backup, sync=sync)


def dumps(doc, indent=1, sort_keys=False):
    """The file text of `doc`: ASCII-escaped JSON plus one trailing LF."""
    return json.dumps(doc, indent=indent, sort_keys=sort_keys, ensure_ascii=True) + "\n"


def write_json(path, doc, indent=1, sort_keys=False, backup=False, sync=True):
    """Write `doc` as JSON (ASCII, LF, trailing newline) atomically."""
    write_text(path, dumps(doc, indent=indent, sort_keys=sort_keys),
               backup=backup, sync=sync)


class Saver:
    """Dirty flag plus back-off for one store's save.

    `save` is a callable that writes the store's current state and raises on
    failure. mark() records unsaved changes; flush(now) saves when dirty and
    the back-off allows it. After the n-th failure in a row the next attempt
    waits SAVER_DELAYS[n-1] (1, 5, 30, then 60 s for every later one); a
    mark() during the wait does not shorten it. A success clears the dirty
    flag, the failure count and last_error."""

    def __init__(self, save, delays=SAVER_DELAYS, clock=time.monotonic):
        self._save = save
        self._delays = tuple(delays)
        self._clock = clock
        self._lock = threading.Lock()
        self.dirty = False
        self.failures = 0
        self.last_error = None
        self.next_at = 0.0

    def mark(self):
        with self._lock:
            self.dirty = True

    def flush(self, now=None, force=False):
        """Save if dirty and due (force: ignore the back-off). True when
        nothing is left unsaved, False while a save is pending."""
        with self._lock:
            if not self.dirty:
                return True
            t = self._clock() if now is None else now
            if not force and t < self.next_at:
                return False
            self.dirty = False
            try:
                self._save()
            except Exception as exc:
                self.dirty = True
                self.failures += 1
                self.last_error = "%s: %s" % (type(exc).__name__, exc)
                i = min(self.failures, len(self._delays)) - 1
                self.next_at = t + self._delays[i]
                return False
            self.failures = 0
            self.last_error = None
            self.next_at = 0.0
            return True
