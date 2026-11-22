"""AUDIT-TC-WIRE: the core's PoB calc provider (theorycraft.calcwire).

Driven with the TC-BRIDGE stdio test double (tests/fixtures/tc_bridge/
fake_bridge.py) and in-memory doubles; no LuaJIT, no PoB."""

import os
import sys
import time
from pathlib import Path

import pytest

from server.al.theorycraft import bridge, calcwire, delta, model
from server.al.theorycraft import evaluate as tc_evaluate
from tc_eval_fixtures import EVAL_BUILD_XML, RARE_GLOVES

FAKE = Path(__file__).resolve().parent / "fixtures" / "tc_bridge" / "fake_bridge.py"


def test_map_outputs_prefers_pob_names_in_order():
    assert calcwire.map_outputs({"FullDPS": 10, "TotalDPS": 5, "TotalEHP": 900,
                                 "Life": 1}) == {"dps": 10.0, "ehp": 900.0}
    assert calcwire.map_outputs({"TotalDPS": 5, "Life": 100, "EnergyShield": 50}) == \
        {"dps": 5.0, "ehp": 150.0}
    assert calcwire.map_outputs({"CombinedDPS": 7, "FullDPS": True, "Life": 3}) == \
        {"dps": 7.0, "ehp": 3.0}
    for bad in (None, {}, {"Life": 1}, {"FullDPS": 1}, {"FullDPS": float("nan"), "Life": 1}):
        with pytest.raises(calcwire.OutputError):
            calcwire.map_outputs(bad)


class FakeBridge:
    def __init__(self):
        self.log = []
        self.items = []

    def load_build(self, xml):
        self.log.append("load")
        self.items = []

    def set_item(self, text, slot=None):
        self.log.append(("set", slot))
        self.items.append(text)

    def outputs(self, keys=None):
        self.log.append("out")
        assert "FullDPS" in keys and "TotalEHP" in keys
        return {"FullDPS": 100.0 + 5 * len(self.items), "Life": 1000.0 + len(self.items)}


def test_make_calc_reloads_around_swaps():
    b = FakeBridge()
    calc = calcwire.make_calc(lambda: b)
    build = model.parse(EVAL_BUILD_XML)
    assert calc(build, {}) == {"dps": 100.0, "ehp": 1000.0}
    assert calc(build, {}) == {"dps": 100.0, "ehp": 1000.0}
    assert b.log == ["load", "out", "out"]  # a clean build is not reloaded
    assert calc(build, {"Gloves": "x"}) == {"dps": 105.0, "ehp": 1001.0}
    # the swap never leaks into the next plain run
    assert calc(build, {}) == {"dps": 100.0, "ehp": 1000.0}
    assert b.log[3:] == ["load", ("set", "Gloves"), "out", "load", "out"]
    with pytest.raises(calcwire.OutputError):
        calc(None, {})


def test_provider_off_unless_opted_in_and_available():
    calls = []
    p = calcwire.Provider(lambda: False, available=lambda: calls.append(1) or True,
                          get_bridge=FakeBridge)
    assert p() is None and calls == []  # off: the component is not even checked
    t = [0.0]
    p = calcwire.Provider(lambda: True, available=lambda: calls.append(1) or False,
                          get_bridge=FakeBridge, clock=lambda: t[0])
    assert p() is None and p() is None and len(calls) == 1  # rate-limited recheck
    t[0] = calcwire.RECHECK_S + 1
    assert p() is None and len(calls) == 2
    on = calcwire.Provider(lambda: True, available=lambda: True, get_bridge=FakeBridge)
    assert callable(on()) and on() is on()

    def boom():
        raise ValueError("bad config")
    assert calcwire.Provider(boom, available=lambda: True)() is None
    assert calcwire.Provider(lambda: True, available=boom)() is None


def test_p3_6_turning_tc_calc_off_stops_the_calc_process(tmp_path):
    """AREA-AUDIT P3-6: the shared luajit process stops once the user turns
    tc_calc off, from the core's loop tick, not only at core close."""
    on, stopped = [True], []
    p = calcwire.Provider(lambda: on[0], available=lambda: True, get_bridge=FakeBridge,
                          stop=lambda: stopped.append(1))
    assert p.reap() is False and stopped == []  # nothing started yet
    assert callable(p())
    assert p.reap() is False and stopped == []  # still on: keep it
    on[0] = False
    assert p.reap() is True and stopped == [1]
    assert p.reap() is False and stopped == [1]  # stopped once
    on[0] = True
    assert callable(p())  # turning it on again starts a fresh calc
    on[0] = False
    assert p() is None and stopped == [1, 1]  # a call while off also stops it
    # the core's loop tick reaps through the provider
    from server.al.core import Core
    log = tmp_path / "Client.txt"
    log.write_text("", encoding="utf-8")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    reaped = []
    core.tc_provider = type("P", (), {"reap": lambda self, idle=False: reaped.append(1)
                                      or False,
                                      "running": lambda self: True,
                                      "close": lambda self: None})()
    core.tick_calc()
    assert reaped == [1]
    # RUN-SEAMS (decision 0056): the loop runs tick_calc through Core's
    # tick list, in its old place, and __main__'s loop calls tick_all
    assert [n for n, _ in core.ticks].index("tick_calc") == 3
    core.tick_all()
    assert reaped == [1, 1]
    core.close()
    import ast
    main = ast.parse((Path(__file__).resolve().parents[1] / "server" / "al"
                      / "__main__.py").read_text(encoding="ascii"))
    calls = [n.func.attr for n in ast.walk(main)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "core"]
    assert "tick_all" in calls and "tick_calc" not in calls


def _idle_provider(t, stopped, bridge_log=None):
    """A Provider on a fake clock `t` ([seconds]) whose stop is recorded."""
    def get_bridge():
        b = FakeBridge()
        if bridge_log is not None:
            bridge_log.append(b)
        return b
    return calcwire.Provider(lambda: True, available=lambda: True, get_bridge=get_bridge,
                             clock=lambda: t[0], stop=lambda: stopped.append(t[0]))


def test_provider_stops_after_idle_and_answers_later():
    """TC-CALC-IDLE (F-154): the calc process stops after IDLE_STOP_S
    without a calc call and the next press makes a fresh calc that
    answers; the opt-in stays on throughout."""
    t, stopped = [0.0], []
    p = _idle_provider(t, stopped)
    build = model.parse(EVAL_BUILD_XML)
    calc = p()
    assert callable(calc) and p.last_used == 0.0 and p.running()
    t[0] = 10.0
    assert calc(build, {}) == {"dps": 100.0, "ehp": 1000.0}
    assert p.last_used == 10.0
    assert calc.raw(build, calcwire.OUTPUT_KEYS) == {"FullDPS": 100.0, "Life": 1000.0}
    for now in (11.0, 600.0, 10.0 + calcwire.IDLE_STOP_S - 1):
        t[0] = now
        assert p.reap() is False and stopped == []  # used too recently
    t[0] = 10.0 + calcwire.IDLE_STOP_S
    assert p.reap() is True and stopped == [t[0]]
    assert not p.running() and p.reap() is False and len(stopped) == 1
    # the next press: a fresh calc at once (no RECHECK_S wait), answering
    t[0] += 5
    again = p()
    assert callable(again) and again is not calc and p.running()
    assert again(build, {"Gloves": "x"}) == {"dps": 105.0, "ehp": 1001.0}
    # a call on the dropped calc (a holder kept it) is adopted again, so
    # the process it starts is reaped like any other
    assert p.close() is True and len(stopped) == 2 and not p.running()
    assert calc(build, {}) == {"dps": 100.0, "ehp": 1000.0} and p.running()
    t[0] += calcwire.IDLE_STOP_S
    assert p.reap() is True and len(stopped) == 3


def test_idle_stop_never_fires_mid_press():
    """TC-CALC-IDLE: neither the idle timer nor game idle stops the calc
    while a press holds it: mid call, or between two of a press's stages
    (PRESS_HOLD_S after the last call)."""
    import threading
    t, stopped = [0.0], []
    gate, inside = threading.Event(), threading.Event()

    class SlowBridge(FakeBridge):
        def outputs(self, keys=None):
            inside.set()
            assert gate.wait(10)
            return super().outputs(keys)

    p = calcwire.Provider(lambda: True, available=lambda: True, get_bridge=SlowBridge,
                          clock=lambda: t[0], stop=lambda: stopped.append(t[0]))
    calc = p()
    build = model.parse(EVAL_BUILD_XML)
    got = []
    worker = threading.Thread(target=lambda: got.append(calc(build, {"Ring 1": "r"})))
    worker.start()
    try:
        assert inside.wait(10)
        t[0] = 5 * calcwire.IDLE_STOP_S  # a very long call
        assert p.held()
        assert p.reap(idle=True) is False and p.reap() is False and stopped == []
    finally:
        gate.set()
        worker.join(10)
    assert got == [{"dps": 105.0, "ehp": 1001.0}]
    # between two stages: the call just ended, so the press still holds it
    t[0] += calcwire.PRESS_HOLD_S - 1
    assert p.held() and p.reap(idle=True) is False and stopped == []
    t[0] += 1
    assert not p.held() and p.reap(idle=True) is True and len(stopped) == 1
    # a fresh calc is held while its press starts (stamped in __call__)
    assert callable(p())
    assert p.held() and p.reap(idle=True) is False and len(stopped) == 1
    # turning the opt-in off still stops it at once, held or not
    on = [True]
    q = calcwire.Provider(lambda: on[0], available=lambda: True, get_bridge=FakeBridge,
                          clock=lambda: t[0], stop=lambda: stopped.append("off"))
    assert callable(q()) and q.held()
    on[0] = False
    assert q.reap() is True and stopped[-1] == "off"


def test_game_idle_stops_the_calc(tmp_path):
    """TC-CALC-IDLE: the core's loop tick passes the state's game-idle flag
    (decision 0029 Client.txt staleness, no process-list check) and the
    calc stops once no press holds it; nothing is read while no calc runs."""
    from server.al.core import Core
    log = tmp_path / "Client.txt"
    log.write_text("", encoding="utf-8")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    try:
        t, stopped = [0.0], []
        core.tc_provider = _idle_provider(t, stopped)
        assert core.tick_calc() is False and stopped == []  # nothing running
        assert callable(core.tc_provider())
        core.state.set_tailer(consented=True, idle=False)
        t[0] = 2 * calcwire.PRESS_HOLD_S
        assert core.game_idle() is False
        assert core.tick_calc() is False and stopped == []  # game active
        core.state.set_tailer(idle=True)
        assert core.game_idle() is True and core.state.snapshot()["game_idle"] is True
        assert core.tick_calc() is True and len(stopped) == 1
        assert core.tick_calc() is False and len(stopped) == 1
        # without the log opt-in the flag is never idle (as the snapshot)
        core.state.set_tailer(consented=False)
        assert core.game_idle() is False and core.state.snapshot()["game_idle"] is False
        # the next press while the game is idle still gets a calc; it stops
        # again only after the press let go of it
        core.state.set_tailer(consented=True)
        assert callable(core.tc_provider())
        assert core.tick_calc() is False and len(stopped) == 1
        t[0] += calcwire.PRESS_HOLD_S
        assert core.tick_calc() is True and len(stopped) == 2
    finally:
        core.close()


def test_core_reads_the_opt_in(tmp_path):
    from server.al.core import Core
    log = tmp_path / "Client.txt"
    log.write_text("", encoding="utf-8")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    assert core.tc_calc_enabled() is False
    assert core.tc_provider() is None
    (tmp_path / "rt" / "local.json").write_text('{"tc_calc": true}', encoding="utf-8")
    assert core.tc_calc_enabled() is True
    core.close()


def test_p4_4_config_is_read_only_when_its_mtime_or_size_changes(tmp_path, monkeypatch):
    """AREA-AUDIT P4-4: the 0.5 s loop tick asks tc_calc_enabled (tick_sources
    and the provider's reap); the config file is stat-ed each time but read
    and parsed only when its mtime or size changed."""
    import os
    from server.al.core import Core
    log = tmp_path / "Client.txt"
    log.write_text("", encoding="utf-8")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    cfg = tmp_path / "rt" / "local.json"
    old = int((time.time() - 600) * 1e9)

    def write(text, mtime_ns):
        # AREA-AUDIT P5-4: a file written more than CONFIG_COARSE_S before the
        # read is trusted by its stat alone (a fresher one is re-hashed)
        cfg.write_text(text, encoding="utf-8")
        os.utime(cfg, ns=(mtime_ns, mtime_ns))

    write('{"tc_calc": true}', old)
    reads = []
    real = Core._read_config_bytes

    def counting(self):
        reads.append(1)
        return real(self)

    monkeypatch.setattr(Core, "_read_config_bytes", counting)
    try:
        for _ in range(20):
            assert core.tc_calc_enabled() is True
            core.tick_sources()
        assert len(reads) == 1
        write('{"tc_calc": false}', old)  # size changes
        assert core.tc_calc_enabled() is False
        assert len(reads) == 2
        write('{"tc_calc": 00000}', old + 10**9)  # same size, new mtime
        assert core.tc_calc_enabled() is False
        assert len(reads) == 3
        cfg.unlink()  # a missing file reads as off
        assert core._config() == {}
        cfg.write_text('{"tc_calc": true}', encoding="utf-8")
        assert core.tc_calc_enabled() is True
        # the cached dict is never handed out for mutation
        core._config()["tc_calc"] = False
        assert core.tc_calc_enabled() is True
    finally:
        monkeypatch.undo()
        core.close()


def test_end_to_end_over_the_stdio_bridge(tmp_path):
    """Provider -> make_calc -> Bridge (fake process) -> delta engine."""
    env = dict(os.environ)
    b = bridge.Bridge([sys.executable, "-I", str(FAKE)], cwd=str(tmp_path), env=env,
                      timeout=10.0)
    try:
        p = calcwire.Provider(lambda: True, available=lambda: True, get_bridge=lambda: b)
        build = model.parse(EVAL_BUILD_XML)
        r = tc_evaluate.evaluate(RARE_GLOVES, build, None, calc=p())
        assert r["calc"] == {"source": delta.SOURCE_POB, "notice": None}
        # fake PoB: Life 1000 + 10 per equipped item, FullDPS fixed
        c = r["comparisons"][0]
        assert c["dps"]["pct"] == 0.0 and c["ehp"]["new"] == 1010
    finally:
        b.close()


def test_bridge_failure_falls_back_with_notice():
    def dead():
        raise bridge.BridgeUnavailable("calc component absent")
    p = calcwire.Provider(lambda: True, available=lambda: True, get_bridge=dead)
    r = tc_evaluate.evaluate(RARE_GLOVES, model.parse(EVAL_BUILD_XML), None, calc=p())
    assert r["ok"] and r["calc"] == {"source": "weights", "notice": "failed"}
