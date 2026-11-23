"""SessionState's trade cards as TradesMixin (TEST-STATE-MIXIN-A, F-192,
research 0047 R5 (2); the pattern is the loop's mixins, tools/loop_inbox.py
and tools/loop_merge.py).

The open trade whisper cards (HUD-WHISPER), their expiry (DS-TRADE-EXPIRE),
dismissal, close on a finished trade (decision 0019) and refresh
(PLAY-F-120-TRADE-REFRESH). The methods moved verbatim from state.py: the
lock is SessionState's one lock, the event dispatcher (apply /
_apply_locked) stays in state.py and calls the helpers there. state.py
re-exports every name here, so state.<name> stays. Stdlib only.
"""

import collections

from .text.events import trade_card_text

TRADE_REQUESTS = 5  # open trade whisper cards (HUD-WHISPER); oldest drops
# DS-TRADE-EXPIRE (design 0001 N5): a card clears by itself this long after
# it arrived; the dashboard states the rule and Dismiss stays.
TRADE_EXPIRE_S = 600
TRADE_FIELDS = ("kind", "item", "price_amount", "price_currency", "want_amount",
                "league", "stash_tab", "left", "top")


class TradesMixin:
    """Mixed into state.SessionState. _init_trades() runs from __init__,
    _view_trades(now) from snapshot() (after its _expire_trades)."""

    def _init_trades(self):
        self.trade_requests = collections.deque(maxlen=TRADE_REQUESTS)
        self._trade_ids = 0

    def _view_trades(self, now):
        """Caller holds the lock. The snapshot's trade keys."""
        return {"trade_requests": [dict(r, **trade_card_text(r))
                                   for r in self.trade_requests]}

    def expire_trades(self, now=None):
        """From the core's loop tick: drop expired trade cards now, so the
        change is pushed without waiting for a snapshot."""
        with self._lock:
            self._expire_trades(self._clock() if now is None else now)

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

    def _refresh_trade(self, ev, now):
        """PLAY-F-120-TRADE-REFRESH: an incoming trade whisper with the same
        sender and item text as an open card refreshes that card (its at and
        the TRADE_FIELDS of the newest whisper) instead of adding one; the
        card keeps its id and place. Caller holds the lock. Returns True when
        a card was refreshed."""
        sender = ev.get("from")
        trade = ev.get("trade") or {}
        item = trade.get("item")
        if not isinstance(sender, str) or not sender or not isinstance(item, str):
            return False
        row = next((r for r in self.trade_requests
                    if r.get("from") == sender and r.get("item") == item), None)
        if row is None:
            return False
        row["at"] = now
        for k in TRADE_FIELDS:
            if k in trade:
                row[k] = trade[k]
            else:
                row.pop(k, None)
        return True
