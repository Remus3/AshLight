"""In-process pub/sub event bus.

Thread-safe; a bounded ring buffer keeps the most recent events; each
subscriber has its own bounded queue and a slow subscriber loses its OLDEST
events (counted in .dropped), never blocking the publisher.
"""

import collections
import itertools
import threading
import time

RING_SIZE = 500
QUEUE_SIZE = 256


class Subscription:
    def __init__(self, bus, maxlen):
        self._bus = bus
        self._q = collections.deque(maxlen=maxlen)
        self._cond = threading.Condition(threading.Lock())
        self.dropped = 0
        self.closed = False
        self._woken = False  # a wake() not yet seen by get() (never lost)

    def _push(self, event):
        with self._cond:
            if len(self._q) == self._q.maxlen:
                self.dropped += 1  # deque(maxlen) drops the oldest on append
            self._q.append(event)
            self._cond.notify()

    def get(self, timeout=None):
        """All queued events (oldest first); waits up to timeout for one."""
        with self._cond:
            if not self._q and not self.closed and not self._woken:
                self._cond.wait(timeout)
            self._woken = False
            out = list(self._q)
            self._q.clear()
            return out

    def wake(self):
        with self._cond:
            self._woken = True
            self._cond.notify_all()

    def close(self):
        self.closed = True
        self._bus.unsubscribe(self)
        self.wake()


class EventBus:
    def __init__(self, ring_size=RING_SIZE, queue_size=QUEUE_SIZE):
        self._lock = threading.Lock()
        self._ring = collections.deque(maxlen=ring_size)
        self._subs = set()
        self._seq = itertools.count(1)
        self._queue_size = queue_size
        self._listeners = []
        self.published = 0

    def add_listener(self, fn):
        """fn(event) is called synchronously on publish (state updates)."""
        with self._lock:
            self._listeners.append(fn)

    def publish(self, event):
        """Stamp seq and recv_ts, store in the ring, fan out. Returns the event."""
        with self._lock:
            event["seq"] = next(self._seq)
            event.setdefault("recv_ts", time.time())
            self._ring.append(event)
            self.published += 1
            listeners = list(self._listeners)
            subs = list(self._subs)
        for fn in listeners:
            fn(event)
        for sub in subs:
            sub._push(event)
        return event

    def subscribe(self, maxlen=None):
        sub = Subscription(self, maxlen or self._queue_size)
        with self._lock:
            self._subs.add(sub)
        return sub

    def wake_all(self):
        """TEST-FULLSTACK-SSE-IDLE: wake every waiting subscriber with no
        event (its get() returns []), so a state change with no log line
        is pushed at once."""
        with self._lock:
            subs = list(self._subs)
        for sub in subs:
            sub.wake()

    def unsubscribe(self, sub):
        with self._lock:
            self._subs.discard(sub)

    def recent(self, n=None):
        with self._lock:
            items = list(self._ring)
        return items if n is None else items[-n:]

    @property
    def subscriber_count(self):
        with self._lock:
            return len(self._subs)
