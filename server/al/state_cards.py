"""SessionState's press cards as CardsMixin (TEST-STATE-MIXIN-A, F-192,
research 0047 R5 (2); the pattern is the loop's mixins, tools/loop_inbox.py
and tools/loop_merge.py).

The item check (TC-EVAL-UI), the price check (PRICE-1-UI, decision 0016),
the loaded build's summary (TC-VIEW), its upgrade notices and stale-build
alert (BUILD-LIVE, decision 0045) and the calc revision (MATH-SKILL-SPLIT).
The methods moved verbatim from state.py: the lock is SessionState's one
lock and the event dispatcher stays in state.py. Stdlib only.
"""

from .text.buildlive import build_alert_text, upgrade_notice_text, upgrades_text
from .text.common import _dicts
from .text.itemcheck import eval_card_text
from .text.overlaycard import EVAL_CARD_S, PRICE_CARD_S, price_until
from .text.price import PRICE_LISTINGS, price_card_text
from .theorycraft import buildlive as buildlive_mod


class CardsMixin:
    """Mixed into state.SessionState. _init_cards() runs from __init__,
    _view_cards(now) from snapshot()."""

    def _init_cards(self):
        # TC-EVAL-UI / TC-VIEW (server/al/theorycraft/live.py).
        self.eval = None
        self._eval_ids = 0
        # PRICE-1-UI: the last price check (decision 0016 contract).
        self.price = None
        self._price_ids = 0
        self.build_info = None
        # BUILD-LIVE (decision 0045): the checked items that are upgrades
        # now (live.LastEval.rescore)
        self.upgrades = None

    def _view_cards(self, now):
        """Caller holds the lock. The snapshot's card keys; build_alert is
        worked out once (BUILD-LIVE, decision 0045) and the item check words
        carry its caveat (TC-VERDICT-CAVEAT, F-043); snapshot() hands it to
        the overlay card slot too."""
        alert = self._build_alert()
        return {
            "eval": (dict(self.eval, text=eval_card_text(self.eval, alert),
                          expires_at=self.eval["at"] + self._card_time(EVAL_CARD_S))
                     if self.eval else None),
            "price": (dict(self.price, text=price_card_text(self.price),
                           expires_at=price_until(self.price,
                                                  self._card_time(PRICE_CARD_S)))
                      if self.price else None),
            "build": dict(self.build_info) if self.build_info else None,
            "build_alert": alert,
            "upgrades": self._upgrades_view(),
        }

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
            if not keep_time:  # OVL-CARD-SLOT: a real press, not a re-score
                self.overlay.on_press(at)
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

    def set_upgrades(self, view):
        """BUILD-LIVE: the upgrade notices of the current character's
        checked items (live.LastEval.rescore)."""
        with self._lock:
            view = dict(view) if isinstance(view, dict) else None
            if view != self.upgrades:
                self.upgrades = view
                self.version += 1

    def _upgrades_view(self):
        """Caller holds the lock. None until the first check."""
        v = self.upgrades
        if not v:
            return None
        items = [dict(n, **upgrade_notice_text(n)) for n in _dicts(v.get("items"))]
        return dict(v, items=items, text=upgrades_text(v),
                    new=sum(1 for n in items if n.get("new")))

    def _build_alert(self):
        """Caller holds the lock. BUILD-LIVE: the stale-build alert."""
        found = buildlive_mod.alert(self.build_info, self.character, self.char_class,
                                    self.level)
        return dict(found, **build_alert_text(found)) if found else None

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
