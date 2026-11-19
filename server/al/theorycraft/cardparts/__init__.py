"""TC-CARD-PARTS: the one append-point of the item check card.

A later feature adds ONE module to this package and edits nothing else
(not state.py, live.py or core.py). A part module exposes:

- NAME: a short str, unique among the parts; the key of its value in
  card["parts"].
- ORDER: an int (or float); parts run by ORDER, then by NAME.
- compute(ctx) -> value or None: runs inside the item-check press and every
  re-score (LastEval.run). `ctx` keys: text (the item text of this press,
  in memory only), parsed (theorycraft.item.parse(text)), result (the
  evaluate() result), build (the loaded build or None), character and
  level (the player's own Client.txt facts), area_id (the current area id
  or None) and config (a callable returning the local config dict). The
  value must be JSON-serialisable and at most VALUE_MAX characters as JSON
  (it rides the state snapshot and every push); None adds nothing.
- words(value, card, out) -> None: adds wording to `out`, the
  state.eval_card_text() dict, for a card whose parts hold this part's
  value. It may change only these keys (every other key is put back):
  - notes: append lines (at most NOTES_MAX survive, in part order). Each
    is one plain sentence, subject first, 20 words or fewer, ASCII, no
    "!"; when a part cannot answer, its note names the missing input.
    Notes are dashboard lines; they never reach the 3-line overlay card.
  - word: the word that pairs the verdict mark (design 0001 section 9:
    Upgrade, Sidegrade, Downgrade, Not checked, Risky, No risky mods, or a
    new word added to section 9 first).
  - tone: the mark's tone, the overlay card's verdict edge; one of TONES.
    A tone is honoured only together with a new word (colour is never
    alone); a tone outside TONES, or a new tone under the old word, is
    put back.
  - head: the overlay head; it must start with the word and fit HEAD_MAX.
    When the word changed and the head does not start with it, the head
    becomes "<word> - <head>", clipped to HEAD_MAX.
  - answers: True when the card answers without a build, so the overlay
    keeps the item card even when no build is loaded.
  Every string is AshLight's own words (design 0001 section 9).

Discovery is pkgutil.iter_modules over this package (stdlib); there is no
shared list to edit. A part that raises, or a module that is not a part,
is skipped and logged once by name; the item check always publishes.
Nothing here reads the clipboard, the screen or the game, or sends
anything anywhere.
"""

import copy
import importlib
import json
import logging
import pkgutil
import threading

LOG = logging.getLogger("al.cardparts")
NOTES_MAX = 4
VALUE_MAX = 2000  # characters of a part value as JSON
HEAD_MAX = 34  # design 0001 section 9 rule 6 (state.CARD_LINE)
# the overlay card's verdict edges (app/overlay data-verdict)
TONES = ("upgrade", "sidegrade", "downgrade", "risky", "note", "")
# the keys a part's words() may change; every other key is put back
WORD_KEYS = ("notes", "word", "tone", "head", "answers")

_lock = threading.Lock()
_PARTS = None  # the discovered parts, cached on first use
_logged = set()


def _log_once(name, what, exc=None):
    key = (name, what)
    with _lock:
        if key in _logged:
            return
        _logged.add(key)
    # only the part name and the error type: never item text or values
    LOG.warning("card part %s skipped: %s%s", name, what,
                f" ({type(exc).__name__})" if exc is not None else "")


def _is_part(mod):
    name = getattr(mod, "NAME", None)
    order = getattr(mod, "ORDER", None)
    return (isinstance(name, str) and name != ""
            and isinstance(order, (int, float)) and not isinstance(order, bool)
            and order == order
            and callable(getattr(mod, "compute", None))
            and callable(getattr(mod, "words", None)))


def discover(package=None):
    """The part modules of `package` (default: this one), sorted by
    (ORDER, NAME). Private modules (leading underscore) and subpackages are
    not parts; a module that fails to import or lacks the contract is
    skipped and logged once; a repeated NAME keeps the first by sort."""
    pkg = importlib.import_module(package or __name__)
    found = []
    for info in pkgutil.iter_modules(getattr(pkg, "__path__", []), pkg.__name__ + "."):
        short = info.name.rsplit(".", 1)[-1]
        if info.ispkg or short.startswith("_"):
            continue
        try:
            mod = importlib.import_module(info.name)
        except Exception as exc:  # noqa: BLE001 - one broken part never stops the card
            _log_once(short, "import failed", exc)
            continue
        if not _is_part(mod):
            _log_once(short, "not a card part (NAME, ORDER, compute, words)")
            continue
        found.append(mod)
    found.sort(key=lambda m: (m.ORDER, m.NAME))
    out, names = [], set()
    for mod in found:
        if mod.NAME in names:
            _log_once(mod.NAME, "repeated NAME")
            continue
        names.add(mod.NAME)
        out.append(mod)
    return out


def parts():
    """The discovered parts of this package, found once per process (a code
    change restarts the core, decision 0042)."""
    global _PARTS
    with _lock:
        cached = _PARTS
    if cached is not None:
        return cached
    found = discover()
    with _lock:
        if _PARTS is None:
            _PARTS = found
        return _PARTS


def reset():
    """Forget the cached parts and the logged names (tests)."""
    global _PARTS
    with _lock:
        _PARTS = None
        _logged.clear()


def compute(ctx, found=None):
    """{NAME: value} for every part whose compute(ctx) gave a value; a
    None value, a raising part or a value that is not JSON-serialisable
    adds nothing."""
    values = {}
    for part in (parts() if found is None else found):
        try:
            value = part.compute(ctx)
        except Exception as exc:  # noqa: BLE001 - the press must still publish
            _log_once(part.NAME, "compute raised", exc)
            continue
        if value is None:
            continue
        try:
            size = len(json.dumps(value, allow_nan=False))
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            _log_once(part.NAME, "value is not JSON", exc)
            continue
        if size > VALUE_MAX:
            _log_once(part.NAME, "value too large")
            continue
        values[part.NAME] = value
    return values


def _ok_word(value):
    return isinstance(value, str) and value.strip() != ""


def _clip(text, width=HEAD_MAX):
    return text if len(text) <= width else text[:width - 3].rstrip() + "..."


def _keep_contract(out, before):
    """Put back every key a part may not change and every bad value."""
    for key in list(out):
        if key not in before and key not in WORD_KEYS:
            del out[key]
    for key, value in before.items():
        if key not in WORD_KEYS:
            out[key] = value
    notes = out.get("notes")
    out["notes"] = [n for n in (notes if isinstance(notes, list) else [])
                    if _ok_word(n)][:NOTES_MAX]
    word = out.get("word") if _ok_word(out.get("word")) else before.get("word")
    new_word = word != before.get("word")
    tone = out.get("tone")
    if not isinstance(tone, str) or tone not in TONES or (tone != before.get("tone")
                                                          and not new_word):
        tone = before.get("tone")
    head = out.get("head")
    if not (isinstance(head, str) and isinstance(word, str) and head.startswith(word)
            and len(head) <= HEAD_MAX):
        head = before.get("head")
    if new_word and isinstance(word, str) and isinstance(head, str) \
            and not head.startswith(word):
        head = _clip(f"{word} - {head}" if head else word)
    out.update(word=word, tone=tone, head=head, answers=out.get("answers") is True)


def words(card, out, found=None):
    """Let every part with a value on `card` add its words to `out`, in
    part order. After each part the out contract holds (see the module
    text): only WORD_KEYS change, notes are non-empty strings (at most
    NOTES_MAX), a new tone needs a new word, the head starts with the word,
    answers is a bool. A raising part leaves `out` as it was before it."""
    values = card.get("parts") if isinstance(card, dict) else None
    if not isinstance(out, dict):
        return
    out.setdefault("notes", [])
    if isinstance(values, dict) and values:
        for part in (parts() if found is None else found):
            if part.NAME not in values:
                continue
            before = copy.deepcopy(out)
            try:
                part.words(values[part.NAME], card, out)
            except Exception as exc:  # noqa: BLE001 - the card must still read
                _log_once(part.NAME, "words raised", exc)
                out.clear()
                out.update(before)
                continue
            _keep_contract(out, before)
    notes = out.get("notes")
    out["notes"] = [n for n in (notes if isinstance(notes, list) else [])
                    if _ok_word(n)][:NOTES_MAX]
    out["answers"] = out.get("answers") is True
