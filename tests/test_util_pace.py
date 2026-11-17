"""UTIL-PACE: levelling pace from level-up lines (Client.txt has no XP).
Exact sentence tests on replayed level-ups; no network, no game."""

from server.al import pace
from server.al.state import SessionState


class Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def up(level, at, who="Ash"):
    return {"type": "level_up", "character": who, "class": "Witch",
            "level": level, "recv_ts": at}


def test_pace_empty_and_one_level():
    p = pace.Pace()
    assert p.view(0.0, 0.0) == {"per_level_s": None, "per_hour": None, "text": ""}
    p.on_level(10, 100.0)
    # one level-up is no interval and no hourly rate (design P-2)
    assert p.view(1800.0, 0.0)["text"] == ""


def test_pace_last_levels_exact():
    p = pace.Pace()
    for i, at in enumerate((0.0, 300.0, 700.0, 1200.0, 1800.0, 2500.0, 3300.0)):
        assert p.on_level(10 + i, at) is True
    v = p.view(3600.0, 0.0)
    # the window keeps the last 5 levels: 11 at 300 .. 16 at 3300
    assert v["per_level_s"] == 600.0
    assert v["per_hour"] == 7.0
    assert v["text"] == ("Pace: about 10:00 a level over the last 5, "
                         "7.0 levels an hour.")


def test_pace_hourly_needs_ten_minutes_and_singular():
    p = pace.Pace()
    p.on_level(10, 0.0)
    p.on_level(11, 60.0)
    assert p.view(300.0, 0.0)["text"] == "Pace: about 1:00 for the last level."
    assert p.view(7200.0, 0.0)["text"] == (
        "Pace: about 1:00 for the last level, 1.0 level an hour.")


def test_pace_skipped_levels_and_new_character():
    p = pace.Pace()
    p.on_level(10, 0.0)
    p.on_level(12, 400.0)   # two levels in one gap (a missed line)
    assert p.view(0.0, 0.0)["text"] == (
        "Pace: about 3:20 a level over the last 2.")
    assert p.on_level(2, 5000.0) is True   # lower level: a new character
    assert p.view(5000.0, 0.0)["per_level_s"] is None
    p.on_level(3, 5300.0)
    # the hourly rate counts from the character change, not session start
    assert p.view(8600.0, 0.0)["per_hour"] == 2.0
    assert p.on_level(None, 600.0) is False


def test_snapshot_pace_counts_only_the_player():
    clock = Clock(0.0)
    st = SessionState(character="Ash", clock=clock)
    st.apply(up(20, 60.0))
    st.apply(up(30, 70.0, who="Other"))
    st.apply(up(21, 660.0))
    clock.t = 1200.0
    assert st.snapshot()["pace"]["text"] == (
        "Pace: about 10:00 for the last level, 6.0 levels an hour.")


def test_pace_base_ignores_the_resumed_session_start():
    """UX-NEW-CARDS: LIVE-RESUME moves the Session tile back to the log
    opening; the pace counts live level-ups only, so its hour stays the
    core start."""
    clock = Clock(3600.0)
    st = SessionState(character="Ash", clock=clock)
    st.restore({"session_started_at": 0.0})
    st.apply(up(20, 3660.0))
    st.apply(up(21, 3960.0))
    st.apply(up(22, 4260.0))
    clock.t = 3600.0 + 1800.0
    v = st.snapshot()
    assert v["session_s"] == 5400.0
    assert v["pace"]["per_hour"] == 6.0
