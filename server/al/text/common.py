"""Shared text helpers for the card and event words (FS-STATE-TEXT).

Moved byte for byte out of server/al/state.py (RUN-ZONE-RESET, folded
TEST-STATE-TEXT-1); state.py re-exports every name, so state.<name> is
the same object. Pure functions and constants; stdlib only.
"""


def _text(value, default):
    """A field as display text; missing or empty reads as the default."""
    if value is None:
        return default
    value = str(value)
    return value if value.strip() else default


# FUZZ-3 (TEST-FUZZ): card fields are read through these so a wrong-typed
# field (a number for a dict, a dict for a key, a non-list) reads as
# missing instead of raising and breaking every snapshot.
def _dict(value):
    return value if isinstance(value, dict) else {}


def _dicts(value):
    return [v for v in value if isinstance(v, dict)] if isinstance(value, (list, tuple)) else []


def _key(value):
    return value if isinstance(value, str) else None


def _amount(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def _num_text(n):
    """A number as short display text: at most 1 decimal, no trailing .0."""
    try:
        n = round(float(n), 1)
    except (TypeError, ValueError, OverflowError):
        return "0"
    if n == 0:
        n = 0.0  # no "-0"
    return str(int(n)) if n.is_integer() else str(n)


def _signed(n):
    t = _num_text(n)
    return t if t.startswith("-") else "+" + t


def _signed_points(n):
    """"+1 point", "-1 point", "+2.5 points" (rule 7: correct plurals)."""
    t = _signed(n)
    return f"{t} point" + ("" if t in ("+1", "-1") else "s")


def _points(n):
    try:
        t = _num_text(abs(float(n or 0)))
    except (TypeError, ValueError, OverflowError):
        t = "0"
    return f"{t} point" + ("" if t == "1" else "s")


CARD_LINE = 26  # design 0001 section 9 rule 6: overlay card line length


def _short_list(words, width=CARD_LINE):
    """Words joined by ", " within `width`; the rest as " +N more"."""
    shown = []
    for i, w in enumerate(words):
        rest = len(words) - i - 1
        tail = f" +{rest} more" if rest else ""
        cand = ", ".join(shown + [w])
        if len(cand + tail) > width and shown:
            return ", ".join(shown) + f" +{len(words) - len(shown)} more"
        shown.append(w)
    text = ", ".join(shown)
    return text if len(text) <= width else text[:width - 3] + "..."


def _is_time(value):
    """A usable epoch time: a real number within any plausible range (a
    huge int would overflow float arithmetic, FUZZ-3)."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and abs(value) < 1e15)
