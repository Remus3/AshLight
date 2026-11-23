"""TEST-STATE-PUBLISH (research 0047 R5 (1)): SessionState.publish(key,
view) stores a view the core only publishes, and snapshot() carries it, so
a new core-published view needs no state.py edit. set_run_history,
set_price_watch and set_diag are wrappers of it.

No event, no file, no request: the views here are invented."""

import pytest

from server.al import state as state_mod
from server.al.state import SessionState


def _st():
    return SessionState(clock=lambda: 1000.0)


def test_a_new_key_reaches_the_snapshot_with_no_state_edit():
    st = _st()
    assert "probe_view" not in st.snapshot()
    v0 = st.version
    assert st.publish("probe_view", {"rows": [1, 2], "text": "Probe."}) is True
    snap = st.snapshot()
    assert snap["probe_view"] == {"rows": [1, 2], "text": "Probe."}
    assert snap["version"] == v0 + 1
    # the snapshot holds a copy: changing it leaves the state alone
    snap["probe_view"]["text"] = "changed"
    assert st.snapshot()["probe_view"]["text"] == "Probe."
    # a list view and an empty view (None)
    assert st.publish("probe_list", [3, 4]) is True
    assert st.snapshot()["probe_list"] == [3, 4]
    assert st.publish("probe_view", {}) is True
    assert st.snapshot()["probe_view"] is None


def test_an_unchanged_view_does_not_bump_the_version():
    st = _st()
    st.publish("probe_view", {"a": 1})
    v = st.version
    assert st.publish("probe_view", {"a": 1}) is False
    assert st.version == v
    assert st.publish("probe_view", {"a": 2}) is True
    assert st.version == v + 1


def test_the_three_old_setters_keep_their_flags_and_keys():
    st = _st()
    snap = st.snapshot()
    for key in state_mod.PUBLISHED_KEYS:
        assert key in snap and snap[key] is None
    v = st.version
    assert st.set_run_history(None) is False and st.version == v
    assert st.set_run_history({"runs": []}) is True
    assert st.set_run_history({"runs": []}) is False
    assert st.set_price_watch({"rows": [1]}) is True
    assert st.set_price_watch({"rows": [1]}) is False
    assert st.set_diag({"rows": []}) is True
    assert st.set_diag({"rows": []}) is False
    assert st.version == v + 3
    snap = st.snapshot()
    assert snap["run_history"] == {"runs": []}
    assert snap["price_watch"] == {"rows": [1]}
    assert snap["diag"] == {"rows": []}
    assert st.set_run_history(None) is True
    assert st.snapshot()["run_history"] is None


@pytest.mark.parametrize("key", ["maps", "character", "play", "version"])
def test_a_key_that_would_shadow_a_built_in_key_is_refused(key):
    st = _st()
    v = st.version
    before = st.snapshot()[key]
    with pytest.raises(ValueError):
        st.publish(key, {"a": 1})
    assert st.version == v
    assert st.snapshot()[key] == before


def test_bad_keys_and_views_are_refused():
    st = _st()
    for key in ("", None, 3):
        with pytest.raises(ValueError):
            st.publish(key, {"a": 1})
    with pytest.raises(ValueError):
        st.publish("probe_view", "text")


def test_built_in_key_list_matches_a_real_snapshot():
    snap = _st().snapshot()
    assert set(snap) == state_mod.BUILTIN_SNAPSHOT_KEYS | set(state_mod.PUBLISHED_KEYS)
    assert not state_mod.BUILTIN_SNAPSHOT_KEYS & set(state_mod.PUBLISHED_KEYS)
