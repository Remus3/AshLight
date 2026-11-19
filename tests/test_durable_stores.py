"""RUN-DURABLE-STORES (finding F-014): the core's store saves are retried
from the tick with back-off through a jsonfile.Saver instead of being lost
or retried at 2 Hz; config/local.json and consent.json keep one .bak and
read with the .bak restore; Checks shows one row while a store is unsaved
and one note after a restore (server/al/plug/stores.py).

Synthetic events and tmp files only; a failing disk is a patched save
function, never a real one.
"""

import json

import pytest

from server.al import jsonfile, runhistory, zoneguide
from server.al.core import ConfigUnreadable, Core
from server.al.plug import stores


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def gen(area_id, at):
    return {"type": "area_generated", "area_id": area_id, "area_level": 1,
            "seed": "1", "recv_ts": at}


class FailingSave:
    """Stands in for runhistory.save: raises OSError while `failing`,
    counting every attempt; writes through the real function otherwise."""

    def __init__(self, real):
        self.real = real
        self.failing = True
        self.attempts = 0

    def __call__(self, path, runs):
        self.attempts += 1
        if self.failing:
            raise OSError(28, "No space left on device")
        return self.real(path, runs)


@pytest.fixture
def core(tmp_path):
    jsonfile.pop_restored()  # restores of earlier tests are not this core's
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    c.store_clock = Clock()
    try:
        yield c
    finally:
        c.close()


@pytest.fixture
def failing(monkeypatch):
    fake = FailingSave(runhistory.save)
    monkeypatch.setattr(runhistory, "save", fake)
    return fake


def _close_act(core):
    core.state.apply(gen("G1_1", 1000.0))
    core.state.apply(gen("G2_1", 2200.0))


def _checks(core):
    core.tick_all()
    core.tick_diag(force=True)
    return {r["id"]: r for r in core.state.snapshot()["diag"]["checks"]}


def test_failed_history_write_is_written_by_a_later_tick(core, failing):
    """C10: the act split whose save failed is not lost: a later tick
    writes it once the back-off allows."""
    path = core.runtime / runhistory.FILE_NAME
    _close_act(core)
    assert core.tick_history() is False
    assert failing.attempts == 1 and not path.exists()
    assert core.savers["history"].dirty
    failing.failing = False
    core.store_clock.t += 0.5
    assert core.tick_history() is True  # the first retry is due at once
    assert not core.savers["history"].dirty
    runs = runhistory.load(path)
    assert len(runs) == 1 and runs[0]["splits"][0]["time_s"] == 1200.0
    assert jsonfile.bak_path(path).is_file()
    # saved once: nothing more is written while nothing changes
    before = failing.attempts
    core.store_clock.t += 120.0
    assert core.tick_history() is False and failing.attempts == before


def test_thirty_failing_ticks_make_at_most_four_attempts(core, failing):
    """C11: a failing disk is tried after 1, 5, 30, then 60 s, never at
    the 2 Hz tick rate."""
    _close_act(core)
    for _ in range(30):
        core.tick_history()
        core.store_clock.t += 0.5
    assert 2 <= failing.attempts <= 4
    s = core.savers["history"]
    assert s.dirty and s.failures >= 1 and "No space left" in s.last_error
    # the run is still in memory, so nothing is lost
    assert len(core.history.runs) == 1


def test_unsaved_row_shows_and_clears(core, failing):
    assert "tick_stores" in [n for n, _ in core.ticks]
    assert "stores_unsaved" not in _checks(core)
    _close_act(core)
    core.tick_history()
    row = _checks(core)["stores_unsaved"]
    assert row["status"] == "fail" and row["label"] == "Saved data"
    assert row["detail"] == ("AshLight couldn't save your run history yet. "
                             "It keeps trying on its own.")
    assert row["fix"] == stores.UNSAVED_FIX
    assert core.diag_facts()["stores_unsaved"] == ["history"]
    failing.failing = False
    core.store_clock.t += 61.0
    checks = _checks(core)  # tick_all runs tick_history: the retry lands
    assert "stores_unsaved" not in checks
    assert not core.savers["history"].dirty
    assert runhistory.load(core.runtime / runhistory.FILE_NAME)


def test_unsaved_text_names_every_store():
    assert stores.unsaved_text(["visits", "history"]) == (
        "AshLight couldn't save your run history and zone visits yet. "
        "It keeps trying on its own.")
    assert stores.restored_text(["run_history.json"]) == (
        "Run history was damaged and restored from the last good copy.")
    assert stores.restored_text(["settings", "map_ladder.json"]) == (
        "Settings and the map ladder were damaged and restored from the "
        "last good copy.")


def test_broken_config_restores_from_bak_and_says_so(core):
    """C9: a damaged config/local.json comes back from the .bak of its
    last good write, and Checks says so once."""
    cfg = core.config_path
    core.set_history(enabled=False)
    bak = jsonfile.bak_path(cfg)
    assert bak.is_file()
    assert json.loads(bak.read_text(encoding="ascii")) == {"run_history": False}
    cfg.write_bytes(b'{"run_history": fal')  # half written
    assert core._config() == {"run_history": False}
    assert json.loads(cfg.read_text(encoding="ascii")) == {"run_history": False}
    assert core.history_enabled() is False
    note = _checks(core)["stores_restored"]
    assert note["status"] == "note" and note["fix"] is None
    assert note["detail"] == "Settings were damaged and restored from the last good copy."
    assert core.diag_facts()["stores_restored"] == ["settings"]
    # a write over a damaged file restores it first, keeping every key
    cfg.write_bytes(b"[1, 2")
    core.set_web_data(False)
    assert json.loads(cfg.read_text(encoding="ascii")) == {"run_history": False,
                                                          "web_data": False}
    # no good .bak: the hand-broken file is never written over
    bak.unlink()
    cfg.write_bytes(b"{broken")
    with pytest.raises(ConfigUnreadable):
        core.set_web_data(True)
    assert cfg.read_bytes() == b"{broken"


def test_consent_keeps_a_bak_and_reads_it(core):
    core.record_consent(False)
    path = core.consent_path
    assert jsonfile.bak_path(path).is_file()
    path.write_bytes(b"")  # torn by a crash
    assert core.consent_record()["consented"] is False
    assert json.loads(path.read_text(encoding="ascii"))["consented"] is False
    assert "Your log reading choice was damaged" in _checks(core)["stores_restored"]["detail"]


def test_clear_visits_removes_the_bak(core, monkeypatch):
    path = core.visits_path
    core.state.apply({"type": "level_up", "character": "Ash", "class": "Monk", "level": 2})
    core.state.apply(gen("G1_1", 1000.0))
    core.state.apply({"type": "scene_changed", "scene": "The Riverbank", "recv_ts": 1001.0})
    assert core.tick_guide() is True
    bak = jsonfile.bak_path(path)
    assert bak.is_file()
    # the clear's write fails: the .bak still goes, the empty book is
    # written by a later tick
    real = zoneguide.write_visits
    calls = []

    def broken(p, doc):
        calls.append(doc)
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(zoneguide, "write_visits", broken)
    core.set_history(clear=True)
    assert calls and not bak.exists()
    assert core.savers["visits"].dirty
    assert json.loads(path.read_text(encoding="ascii"))["characters"]  # old data
    monkeypatch.setattr(zoneguide, "write_visits", real)
    core.store_clock.t += 2.0
    assert core.tick_guide() is True
    assert json.loads(path.read_text(encoding="ascii"))["characters"] == {}
    assert not bak.exists() and not core.savers["visits"].dirty
    # a clear whose write lands removes the .bak too
    core.state.apply({"type": "scene_changed", "scene": "Clearfell", "recv_ts": 1002.0})
    core.tick_guide()
    assert bak.is_file()
    core.set_history(clear=True)
    assert not bak.exists()


def test_failed_summary_card_is_written_later(core, monkeypatch):
    from server.al import summary as summary_mod
    real = summary_mod.save
    tries = []

    def broken(path, card, keep=summary_mod.MAX_SAVED):
        tries.append(card)
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(summary_mod, "save", broken)
    core.state.set_session_summary({"id": "s1", "text": "x"})
    assert core.tick_summary(now=1.0)["id"] == "s1"
    assert len(tries) == 1 and core.savers["summary"].dirty
    for _ in range(4):  # inside the 1 s back-off: no new attempt
        core.tick_summary(now=1.0)
    assert len(tries) == 1
    monkeypatch.setattr(summary_mod, "save", real)
    core.store_clock.t += 1.5
    core.tick_summary(now=1.0)
    assert not core.savers["summary"].dirty
    assert summary_mod.load_last(core.summary_path)["id"] == "s1"
