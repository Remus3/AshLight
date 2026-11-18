"""MATH-MAGIC-BASE: a magic item's true base type.

A magic item's name line is "<prefix> <base> <suffix>" ("Hale Iron Ring of
the Bear"); the game puts no separate base line under it. The trade link
(decision 0017), the upgrade search and the price card need the base alone.

Resolution order (first that answers):
1. The build-time snapshot base list (repoe-fork base_items.json in the AL
   sidecar cache, decision 0009; read only, never fetched here): the
   longest run of whole words in the name line that is a known base name.
2. The advanced item text (Ctrl+Alt+C): the affix names in the `{ Prefix
   Modifier "Hale" }` headers are removed from the ends of the line.
3. A shape strip: " of ..." is the suffix; a leading word is a prefix when
   the explicit mod count says the item has one (a magic item carries at
   most one prefix and one suffix; with a suffix, two or more explicit
   lines mean a prefix too, without one any explicit line is the prefix).
4. The line as it is.

Pure functions plus a small mtime-keyed cache; no network, no clipboard.
"""

import json
import re
from pathlib import Path

from . import datacredit
from .. import hotreload

FILE_NAME = "base_items.json"
MAX_BYTES = 64 * 1024 * 1024
MAX_WORDS = 12
SNAPSHOT, ADVANCED, SHAPE, AS_IS = "snapshot", "advanced", "shape", "as-is"
EXPLICIT_SECTIONS = ("explicit", "desecrated", "fractured")
_OF_RE = re.compile(r"\s+of\s+", re.I)


def load_names(path):
    """{lower name: name} of the released base items in a cached
    base_items.json (an object keyed by metadata id; `name`, optional
    `release_state`). Missing, oversized or malformed gives {}."""
    try:
        p = Path(path)
        if p.stat().st_size > MAX_BYTES:
            return {}
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(doc, dict):
        return {}
    out = {}
    for entry in doc.values():
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if entry.get("release_state") == "unreleased":
            continue
        name = " ".join(name.split())
        if len(name.split()) <= MAX_WORDS:
            out.setdefault(name.lower(), name)
    return out


def default_path(environ=None):
    return datacredit.cache_dir(environ) / FILE_NAME


class NamesCache(hotreload.Watched):
    """Loads the base list once and again only when the file changes;
    a malformed rewrite keeps the last good list (HOT-RELOAD, 0042)."""

    def __init__(self, path):
        super().__init__(path, load_names, name="Base item list", default=dict,
                         check=hotreload.check_json(MAX_BYTES))


def from_names(line, names):
    """The longest whole-word run of `line` that is a known base name (the
    leftmost on a tie), in the list's own spelling; None when none is."""
    if not names or not isinstance(line, str):
        return None
    words = line.split()
    for size in range(min(len(words), MAX_WORDS), 0, -1):
        for start in range(0, len(words) - size + 1):
            hit = names.get(" ".join(words[start:start + size]).lower())
            if hit:
                return hit
    return None


def _strip_start(line, word):
    if word and line.lower().startswith(word.lower() + " "):
        return line[len(word):].strip()
    return line


def _strip_end(line, words):
    if words and line.lower().endswith(" " + words.lower()):
        return line[:-len(words)].strip()
    return line


def from_affix_names(line, mods):
    """The line with the advanced headers' prefix / suffix names removed;
    None when no mod carries an affix name."""
    pre = [m.name for m in mods if getattr(m, "kind", None) == "prefix" and m.name]
    suf = [m.name for m in mods if getattr(m, "kind", None) == "suffix" and m.name]
    if not pre and not suf:
        return None
    out = line
    for name in pre[:1]:
        out = _strip_start(out, name)
    for name in suf[:1]:
        out = _strip_end(out, name)
    return out or None


def explicit_count(mods):
    return sum(1 for m in mods if getattr(m, "section", None) in EXPLICIT_SECTIONS)


def from_shape(line, mods):
    """The base by the name's shape and the explicit mod count."""
    words = line.split()
    m = _OF_RE.search(line)
    # a suffix needs a base word before it and words after it
    has_suffix = bool(m) and m.start() > 0 and line[m.end():].strip() != ""
    head = line[:m.start()].strip() if has_suffix else line.strip()
    n = explicit_count(mods)
    has_prefix = n >= 2 if has_suffix else n >= 1
    words = head.split()
    if has_prefix and len(words) >= 2:
        words = words[1:]
    return " ".join(words) or None


def magic_base(line, mods=(), names=None):
    """(base, source) for a magic item's name line. `names`: the snapshot
    base list ({lower: name}) or None. Never raises on content."""
    if not isinstance(line, str) or not line.strip():
        return line, AS_IS
    line = " ".join(line.split())
    mods = list(mods or ())
    hit = from_names(line, names)
    if hit:
        return hit, SNAPSHOT
    adv = from_affix_names(line, mods)
    if adv:
        return adv, ADVANCED
    shape = from_shape(line, mods)
    if shape and shape != line:
        return shape, SHAPE
    return line, AS_IS
