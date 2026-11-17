"""AUDIT-TC-WIRE: the core's PoB calc provider (theorycraft.calcwire).

Driven with the TC-BRIDGE stdio test double (tests/fixtures/tc_bridge/
fake_bridge.py) and in-memory doubles; no LuaJIT, no PoB."""

import os
import sys
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
    core.tc_provider = type("P", (), {"reap": lambda self: reaped.append(1) or False,
                                      "close": lambda self: None})()
    core.tick_calc()
    assert reaped == [1]
    core.close()
    main = (Path(__file__).resolve().parents[1] / "server" / "al" / "__main__.py").read_text(
        encoding="ascii")
    assert "core.tick_calc()" in main


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
    cfg.write_text('{"tc_calc": true}', encoding="utf-8")
    reads = []
    real = Path.read_text

    def counting(self, *a, **k):
        if self == core.config_path:
            reads.append(1)
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", counting)
    try:
        for _ in range(20):
            assert core.tc_calc_enabled() is True
            core.tick_sources()
        assert len(reads) == 1
        cfg.write_text('{"tc_calc": false}', encoding="utf-8")  # size changes
        assert core.tc_calc_enabled() is False
        assert len(reads) == 2
        st = cfg.stat()
        cfg.write_text('{"tc_calc": 00000}', encoding="utf-8")  # same size
        os.utime(cfg, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))  # new mtime
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
