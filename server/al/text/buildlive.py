"""Build alert and upgrade notice text (BUILD-LIVE, decision 0045).

Moved byte for byte out of server/al/state.py (TEST-STATE-TEXT-4): the
stale-build alert words and the upgrade notices for items checked earlier.
state.py re-exports every name, so state.<name> is the same object. Pure
functions and constants; stdlib only.
"""

from .common import _dict, _dicts, _num_text, _signed, _signed_points, _text


# BUILD-LIVE (decision 0045): the stale-build alert and the upgrade
# notices for items checked earlier. Exact-output tests in
# tests/test_build_live.py.
# TC-VERDICT-CAVEAT (F-042, F-043): every alert sentence names both routes
# (the Build tab paste and the item-key build load), and `short` is the
# overlay card's third line while the alert lasts (LINE_FIT at most;
# CARD-LINE-LIMIT-COPY2: common.CARD_LINE stays 34 until CARD-LINE-LIMIT-FLIP).
LINE_FIT = 26
ALERT_ROUTES = ("on the Build tab, or copy the code in Path of Building and press "
                "the item key.")


def _a_class(value):
    """A class name with its article (a Ranger, an Invoker); a missing one
    reads "another class"."""
    word = _text(value, "")
    if not word:
        return "another class"
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word


def _fit(text, fallback):
    return text if len(text) <= LINE_FIT else fallback


def build_alert_text(alert):
    """The words of a buildlive.alert() finding, or None: `head` (the alert
    heading), `short` (the overlay card's line 3, at most LINE_FIT) and
    `text` (the sentence, printed in the Your build card and as an item
    check note)."""
    a = _dict(alert)
    kind = a.get("kind")
    who = _text(a.get("character"), "this character")
    if kind == "missing":
        return {"kind": kind, "head": f"No build saved for {who} yet",
                "short": _fit(f"No build for {who}", "No build saved"),
                "text": f"No build saved for {who} yet. Paste a PoB code " + ALERT_ROUTES}
    if kind == "class":
        build_class = _a_class(a.get("build_class"))
        log_class = _a_class(a.get("log_class"))
        return {"kind": kind, "head": f"Build is for {build_class}",
                "short": _fit(f"Build is for {build_class}", "Build is for another class"),
                "text": (f"Build is for {build_class}, but {who} is {log_class}. "
                         f"Paste {who}'s own PoB code " + ALERT_ROUTES)}
    if kind == "level":
        built = _num_text(a.get("build_level"))
        return {"kind": kind, "head": f"Build is from level {built}",
                "short": _fit(f"Build is from level {built}", "Build is for a lower level"),
                "text": (f"Build is from level {built}; you are level "
                         f"{_num_text(a.get('level'))}. Paste a fresh PoB code "
                         + ALERT_ROUTES)}
    return None


def _upgrade_delta(n):
    d = n.get("score_delta") or 0
    if n.get("source") in ("pob", "pob_cached"):
        return _signed(d) + "%"
    return _signed_points(d)


def upgrade_notice_text(n):
    """One upgrade notice: `head` (new or not, slot, item), `line` (what it
    replaces and by how much) and `fit` (class / level fit)."""
    n = _dict(n)
    name = _text(n.get("name") or n.get("base"), "Unnamed item")
    slot = _text(n.get("slot"), "its slot")
    head = ("New upgrade" if n.get("new") else "Upgrade") + f" for {slot}: {name}"
    delta = _upgrade_delta(n)
    if n.get("empty") or not n.get("replaces"):
        line = f"Goes in your empty {slot} slot, {delta}."
    else:
        line = f"Replaces {_text(n.get('replaces'), 'your item')}, {delta}."
    fit = _dict(n.get("fit"))
    if fit.get("kind") == "level" and not fit.get("ok", True):
        fit_text = (f"Needs level {_num_text(fit.get('need'))}; you are level "
                    f"{_num_text(fit.get('level'))}.")
    elif fit.get("build_class"):
        fit_text = f"Fits your {_text(fit.get('build_class'), 'current')} build."
    else:
        fit_text = "Fits your build."
    return {"head": head, "line": line, "fit": fit_text}


def upgrades_text(view):
    """The heading line of the upgrade list ("" with none: the dashboard
    then hides the list)."""
    count = len(_dicts(_dict(view).get("items")))
    if count == 0:
        return ""
    if count == 1:
        return "1 item you checked is an upgrade now."
    return f"{count} items you checked are upgrades now."
