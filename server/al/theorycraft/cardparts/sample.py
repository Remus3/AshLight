"""TC-PRESS-SAMPLES (decision 0045 amendment 2026-11-18): dev-host capture
of sanitized item-press samples.

A card part (TC-CARD-PARTS) that never adds anything to the card: compute()
returns None always. Only while the gitignored config/local.json key
"dev_press_samples" is exactly true (a dev-host switch, not a player
setting: it is not in settingsio.ALLOWED, so it is never exported or
imported, and no surface shows it), it saves a sanitized copy of the
press's item text as a fixture candidate under
<sidecar>/Scratch/press-samples/. An installed copy has no Scratch folder
(paths.sidecar_dir raises), so it never writes there.

Same reads as normal use: the text is the one clipboard read of the press
that ctx["text"] already holds; nothing here reads the clipboard, the
screen, the game or Client.txt, and nothing is sent anywhere.

Sanitizing (sanitize): the Note line keeps only a "~price" / "~b/o" price
form and masks every other word (account or character names); every
@name becomes "@<name>"; anything after a whisper marker ("@From",
"@To", or a "From <name>:" / "To <name>:" line start) is masked; control
characters are dropped and the text is capped at TEXT_MAX characters.
leaks() names any mask pattern a text still matches (a sanitized text
matches none); tools/press_samples.py refuses to promote a candidate
that leaks.

Bounds: at most MAX_FILES candidates; at the cap a new sample is not
written (nothing is deleted). A candidate's file name is the hash of its
sanitized text, so a re-score or a repeat press of the same item writes
nothing new. In a pytest run a sample is written only while AL_SIDECAR_ROOT
points the sidecar at a test folder, so a test core never writes into the
real sidecar.
"""

import hashlib
import os
import re
import sys

from ... import paths

NAME = "sample"
ORDER = 900  # last: it never changes the card
KEY = "dev_press_samples"
SUBDIR = "press-samples"
MAX_FILES = 50
TEXT_MAX = 8000  # characters of item text kept in one candidate
SUFFIX = ".txt"
MASK = "<masked>"
AT_MASK = "@<name>"

_NOTE = re.compile(r"^(Note:)[ \t]*(.*)$", re.M)
_PRICE = re.compile(r"^~(?:price|b/o)[ \t]+\d+(?:[./]\d+)?[ \t]+[a-z][a-z' -]{0,30}$")
_AT = re.compile(r"@(?!(?i:from|to)\b)[^\s@<>]+")
_WHISPER = re.compile(r"(@(?:From|To)\b|^(?:From|To)[ \t]+[^:\r\n]{1,40}:)(.*)$",
                      re.M | re.I)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _note(match):
    rest = match.group(2).strip()
    if not rest:
        return match.group(1)
    return f"{match.group(1)} {rest if _PRICE.match(rest) else MASK}"


def _whisper(match):
    marker = match.group(1)
    if marker.startswith("@"):
        marker = marker[:1] + marker[1:].capitalize()
    else:
        marker = marker.split()[0] + " " + MASK + ":"
    return f"{marker} {MASK}"


def sanitize(text):
    """The sanitized copy of an item text (a str), or None for no text."""
    if not isinstance(text, str) or not text.strip():
        return None
    text = _CTRL.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))[:TEXT_MAX]
    text = _WHISPER.sub(_whisper, text)
    text = _NOTE.sub(_note, text)
    text = _AT.sub(AT_MASK, text)
    return text if text.endswith("\n") else text + "\n"


def leaks(text):
    """The mask patterns `text` still matches: "note" (a Note line with
    words that are not a price form), "at" (an @name), "whisper" (text after
    a whisper marker). [] for a clean text."""
    found = []
    if not isinstance(text, str):
        return ["text"]
    for m in _NOTE.finditer(text):
        rest = m.group(2).strip()
        if rest and rest != MASK and not _PRICE.match(rest):
            found.append("note")
            break
    for m in _WHISPER.finditer(text):
        marker, rest = m.group(1), m.group(2).strip()
        named = not marker.startswith("@") and MASK not in marker
        if named or (rest and rest != MASK):
            found.append("whisper")
            break
    if _AT.search(text):
        found.append("at")
    return found


def sample_dir(environ=None):
    """<sidecar>/Scratch/press-samples; ValueError in an install."""
    return paths.sidecar_dir("Scratch", environ) / SUBDIR


def _allowed(environ=None):
    env = os.environ if environ is None else environ
    if "pytest" in sys.modules and not (env.get(paths.SIDECAR_ENV) or "").strip():
        return False
    return True


def candidates(folder):
    """The candidate files of `folder`, sorted by name ([] when absent)."""
    try:
        return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix == SUFFIX)
    except OSError:
        return []


def save(text, environ=None):
    """Write the sanitized `text` as a candidate. Returns the path written,
    or None (no text, an install, a pytest run without a test sidecar, the
    cap reached, the same candidate already there, or a write error)."""
    clean = sanitize(text)
    if clean is None or leaks(clean) or not _allowed(environ):
        return None
    try:
        folder = sample_dir(environ)
    except ValueError:
        return None
    name = hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16] + SUFFIX
    target = folder / name
    try:
        folder.mkdir(parents=True, exist_ok=True)
        if target.exists() or len(candidates(folder)) >= MAX_FILES:
            return None
        tmp = folder / (name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(clean)
        os.replace(tmp, target)
    except OSError:
        return None
    return target


def compute(ctx):
    if not isinstance(ctx, dict):
        return None
    config = ctx.get("config")
    try:
        cfg = config() if callable(config) else None
    except Exception:  # noqa: BLE001 - a bad config means the switch is off
        cfg = None
    if isinstance(cfg, dict) and cfg.get(KEY) is True:
        save(ctx.get("text"))
    return None


def words(value, card, out):
    """compute() never gives a value, so there is nothing to word."""
    return None
