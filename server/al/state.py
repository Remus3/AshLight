"""Derived session state, built only from bus events.

Times are wall-clock receipt times (time.time()); the line's own timestamp is
local time without a zone, so it is kept for display only. Every buffer is
bounded.
"""

import collections
import math
import threading
import time

from . import acts as acts_mod
from . import campaign as campaign_mod
from . import hints as hints_mod
from . import langguard as langguard_mod
from . import num as num_mod
from . import pace as pace_mod
from . import runs as runs_mod
from . import summary as summary_mod
from . import underlevel as underlevel_mod
from . import zonenotes
from . import zoneguide as zoneguide_mod

RECENT_EVENTS = 30
RECENT_WHISPERS = 10
TRADE_REQUESTS = 5  # open trade whisper cards (HUD-WHISPER); oldest drops
# DS-TRADE-EXPIRE (design 0001 N5): a card clears by itself this long after
# it arrived; the dashboard states the rule and Dismiss stays.
TRADE_EXPIRE_S = 600
# TC-EVAL-UI: the overlay shows the item check card this long after the
# hotkey press, then the card leaves by itself (design 0001 N5); the
# dashboard keeps the last result.
EVAL_CARD_S = 20
# PRICE-1-UI (decision 0016): the price check result rides the same card
# slot for this long after the press; an eval and a price stamped within
# SAME_PRESS_S of each other came from one press and share one card.
PRICE_CARD_S = 20
SAME_PRESS_S = 2.0
# "link" (decision 0017) is the only success status the core produces now;
# searching / waiting / done / off are kept for the 0016 contract's readers
PRICE_STATUSES = ("link", "searching", "waiting", "done", "off", "error")
PRICE_LISTINGS = 10
TRADE_FIELDS = ("kind", "item", "price_amount", "price_currency", "want_amount",
                "league", "stash_tab", "left", "top")

# Event types shown in the dashboard's recent list. UX-COPY: not
# session_connect - the game logs one before every zone change, so
# "Connected to a game server" doubled every "Entered <zone>" row and
# pushed deaths and whispers out of the 30-row list sooner.
LISTED = {"scene_changed", "area_entered", "level_up", "death", "whisper_in",
          "whisper_out", "afk_changed", "dnd_changed", "player_joined_area",
          "player_left_area", "trade_accepted", "tailer_started", "tailer_reset"}


FALLBACK_TEXT = "Something happened in the log"
UNKNOWN_CHARACTER = "Unknown character"
# UTIL-MULTICHAR (decision 0038): at most this many characters are kept
# (the current one included); names seen joining / leaving the area this
# game run are other players and never switch the current character, and
# a switch happens only on the first name line after a game start.
MAX_CHARACTERS = 12
MAX_OTHERS = 64
# The per-character fields; SessionState holds the current character's
# set as attributes and parks the others' sets by name.
CHAR_FIELDS = ("char_class", "level", "level_ups", "deaths", "acts", "pace",
               "run_deaths", "_run_start")
UNKNOWN_PLAYER = "Unknown player"
UNKNOWN_ZONE = "an unknown zone"

# tailer_reset reasons, as plain sentences (design 0001 section 9).
RESET_TEXT = {
    "missing": "Client.txt is missing - waiting for the game",
    "replaced": "Client.txt was replaced - reading the new file",
    "truncated": "Client.txt was cleared - reading from the start",
}


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


def _trade_text(sender, tr):
    """<from> wants <item> - <price> (design 0001 section 9)."""
    item = _text(tr.get("item"), "an item")
    if tr.get("kind") == "exchange":
        if tr.get("want_amount") is not None:
            item = f"{_amount(tr['want_amount'])} {item}"
        price = "no price set"
        if tr.get("price_amount") is not None:
            price = " ".join(p for p in ("for", _amount(tr["price_amount"]),
                                         _text(tr.get("price_currency"), "")) if p)
    elif tr.get("price_amount") is not None:
        price = " ".join(p for p in (_amount(tr["price_amount"]),
                                     _text(tr.get("price_currency"), "")) if p)
    else:
        price = "no price set"
    return f"{sender} wants {item} - {price}"


def _trade_where(tr):
    """Stash position as the overlay writes it: "tab Sale (3,7)", "tab
    Sale" without a position, "" without a tab."""
    tab = tr.get("stash_tab")
    if tab is None or not str(tab).strip():
        return ""
    where = f"tab {tab}"
    if tr.get("left") is not None and tr.get("top") is not None:
        where += f" ({tr['left']},{tr['top']})"
    return where


def trade_card_text(row):
    """UI-REVIEW-2: the sentence and stash position for one open trade card
    row, so the dashboard prints the section 9 template and never builds
    trade wording itself."""
    row = _dict(row)
    sender = _text(row.get("from"), UNKNOWN_PLAYER)
    return {"text": _trade_text(sender, row), "where": _trade_where(row)}


# -- TC-EVAL-UI: item check text (design 0001 section 9). The dashboard and
# the overlay print these; neither builds verdict wording itself.
VERDICT_WORD = {"upgrade": "Upgrade", "sidegrade": "Sidegrade", "downgrade": "Downgrade"}
EVAL_ERROR_TEXT = {
    # error: (overlay head, overlay line, dashboard sentence)
    "no build loaded": ("No build loaded", "Paste a build on the dashboard",
                        "No build loaded yet. Paste a Path of Building code under Build, "
                        "then press the hotkey again."),
    "not an item": ("Not an item", "Copy an item in game first",
                    "The clipboard did not hold an item. Hover an item in game, press "
                    "Ctrl+C, then press the hotkey."),
    "no gear slot for this item class": ("Can't compare this", "Only gear is compared",
                                         "Only gear is compared, and this item has no "
                                         "gear slot."),
}


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


CARD_LINE = 34  # design 0001 section 9 rule 6: overlay card line length


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


WAYSTONE_LISTED = 3  # design 0001 rule 1: the sentence names at most 3 mods


def waystone_rewards_text(ws):
    """UTIL-WAYSTONE-REWARD: `rewards` (the dashboard sentence) and
    `reward_line` (the overlay card's item line, "" when there is nothing to
    show). Exact tests in tests/test_waystone_reward.py."""
    ws = _dict(ws)
    if ws.get("unidentified"):
        return {"rewards": "Rewards: identify it to see them.", "reward_line": ""}
    rows = [r for r in _dicts(ws.get("rewards"))
            if _reward_pct(r.get("pct")) is not None and _text(r.get("label"), "")]
    if not rows:
        return {"rewards": "Rewards: none found in the item text.", "reward_line": ""}
    full = ", ".join(f"{_signed(r['pct'])}% {_text(r.get('label'), '')}" for r in rows)
    shorts = [f"{_signed(r['pct'])}% {_text(r.get('short'), '') or _text(r.get('label'), '')}"
              for r in rows]
    return {"rewards": f"Rewards: {full}.", "reward_line": _short_list(shorts)}


def _reward_pct(v):
    v = num_mod.finite(v)
    return v if v is not None and abs(v) <= 10000 and v != 0 else None


def waystone_text(ws):
    """UTIL-WAYSTONE (decision 0030): `head`, `line` and `sentence` for a
    waystone check, plus the UTIL-WAYSTONE-REWARD `rewards` / `reward_line`.
    Exact tests in tests/test_waystone.py."""
    out = _waystone_risk_text(ws)
    out.update(waystone_rewards_text(ws))
    return out


def _waystone_risk_text(ws):
    ws = _dict(ws)
    tier = ws.get("tier")
    what = (f"Tier {tier} waystone" if isinstance(tier, int) and not isinstance(tier, bool)
            else "Waystone")
    if ws.get("unidentified"):
        return {"head": "Waystone unidentified", "line": "Identify it to check its mods",
                "sentence": f"{what}. Identify it to see its mods, then press the hotkey "
                            "again."}
    risky = _dicts(ws.get("risky"))
    labels = [_text(r.get("label"), "") for r in risky if _text(r.get("label"), "")]
    shorts = [_text(r.get("short"), "") for r in risky if _text(r.get("short"), "")]
    loaded = bool(ws.get("build_loaded"))
    if not labels:
        if loaded:
            return {"head": "No risky mods found", "line": what,
                    "sentence": f"{what}. None of its mods look risky for this build."}
        return {"head": "No risky mods found", "line": "No build loaded",
                "sentence": f"{what}. None of its mods look risky. Load a build to check "
                            "them against your resistances too."}
    head = "Risky for this build" if loaded else "Risky waystone"
    sentence = (f"{what}. Risky for this build: " if loaded
                else f"{what}. Risky mods (no build loaded, so resistances are unknown): ")
    listed = ", ".join(labels[:WAYSTONE_LISTED])
    if len(labels) > WAYSTONE_LISTED:
        listed += f", and {len(labels) - WAYSTONE_LISTED} more"
    return {"head": head, "line": _short_list(shorts), "sentence": sentence + listed + "."}


def eval_card_text(card):
    """The words for one item check (TC-EVAL-UI): `head`, `item` and `line`
    for the 3-line overlay card, `sentence` for the dashboard, and per
    compared slot a sentence and its stat rows. Missing values read
    honestly; every template has an exact-output test
    (tests/test_eval_text.py)."""
    card = _dict(card)
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
    out["head"] = (f"{verdict} {delta} - {slot} empty" if best.get("empty")
                   else f"{verdict} {delta} vs {slot}")
    counted = [stat_delta_text(s.get("key"), s.get("delta"))
               for s in _dicts(best.get("stats")) if s.get("weighted")]
    if card.get("unidentified"):
        out["line"] = "Mods hidden - identify it first"
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


# -- PRICE-1-UI: price check text (design 0001 section 9, decision 0016).
# The PRICE-1 result contract (state snapshot "price") is documented in
# docs/decisions/0016-price-ui-contract.md; these templates are the only
# place price wording is made.
PRICE_TEXT = {
    # status / error: (overlay price line, overlay detail line, dashboard sentence)
    # PRICE-TRADE-LINK (decision 0017): the overlay says only that the link
    # is ready; the dashboard shows the link itself
    "link": ("Trade link ready", "",
             "A trade site search for this item in {league} is ready. Click the link to "
             "see who sells it."),
    "searching": ("Searching prices...", "On the official trade site",
                  "Searching the official trade site for this item..."),
    "off": ("Web data is off", "Switch it on in the dashboard",
            "Price checks need web data, which is off. Turn it on under Prices and web "
            "data on this page."),
    "contact not set": ("Contact not set", "Add it in config/local.json",
                        "Price checks need a contact for the trade site, such as an email "
                        "or a name. Add it as \"contact\" in config/local.json, then press "
                        "the hotkey again."),
    "not an item": ("Not an item", "Copy an item in game first",
                    "The clipboard did not hold an item. Hover an item in game, press "
                    "Ctrl+C, then press the hotkey."),
    "no base type": ("Can't price this item", "Try a different item",
                     "AshLight can't make a trade search for this item. Try a different "
                     "one."),
    "no league": ("League unknown", "Try again in a minute",
                  "AshLight doesn't know which league to search yet. Try again in a "
                  "minute."),
    "error": ("Price check failed", "Press the hotkey again",
              "AshLight couldn't make a trade search for this item. Press the hotkey "
              "again."),
    # PRICE-UNIQUE / PRICE-STACKABLES: after a poe.ninja value sentence
    "link_too": "A trade site search in {league} is ready too; click the link to "
                "see who sells it.",
    "none": ("No listings found", "Nobody sells this now",
             "Nobody lists this item in {league} right now, so AshLight can't price it."),
}


def _price_amount(value):
    """A listed amount: digits, at most 2 decimals, no trailing zeros."""
    try:
        n = round(float(value), 2)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(n):
        return None
    if n == 0:
        n = 0.0
    return str(int(n)) if n.is_integer() else f"{n:.2f}".rstrip("0")


def _listing_text(row):
    row = row if isinstance(row, dict) else {}
    amount = _price_amount(row.get("amount"))
    cur = _text(row.get("currency"), "")
    if amount is None:
        return "price unknown"
    return f"{amount} {cur}" if cur else f"{amount} (currency unknown)"


def _ninja_amount(v):
    """A poe.ninja value: 2 decimals from 1 up, 3 significant digits below,
    None for dust (under 0.001)."""
    v = float(v)
    if v >= 1:
        return _price_amount(v)
    if v < 0.001:
        return None
    return f"{v:.3g}"


def ninja_text(ninja):
    """PRICE-UNIQUE / PRICE-STACKABLES: {line, detail, sentence} for the
    card's cached poe.ninja price, or None. Exact tests in
    tests/test_price_book.py."""
    if not isinstance(ninja, dict):
        return None
    v = ninja.get("value")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 0:
        return None
    unit = _text(ninja.get("unit"), "")
    amount = _ninja_amount(v)
    dust = amount is None
    amount = "0.001" if dust else amount
    money = f"{amount} {unit}" if unit else amount
    league = _text(ninja.get("league"), "this league")
    listings = ninja.get("listings")
    has_n = isinstance(listings, int) and not isinstance(listings, bool)
    change = ninja.get("change")
    has_ch = (isinstance(change, (int, float)) and not isinstance(change, bool)
              and change == change and abs(change) >= 0.5)
    trend = ""
    if has_ch:
        word = "up" if change > 0 else "down"
        trend = f"{word} {_num_text(abs(change))}% over 7 days"
    if ninja.get("few"):
        detail = "Few listings: rough price"
    elif trend:
        detail = trend[0].upper() + trend[1:] + " (poe.ninja)"
    else:
        detail = "From poe.ninja"
    sentence = (f"poe.ninja puts this at under {money} in {league}" if dust
                else f"poe.ninja puts this at about {money} in {league}")
    rough = has_n and ninja.get("few")
    if rough:
        sentence += f", but only {listings} {'is' if listings == 1 else 'are'} listed."
        sentence += f" The price is rough; {trend}." if trend else " The price is rough."
    else:
        if has_n:
            sentence += f", from {listings} listing{'' if listings == 1 else 's'}"
        sentence += f"; {trend}." if trend else "."
    line = f"Under {money}" if dust else f"About {money}"
    return {"line": line, "detail": detail, "sentence": sentence}


def price_card_text(card):
    """The words for one price check (PRICE-1-UI): `head`, `line` and
    `detail` for the overlay card, `sentence` and `rows` (one per listing)
    for the dashboard. Missing values read honestly; every template has an
    exact-output test (tests/test_price_text.py)."""
    card = _dict(card)
    item = _dict(card.get("item"))
    name = _text(item.get("name") or item.get("base"), "Unnamed item")
    listings = _dicts(card.get("listings"))
    rows = [_listing_text(r) for r in listings[:PRICE_LISTINGS]]
    out = {"head": f"Price: {name}", "item": name, "line": "", "detail": "",
           "sentence": "", "rows": rows}
    status = _key(card.get("status"))
    league = _text(card.get("league"), "this league")
    if status == "waiting":
        try:
            secs = max(1, int(-(-float(card.get("wait_s") or 0) // 1)))
        except (TypeError, ValueError, OverflowError):
            secs = 1
        out.update(line=f"Prices in about {secs} s", detail="Waiting for the trade site",
                   sentence=f"Waiting about {secs} s for the trade site, then AshLight "
                            "searches by itself.")
        return out
    if status == "done":
        count = card.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < len(rows):
            count = len(rows)
        if not rows:
            line, detail, sentence = PRICE_TEXT["none"]
            out.update(line=line, detail=detail, sentence=sentence.format(league=league))
            return out
        low, mid = rows[0], rows[(len(rows) - 1) // 2]
        out["line"] = f"{count} listed, ~{mid}"
        out["detail"] = f"Lowest {low}"
        if len(rows) == 1:
            out["sentence"] = f"{count} listed in {league}, for {low}."
        else:
            out["sentence"] = (f"{count} listed in {league}. The cheapest is {low}; the "
                               f"middle of the {len(rows)} cheapest is {mid}.")
        return out
    if status == "link":
        line, detail, sentence = PRICE_TEXT["link"]
        out.update(line=line, detail=detail, sentence=sentence.format(league=league))
        ninja = ninja_text(card.get("ninja"))
        if ninja:
            out.update(line=ninja["line"], detail=ninja["detail"],
                       sentence=ninja["sentence"] + " " + PRICE_TEXT["link_too"].format(
                           league=league))
        return out
    if status == "searching":
        key = status
    elif status == "off":
        key = "contact not set" if card.get("error") == "contact not set" else "off"
    else:
        err = _key(card.get("error"))
        key = err if err in PRICE_TEXT else "error"
        if key in ("link", "searching", "off", "none", "contact not set"):
            key = "error"
    line, detail, sentence = PRICE_TEXT[key]
    out.update(line=line, detail=detail, sentence=sentence)
    return out


def _is_time(value):
    """A usable epoch time: a real number within any plausible range (a
    huge int would overflow float arithmetic, FUZZ-3)."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and abs(value) < 1e15)


def _fresh(part, life_s, now):
    return (isinstance(part, dict) and _is_time(part.get("at"))
            and now < part["at"] + life_s)


def price_until(price):
    """When the price card leaves: 20 s from the press, and never sooner
    than 20 s after its last update, so a result that waited on the trade
    site's limit still shows for the full time (design 0001 N5)."""
    at = price["at"]
    upd = price.get("updated_at")
    last = upd if _is_time(upd) and upd > at else at
    wait = price.get("wait_s") if price.get("status") == "waiting" else 0
    if not isinstance(wait, (int, float)) or isinstance(wait, bool) or not wait >= 0:
        wait = 0
    # a long wait keeps the card until the result can arrive (review N4);
    # min() before float(): a huge int would overflow (FUZZ-3)
    return last + float(min(wait, 600)) + PRICE_CARD_S


def overlay_card(ev, price, now):
    """The one overlay card (design 0001 section 10, decision 0016 fork 2):
    {kind, head, line2, line3, verdict, expires_at} or None.
    - eval and price both fresh and from one press: a merged card (eval
      head, price line, eval top stat); a price error or "off" leaves the
      eval card unchanged; a "no build loaded" eval gives the price card;
    - from different presses: the newest one;
    - only one fresh: that one."""
    ev_ok = _fresh(ev, EVAL_CARD_S, now)
    pr_ok = (isinstance(price, dict) and _is_time(price.get("at"))
             and now < price_until(price))
    if not ev_ok and not pr_ok:
        return None

    ws = ev.get("waystone") if isinstance(ev, dict) and isinstance(ev.get("waystone"), dict) \
        else None

    def eval_part():
        t = eval_card_text(ev)
        verdict = str(ev.get("verdict") or "") if ev.get("ok") else "note"
        # UX-OVERLAY-WAYSTONE: a risky waystone takes the warn edge, as its
        # dashboard pill does (never alone: the head says "Risky")
        if ws and _dicts(ws.get("risky")) and not ws.get("unidentified"):
            verdict = "risky"
        # UTIL-WAYSTONE-REWARD: a waystone's reward totals take the item line
        # (as a price line does, design 0001 section 10); never a third line
        line2 = t.get("reward_line") or t["item"]
        return {"kind": "eval", "head": t["head"], "line2": line2, "line3": t["line"],
                "verdict": verdict, "expires_at": ev["at"] + EVAL_CARD_S}

    def price_part():
        t = price_card_text(price)
        return {"kind": "price", "head": t["head"], "line2": t["line"],
                "line3": t["detail"], "verdict": "price",
                "expires_at": price_until(price)}

    if ev_ok and pr_ok:
        if abs(price["at"] - ev["at"]) >= SAME_PRESS_S:
            return price_part() if price["at"] > ev["at"] else eval_part()
        # a waystone's verdict needs no build (UX-OVERLAY-WAYSTONE): keep it
        if not ev.get("ok") and ev.get("error") == "no build loaded" and not ws:
            return price_part()
        if price.get("status") in ("off", "error"):
            return eval_part()
        card = eval_part()
        card.update(kind="merged", line2=price_card_text(price)["line"],
                    expires_at=max(card["expires_at"], price_until(price)))
        return card
    return eval_part() if ev_ok else price_part()


def summarize(ev):
    """One natural sentence for an event (design 0001 section 9). This is
    the only place event wording is made; every template has an exact-output
    test in tests/test_summarize.py. Missing fields read honestly, never
    "None", and internal ids never show."""
    t = ev.get("type")
    if t in ("scene_changed", "area_entered"):
        zone = _text(ev.get("scene") if t == "scene_changed" else ev.get("name"),
                     UNKNOWN_ZONE)
        tag = " (hideout)" if t == "scene_changed" and ev.get("is_hideout") else ""
        return f"Entered {zone}{tag}"
    if t == "area_generated":
        return f"Area level {_text(ev.get('area_level'), 'unknown')}"
    if t == "level_up":
        who = _text(ev.get("character"), UNKNOWN_CHARACTER)
        if ev.get("level") is None:
            return f"{who} reached a new level (level unknown)"
        return f"{who} reached level {ev['level']}"
    if t == "death":
        who = _text(ev.get("character"), UNKNOWN_CHARACTER)
        return f"{who} died" + (" (self-inflicted)" if ev.get("suicide") else "")
    if t == "whisper_in":
        sender = _text(ev.get("from"), UNKNOWN_PLAYER)
        tr = ev.get("trade")
        if isinstance(tr, dict):
            return _trade_text(sender, tr)
        body = _text(ev.get("text"), "")
        return f'{sender}: "{body}"' if body else f"{sender} sent an empty whisper"
    if t == "whisper_out":
        to = _text(ev.get("to"), "unknown player")
        body = _text(ev.get("text"), "")
        return f'To {to}: "{body}"' if body else f"Sent an empty whisper to {to}"
    if t == "afk_changed":
        return "You're AFK" if ev.get("on") else "You're back"
    if t == "dnd_changed":
        return "Do not disturb on" if ev.get("on") else "Do not disturb off"
    if t == "player_joined_area":
        return f"{_text(ev.get('character'), UNKNOWN_CHARACTER)} joined the area"
    if t == "player_left_area":
        return f"{_text(ev.get('character'), UNKNOWN_CHARACTER)} left the area"
    if t == "trade_accepted":
        return "Trade accepted"
    if t == "trade_cancelled":
        return "Trade cancelled"
    if t == "session_connect":
        return "Connected to a game server"
    if t == "tailer_started":
        return "Reading Client.txt"
    if t == "tailer_reset":
        return RESET_TEXT.get(ev.get("reason"), "Client.txt was reset")
    return FALLBACK_TEXT


class SessionState:
    def __init__(self, character=None, clock=time.time):
        self._lock = threading.Lock()
        self._clock = clock
        # TEST-FULLSTACK-SSE-IDLE: on_change() runs (under the lock) on every
        # version bump outside apply(); the core points it at the bus wake so
        # a change with no log line (idle, the summary card, a trade card
        # expiring, the calc or price book status) reaches SSE clients at
        # once instead of on the next heartbeat. apply() bumps are pushed
        # with their event, so they do not wake.
        self.on_change = None
        self._applying = False
        self._version = 0
        # The calc and price book status (core tick_sources); no request.
        self.sources = {"calc_on": False, "calc_running": False,
                        "rates_checked_at": None, "book_checked_at": None}
        self.session_started_at = clock()
        # The pace counts only level-ups seen live, so its hourly base stays
        # the core start even when LIVE-RESUME moves the Session tile back
        # to the log opening (UX-NEW-CARDS).
        self.pace_started_at = self.session_started_at
        # "" (the shipped config default) means "learn it from the log".
        self.character = character or None
        self.character_fixed = bool(character)
        self.char_class = None
        self.level = None
        self.zone = None
        self.area_id = None
        self.area_level = None
        self.zone_entered_at = None
        self.in_hideout = False
        self.deaths = 0
        self.level_ups = 0
        self.afk = False
        self.dnd = False
        self.events_seen = 0
        self.recent_whispers = collections.deque(maxlen=RECENT_WHISPERS)
        self.recent_events = collections.deque(maxlen=RECENT_EVENTS)
        self.trade_requests = collections.deque(maxlen=TRADE_REQUESTS)
        self.overlay_layout = None
        self._trade_ids = 0
        # TC-EVAL-UI / TC-VIEW (server/al/theorycraft/live.py).
        self.eval = None
        self._eval_ids = 0
        # PRICE-1-UI: the last price check (decision 0016 contract).
        self.price = None
        self._price_ids = 0
        self.build_info = None
        # HUD-ACT: per-act splits; zone level table from the game-data cache.
        self.acts = acts_mod.ActSplits()
        self.zone_table = {}
        # ZONE-GUIDE (decision 0043): the guide file, the snapshot area
        # graph and the zones each character entered (zoneguide.py).
        self.zone_guide = {}
        self.area_graph = {}
        self.visits = zoneguide_mod.VisitBook()
        # UTIL-MAPS / UTIL-DEATHS: map runs and the death recap (runs.py).
        self.maps = runs_mod.MapRuns()
        self.death_log = runs_mod.DeathLog()
        # UTIL-PACE: levelling pace from the player's level-ups (pace.py).
        self.pace = pace_mod.Pace()
        # UTIL-SESSION-SUMMARY: the open play stretch and its last card.
        self.stretch = summary_mod.Tracker()
        self.session_summary = None
        self._summary_ids = 0
        # TEST-LIVE-EXIT (decision 0029): "idle" = no Client.txt line for
        # summary.IDLE_S while consented (the game may be closed; a killed
        # game writes no line). Log staleness only, no process check.
        self.tailer = {"consented": False, "reading": False, "path": None,
                       "last_reset": None, "idle": False,
                       "last_line_at": None}
        self._idle_paused_map = False  # AREA-AUDIT P3-4
        # UTIL-UNDERLEVEL: the gap threshold ("underlevel_gap" setting).
        self.underlevel_gap = underlevel_mod.DEFAULT_GAP
        # UTIL-CAMPAIGN-CHECKS (ruling H): the loaded build's facts, the
        # snapshot flask table and the boots level setting (campaign.py).
        self.campaign_facts = None
        self.flask_table = {}
        self.boots_level = campaign_mod.DEFAULT_BOOTS_LEVEL
        # UTIL-RUN-HISTORY: the player's deaths per zone in the current
        # campaign run (keyed by the run's first split start), and the
        # history view the core publishes (runhistory.py).
        self.run_deaths = collections.Counter()
        self._run_start = None
        self.run_history = None
        # UTIL-MULTICHAR: the other characters' field sets by name (oldest
        # use first) and the other players' names of this game run.
        self._parked = collections.OrderedDict()
        self._others = set()
        # Decision 0038 switch rule: True from a game start (log_opened)
        # until its first level-up or death line; party is True once
        # another player joined or left the area since that game start.
        self._start_window = False
        self._party_since_start = False
        # AREA-AUDIT P8-1: the session's map runs stay across a character
        # switch, so the map ladder saves only the maps opened since the
        # current character's game start (None: every session map).
        self._game_start_at = None
        self._ladder_from = None
        # The time of the first campaign zone generated since the last name
        # line: a brand-new character's run starts there, not at its first
        # level-up (decision 0038).
        self._first_gen_at = None
        # UTIL-PRICE-WATCH: the price watch view the core publishes.
        self.price_watch = None
        # UTIL-MAP-LADDER: the all-sessions ladder the core publishes
        # (mapladder.py; None while run history is off).
        self.map_ladder_all = None
        # NEWBIE-HINTS (ruling L): first-hours hints; memory only until the
        # core gives the store file (use_hint_store).
        self.hints = hints_mod.Hints()
        # LANG-GUARD (ruling K, decision 0040): the in-memory language
        # verdict from the log; DIAG-SELF (ruling J): the core's checks view.
        self.lang = langguard_mod.LangGuard()
        self.diag = None

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, value):
        self._version = value
        if not self._applying and self.on_change is not None:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001 - a wake never breaks a state change
                pass

    # -- updates
    def set_sources(self, **fields):
        """TEST-FULLSTACK-SSE-IDLE: the calc on / running and the poe.ninja
        rates / price book check times, from the core's loop tick. Bumps
        the version (so SSE pushes it) only when one changed."""
        with self._lock:
            fields = {k: v for k, v in fields.items() if k in self.sources}
            changed = any(self.sources.get(k) != v for k, v in fields.items())
            if changed:
                self.sources.update(fields)
                self.version += 1
            return changed

    def expire_trades(self, now=None):
        """From the core's loop tick: drop expired trade cards now, so the
        change is pushed without waiting for a snapshot."""
        with self._lock:
            self._expire_trades(self._clock() if now is None else now)

    def set_tailer(self, **fields):
        with self._lock:
            changed = any(self.tailer.get(k) != v for k, v in fields.items())
            self.tailer.update(fields)
            if changed:
                self.version += 1
            return changed

    def set_overlay_layout(self, layout):
        with self._lock:
            if layout != self.overlay_layout:
                self.overlay_layout = dict(layout)
                self.version += 1

    def now(self):
        """The state clock (server time, s); PRICE-1-WIRE stamps one press
        with it so the item check and the price check share `at`."""
        return self._clock()

    def set_eval(self, card, keep_time=False, at=None):
        """TC-EVAL-UI: publish the last item check (a live.compact() card).
        keep_time keeps the previous card's time (a re-score after a
        weights or build change), so the overlay does not show it again.
        `at`: the press time when the caller already took it."""
        with self._lock:
            if at is None:
                at = self._clock()
                if keep_time and self.eval is not None:
                    at = self.eval["at"]
            self._eval_ids += 1
            self.eval = dict(card, id=self._eval_ids, at=at)
            self.version += 1

    def set_price(self, card, at=None, keep_time=False):
        """PRICE-1-UI (decision 0016): publish the last price check. `card`
        follows the PRICE-1 result contract (status, wait_s, item, league,
        count, listings, error). `at` is the hotkey press time (the same
        press stamps the eval too); keep_time keeps the previous card's time
        for a status update of the same check (searching -> done)."""
        card = dict(card) if isinstance(card, dict) else {}
        card["listings"] = [dict(r) for r in _dicts(card.get("listings"))][:PRICE_LISTINGS]
        with self._lock:
            if at is None:
                at = self._clock()
                if keep_time and self.price is not None:
                    at = self.price["at"]
            self._price_ids += 1
            self.price = dict(card, id=self._price_ids, at=float(at),
                              updated_at=float(self._clock()))
            self.version += 1

    def set_build_info(self, info):
        """TC-VIEW: the loaded build's summary (live.build_info())."""
        with self._lock:
            if info != self.build_info:
                self.build_info = dict(info) if info else None
                self.version += 1

    def bump_calc_rev(self):
        """MATH-SKILL-SPLIT: a new PoB output table is ready, so the build
        view is read again. AREA-AUDIT P7-4: read and write under one lock
        hold, so a build loaded meanwhile is never overwritten. Returns
        whether a build summary was there to bump."""
        with self._lock:
            info = self.build_info
            if not info:
                return False
            rev = info.get("calc_rev")
            rev = rev if isinstance(rev, int) and not isinstance(rev, bool) else 0
            self.build_info = dict(info, calc_rev=rev + 1)
            self.version += 1
            return True

    def set_campaign(self, facts=False, flasks=False, boots_level=False):
        """UTIL-CAMPAIGN-CHECKS: any of the build facts
        (campaign.build_facts()), the flask table (campaign.load_flasks())
        and the boots level setting; an argument left out keeps its value.
        Bumps the version only on a change; returns whether it changed."""
        with self._lock:
            new = {"campaign_facts": self.campaign_facts, "flask_table": self.flask_table,
                   "boots_level": self.boots_level}
            if facts is not False:
                new["campaign_facts"] = dict(facts) if isinstance(facts, dict) else None
            if flasks is not False:
                new["flask_table"] = flasks if isinstance(flasks, dict) else {}
            if boots_level is not False:
                new["boots_level"] = campaign_mod.boots_level_setting(boots_level)
            if all(getattr(self, k) == v for k, v in new.items()):
                return False
            for k, v in new.items():
                setattr(self, k, v)
            self.version += 1
            return True

    def set_underlevel_gap(self, value):
        """UTIL-UNDERLEVEL: the threshold from the local config (core
        tick). Bumps the version only when it changed."""
        value = underlevel_mod.gap_setting(value)
        with self._lock:
            if value == self.underlevel_gap:
                return False
            self.underlevel_gap = value
            self.version += 1
            return True

    def _run_counter(self):
        """UTIL-RUN-HISTORY: the deaths counter of the current run, reset
        when the act splits start a new run. Caller holds the lock."""
        start = self.acts.splits[0]["started_at"] if self.acts.splits else None
        if start != self._run_start:
            self._run_start = start
            self.run_deaths = collections.Counter()
        return self.run_deaths

    def run_record(self):
        """UTIL-RUN-HISTORY: the current campaign run as a history record
        (runhistory.clean_run shape) plus "closed" (closed split count),
        or None before the first act split. Only closed, complete splits
        carry a time (a partial or open split is no best)."""
        with self._lock:
            if not self.acts.splits:
                return None
            self._run_counter()
            return self._record_of(self.character,
                                   {f: getattr(self, f) for f in CHAR_FIELDS})

    def _record_of(self, name, fields):
        """A history record of one character's field set. Caller holds the
        lock and has reset a stale death counter."""
        acts = fields["acts"]
        rows = acts.rows(self._clock())
        closed = [r for r in rows if not r["current"]]
        start = acts.splits[0]["started_at"]
        deaths = fields["run_deaths"] if fields["_run_start"] == start else {}
        return {"started_at": start,
                "character": name, "class": fields["char_class"],
                "splits": [{"key": r["key"], "label": r["label"],
                            "time_s": r["time_s"]}
                           for r in closed if not r["partial"]],
                "deaths": dict(deaths), "finished": acts.finished,
                "closed": len(closed)}

    def set_run_history(self, view):
        """UTIL-RUN-HISTORY: the history view (core tick)."""
        with self._lock:
            if view != self.run_history:
                self.run_history = dict(view) if view else None
                self.version += 1
                return True
            return False

    def use_hint_store(self, path):
        """NEWBIE-HINTS: keep the hint store in `path` (core start)."""
        with self._lock:
            self.hints.use_file(path)

    def reset_hints(self):
        """NEWBIE-HINTS: the dashboard's "reset hints" click."""
        with self._lock:
            self.hints.reset()
            self.version += 1
            return hints_mod.RESET_TEXT

    def _hint(self, shown, now):
        """List a hint that just started in the event list. Caller holds
        the lock."""
        if shown is None:
            return False
        self.recent_events.append({"seq": None, "type": "hint", "at": now,
                                   "text": shown["text"], "trade": False,
                                   "whisper": False})
        return True

    def map_ladder_rows(self):
        """UTIL-MAP-LADDER: (character, this session's map rows) for the
        core's saved ladder."""
        with self._lock:
            rows = self.maps.ladder_rows(self._clock())
            since = self._ladder_from
            if since is not None:  # AREA-AUDIT P8-1: not a parked character's
                rows = [r for r in rows if isinstance(r.get("opened_at"), (int, float))
                        and r["opened_at"] >= since]
            return self.character, rows

    def set_map_ladder(self, view):
        """UTIL-MAP-LADDER: the all-sessions ladder view, or None."""
        with self._lock:
            if view != self.map_ladder_all:
                self.map_ladder_all = dict(view) if view else None
                self.version += 1

    def set_price_watch(self, view):
        """UTIL-PRICE-WATCH: the price watch view (core tick)."""
        with self._lock:
            if view != self.price_watch:
                self.price_watch = dict(view) if view else None
                self.version += 1
                return True
            return False

    def set_zone_table(self, table):
        """HUD-ACT: the act / zone level table (acts.load_table())."""
        with self._lock:
            table = table if isinstance(table, dict) else {}
            # HOT-RELOAD: polled every tick; the same object is no change
            if table is not self.zone_table and table != self.zone_table:
                self.zone_table = table
                self.lang.set_table(table)
                self.version += 1

    def set_zone_guide(self, guide=False, graph=False):
        """ZONE-GUIDE: the guide document and / or the snapshot area graph
        (an argument left out keeps its value). Bumps only on a change."""
        with self._lock:
            changed = False
            if guide is not False:
                guide = guide if isinstance(guide, dict) else {}
                if guide is not self.zone_guide and guide != self.zone_guide:
                    self.zone_guide, changed = guide, True
            if graph is not False:
                graph = graph if isinstance(graph, dict) else {}
                if graph is not self.area_graph and graph != self.area_graph:
                    self.area_graph, changed = graph, True
            if changed:
                self.version += 1
            return changed

    def visits_doc(self):
        """ZONE-GUIDE: (version, file document) of the visited zones."""
        with self._lock:
            return self.visits.version, self.visits.to_doc()

    def load_visits(self, doc):
        """ZONE-GUIDE: merge the saved visited zones in (core start)."""
        with self._lock:
            if self.visits.load_doc(doc):
                self.version += 1
                return True
            return False

    def clear_visits(self):
        with self._lock:
            self.visits.clear()
            self.version += 1

    def set_diag(self, view):
        """DIAG-SELF: the self-check view (core tick_diag); bumps only on
        a change."""
        with self._lock:
            if view != self.diag:
                self.diag = dict(view) if view else None
                self.version += 1
                return True
            return False

    def dismiss_trade(self, trade_id=None):
        """Drop one open trade card by id, or all of them (trade_id None).
        Returns how many were dismissed. Dashboard only: nothing goes to the
        game."""
        with self._lock:
            before = len(self.trade_requests)
            if trade_id is None:
                self.trade_requests.clear()
            else:
                kept = [r for r in self.trade_requests if r["id"] != trade_id]
                self.trade_requests.clear()
                self.trade_requests.extend(kept)
            n = before - len(self.trade_requests)
            if n:
                self.version += 1
            return n

    def _expire_trades(self, now):
        """Drop trade cards older than TRADE_EXPIRE_S. Caller holds the
        lock. Bumps the version when one goes, so the change is pushed."""
        kept = [r for r in self.trade_requests if now - r["at"] < TRADE_EXPIRE_S]
        if len(kept) != len(self.trade_requests):
            self.trade_requests.clear()
            self.trade_requests.extend(kept)
            self.version += 1

    def _close_trade(self, name=None):
        """OVL-TRADE-CANCEL (decision 0019): a finished trade ("Trade
        accepted." / "Trade cancelled.") closes one open card: the one from
        `name` when a line names the counterparty, else the oldest. Caller
        holds the lock. Returns True when a card went."""
        if not self.trade_requests:
            return False
        rows = list(self.trade_requests)
        drop = next((r for r in rows if name and r.get("from") == name), rows[0])
        self.trade_requests.clear()
        self.trade_requests.extend(r for r in rows if r is not drop)
        return True

    def _trade_row(self, ev, now):
        self._trade_ids += 1
        row = {"id": self._trade_ids, "at": now, "from": ev.get("from")}
        trade = ev.get("trade") or {}
        for k in TRADE_FIELDS:
            if k in trade:
                row[k] = trade[k]
        return row

    def _is_me(self, name):
        return self.character is None or name == self.character

    # -- UTIL-MULTICHAR (decision 0038)
    @staticmethod
    def _fresh_fields(now):
        p = pace_mod.Pace()
        p.reset_at = now  # its hourly rate counts from the switch
        return {"char_class": None, "level": None, "level_ups": 0, "deaths": 0,
                "acts": acts_mod.ActSplits(), "pace": p,
                "run_deaths": collections.Counter(), "_run_start": None}

    def _may_switch(self, name):
        """True when a name line should make `name` the current character
        (decision 0038): only the first level-up or death line after a game
        start (log_opened), and only while no other player has joined or
        left the area since that start. Never mid-session: a party member
        already in the area levels up with no join line of their own. A
        configured character never switches; other players' names (seen
        joining or leaving the area this game run) never do. The first
        level-up when no character is known yet names it (apply)."""
        if (self.character_fixed or not name or name == self.character
                or self.character is None or name in self._others):
            return False
        return self._start_window and not self._party_since_start

    def _switch(self, name, now):
        """Park the current character's fields and load `name`'s (fresh
        when new). Caller holds the lock."""
        if self.character is not None:
            self._parked[self.character] = {f: getattr(self, f) for f in CHAR_FIELDS}
            self._parked.move_to_end(self.character)
        loaded = self._parked.pop(name, None)
        if loaded is None:
            loaded = self._fresh_fields(now)
            if self._first_gen_at is not None:
                loaded["acts"].fold(acts_mod.FIRST_AREA, self._first_gen_at, None)
        for f in CHAR_FIELDS:
            setattr(self, f, loaded[f])
        self.character = name
        # AREA-AUDIT P8-1: maps of this game run are the new character's
        self._ladder_from = self._game_start_at if self._game_start_at is not None else now
        while len(self._parked) > MAX_CHARACTERS - 1:
            self._parked.popitem(last=False)

    def _note_other(self, name):
        if name and name != self.character and len(self._others) < MAX_OTHERS:
            self._others.add(name)

    def character_names(self):
        """The current character first, then the others, newest use first."""
        with self._lock:
            names = [self.character] if self.character else []
            return names + [n for n in reversed(self._parked) if n not in names]

    def _char_view(self, name, fields, now, current):
        acts_v = acts_mod.view(fields["acts"], self.zone_table,
                               self.area_id if current else None,
                               self.zone if current else None, now)
        return {"name": name, "current": current, "class": fields["char_class"],
                "level": fields["level"], "deaths": fields["deaths"],
                "level_ups": fields["level_ups"], "acts": acts_v,
                "pace": fields["pace"].view(now, self.pace_started_at)}

    def _characters_view(self, now):
        """The snapshot `characters` list (current first, at most
        MAX_CHARACTERS). Caller holds the lock."""
        out = []
        if self.character:
            out.append(self._char_view(self.character,
                                       {f: getattr(self, f) for f in CHAR_FIELDS},
                                       now, True))
        for name in reversed(self._parked):
            if len(out) >= MAX_CHARACTERS:
                break
            out.append(self._char_view(name, self._parked[name], now, False))
        return out

    def parked_record(self, name):
        """UTIL-MULTICHAR: a parked character's run as a history record
        (run_record shape), or None."""
        with self._lock:
            fields = self._parked.get(name)
            if not fields or not fields["acts"].splits:
                return None
            return self._record_of(name, fields)

    def apply(self, ev):
        """Fold one event in. Returns True when the snapshot changed."""
        t = ev.get("type")
        now = ev.get("recv_ts") or self._clock()
        with self._lock:
            self._applying = True
            try:
                return self._apply_locked(ev, t, now)
            finally:
                self._applying = False

    def _apply_locked(self, ev, t, now):
        """apply() under the lock (its bumps do not wake: see on_change)."""
        self.events_seen += 1
        changed = False
        listed = t in LISTED
        # LANG-GUARD: the language verdict from area loads and system lines
        if ev.get("source") != "tailer" and self.lang.feed(ev, now):
            changed = True
        # TEST-LIVE-EXIT: any line proves the log is alive again. The
        # tailer's own status events (source "tailer") are not log
        # lines (AREA-AUDIT P3-1): they neither refresh the last line
        # (which would overwrite the resume mtime seed) nor clear idle.
        if ev.get("source") != "tailer":
            self.tailer["last_line_at"] = now
            if self.tailer.get("idle"):
                self.tailer["idle"] = False
                changed = True
                # AREA-AUDIT P3-4: the map clock idle froze runs again
                # from this line while the player is still in that map
                # (a zone change below then decides as usual); a game
                # restart (log_opened) keeps it stopped.
                if self._idle_paused_map and t != "log_opened":
                    self.maps.on_scene(self.zone, now, self.in_hideout)
            self._idle_paused_map = False
        active = t in summary_mod.ACTIVITY
        if active:
            self.stretch.begin(self._counters())
        if t == "log_opened":
            # UTIL-SESSION-SUMMARY: a new game run; the last one closed
            changed = self._close_stretch("game_closed")
        if t == "scene_changed":
            # Null and transient scenes (LIVE-1) keep the zone and its
            # timer and are not listed; only a real zone change is.
            listed = False
            if (not ev.get("is_null") and not ev.get("is_transient")
                    and ev.get("scene") != self.zone):
                self.zone = ev.get("scene")
                self.in_hideout = bool(ev.get("is_hideout"))
                self.zone_entered_at = now
                self.maps.on_scene(self.zone, now, self.in_hideout)
                listed = True
                changed = True
            # ZONE-GUIDE: the zone this character entered (quest tracker)
            if (not ev.get("is_null") and not ev.get("is_transient")
                    and not ev.get("is_hideout") and ev.get("scene")):
                if self.visits.visit(self.character, self.area_id, ev.get("scene")):
                    changed = True
        elif t == "area_generated":
            self.area_id = ev.get("area_id")
            self.area_level = ev.get("area_level")
            self.acts.fold(self.area_id, now, self.level)
            if self.area_id == acts_mod.FIRST_AREA:
                self._first_gen_at = now
            self.maps.on_generated(self.area_id, now, self.area_level,
                                   ev.get("seed"))
            self._hint(self.hints.on_area(self.character, self.area_id,
                                          self.level, now), now)
            changed = True
        elif t == "area_entered":
            if ev.get("name") != self.zone:
                self.zone = ev.get("name")
                self.in_hideout = "hideout" in (self.zone or "").lower()
                self.zone_entered_at = now
                self.maps.on_scene(self.zone, now, self.in_hideout)
                changed = True
        elif t == "log_opened":
            # TEST-LIVE-RESTART: a new game run. The player is at the
            # login screen, so the old run's zone, area, zone timer and
            # AFK / DND are void. Character, level and counts stay.
            if self.maps.pause(now):
                changed = True
            self._others.clear()
            self._start_window = True
            self._game_start_at = now
            self._party_since_start = False
            if (self.zone is not None or self.area_id is not None
                    or self.area_level is not None or self.in_hideout
                    or self.zone_entered_at is not None
                    or self.afk or self.dnd):
                self.zone = self.area_id = self.area_level = None
                self.zone_entered_at = None
                self.in_hideout = self.afk = self.dnd = False
                changed = True
        elif t == "level_up":
            # The first level-up names the character unless one was
            # configured; other players' level-ups are listed, not counted.
            if self.character is None:
                if ev.get("character") not in self._others:
                    self.character = ev.get("character")
            elif self._may_switch(ev.get("character")):
                # UTIL-MULTICHAR: another of the player's characters
                self._switch(ev.get("character"), now)
            if ev.get("character"):
                self._start_window = False
            if ev.get("character") == self.character:
                self._first_gen_at = None
                self.char_class = ev.get("class")
                self.level = ev.get("level")
                self.level_ups += 1
                self.pace.on_level(self.level, now)
                self.maps.on_level_up(now)  # UTIL-MAP-LADDER
                self._hint(self.hints.on_level(self.character, self.level, now), now)
                changed = True
        elif t == "death":
            if self._may_switch(ev.get("character")):
                self._switch(ev.get("character"), now)
            if ev.get("character"):
                self._start_window = False
            if self._is_me(ev.get("character")):
                self._first_gen_at = None
                self.deaths += 1
                self.death_log.add(
                    at=now, zone=self.zone, area_level=self.area_level,
                    level=self.level,
                    zone_s=(max(0.0, now - self.zone_entered_at)
                            if self.zone_entered_at else None))
                self.maps.on_death(now)
                # UTIL-RUN-HISTORY: campaign deaths per zone of this run
                if self.acts.splits and not self.acts.finished and self.zone:
                    self._run_counter()[self.zone] += 1
                self._hint(self.hints.on_death(self.character, self.area_id,
                                               self.level, now), now)
                changed = True
        elif t in ("player_joined_area", "player_left_area"):
            self._note_other(ev.get("character"))
            self._party_since_start = True
        elif t in ("whisper_in", "whisper_out"):
            self.recent_whispers.append(self._row(ev, now))
            if t == "whisper_in" and ev.get("trade"):
                self._expire_trades(now)
                self.trade_requests.append(self._trade_row(ev, now))
            changed = True
        elif t in ("trade_accepted", "trade_cancelled"):
            self._expire_trades(now)
            if self._close_trade(ev.get("name")):
                changed = True
        elif t == "afk_changed":
            self.afk = bool(ev.get("on"))
            changed = True
        elif t == "dnd_changed":
            self.dnd = bool(ev.get("on"))
            changed = True
        elif t == "tailer_started":
            self.tailer["reading"] = True
            self.tailer["path"] = ev.get("path")
            changed = True
        elif t == "tailer_reset":
            self.tailer["last_reset"] = ev.get("reason")
            if ev.get("reason") == "missing":
                self.tailer["reading"] = False
            changed = True
        if listed:
            self.recent_events.append(self._row(ev, now))
            changed = True
        if active:
            self.stretch.touch(now, self._counters())
        if changed:
            self.version += 1
        return changed

    # -- UTIL-SESSION-SUMMARY
    def _zone_note(self):
        """UX-ZONE-NOTES: {"text", "source", "zone"} for the campaign zone
        the player is in, else None. Caller holds the lock."""
        if self.in_hideout:
            return None
        note = zonenotes.note_for(self.area_id, self.zone)
        return dict(note, zone=self.zone) if note else None

    def _zone_guide_view(self):
        """ZONE-GUIDE: the guide for the zone the player is in. Caller
        holds the lock."""
        zone_level = None
        info = acts_mod.act_of(self.area_id)
        if info is not None and self.zone:
            row = next((r for r in self.zone_table.get(info["key"], ())
                        if r["id"] == self.area_id or r["name"] == self.zone), None)
            zone_level = row["level"] if row else None
        visits = (self.visits.by_name.get(self.character or "")
                  if self.visits.by_name else None)
        return zoneguide_mod.view(self.zone_guide, self.area_graph, self.area_id,
                                  self.zone, self.in_hideout, self.level,
                                  self.area_level, visits, zone_level)

    def _counters(self):
        return {"level": self.level, "level_ups": self.level_ups,
                "deaths": self.deaths, "maps": self.maps.count}

    def _close_stretch(self, reason, movers=None):
        """Close the open play stretch into the summary card. Caller holds
        the lock. True when a card was made."""
        card = self.stretch.close(reason, movers)
        if card is None:
            return False
        self._summary_ids += 1
        self.session_summary = dict(card, id=self._summary_ids)
        return True

    def session_end_due(self, now=None):
        """True when the open stretch has been idle for IDLE_S (cheap; the
        core reads the movers only then)."""
        with self._lock:
            return self.stretch.due(self._clock() if now is None else now)

    def check_session_end(self, now=None, movers=None):
        """From the core's main loop: close the stretch after IDLE_S with no
        game activity. Returns the new card, or None."""
        with self._lock:
            now = self._clock() if now is None else now
            if not self.stretch.due(now):
                return None
            if not self._close_stretch("idle", movers):
                return None
            self.version += 1
            return dict(self.session_summary)

    # -- TEST-LIVE-EXIT (decision 0029)
    def _idle_due(self, now):
        tl = self.tailer
        last = tl.get("last_line_at")
        return (bool(tl.get("consented")) and not tl.get("idle")
                and last is not None and now - last >= summary_mod.IDLE_S)

    def seed_last_line(self, at):
        """LIVE-RESUME: the resumed log's last write time (file mtime)
        stands in for the last line until a live one comes, so a game that
        closed before the core started turns idle too."""
        with self._lock:
            if self.tailer.get("last_line_at") is None and isinstance(at, (int, float)):
                self.tailer["last_line_at"] = float(at)

    def log_idle_due(self, now=None):
        """True when Client.txt has been quiet for IDLE_S while consented
        and the idle state is not set yet (cheap; the core reads the
        movers only then)."""
        with self._lock:
            return self._idle_due(self._clock() if now is None else now)

    def check_log_idle(self, now=None, movers=None):
        """From the core's main loop: after IDLE_S with no Client.txt line
        the game may be closed (a killed game writes nothing). Set the idle
        state, keep the zone, freeze the zone and map clocks at the last
        line and close the play stretch into the summary card. The next
        line clears it (apply). True when the state turned idle."""
        with self._lock:
            now = self._clock() if now is None else now
            if not self._idle_due(now):
                return False
            last = self.tailer["last_line_at"]
            self.tailer["idle"] = True
            self._idle_paused_map = self.maps.pause(last)
            if self.stretch.start is not None:
                self._close_stretch("idle", movers)
            self.version += 1
            return True

    def set_session_summary(self, card):
        """A saved card loaded at core start (shown until a new one)."""
        with self._lock:
            if isinstance(card, dict) and self.session_summary is None:
                self.session_summary = dict(card)
                self._summary_ids = max(self._summary_ids,
                                        card.get("id") if isinstance(card.get("id"), int) else 0)
                self.version += 1

    _RESTORE = {"zone": "zone", "in_hideout": "in_hideout", "area_id": "area_id",
                "area_level": "area_level", "zone_entered_at": "zone_entered_at",
                "class": "char_class", "level": "level", "deaths": "deaths",
                "level_ups": "level_ups", "afk": "afk", "dnd": "dnd",
                "session_started_at": "session_started_at"}

    def restore(self, fields):
        """LIVE-RESUME: set state fields recovered from the end of Client.txt
        (server/al/resume.py). Nothing is listed. A configured character is
        kept; another character's level, class and counts are ignored.
        Act splits are run-wide and are rebuilt for any character."""
        with self._lock:
            name = fields.get("character")
            other = bool(name) and self.character_fixed and name != self.character
            if name and not self.character_fixed:
                self.character = name
            for key, attr in self._RESTORE.items():
                if other and key in ("class", "level", "deaths", "level_ups"):
                    continue
                if key in fields:
                    setattr(self, attr, fields[key])
            # HUD-ACT-RESUME: rebuild the act splits from the run's area
            # generations (decision 0023); none keeps the current splits.
            rebuilt = acts_mod.ActSplits()
            for a in fields.get("act_areas") or ():
                rebuilt.fold(a.get("area_id"), a.get("at"), a.get("level"))
            if rebuilt.splits:
                self.acts = rebuilt
            # UTIL-MAPS-RESUME: replay the run's map runs and death recap;
            # no run events keep the current ones.
            events = fields.get("run_events")
            if events and not self.character_fixed:
                # UTIL-MULTICHAR: the run's character by the live rule
                self._restore_chars(events,
                                    fields.get("session_started_at") is not None)
            if events:
                self.maps, self.death_log = runs_mod.replay(events,
                                                            self.character)
            # ZONE-GUIDE: the run's entered zones for the tracker
            if events:
                zoneguide_mod.replay(events, self.visits, self.character)
            # UTIL-RUN-HISTORY: this run's deaths per zone from the
            # replayed death recap (its rows are capped, like the card)
            start = self.acts.splits[0]["started_at"] if self.acts.splits else None
            self._run_start = start
            self.run_deaths = collections.Counter(
                r["zone"] for r in self.death_log.rows
                if start is not None and r.get("zone")
                and isinstance(r.get("at"), (int, float)) and r["at"] >= start)
            self.version += 1
            return True

    _REPLAY_TYPES = ("scene_changed", "area_entered", "area_generated", "death",
                     "level_up", "player_joined_area", "player_left_area",
                     "log_opened")

    def _restore_chars(self, events, run_start_known):
        """UTIL-MULTICHAR: replay the current game run's events through a
        scratch state seeded with the scanned character (the newest
        level-up) and a game start when the scan reached the run's marker,
        so the decision 0038 switch rule decides the run's character the
        same way it does live: the first name line after the start, unless
        another player joined or left the area first. When the rule keeps
        the scanned character, the single-character restore above stays;
        otherwise the run's character takes its name, class, level and
        counts from the replay.
        A scanned name that the run shows joining or leaving the area is
        another player: the character becomes unknown, so the player's
        next level-up names it. Pace counts live level-ups only
        (UTIL-PACE), so it starts fresh. Caller holds the lock."""
        tmp = SessionState(clock=self._clock)
        tmp.character = self.character
        first = next((e["at"] for e in events
                      if isinstance(e.get("at"), (int, float))), None)
        if run_start_known and first is not None:
            tmp.apply({"type": "log_opened", "recv_ts": first})
        for e in events:
            if e.get("type") in self._REPLAY_TYPES and isinstance(e.get("at"), (int, float)):
                tmp.apply(dict(e, recv_ts=e["at"]))
        self._start_window = tmp._start_window
        self._party_since_start = tmp._party_since_start
        joined = {e.get("character") for e in events
                  if e.get("type") in ("player_joined_area", "player_left_area")
                  and e.get("character")}
        self._others = set(list(tmp._others | joined)[:MAX_OTHERS])
        if tmp.character is not None and tmp.character in joined:
            self.character = None
            self.char_class = self.level = None
            self.level_ups = self.deaths = 0
            return
        if tmp.character is None or tmp.character == self.character:
            return
        # The act splits stay the run-wide rebuild above (decision 0023):
        # one game run is one character now, and its first campaign zone
        # still starts a brand-new character's run.
        self.character = tmp.character
        for f in ("char_class", "level", "level_ups", "deaths"):
            setattr(self, f, getattr(tmp, f))
        self.pace = pace_mod.Pace()

    @staticmethod
    def _row(ev, now):
        return {"seq": ev.get("seq"), "type": ev.get("type"), "at": now,
                "text": summarize(ev), "trade": bool(ev.get("trade")),
                "whisper": ev.get("type") in ("whisper_in", "whisper_out")}

    def _zone_until(self, now):
        if self.tailer.get("idle") and self.tailer.get("last_line_at") is not None:
            return self.tailer["last_line_at"]
        return now

    # -- read
    def snapshot(self):
        with self._lock:
            now = self._clock()
            self._expire_trades(now)
            return {
                "version": self.version,
                "now": now,
                "session_started_at": self.session_started_at,
                "session_s": max(0.0, now - self.session_started_at),
                "character": self.character,
                "class": self.char_class,
                "level": self.level,
                "zone": self.zone,
                "area_id": self.area_id,
                "area_level": self.area_level,
                "zone_entered_at": self.zone_entered_at,
                # TEST-LIVE-EXIT: idle freezes the zone clock at the last line
                "zone_s": (max(0.0, self._zone_until(now) - self.zone_entered_at)
                           if self.zone_entered_at else None),
                "in_hideout": self.in_hideout,
                "deaths": self.deaths,
                "level_ups": self.level_ups,
                "afk": self.afk,
                "dnd": self.dnd,
                "events_seen": self.events_seen,
                "recent_whispers": list(self.recent_whispers),
                "recent_events": list(self.recent_events),
                "trade_requests": [dict(r, **trade_card_text(r))
                                   for r in self.trade_requests],
                "overlay_layout": dict(self.overlay_layout) if self.overlay_layout else None,
                "tailer": dict(self.tailer),
                # decision 0029 amendment (DESKTOP-CLIENT): the 0029 idle
                # "game may be closed" state as one boolean; the overlay
                # hides while it is true
                "game_idle": bool(self.tailer.get("consented") and self.tailer.get("idle")),
                "eval": (dict(self.eval, text=eval_card_text(self.eval),
                              expires_at=self.eval["at"] + EVAL_CARD_S)
                         if self.eval else None),
                "price": (dict(self.price, text=price_card_text(self.price),
                               expires_at=price_until(self.price))
                          if self.price else None),
                # The one overlay card chosen at this moment (decision 0016).
                "card": overlay_card(self.eval, self.price, now),
                "build": dict(self.build_info) if self.build_info else None,
                "acts": acts_mod.view(self.acts, self.zone_table, self.area_id,
                                      self.zone, now),
                "maps": dict(self.maps.view(now),
                             ladder_all=(dict(self.map_ladder_all)
                                         if self.map_ladder_all else None)),
                # UTIL-UNDERLEVEL (ruling B): log area level minus player level
                "underlevel": underlevel_mod.view(
                    self.level, self.area_level, self.area_id, self.zone,
                    self.in_hideout, self.zone_table, self.underlevel_gap),
                # UX-ZONE-NOTES (decision 0030): our own note for this zone
                "zone_note": self._zone_note(),
                # ZONE-GUIDE (decision 0043): the live zone guide and tracker
                "zone_guide": self._zone_guide_view(),
                # UTIL-CAMPAIGN-CHECKS (ruling H, decision 0039)
                "campaign": campaign_mod.view(self.level, self.area_id,
                                              self.campaign_facts, self.flask_table,
                                              self.boots_level),
                "death_recap": self.death_log.view(self.deaths),
                # NEWBIE-HINTS: the first-hours hint on show, or None
                "hint": self.hints.view(now),
                "pace": self.pace.view(now, self.pace_started_at),
                # UTIL-MULTICHAR: every character's numbers, current first
                "characters": self._characters_view(now),
                "session_summary": (dict(self.session_summary)
                                    if self.session_summary else None),
                "sources": dict(self.sources),
                # UTIL-RUN-HISTORY / UTIL-PRICE-WATCH (core-published views)
                "run_history": (dict(self.run_history)
                                if self.run_history else None),
                "price_watch": (dict(self.price_watch)
                                if self.price_watch else None),
                # LANG-GUARD / DIAG-SELF (rulings K, J; decision 0040)
                "lang": self.lang.view(),
                "diag": dict(self.diag) if self.diag else None,
            }
