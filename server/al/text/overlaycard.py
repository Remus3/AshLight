"""The one overlay card (design 0001 section 10, decision 0016 fork 2).

Moved byte for byte out of server/al/state.py (TEST-STATE-TEXT-4): the
card timers, price_until and overlay_card. state.py re-exports every name,
so state.<name> is the same object. OVL-ZONE-CARD: the zone moment card's
timer, copy and pure line builders (zone_lines and its helpers) live here
too, and so does the act moment card's copy (OVL-ACT-CARD);
server/al/overlayview.py re-exports them. Pure functions and
constants; stdlib only.
"""

import re

from .common import CARD_LINE, _is_time
from .itemcheck import eval_card_text
from .price import ninja_text, price_card_text


# TC-EVAL-UI: the overlay shows the item check card this long after the
# hotkey press, then the card leaves by itself (design 0001 N5); the
# dashboard keeps the last result.
EVAL_CARD_S = 20
# PRICE-1-UI (decision 0016): the price check result rides the same card
# slot for this long after the press; an eval and a price stamped within
# SAME_PRESS_S of each other came from one press and share one card.
PRICE_CARD_S = 20
SAME_PRESS_S = 2.0


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


def overlay_card(ev, price, now, alert=None):
    """The one overlay card (design 0001 section 10, decision 0016 fork 2):
    {kind, head, line2, line3, verdict, expires_at} or None.
    - eval and price both fresh and from one press: a merged card (eval
      head, price line, eval top stat); a price error or "off" leaves the
      eval card unchanged; a "no build loaded" eval gives the price card;
    - from different presses: the newest one;
    - only one fresh: that one.
    `alert` (TC-VERDICT-CAVEAT): the snapshot's build alert, passed to
    eval_card_text so a compared item's line 3 carries its short head."""
    ev_ok = _fresh(ev, EVAL_CARD_S, now)
    pr_ok = (isinstance(price, dict) and _is_time(price.get("at"))
             and now < price_until(price))
    if not ev_ok and not pr_ok:
        return None

    ws = ev.get("waystone") if isinstance(ev, dict) and isinstance(ev.get("waystone"), dict) \
        else None
    # TC-CARD-PARTS: the words at most once per call, only when the item
    # card can show; the mark's tone (risky waystone included) and
    # `answers` come from eval_card_text
    words = []

    def eval_text():
        if not words:
            words.append(eval_card_text(ev, alert))
        return words[0]

    def eval_part():
        et = eval_text()
        # UTIL-WAYSTONE-REWARD: a waystone's reward totals take the item line
        # (as a price line does, design 0001 section 10); never a third line
        line2 = et.get("reward_line") or et["item"]
        return {"kind": "eval", "head": et["head"], "line2": line2, "line3": et["line"],
                "verdict": et["tone"], "expires_at": ev["at"] + EVAL_CARD_S}

    def price_line():
        # OVL-CARD-NAME (decision 0016 amendment 2026-11-19): a trade link
        # with no poe.ninja value keeps the item name on line 2; the link
        # itself is on the dashboard
        t = price_card_text(price)
        if price.get("status") != "link" or ninja_text(price.get("ninja")):
            return t["line"]
        return t["item"]

    def price_part():
        t = price_card_text(price)
        return {"kind": "price", "head": t["head"], "line2": price_line(),
                "line3": t["detail"], "verdict": "price",
                "expires_at": price_until(price)}

    if ev_ok and pr_ok:
        if abs(price["at"] - ev["at"]) >= SAME_PRESS_S:
            return price_part() if price["at"] > ev["at"] else eval_part()
        # a waystone's verdict needs no build (UX-OVERLAY-WAYSTONE): keep it;
        # so does a card a part answers without a build (TC-CARD-PARTS)
        if (not ev.get("ok") and ev.get("error") == "no build loaded" and not ws
                and not eval_text()["answers"]):
            return price_part()
        if price.get("status") in ("off", "error"):
            return eval_part()
        card = eval_part()
        card.update(kind="merged", line2=price_line(),
                    expires_at=max(card["expires_at"], price_until(price)))
        return card
    return eval_part() if ev_ok else price_part()


# OVL-ZONE-CARD: the zone moment card (server/al/overlayview.py owns its slot)
MOMENT_CARD_S = 12
# Card copy (design 0001 section 9); every line is clipped to CARD_LINE.
# CARD-LINE-LIMIT-COPY: the fixed lines fit 26 characters (a two-digit gap,
# the longest element) while CARD_LINE stays 34.
BONUS_TEXT = "Bonus: {text}"
NEXT_TEXT = "Next: {zone}"
CLEAR_LINE = "{n} {lv} under: clear it"
PUSH_LINE = "{n} {lv} over: move on"
FIT_LINE = "Your level fits this zone"
BOSS_LINE = "Boss hits mostly {element}"

# OVL-ACT-CARD: the act moment card copy (design 0001 section 9 rule 6);
# server/al/overlayview.py owns the card and re-exports these.
ACT_HEAD = "{label} done"
ACT_TIME = "Act time {time}"
ACT_TIME_PARTIAL = "Act time {time}, partial"
ACT_FASTER = "New best by {gap}"
ACT_SLOWER = "{gap} behind your best"
ACT_SAME = "Ties your best"

_LEVELS = re.compile(r"\D*(\d+)")


def clip(text, width=CARD_LINE):
    """format.js clip(): over the width, cut to width - 3 plus "..."."""
    text = text or ""
    return text if len(text) <= width else text[:width - 3] + "..."


def clip_words(text, width=CARD_LINE):
    """Like clip(), but cut at the last whole word that fits before "...",
    so a cut line never ends mid-word."""
    text = text or ""
    if len(text) <= width:
        return text
    cut = text[:width - 3]
    if " " in cut and text[width - 3] != " ":
        cut = cut[:cut.rindex(" ")]
    return cut.rstrip(" ,;:-") + "..."


def _lv(n):
    return "level" if n == 1 else "levels"


def zone_lines(guide):
    """(head, line2, line3) of the zone card for a zoneguide.view() dict,
    or None (not a campaign zone, no short, or nothing to add to the short:
    a card that repeats its first line only is not worth the slot). Every
    line is at most CARD_LINE; an empty line 2 takes line 3's text."""
    if not isinstance(guide, dict) or guide.get("kind") != "campaign":
        return None
    head = guide.get("short")
    if not isinstance(head, str) or not head.strip():
        return None
    head = head.strip()
    said = _plain(head)
    optional = guide.get("optional") or ()
    first = optional[0] if optional and isinstance(optional[0], dict) else {}
    nxt = guide.get("next").strip() if isinstance(guide.get("next"), str) else ""
    bonus = ""
    if isinstance(first.get("text"), str) and first["text"].strip():
        # the reward before its " - where" part: "+10% cold resistance"
        bonus = first["text"].split(" - ")[0].strip().rstrip(".")
    # line 2: the bonus, else the next zone; a text the short already says,
    # or a bonus that would be cut, gives way to the next zone
    line2 = ""
    bonus_line = BONUS_TEXT.format(text=bonus) if bonus else ""
    next_line = NEXT_TEXT.format(zone=nxt) if nxt and _plain(nxt) not in said else ""
    if bonus and _plain(bonus) in said:
        bonus_line = ""
    if bonus_line and (len(bonus_line) <= CARD_LINE or not next_line):
        line2 = clip_words(bonus_line)
    else:
        line2 = next_line
    adv = guide.get("advice") if isinstance(guide.get("advice"), dict) else {}
    mode = adv.get("mode")
    m = _LEVELS.match(adv.get("text") or "")
    boss = guide.get("boss")
    # line 3: the boss element first (only the guide knows it; the HUD
    # already shows an under-level word), then the level advice
    line3 = ""
    if isinstance(boss, str) and boss:
        line3 = BOSS_LINE.format(element=boss)
    elif mode in ("clear", "push") and m:
        n = int(m.group(1))
        line3 = (CLEAR_LINE if mode == "clear" else PUSH_LINE).format(n=n, lv=_lv(n))
    elif mode == "fit":
        line3 = FIT_LINE
    if not line2:
        line2, line3 = line3, ""
    if not line2:
        return None
    return clip(head), clip(line2), clip(line3)


def _plain(text):
    """Lower case without a leading article, to see whether the short
    already says a line's text."""
    text = text.strip().lower()
    for article in ("a ", "an ", "the "):
        if text.startswith(article):
            return text[len(article):]
    return text
