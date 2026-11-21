"""DATA-PRICE-REFRESH-CORE (F-036): when the core loop starts a due price
refresh by itself.

Before this, a price refresh started only when a page read /api/rates, so
overlay-only play kept stale prices. The rule here: at most one check a
minute; a check asks for a refresh only while web data is on and either
the game log is active (consented and not idle, decision 0029: Client.txt
staleness, never a process check) or /api/rates was read in the last 10
minutes. The poe.ninja hourly gates, the back-off and the contact rule
still decide whether a request is made (ninja.RatesClient.refresh_async),
so this module never makes a request and holds no network code.
"""

CHECK_S = 60.0          # at most one check a minute
READ_WINDOW_S = 600.0   # an /api/rates read keeps refreshing for 10 min


class Gate:
    """The once-a-minute refresh decision. Times are one clock's seconds
    (the core passes time.monotonic()); a clock that moved back counts as
    a minute gone, so the gate never sticks."""

    def __init__(self, check_s=CHECK_S, read_window_s=READ_WINDOW_S):
        self.check_s = float(check_s)
        self.read_window_s = float(read_window_s)
        self.checked_at = None

    def ready(self, now):
        """True when a check may run now (cheap: no state read)."""
        last = self.checked_at
        return last is None or not 0 <= now - last < self.check_s

    def due(self, now, web_on, log_idle, last_read_at):
        """One check: True when a refresh should be asked for. A call
        inside the minute after the last check is False and does not count
        as a check."""
        if not self.ready(now):
            return False
        self.checked_at = now
        if not web_on:
            return False
        if not log_idle:
            return True
        return (isinstance(last_read_at, (int, float))
                and 0 <= now - last_read_at < self.read_window_s)
