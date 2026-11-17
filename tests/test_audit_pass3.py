"""AREA-AUDIT pass 3 regression tests (docs/audit/2026-11-17-audit.md,
"Pass 3"). Synthetic events and a fake clock; no game, no network."""

from server.al import summary
from server.al.state import SessionState

IDLE = summary.IDLE_S


def _consented(t=5000.0):
    st = SessionState(clock=lambda: t)
    st.set_tailer(consented=True, reading=True, path="logs/Client.txt")
    return st


def test_p3_1_tailer_status_is_not_a_log_line():
    # Decision 0029: last_line_at is the receipt time of the last PARSED
    # Client.txt line. The tailer's own status events are not log lines.
    st = _consented()
    st.apply({"type": "area_generated", "area_id": "MapCrypt", "area_level": 65,
              "seed": "1", "recv_ts": 1000.0, "source": "client_log"})
    st.apply({"type": "tailer_reset", "reason": "missing", "source": "tailer",
              "recv_ts": 1000.0 + IDLE / 2})
    assert st.snapshot()["tailer"]["last_line_at"] == 1000.0
    assert st.check_log_idle(now=1000.0 + IDLE) is True
    # a status event after the idle state does not clear it either
    st.apply({"type": "tailer_started", "path": "x", "source": "tailer",
              "recv_ts": 1000.0 + IDLE + 5})
    assert st.snapshot()["tailer"]["idle"] is True


def test_p3_1_core_resume_seed_survives_the_tailer_start(tmp_path):
    # The real tailer calls on_resume (the mtime seed) and THEN emits
    # tailer_started; the seed must survive it, so a game closed before the
    # core started turns idle IDLE_S after its last write, not after start.
    import os
    from server.al.core import Core
    log = tmp_path / "Client.txt"
    log.write_text("2026/11/16 20:00:05 1 a [INFO Client 1] [SCENE] Set Source [Crypt]\n",
                   encoding="ascii", newline="\n")
    os.utime(log, (1000.0, 1000.0))
    core = Core(runtime=tmp_path, tail=False)
    try:
        core.state.set_tailer(consented=True, reading=True, path=str(log))
        core._resume(log, log.stat().st_size)
        core._on_status({"type": "tailer_started", "path": str(log),
                         "offset": log.stat().st_size, "file_size": log.stat().st_size,
                         "resumed": False, "recv_ts": 2000.0})
        assert core.state.snapshot()["tailer"]["last_line_at"] == 1000.0
        core.tick_summary(now=1000.0 + IDLE)
        assert core.state.snapshot()["tailer"]["idle"] is True
    finally:
        core.close()


def test_p3_2_pricebook_parsers_survive_a_huge_json_int():
    # FUZZ-4 was fixed in ninja._num only; the price book kept its own copy.
    from server.al import pricebook
    huge = "1" + "0" * 400
    body = ('{"core": {}, "lines": [{"name": "A", "primaryValue": %s},'
            ' {"name": "B", "primaryValue": 2}]}' % huge)
    got = pricebook.parse_item_overview(body)
    assert [e["name"] for e in got["entries"]] == ["B"]
    assert pricebook._num(10 ** 400) is None
