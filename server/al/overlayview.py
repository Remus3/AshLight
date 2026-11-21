"""OVL-CARD-SLOT (F-118): the overlay view seam, the one owner of the card slot.

The overlay shows at most one card (design 0001 section 10). Which card
holds the slot at a given moment is decided here, in the fixed order of
CARD_HOLDERS: the first holder with a card wins.

- press: the item-check / price card of the last hotkey press
  (text.overlaycard.overlay_card, unchanged). A live press card always
  wins (design 0001 section 7.2: the press card comes first).
- sample: the 10 s sample card the Settings "show a sample card" button
  asks for (POST /api/overlay-sample), shown only while no press card
  holds the slot. It is display state only: it never enters the recent
  events, the item check, the price check or run history, and it leaves
  by itself SAMPLE_S after the click.
- moment (OVL-ZONE-CARD): the zone card, MOMENT_CARD_S from the first
  entry of a guided campaign zone in a game run (log_opened starts a new
  run). Line 1 is the guide entry's short, line 2 the bonus or the next
  zone, line 3 the level advice or the boss element. It shows only while
  no earlier holder has a card, no open trade request takes the slot and
  the layout allows it (parts.moment, zone_guide not "never"). It never
  waits and never returns: anything that takes the slot first drops it.
  The trade card is built on the overlay page itself, so the order the
  player sees is press, sample, trade, moment.

OverlayView also carries a small bounded store (to_doc / load_doc, a dirty
flag) that the core loads from ops/runtime/overlay-view.json at start and
saves from its guide tick. It is empty today: later packages (OVL-ACT-CARD,
OVL-KEY-HINT, OVL-OVERLAY-FEED) record act close and the first press here
through on_event / on_press. The zone entries seen in this game run stay in
memory only. view() fills the snapshot's "overlay" dict: guide_short (the
short of the current guided campaign zone, else "") and calm_at (the last
death or level-up time + CALM_S, else None) for the HUD guide line
(OVL-LINE2-GUIDE). The guide is read only through the state's zone-guide
view (zoneguide.view). Nothing is read from the game and nothing is sent;
stdlib only. The caller (SessionState) holds its lock around every call.
"""

import re

from .text.common import CARD_LINE, _is_time
from .text.overlaycard import EVAL_CARD_S, overlay_card

FILE_NAME = "overlay-view.json"
SCHEMA = 1
MAX_BYTES = 16 * 1024  # read cap of the store file (a bigger file reads as empty)
# The store's known keys besides "schema"; load_doc drops every other key.
# Empty today; a later package adds its key here and its bound.
STORE_KEYS = ()

SAMPLE_S = 10
SAMPLE_HEAD = "Sample card"
SAMPLE_LINE2 = "This is how a card looks"
SAMPLE_LINE3 = "It leaves in %d s" % SAMPLE_S

# OVL-ZONE-CARD: the zone moment card and the HUD guide-line fields
MOMENT_CARD_S = 12
CALM_S = 20  # the guide line keeps quiet this long after a death / level-up
MAX_SEEN = 256  # zone entries remembered per game run (the campaign has ~100)
ENTRY_TYPES = ("scene_changed", "area_entered")
# Card copy (design 0001 section 9); every line is clipped to CARD_LINE.
BONUS_TEXT = "Bonus: {text}"
NEXT_TEXT = "Next: {zone}"
CLEAR_LINE = "You are {n} {lv} under: clear it"
PUSH_LINE = "You are {n} {lv} over: move on"
FIT_LINE = "Your level fits this zone"
BOSS_LINE = "Boss deals mostly {element} damage"

# The card-slot holders, first match wins. Each entry: kind, life_s (how
# long its card shows), and twin = the id(s) of its dashboard twin in
# web/index.html, or exempt = why it needs none (tests/test_glance_rules.py
# reads both). The press card's own kinds (eval, price, merged) keep their
# twins in that test's TWINS table; `cards` names the card kinds a holder
# publishes when they differ from its own kind.
CARD_HOLDERS = (
    {"kind": "press", "life_s": EVAL_CARD_S,
     "twin": ("eval-result", "price-result")},
    {"kind": "sample", "life_s": SAMPLE_S,
     "exempt": "shown only on its Settings button, which is its own twin"},
    {"kind": "moment", "life_s": MOMENT_CARD_S, "cards": ("zone",),
     "twin": ("zone-guide",)},
)

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


def _layout_allows(state):
    """parts.moment on and zone_guide not "never" (no layout = defaults)."""
    lay = getattr(state, "overlay_layout", None)
    if not isinstance(lay, dict):
        return True
    parts = lay.get("parts") if isinstance(lay.get("parts"), dict) else {}
    return parts.get("moment", True) is not False and lay.get("zone_guide") != "never"


def _trade_takes_slot(state):
    """An open trade request takes the slot while the trade part is on
    (the overlay page builds that card itself)."""
    if not getattr(state, "trade_requests", None):
        return False
    lay = getattr(state, "overlay_layout", None)
    parts = lay.get("parts") if isinstance(lay, dict) and isinstance(
        lay.get("parts"), dict) else {}
    return parts.get("trade", True) is not False


class OverlayView:
    def __init__(self):
        self.sample_at = None
        self.dirty = False
        # OVL-ZONE-CARD: in memory only, reset by a new game run
        self.moment = None  # {"at", "gen", "head", "line2", "line3"}
        self.seen = {}  # (act, zone) -> True, the zones entered this run
        self.guide_short = ""
        self.calm_at = None
        self._guide_key = None  # the zone generation guide_short was read for
        self._counts = (0, 0)  # (deaths, level_ups) after the last event

    # -- feed
    def on_event(self, ev, state, now):
        """One bus event, after the state applied it. False: nothing of the
        overlay view changed."""
        t = ev.get("type") if isinstance(ev, dict) else None
        changed = False
        counts = (getattr(state, "deaths", 0), getattr(state, "level_ups", 0))
        if (t in ("death", "level_up")
                and counts != self._counts and _is_time(now)):
            # the player's own death or level-up: the guide line keeps quiet
            self.calm_at = float(now) + CALM_S
            changed = True
        self._counts = counts
        if t == "log_opened":
            # a new game run: every zone may show its card once again
            changed = changed or bool(self.seen) or self.moment is not None
            self.seen = {}
            self.moment = None
        if t in ENTRY_TYPES and state.zone and state.zone_entered_at == now:
            changed = self._enter(state, now) or changed
        if self._sync_guide(state):
            changed = True
        return changed

    def on_press(self, now):
        """A real item-key press (not a re-score). False: nothing changed.
        A press drops the zone card: it never waits or returns."""
        if self.moment is not None:
            self.moment = None
            return True
        return False

    def _guide(self, state):
        view = getattr(state, "_zone_guide_view", None)
        return view() if callable(view) else None

    def _enter(self, state, now):
        """A fresh zone entry: the zone card of the zone before it goes; a
        guided campaign zone not entered before in this run gets its own."""
        changed = self.moment is not None
        self.moment = None
        if state.in_hideout or not _is_time(now):
            return changed
        guide = self._guide(state)
        self._guide_key = getattr(state, "_zone_gen", None)
        short = self._short_of(guide)
        if short != self.guide_short:
            self.guide_short, changed = short, True
        lines = zone_lines(guide)
        if lines is None:
            return changed
        key = (guide.get("act"), guide.get("zone"))
        if key in self.seen:
            return changed
        if len(self.seen) >= MAX_SEEN:
            self.seen.pop(next(iter(self.seen)))
        self.seen[key] = True
        head, line2, line3 = lines
        self.moment = {"at": float(now), "gen": getattr(state, "_zone_gen", None),
                       "head": head, "line2": line2, "line3": line3}
        return True

    @staticmethod
    def _short_of(guide):
        if isinstance(guide, dict) and guide.get("kind") == "campaign":
            short = guide.get("short")
            return short if isinstance(short, str) else ""
        return ""

    def _sync_guide(self, state):
        """Re-read guide_short when the zone generation moved without an
        entry this view saw (a resume, a game start). True on a change."""
        gen = getattr(state, "_zone_gen", None)
        if gen == self._guide_key:
            return False
        self._guide_key = gen
        short = self._short_of(self._guide(state)) if state.zone else ""
        if short != self.guide_short:
            self.guide_short = short
            return True
        return False

    # -- the sample card
    def set_sample(self, now):
        """Show the sample card for SAMPLE_S from `now`; a second click
        starts the 10 s again."""
        self.sample_at = float(now)

    def _sample_card(self, now):
        at = self.sample_at
        if not _is_time(at):
            return None
        if not at <= now < at + SAMPLE_S:
            if now >= at + SAMPLE_S:
                self.sample_at = None  # gone for good, no stale state kept
            return None
        return {"kind": "sample", "head": SAMPLE_HEAD, "line2": SAMPLE_LINE2,
                "line3": SAMPLE_LINE3, "verdict": "note",
                "expires_at": at + SAMPLE_S}

    def _press_card(self, state, now, alert=None):
        return overlay_card(state.eval, state.price, now, alert)

    # -- the zone moment card
    def _moment_card(self, state, now):
        m = self.moment
        if m is None:
            return None
        at = m["at"]
        if (not at <= now < at + MOMENT_CARD_S
                or m["gen"] != getattr(state, "_zone_gen", None)
                or _trade_takes_slot(state) or not _layout_allows(state)):
            if now >= at:
                self.moment = None  # it never waits and never returns
            return None
        return {"kind": "zone", "head": m["head"], "line2": m["line2"],
                "line3": m["line3"], "verdict": "",
                "expires_at": at + MOMENT_CARD_S}

    def card(self, state, now, alert=None):
        """The one card dict {kind, head, line2, line3, verdict,
        expires_at} that holds the slot at `now`, or None. `alert`: the
        snapshot's build alert, passed on to the press card."""
        self._sync_guide(state)
        for holder in CARD_HOLDERS:
            kind = holder["kind"]
            if kind == "sample":
                c = self._sample_card(now)
            elif kind == "press":
                c = self._press_card(state, now, alert)
            elif kind == "moment":
                c = self._moment_card(state, now)
            else:  # pragma: no cover - a holder without a producer
                c = None
            if c is not None:
                if kind != "moment" and self.moment is not None and self.moment["at"] <= now:
                    self.moment = None  # an earlier holder took the slot
                return c
        return None

    def view(self, now):
        """The snapshot's "overlay" dict: the HUD guide-line fields."""
        calm = self.calm_at if _is_time(self.calm_at) else None
        return {"guide_short": self.guide_short, "calm_at": calm}

    # -- the bounded store (ops/runtime/overlay-view.json)
    def to_doc(self):
        doc = {"schema": SCHEMA}
        for key in STORE_KEYS:
            value = getattr(self, "_store_" + key, None)
            if value is not None:
                doc[key] = value
        return doc

    def load_doc(self, doc):
        """Take the known keys of a read store document; anything else (a
        broken file, a wrong kind, an unknown key) is dropped. Never raises."""
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            return False
        for key in STORE_KEYS:
            if key in doc:
                setattr(self, "_store_" + key, doc[key])
        self.dirty = False
        return True
