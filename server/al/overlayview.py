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
- moment, kind act (OVL-ACT-CARD): an act split closing (the acts
  module's split the area generation just ended) shows for MOMENT_CARD_S:
  line 1 '<act> done', line 2 the split time, line 3 the gap to the best
  saved run of the run history view while run history is on (decision
  0036), else empty (no best, a partial split, history off). Only
  parts.moment turns it off. It holds the slot over the zone card of the
  same entry (the scene line after the closing generation): that zone
  card is dropped, never queued, and the zone counts as seen. Like the
  zone card it never waits and never returns.
- hint (OVL-KEY-HINT): the empty slot teaches the item-check key: one
  line, '<key>: check an item', the bound key of the hotkeys view
  (OVL-KEYS-CORE; no key known = no hint). CARD-LINE-LIMIT-COPY2: over
  HINT_FIT (CARD_LINE, 26) characters it reads 'Check: <key>'; a key too long for
  that (over 19 characters) shows no hint, never a cut key. It has no expiry while due:
  due while no press was ever recorded on this install and fewer than
  HINT_SESSIONS game sessions (log_opened events seen while a key was
  known, so the hint could show) were seen. After that
  it never returns, across a core restart (the store keeps the marker).
  It shows only while no earlier holder has a card, no open trade
  request takes the slot (the page's trade card outranks it) and
  parts.hint is on. The hint reads nothing: the press it teaches is the
  player's own manual press.

OverlayView also carries a small bounded store (to_doc / load_doc, a dirty
flag) that the core loads from ops/runtime/overlay-view.json at start and
saves from its guide tick. OVL-KEY-HINT keeps its marker here ("key_hint":
{"pressed": bool, "sessions": int}: on_press records the first press,
on_event counts game sessions up to HINT_SESSIONS); the act
card (OVL-ACT-CARD) needs no stored key, its moment stays in memory. The zone entries seen in this game run stay in
memory only. view() fills the snapshot's "overlay" dict: guide_short (the
short of the current guided campaign zone, else "") and calm_at (the last
death or level-up time + CALM_S, else None) for the HUD guide line
(OVL-LINE2-GUIDE). The guide is read only through the state's zone-guide
view (zoneguide.view). Nothing is read from the game and nothing is sent;
stdlib only. The caller (SessionState) holds its lock around every call.

OVL-OVERLAY-FEED (F-177): the overlay page's own feed. /events?view=overlay
sends small(snap): only the snapshot fields the HUD reads (OVERLAY_FIELDS,
the same list as SNAP_FIELDS in app/shared/render_gate.js; both tests
check it), and only when one of them changed (change_key: the frame clock
"now", the stamp and a map timer that runs with the clock are not
changes). The frame's "version" is the feed's own change stamp, not the
state version. FeedFrames keeps one serialised frame per view per state
version on the server object, shared by every stream of that view; it has
its own lock and takes the state's snapshot outside SessionState's lock.
"""

import json
import threading
import time

from .text.common import CARD_LINE, _is_time
from .text.overlaycard import EVAL_CARD_S, overlay_card
from .text.overlaycard import (  # noqa: F401 - OVL-ZONE-CARD card copy, re-exported
    BONUS_TEXT, BOSS_LINE, CLEAR_LINE, FIT_LINE, MOMENT_CARD_S, NEXT_TEXT,
    PUSH_LINE, _LEVELS, _lv, _plain, clip, clip_words, zone_lines)
from .text.overlaycard import (  # noqa: F401 - OVL-ACT-CARD card copy, re-exported
    ACT_FASTER, ACT_HEAD, ACT_SAME, ACT_SLOWER, ACT_TIME, ACT_TIME_PARTIAL)

FILE_NAME = "overlay-view.json"
SCHEMA = 1
MAX_BYTES = 16 * 1024  # read cap of the store file (a bigger file reads as empty)
# The store's known keys besides "schema"; load_doc drops every other key.
# A later package adds its key here and its bound.
STORE_KEYS = ("key_hint",)

# OVL-KEY-HINT: the key hint line and when it retires for good
HINT_TEXT = "{key}: check an item"
HINT_SHORT = "Check: {key}"
HINT_FIT = CARD_LINE  # 26 since CARD-LINE-LIMIT-FLIP (design 0001 section 9 rule 6)
HINT_SESSIONS = 3  # game sessions (log_opened) after which the hint retires

SAMPLE_S = 10
SAMPLE_HEAD = "Sample card"
SAMPLE_LINE2 = "This is how a card looks"
SAMPLE_LINE3 = "It leaves in %d s" % SAMPLE_S

# OVL-ZONE-CARD: the zone moment card and the HUD guide-line fields
CALM_S = 20  # the guide line keeps quiet this long after a death / level-up
MAX_SEEN = 256  # zone entries remembered per game run (the campaign has ~100)
ENTRY_TYPES = ("scene_changed", "area_entered")

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
    {"kind": "moment", "life_s": MOMENT_CARD_S, "cards": ("zone", "act"),
     "twin": ("zone-guide", "actsbox")},
    # life_s None: no expiry while due; it retires after the first press
    {"kind": "hint", "life_s": None,
     "exempt": "not a self-leaving answer: it stays until the first press, "
               "and its twin is the item-check help text on the dashboard"},
)


def _layout_allows(state, kind="zone"):
    """parts.moment on and, for the zone card, zone_guide not "never" (no
    layout = defaults). The act card follows parts.moment only."""
    lay = getattr(state, "overlay_layout", None)
    if not isinstance(lay, dict):
        return True
    parts = lay.get("parts") if isinstance(lay.get("parts"), dict) else {}
    if parts.get("moment", True) is False:
        return False
    return kind == "act" or lay.get("zone_guide") != "never"


def _clock_text(seconds):
    """"m:ss", or "h:mm:ss" from one hour (whole seconds)."""
    s = int(max(0, round(seconds)))
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _closed_split(state, now):
    """The act split this area generation closed (its ended_at is `now`),
    else None."""
    acts = getattr(state, "acts", None)
    splits = getattr(acts, "splits", None)
    if not isinstance(splits, list):
        return None
    for i in range(len(splits) - 1, -1, -1):
        s = splits[i]
        if not isinstance(s, dict) or s.get("ended_at") != now:
            continue
        started, ended = s.get("started_at"), s.get("ended_at")
        label = s.get("label")
        if not (_is_time(started) and _is_time(ended)) or not isinstance(label, str):
            return None
        partial = i == 0 and not getattr(acts, "complete_start", False)
        return {"key": s.get("key"), "label": label,
                "time_s": max(0.0, ended - started), "partial": partial}
    return None


def _gap_line(state, split):
    """Line 3 of the act card: the gap to the saved best of this act in
    the run history view, or "" (history off, no saved best, a partial
    split, a best that is this run's own)."""
    if split["partial"]:
        return ""
    view = getattr(state, "run_history", None)
    if not isinstance(view, dict) or view.get("on") is not True:
        return ""
    for row in view.get("best") or ():
        if not isinstance(row, dict) or row.get("key") != split["key"]:
            continue
        best = row.get("best_s")
        if (row.get("this_run") or isinstance(best, bool)
                or not isinstance(best, (int, float)) or not 0 <= best < 1e7):
            return ""
        gap = int(round(split["time_s"])) - int(round(best))
        if gap < 0:
            return clip(ACT_FASTER.format(gap=_clock_text(-gap)))
        if gap > 0:
            return clip(ACT_SLOWER.format(gap=_clock_text(gap)))
        return ACT_SAME
    return ""


def _hint_head(key):
    """The hint line for a known key: HINT_TEXT, else HINT_SHORT, within
    HINT_FIT; None with no key or a key too long for either."""
    if key is None:
        return None
    for form in (HINT_TEXT, HINT_SHORT):
        line = form.format(key=key)
        if len(line) <= HINT_FIT:
            return line
    return None


def _hint_marker(raw):
    """A valid key-hint marker {"pressed": bool, "sessions": 0..HINT_SESSIONS}
    from a read store value, else None (dropped)."""
    if not isinstance(raw, dict):
        return None
    pressed, sessions = raw.get("pressed"), raw.get("sessions")
    if not isinstance(pressed, bool) or isinstance(sessions, bool):
        return None
    if not isinstance(sessions, int) or sessions < 0:
        return None
    return {"pressed": pressed, "sessions": min(sessions, HINT_SESSIONS)}


def _hint_key(state):
    """The bound item-check key of the published hotkeys view, else None."""
    view = getattr(state, "hotkeys", None)
    entry = view.get("eval") if isinstance(view, dict) else None
    key = entry.get("key") if isinstance(entry, dict) else None
    if not isinstance(key, str) or not key or not key.isascii():
        return None
    return key


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
        # OVL-KEY-HINT: the stored marker, None until its first change
        self._store_key_hint = None

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
            if _hint_head(_hint_key(state)) is not None:
                # a game session counts only while a key is known and fits
                # the hint line (the hint could teach it); no client, no
                # key, no count
                changed = self._count_session() or changed
        if t == "area_generated" and _is_time(now):
            changed = self._act_closed(state, now) or changed
        if t in ENTRY_TYPES and state.zone and state.zone_entered_at == now:
            changed = self._enter(state, now) or changed
        if self._sync_guide(state):
            changed = True
        return changed

    def on_press(self, now):
        """A real item-key press (not a re-score). False: nothing changed.
        A press drops the zone card: it never waits or returns. The first
        press retires the key hint for good (OVL-KEY-HINT)."""
        changed = False
        marker = self._hint_state()
        if not marker["pressed"]:
            self._store_key_hint = dict(marker, pressed=True)
            self.dirty = changed = True
        if self.moment is not None:
            self.moment = None
            changed = True
        return changed

    # -- the key hint (OVL-KEY-HINT)
    def _hint_state(self):
        return _hint_marker(self._store_key_hint) or {"pressed": False, "sessions": 0}

    def _count_session(self):
        """One more game session seen, up to HINT_SESSIONS. True on a change."""
        marker = self._hint_state()
        if marker["pressed"] or marker["sessions"] >= HINT_SESSIONS:
            return False
        self._store_key_hint = dict(marker, sessions=marker["sessions"] + 1)
        self.dirty = True
        return True

    def hint_due(self):
        """No press ever recorded and fewer than HINT_SESSIONS game sessions."""
        marker = self._hint_state()
        return not marker["pressed"] and marker["sessions"] < HINT_SESSIONS

    def _hint_card(self, state):
        if not self.hint_due() or _trade_takes_slot(state):
            return None
        lay = getattr(state, "overlay_layout", None)
        parts = lay.get("parts") if isinstance(lay, dict) and isinstance(
            lay.get("parts"), dict) else {}
        if parts.get("hint", True) is False:
            return None
        head = _hint_head(_hint_key(state))
        if head is None:
            return None
        return {"kind": "hint", "head": head,
                "line2": "", "line3": "", "verdict": "hint", "expires_at": None}

    def _guide(self, state):
        view = getattr(state, "_zone_guide_view", None)
        return view() if callable(view) else None

    def _act_closed(self, state, now):
        """OVL-ACT-CARD: an area generation that closed an act split gets
        the act card; any moment card before it goes."""
        split = _closed_split(state, now)
        if split is None or not split["label"]:
            return False
        tmpl = ACT_TIME_PARTIAL if split["partial"] else ACT_TIME
        self.moment = {"at": float(now), "gen": getattr(state, "_zone_gen", None),
                       "kind": "act", "head": clip(ACT_HEAD.format(label=split["label"])),
                       "line2": clip(tmpl.format(time=_clock_text(split["time_s"]))),
                       "split": split}
        return True

    def _enter(self, state, now):
        """A fresh zone entry: the zone card of the zone before it goes; a
        guided campaign zone not entered before in this run gets its own.
        An act card of this same entry keeps the slot: the zone card is
        dropped (never queued) and the zone counts as seen."""
        gen = getattr(state, "_zone_gen", None)
        m = self.moment
        act_here = m is not None and m.get("kind") == "act" and m["gen"] == gen
        changed = m is not None and not act_here
        if not act_here:
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
        if act_here:
            return changed
        head, line2, line3 = lines
        self.moment = {"at": float(now), "gen": gen, "kind": "zone",
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
        # OVL-TD18-CARD-TIME: the state's card time (the layout's card_s)
        card_s = getattr(state, "card_s", EVAL_CARD_S)
        return overlay_card(state.eval, state.price, now, alert, card_s)

    # -- the zone / act moment card
    def _moment_card(self, state, now):
        m = self.moment
        if m is None:
            return None
        at = m["at"]
        kind = m.get("kind", "zone")
        if (not at <= now < at + MOMENT_CARD_S
                or m["gen"] != getattr(state, "_zone_gen", None)
                or _trade_takes_slot(state) or not _layout_allows(state, kind)):
            if now >= at:
                self.moment = None  # it never waits and never returns
            return None
        # the act card's gap is read at show time: the history view the
        # core tick publishes may land after the closing log line
        line3 = _gap_line(state, m["split"]) if kind == "act" else m["line3"]
        return {"kind": kind, "head": m["head"], "line2": m["line2"],
                "line3": line3, "verdict": "",
                "expires_at": at + MOMENT_CARD_S}

    def card(self, state, now, alert=None):
        """The one card dict {kind, head, line2, line3, verdict,
        expires_at} that holds the slot at `now`, or None (the hint card's
        expires_at is None: no expiry while due). `alert`: the
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
            elif kind == "hint":
                c = self._hint_card(state)
            else:  # pragma: no cover - a holder without a producer
                c = None
            if c is not None:
                if (kind in ("press", "sample") and self.moment is not None
                        and self.moment["at"] <= now):
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
                value = doc[key]
                if key == "key_hint":
                    value = _hint_marker(value)  # a bad marker reads as none
                setattr(self, "_store_" + key, value)
        self.dirty = False
        return True


# -- OVL-OVERLAY-FEED (F-177): the overlay's own feed ---------------------------

# Every snapshot field the overlay page reads (app/shared/render_gate.js
# SNAP_FIELDS, the same strings in the same order; app/overlay/overlay.js
# reads only "now" besides). A dotted entry keeps only that part of its
# top-level dict ("maps.current": the open map, not the ladder). The frame
# also carries "version": the feed's own change stamp (STAMP).
OVERLAY_FIELDS = (
    "now", "zone", "in_hideout", "in_town", "zone_entered_at", "level", "deaths",
    "afk", "dnd", "tailer", "game_idle", "maps.current", "trade_requests",
    "underlevel.word", "campaign.word", "card", "eval.text", "eval.expires_at",
    "eval.ok", "eval.verdict", "overlay", "overlay_layout")
STAMP = "version"
VIEWS = ("overlay",)  # the views /events takes besides the default (absent)
# A frame built for a state version is reused by the other streams of its
# view for this long; then the next push takes a fresh snapshot (its "now").
FRAME_REUSE_S = 0.25


def small(snap, stamp=None):
    """The overlay view of a state snapshot: only OVERLAY_FIELDS, plus
    "version" = stamp (the feed's change stamp; None keeps the snapshot's).
    A key the snapshot lacks stays absent; a dotted entry under a value
    that is not a dict keeps that value (None stays None)."""
    out = {}
    if not isinstance(snap, dict):
        return out
    for field in OVERLAY_FIELDS:
        top, _, sub = field.partition(".")
        if top not in snap:
            continue
        value = snap[top]
        if not sub:
            out[top] = value
        elif not isinstance(value, dict):
            out.setdefault(top, value)
        else:
            part = out.setdefault(top, {})
            if isinstance(part, dict) and sub in value:
                part[sub] = value[sub]
    out[STAMP] = snap.get(STAMP) if stamp is None else stamp
    return out


def change_key(doc):
    """The text two overlay frames are compared by: the small view without
    the clock and the stamp. A map timer that runs with the clock (time_s
    while inside) counts by its start (now - time_s), and the last log
    line time only while the log is idle (the HUD reads it only then), so
    neither the clock nor a busy log alone is a change."""
    key = {k: v for k, v in doc.items() if k not in ("now", STAMP)}
    tl = key.get("tailer")
    if isinstance(tl, dict) and not (tl.get("consented") and tl.get("idle")):
        key["tailer"] = {k: v for k, v in tl.items() if k != "last_line_at"}
    maps = key.get("maps")
    cur = maps.get("current") if isinstance(maps, dict) else None
    now = doc.get("now")
    if (isinstance(cur, dict) and cur.get("inside") is True
            and _is_time(now) and _is_time(cur.get("time_s"))):
        cur = dict(cur, time_s=None, started=round(float(now) - cur["time_s"], 3))
        key["maps"] = dict(maps, current=cur)
    return json.dumps(key, sort_keys=True, separators=(",", ":"), default=str)


class FeedFrames:
    """One serialised state frame per view per state version, shared by
    every SSE stream of that view (server/al/http.py _sse_stream). For the
    overlay view the stamp moves only when change_key moves; for the
    default view (None) the stamp is the state version. Thread-safe."""

    def __init__(self, clock=time.monotonic):
        self._lock = threading.Lock()
        self._clock = clock
        self._frames = {}  # view -> (state version, built_at, stamp, text)
        self._key = None  # change key of the last overlay frame
        self._stamp = 0  # the overlay feed's change stamp

    def frame(self, view, state, encode):
        """(state version, stamp, frame text) for `view` (None or "overlay").
        encode(event, data) makes the frame text (Handler._sse_msg)."""
        with self._lock:
            hit = self._frames.get(view)
            now = self._clock()
            if (hit is not None and hit[0] == state.version
                    and 0 <= now - hit[1] < FRAME_REUSE_S):
                return hit[0], hit[2], hit[3]
            snap = state.snapshot()
            if view == "overlay":
                doc = small(snap)
                key = change_key(doc)
                if key != self._key:
                    self._key = key
                    self._stamp += 1
                stamp = doc[STAMP] = self._stamp
            else:
                doc, stamp = snap, snap.get(STAMP)
            text = encode("state", doc)
            self._frames[view] = (snap.get(STAMP), now, stamp, text)
            return snap.get(STAMP), stamp, text
