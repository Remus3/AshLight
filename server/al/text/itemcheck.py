"""Item check text (TC-EVAL-UI, design 0001 section 9; TC-DELTA, decision 0024).

Moved byte for byte out of server/al/state.py (TEST-STATE-TEXT-3):
the verdict words, the error texts, the stat deltas, the calc notices and
eval_card_text. state.py re-exports every name, so state.<name> is the
same object. Pure functions and constants; stdlib only.
"""

from ..theorycraft import cardparts
from .buildlive import build_alert_text
from .common import _dict, _dicts, _key, _num_text, _points, _signed, _signed_points, _text
from .price import EMPTY_CLIPBOARD, EMPTY_CLIPBOARD_TEXT
from .waystone import waystone_text


# -- TC-EVAL-UI: item check text (design 0001 section 9). The dashboard and
# the overlay print these; neither builds verdict wording itself.
VERDICT_WORD = {"upgrade": "Upgrade", "sidegrade": "Sidegrade", "downgrade": "Downgrade"}
# CARD-LINE-LIMIT-COPY: overlay lines are worded to fit 26 characters while
# common.CARD_LINE stays 34; CARD-LINE-LIMIT-FLIP lowers CARD_LINE to it.
LINE_FIT = 26
UNIDENTIFIED_LINE = "Mods hidden: identify it"
EVAL_ERROR_TEXT = {
    # error: (overlay head, overlay line, dashboard sentence)
    EMPTY_CLIPBOARD: EMPTY_CLIPBOARD_TEXT,
    # TC-VERDICT-CAVEAT (F-042): the sentence names the item-key build load
    "no build loaded": ("No build loaded", "Paste a build first",
                        "No build loaded yet. Paste a Path of Building code under Build, "
                        "or copy the code in Path of Building and press the item key, "
                        "then check the item again."),
    "not an item": ("Not an item", "Copy an item in game first",
                    "The clipboard did not hold an item. Hover an item in game, press "
                    "Ctrl+C, then press the hotkey."),
    "no gear slot for this item class": ("Can't compare this", "Only gear is compared",
                                         "Only gear is compared, and this item has no "
                                         "gear slot."),
    # TC-PRESS-BUILD (F-042): the item key held a build, not an item; the
    # card part theorycraft/cardparts/buildload.py adds the class and level
    "build loaded": ("Build loaded", "Item checks use it now",
                     "Item checks now score against the build you copied."),
    "share link not loaded": ("Build not loaded", "See the dashboard",
                              "AshLight did not load a build from the copied share link."),
}


def stat_delta_text(key, delta):
    """One stat change in the item's own words: "+30 to maximum Life",
    "-10% to Lightning Resistance", "+12% increased Attack Speed". A flag
    mod (no number) reads "Gains: <mod>" / "Loses: <mod>"."""
    key = _text(key, "an unknown stat")
    try:
        d = float(delta or 0)
    except (TypeError, ValueError, OverflowError):
        d = 0.0
    if "#" not in key:
        return ("Gains: " if d >= 0 else "Loses: ") + key
    if key.startswith("Adds # to # "):
        return f"{_signed(d)} average {key[len('Adds # to # '):]}"
    if key.startswith("+#"):
        return _signed(d) + key[2:].replace("#", _num_text(abs(d)))
    return ("-" if d < 0 else "+") + key.replace("#", _num_text(abs(d)), 1)


def _equipped_name(comp):
    eq = _dict(comp.get("equipped"))
    return _text(eq.get("name") or eq.get("base"), "an unnamed item")


# MATH-WEAPON-TYPE (decision 0032 amendment): Path of Building says the
# build's main skill cannot use the checked weapon type in that slot
WEAPON_TYPE_HEAD = "Downgrade - wrong weapon type"
WEAPON_TYPE_LINE = "Main skill can't use this weapon"


def _weapon_skill(comp):
    """(unusable?, PoB's main skill name or None) for one compared slot."""
    w = comp.get("weapon_unusable")
    if not isinstance(w, dict):
        return False, None
    return True, _text(w.get("skill"), "") or None


def _weapon_type_calc(best):
    skill = _weapon_skill(best)[1] or "that skill"
    slot = _text(best.get("slot"), "that slot")
    return ("Your main skill can't use this weapon type, so this item is a downgrade "
            f"for this build. Path of Building counts no damage from {skill} with it "
            f"in {slot}.")


def _compare_sentence(comp):
    verdict = VERDICT_WORD.get(_key(comp.get("verdict")), "Checked")
    slot = _text(comp.get("slot"), "that slot")
    if _weapon_skill(comp)[0]:
        where = slot if comp.get("empty") else f"{slot} ({_equipped_name(comp)})"
        return f"Downgrade: your main skill can't use this weapon type in {where}."
    delta = comp.get("score_delta") or 0
    if comp.get("empty"):
        return f"{verdict}: your build has nothing in {slot} ({_signed_points(delta)})."
    name = _equipped_name(comp)
    if comp.get("verdict") == "upgrade":
        return f"{verdict}: {_points(delta)} more than your {slot} ({name})."
    if comp.get("verdict") == "downgrade":
        return f"{verdict}: {_points(delta)} less than your {slot} ({name})."
    return f"{verdict}: about the same as your {slot} ({name}), {_signed_points(delta)}."


def _stat_rows(comp):
    rows = []
    for s in _dicts(comp.get("stats")):
        rows.append({"text": stat_delta_text(s.get("key"), s.get("delta")),
                     "points": _signed_points(s.get("score_delta"))
                     if s.get("weighted") else "not counted"})
    return rows


CALC_NOTICE_TEXT = {
    # TC-DELTA (decision 0024): why the card shows stat-weight points, not
    # Path of Building DPS / EHP
    "off": ("Scored with your stat weights. To see DPS and EHP, turn on the "
            "optional Path of Building calc in AshLight's settings file."),
    "failed": ("Scored with your stat weights. DPS and EHP are not shown because "
               "Path of Building could not be reached. Try the check again."),
    # MATH-DPS-SANITY (decision 0032): PoB answered numbers that make no
    # sense (negative, NaN, an attack build at 0 DPS after the swap)
    "implausible": ("Scored with your stat weights. DPS and EHP are not shown because "
                    "Path of Building's numbers for this item don't add up. Try the "
                    "check again."),
}


# MATH-WEIGHTS: the calc is off or failed, but Path of Building measured
# stat weights for this same build earlier, so those scored the item
CALC_CACHED_TEXT = {
    "off": ("Scored with the stat weights Path of Building measured for this "
            "build earlier. DPS and EHP are not shown because the Path of "
            "Building calc is off."),
    "failed": ("Scored with the stat weights Path of Building measured for this "
               "build earlier. DPS and EHP are not shown because Path of Building "
               "could not be reached. Try the check again."),
    "implausible": ("Scored with the stat weights Path of Building measured for this "
                    "build earlier. DPS and EHP are not shown because its numbers for "
                    "this item don't add up. Try the check again."),
}


def _pct_text(change):
    p = _dict(change).get("pct")
    return "unknown" if p is None else _signed(p) + "%"


def _has_pob(comp):
    return isinstance(comp.get("dps"), dict) and isinstance(comp.get("ehp"), dict)


def _swap_where(best, n_slots):
    """MATH-COMPARE (decision 0032): where the swap goes and what it
    replaces, e.g. "this item in Gloves replaces Old Grip"."""
    slot = _text(best.get("slot"), "")
    if best.get("empty"):
        where = (f"this item goes in the empty {slot} slot" if slot
                 else "this item goes in the empty slot")
    else:
        where = f"this item in {slot or 'that slot'} replaces {_equipped_name(best)}"
    if n_slots > 1:
        where += f" (the better of the {n_slots} slots it fits)"
    return where


def _comp_calc(comp, pob):
    """MATH-COMPARE: one compared slot's own PoB line; "" without PoB."""
    if not pob or not _has_pob(comp):
        return ""
    return f"Path of Building: DPS {_pct_text(comp['dps'])}, EHP {_pct_text(comp['ehp'])}."


def _calc_text(card, best, n_slots=1):
    """(dashboard sentence, overlay line or None) for the calc source."""
    calc = _dict(card.get("calc"))
    if calc.get("notice") == "weapon_type" and _weapon_skill(best)[0]:
        return _weapon_type_calc(best), WEAPON_TYPE_LINE
    if calc.get("source") == "pob" and _has_pob(best):
        dps, ehp = best["dps"], best["ehp"]
        line = f"DPS {_pct_text(dps)}, EHP {_pct_text(ehp)}"
        return (f"Path of Building: {_swap_where(best, n_slots)}. "
                f"DPS {_pct_text(dps)} (from {_num_text(dps.get('old'))} "
                f"to {_num_text(dps.get('new'))}). EHP {_pct_text(ehp)} (from "
                f"{_num_text(ehp.get('old'))} to {_num_text(ehp.get('new'))}).", line)
    if calc.get("source") == "pob_cached":
        return CALC_CACHED_TEXT.get(_key(calc.get("notice")), CALC_CACHED_TEXT["off"]), None
    return CALC_NOTICE_TEXT.get(_key(calc.get("notice")), ""), None


def eval_card_text(card, alert=None):
    """The words for one item check (TC-EVAL-UI): `head`, `item` and `line`
    for the 3-line overlay card, `sentence` for the dashboard, and per
    compared slot a sentence and its stat rows. Missing values read
    honestly; every template has an exact-output test
    (tests/test_eval_text.py).
    TC-CARD-PARTS: `word` is the word that pairs the verdict mark (Upgrade,
    Sidegrade, Downgrade, Not checked, Risky, No risky mods), `tone` the
    mark's tone (the overlay card's verdict), `notes` the card parts'
    extra lines (at most 4) and `answers` True when a part answers without
    a build; the parts in theorycraft/cardparts add their words last.
    TC-VERDICT-CAVEAT (F-043): `alert` is the snapshot's build alert (a
    buildlive.alert() finding, or None). While one is set, a compared
    item's `line` (overlay line 3) is the alert's short head, so the
    caveat travels with the verdict, and its sentence is the first note
    on the dashboard. An unidentified item keeps its "identify it"
    line (the missing input it names comes first); error and waystone
    cards are left as they are (their lines already name what is
    missing, or do not compare gear)."""
    card = _dict(card)
    out = _eval_lines(card)
    ws = _dict(card.get("waystone"))
    risky = bool(ws and _dicts(ws.get("risky")) and not ws.get("unidentified"))
    if risky:
        # UX-OVERLAY-WAYSTONE: a risky waystone takes the warn edge, as its
        # dashboard pill does (never alone: the head says "Risky")
        tone = "risky"
    else:
        tone = str(card.get("verdict") or "") if card.get("ok") else "note"
    if ws:
        word = ("Not checked" if ws.get("unidentified")
                else "Risky" if risky else "No risky mods")
    elif not card.get("ok"):
        word = "Not checked"
    else:
        word = VERDICT_WORD.get(_key(card.get("verdict")), "Checked")
    out.update(notes=[], word=word, tone=tone, answers=False)
    cardparts.words(card, out)
    caveat = build_alert_text(alert) if card.get("ok") and not ws else None
    if caveat:
        if not card.get("unidentified"):
            out["line"] = caveat["short"]
        out["notes"] = [caveat["text"]] + out["notes"][:cardparts.NOTES_MAX - 1]
    return out


def _delta_head(verdict, delta, slot, empty):
    """The compared item's head: "<Verdict> <delta> vs <slot>" (empty slot:
    "<Verdict> <delta> - <slot> empty"); over LINE_FIT the slot name drops
    ("<Verdict> <delta> - slot empty", then "<Verdict> <delta>"), so the
    verdict and the number always show whole and the dashboard names the
    slot."""
    if empty:
        heads = (f"{verdict} {delta} - {slot} empty", f"{verdict} {delta} - slot empty")
    else:
        heads = (f"{verdict} {delta} vs {slot}",)
    return next((h for h in heads if len(h) <= LINE_FIT), f"{verdict} {delta}")


def _eval_lines(card):
    """eval_card_text's head, item, line, sentence, comparisons and calc."""
    item = _dict(card.get("item"))
    name = _text(item.get("name") or item.get("base"), "Unnamed item")
    if card.get("unidentified"):
        name += " (unidentified)"
    out = {"head": "", "item": name, "line": "", "sentence": "", "comparisons": [],
           "calc": ""}
    ws = _dict(card.get("waystone"))
    if ws:
        out.update(waystone_text(ws))
        return out
    if not card.get("ok"):
        head, line, sentence = EVAL_ERROR_TEXT.get(
            _key(card.get("error")), ("Can't check this item", "See the dashboard",
                                "AshLight could not check this item."))
        out.update(head=head, line=line, sentence=sentence)
        return out
    comps = _dicts(card.get("comparisons"))
    best = next((c for c in comps if c.get("slot") == card.get("slot")),
                comps[0] if comps else {})
    verdict = VERDICT_WORD.get(_key(card.get("verdict")), "Checked")
    slot = _text(card.get("slot"), "its slot")
    delta = _signed(card.get("score_delta") or 0)
    out["head"] = _delta_head(verdict, delta, slot, best.get("empty"))
    counted = [stat_delta_text(s.get("key"), s.get("delta"))
               for s in _dicts(best.get("stats")) if s.get("weighted")]
    if card.get("unidentified"):
        out["line"] = UNIDENTIFIED_LINE
    else:
        out["line"] = counted[0] if counted else "No counted stat changes"
    out["calc"], calc_line = _calc_text(card, best, len(comps))
    if calc_line and not card.get("unidentified"):
        out["line"] = calc_line
    if _dict(card.get("calc")).get("notice") == "weapon_type" and _weapon_skill(best)[0]:
        out["head"] = WEAPON_TYPE_HEAD
    out["sentence"] = _compare_sentence(best) if best else f"{verdict}."
    pob = _dict(card.get("calc")).get("source") == "pob"
    out["comparisons"] = [{"slot": c.get("slot"), "sentence": _compare_sentence(c),
                           "calc": _comp_calc(c, pob), "stats": _stat_rows(c)}
                          for c in comps]
    return out
