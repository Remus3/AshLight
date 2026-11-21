"""OVL-CARD-SLOT (F-118): the overlay view seam, the one owner of the card slot.

The overlay shows at most one card (design 0001 section 10). Which card
holds the slot at a given moment is decided here, in the fixed order of
CARD_HOLDERS: the first holder with a card wins.

- sample: the 10 s sample card the Settings "show a sample card" button
  asks for (POST /api/overlay-sample). It is display state only: it never
  enters the recent events, the item check, the price check or run history,
  and it leaves by itself after SAMPLE_S.
- press: the item-check / price card of the last hotkey press
  (text.overlaycard.overlay_card, unchanged).

OverlayView also carries a small bounded store (to_doc / load_doc, a dirty
flag) that the core loads from ops/runtime/overlay-view.json at start and
saves from its guide tick. It is empty today: later packages (OVL-ZONE-CARD,
OVL-ACT-CARD, OVL-KEY-HINT, OVL-OVERLAY-FEED) record zone entry, act close
and the first press here through on_event / on_press, and fill the
snapshot's "overlay" dict from view(). Nothing is read from the game and
nothing is sent; stdlib only. The caller (SessionState) holds its lock
around every call.
"""

from .text.common import _is_time
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
SAMPLE_LINE3 = "It leaves by itself"

# The card-slot holders, first match wins. Each entry: kind, life_s (how
# long its card shows), and twin = the id(s) of its dashboard twin in
# web/index.html, or exempt = why it needs none (tests/test_glance_rules.py
# reads both). The press card's own kinds (eval, price, merged) keep their
# twins in that test's TWINS table.
CARD_HOLDERS = (
    {"kind": "sample", "life_s": SAMPLE_S,
     "exempt": "shown only on its Settings button, which is its own twin"},
    {"kind": "press", "life_s": EVAL_CARD_S,
     "twin": ("eval-result", "price-result")},
)



class OverlayView:
    def __init__(self):
        self.sample_at = None
        self.dirty = False

    # -- feed (no-ops today; the later packages record here)
    def on_event(self, ev, state, now):
        """One bus event, after the state applied it. False: nothing of the
        overlay view changed."""
        return False

    def on_press(self, now):
        """A real item-key press (not a re-score). False: nothing changed."""
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

    def card(self, state, now, alert=None):
        """The one card dict {kind, head, line2, line3, verdict,
        expires_at} that holds the slot at `now`, or None. `alert`: the
        snapshot's build alert, passed on to the press card."""
        for holder in CARD_HOLDERS:
            kind = holder["kind"]
            if kind == "sample":
                c = self._sample_card(now)
            elif kind == "press":
                c = self._press_card(state, now, alert)
            else:  # pragma: no cover - a holder without a producer
                c = None
            if c is not None:
                return c
        return None

    def view(self, now):
        """The snapshot's "overlay" dict; the later packages fill it."""
        return {}

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
