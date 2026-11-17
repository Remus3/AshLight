"""AREA-TEST batch 6: the one helper for AshLight's small JSON / text files
(runtime state under ops/runtime or the sidecar, caches, config/local.json).

read_json() never raises: a missing, unreadable, oversized or corrupt file
reads as None (or `default`), so a hand-broken or half-written file never
stops the core. write_json() / write_text() are atomic: the text goes to
<name>.tmp next to the target, then os.replace swaps it in, so a reader sees
the old file or the new one, never a torn one. Written files are ASCII + LF
(json.dumps(ensure_ascii=True)); a non-ASCII text raises UnicodeEncodeError
before the target is touched.
"""

import json
import os
from pathlib import Path

# AREA-AUDIT P7-8: read_json's cap when the caller names none (config,
# displays.json, summaries, poe.ninja caches); a bigger file reads as default
DEFAULT_MAX_BYTES = 32 * 1024 * 1024

def read_json(path, max_bytes=None, encoding="utf-8", kind=None, default=None):
    """The parsed JSON of `path`, or `default` when the file is missing,
    unreadable, larger than `max_bytes` (None: DEFAULT_MAX_BYTES, AREA-AUDIT
    P7-8; a caller that needs more passes it), not valid JSON in
    `encoding`, or (with `kind`, a type or tuple of types) not an instance
    of `kind`."""
    cap = DEFAULT_MAX_BYTES if max_bytes is None else max_bytes
    try:
        p = Path(path)
        if p.stat().st_size > cap:
            return default
        doc = json.loads(p.read_text(encoding=encoding))
    except (OSError, ValueError, RecursionError):  # AREA-AUDIT P7-3: deep nesting
        return default
    if kind is not None and not isinstance(doc, kind):
        return default
    return doc


def tmp_path(path):
    """The sibling temp file an atomic write goes through."""
    path = Path(path)
    return path.with_name(path.name + ".tmp")


def write_text(path, text):
    """Write `text` (ASCII, LF) to `path` atomically, making its parents."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tmp_path(path)
    with open(tmp, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def write_bytes(path, data):
    """Write `data` to `path` atomically, making its parents."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tmp_path(path)
    tmp.write_bytes(data)
    os.replace(tmp, path)


def dumps(doc, indent=1, sort_keys=False):
    """The file text of `doc`: ASCII-escaped JSON plus one trailing LF."""
    return json.dumps(doc, indent=indent, sort_keys=sort_keys, ensure_ascii=True) + "\n"


def write_json(path, doc, indent=1, sort_keys=False):
    """Write `doc` as JSON (ASCII, LF, trailing newline) atomically."""
    write_text(path, dumps(doc, indent=indent, sort_keys=sort_keys))

