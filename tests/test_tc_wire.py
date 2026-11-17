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
