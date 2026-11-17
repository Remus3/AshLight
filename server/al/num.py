"""AREA-TEST batch 6: the shared number sanitizer for untrusted JSON values
(poe.ninja bodies, PoB output, runtime files a user may have edited)."""

import math


def finite(v):
    """`v` as a finite float, or None for a bool, a non-number, NaN, an
    infinity, or an int too large for a float (FUZZ-4: float() of a huge JSON
    int raises OverflowError, and so does math.isfinite of one)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        f = float(v)
    except OverflowError:
        return None
    return f if math.isfinite(f) else None
