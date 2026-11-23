"""RUN-DIAG-DATA-AGE (finding F-114): a Checks row when the game data is
older than the game, through the plug seam (decision 0056).

A bus listener notes every campaign, cruel, interlude or map area id the
log names (area generation events, acts.area_kind) that the cached
world_areas.json does not list. While at least one such id stays unknown,
Checks shows "Game data is older than your game" with the switch that
refreshes it (RUN-NO-DEAD-ENDS: the supervisor fetches newer data by itself
while web data is on, DATA-SNAP-AT-START; never a script). The id list is re-read only when the cached file changes
(hotreload.Watched, one stat per Checks pass), so the row clears by itself
once a refreshed snapshot lists the ids. With no snapshot file there is
nothing to compare and no row (the built-in "Game data" row covers that).

Reads only the opt-in Client.txt events the core already parses and the
local cache; no fetch, nothing sent anywhere.
"""

import threading

from .. import acts, hotreload

ORDER = 100
MAX_SEEN = 16  # area ids kept for the check, newest kept

ROW_ID = "data_age"
LABEL = "Game data"
FIX = ('Keep "Use web data" ticked under Settings, Reading and web data. '
       "AshLight fetches newer game data by itself, at most once a day.")


def detail_text(n):
    """The row's sentence for n unknown areas (n >= 1)."""
    what = "an area" if n == 1 else f"{n} areas"
    return (f"Game data is older than your game: it doesn't list {what} you "
            f"entered, so zone levels can be missing there.")


class Tracker:
    """The area ids seen that the cached file did not list (bounded,
    insertion order). Thread safe: the listener runs on the tailer
    thread, facts on the core loop."""

    def __init__(self, path, on_new=None):
        # RUN-DATAAGE-SHARED-PARSE: one parse of world_areas per change feeds
        # this list, the zone table and the waypoint graph (share=True)
        self.ids = hotreload.Watched(path, acts.load_ids, name="Game data area list",
                                     default=frozenset,
                                     check=hotreload.check_json(acts.MAX_BYTES),
                                     registry=False, from_doc=acts.ids_from_doc,
                                     share=True)
        self.on_new = on_new
        self._lock = threading.Lock()
        self._seen = {}

    def note(self, area_id):
        """Record one area id; True when it is a new unknown id."""
        kind = acts.area_kind(area_id, self.ids.get())
        if kind["kind"] not in acts.DATA_AGE_KINDS or kind["known"] is True:
            return False
        with self._lock:
            if area_id in self._seen:
                return False
            self._seen[area_id] = True
            while len(self._seen) > MAX_SEEN:
                del self._seen[next(iter(self._seen))]
        if self.on_new is not None:
            self.on_new()
        return True

    def on_event(self, ev):
        if isinstance(ev, dict) and ev.get("type") == "area_generated":
            self.note(ev.get("area_id"))

    def unknown(self):
        """The noted ids the current cached file still lacks, oldest first;
        [] with no snapshot. Ids the file now lists are dropped."""
        known = self.ids.get()
        if not known:
            return []
        with self._lock:
            for k in [k for k in self._seen if k in known]:
                del self._seen[k]
            return list(self._seen)


def attach(core):
    def refresh():
        core._next_diag = 0.0  # the Checks card shows it on the next loop pass

    core.data_age = Tracker(core.zone_table.path, on_new=refresh)
    # fill the list now, from the parse the zone table just made (kept for a
    # late member, hotreload.SHARE_KEEP_S), so no later pass parses again
    core.data_age.ids.get()
    core.bus.add_listener(core.data_age.on_event)


def facts(core, now):
    tracker = getattr(core, "data_age", None)
    if tracker is None:
        return {}
    # the zone read back at core start (LIVE-RESUME) is no bus event
    area_id = getattr(getattr(core, "state", None), "area_id", None)
    if area_id:
        tracker.note(area_id)
    return {"data_age_unknown": tracker.unknown()}


def rows(f, now):
    unknown = [i for i in (f.get("data_age_unknown") or ()) if isinstance(i, str)]
    if not unknown:
        return None
    return {"id": ROW_ID, "label": LABEL, "status": "fail",
            "detail": detail_text(len(unknown)), "fix": FIX}
