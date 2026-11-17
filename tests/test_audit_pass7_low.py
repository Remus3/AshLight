"""AREA-AUDIT pass 7 lows (ROADMAP AUDIT-P7-LOW), one regression test each.

P7-4: core._outputs_ready read state.build_info outside the state lock and
wrote it back, so a build loaded in that window was overwritten by the old
build's summary. The bump now runs inside SessionState under its lock.
P7-5: the health card's calc-off hint showed while the calc was on and its
first background answer was pending (calc_on means "table ready"); the
summary now says calc_pending and the hint hides.
P7-6: campaign.FlaskCache re-reads on change, but the core called get()
once at start; tick_sources now polls it (one stat per tick).
P7-7: build_facts read any "movement speed" text as speed, so boots with
only "reduced Movement Speed" counted as fast; only a positive increase
counts now.
P7-8: jsonfile.read_json had no default size cap; it now has one
(DEFAULT_MAX_BYTES) and callers that need more pass max_bytes."""

import json
import threading
import types

from server.al import campaign, jsonfile
from server.al.core import Core
from server.al.state import SessionState
from server.al.theorycraft import health
from tests.test_util_campaign import SNAP, make_build


def _core(tmp_path):
    cfg = tmp_path / "local.json"
    cfg.write_text("{}", encoding="ascii", newline="\n")
    return Core(runtime=tmp_path, tail=False, config_path=cfg)


# ---- P7-4 ---------------------------------------------------------------

class _RacingState(SessionState):
    """The first read of build_info starts a build load in another thread
    (the window P7-4 names) and gives it a moment to land."""

    armed = False
    loader = None

    @property
    def build_info(self):
        value = self._bi  # the reader holds this one
        if self.armed:
            self.armed = False
            self.loader = threading.Thread(
                target=SessionState.set_build_info, args=(self, {"rev": 2, "class_name": "New"}))
            self.loader.start()
            self.loader.join(0.3)
        return value

    @build_info.setter
    def build_info(self, value):
        self._bi = value


def test_outputs_ready_never_overwrites_a_build_loaded_meanwhile():
    st = _RacingState()
    st.set_build_info({"rev": 1, "class_name": "Old"})
    st.armed = True
    Core._outputs_ready(types.SimpleNamespace(state=st))
    st.loader.join(5)
    assert st._bi["class_name"] == "New"
    assert st._bi["rev"] == 2


def test_bump_calc_rev_keeps_the_summary_and_counts_up():
    st = SessionState()
    assert st.bump_calc_rev() is False  # no build: nothing to bump
    st.set_build_info({"rev": 3, "class_name": "Ranger"})
    v = st.version
    assert st.bump_calc_rev() is True
    assert st.bump_calc_rev() is True
    assert st.build_info == {"rev": 3, "class_name": "Ranger", "calc_rev": 2}
    assert st.version == v + 2


# ---- P7-5 ---------------------------------------------------------------

def test_calc_on_but_pending_is_not_reported_as_off():
    b = make_build()
    off = health.health(b, None)
    assert off["calc_on"] is False and off["calc_pending"] is False
    pending = health.health(b, None, calc_active=True)
    assert pending["calc_on"] is False and pending["calc_pending"] is True
    ready = health.health(b, {"FireResist": 75}, calc_active=True)
    assert ready["calc_on"] is True and ready["calc_pending"] is False
    assert health.health(None)["calc_pending"] is False


def test_store_snapshot_passes_the_calc_switch(tmp_path):
    core = _core(tmp_path)
    try:
        core.builds.calc_active = lambda: True
        core.builds.calc_outputs = lambda b: None
        from server.al.theorycraft import codec
        from tests.test_eval_text import EVAL_BUILD_XML
        core.builds.load_code(codec.encode(EVAL_BUILD_XML))
        assert core.builds.snapshot()["health"]["calc_pending"] is True
        core.builds.calc_active = lambda: False
        assert core.builds.snapshot()["health"]["calc_pending"] is False
    finally:
        core.close()


# ---- P7-6 ---------------------------------------------------------------

def test_flask_table_written_after_start_reaches_the_state(tmp_path):
    core = _core(tmp_path)
    try:
        assert core.state.flask_table == {}
        p = core.flask_table.path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(SNAP), encoding="utf-8")
        core.tick_sources()
        assert core.state.flask_table["life"][0] == (1, "Small Life Flask")
    finally:
        core.close()


# ---- P7-7 ---------------------------------------------------------------

def test_reduced_movement_speed_boots_are_not_fast():
    slow = campaign.build_facts(make_build(boots_text="Plain Boots\n10% reduced Movement Speed"))
    assert slow["boots"] == {"speed": False}
    neg = campaign.build_facts(make_build(boots_text="Plain Boots\n-5% increased Movement Speed"))
    assert neg["boots"] == {"speed": False}
    zero = campaign.build_facts(make_build(boots_text="Plain Boots\n0% increased Movement Speed"))
    assert zero["boots"] == {"speed": False}
    both = campaign.build_facts(make_build(
        boots_text="Plain Boots\n10% reduced Movement Speed\n25% increased Movement Speed"))
    assert both["boots"] == {"speed": True}


# ---- P7-8 ---------------------------------------------------------------

def test_read_json_has_a_default_size_cap(tmp_path, monkeypatch):
    assert jsonfile.DEFAULT_MAX_BYTES == 32 * 1024 * 1024
    p = tmp_path / "big.json"
    p.write_text(json.dumps({"k": "x" * 100}), encoding="ascii")
    monkeypatch.setattr(jsonfile, "DEFAULT_MAX_BYTES", 50)
    assert jsonfile.read_json(p, default="d") == "d"
    # a caller that needs more passes it explicitly
    assert jsonfile.read_json(p, max_bytes=1000)["k"] == "x" * 100
