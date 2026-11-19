"""PLAY-TD-01A: every Play state recipe builds on a core pinned to a temp
log, yields the snapshot fields its docstring names and opens no path
outside tmp_path; the long-string fixture holds every composed row at its
cap.

Each recipe runs a real core and HTTP server on a free test port in
8961-8979 (never 8960) with a synthetic Client.txt under tmp_path; the
live Client.txt, the game and the network are never touched (state g
talks to a loopback mock only).
"""

import os

import pytest

import play_states as ps
from server.al import ports

pytestmark = pytest.mark.server


def test_caps_are_the_plan_figures():
    # plan 03 section 3.4 and packages.json PLAY-TD-01A notes
    assert ps.CAPS == {"context_title": 38, "context_row": 52, "notice_row": 52,
                       "event_sentence": 38, "build_row": 36, "item_sentence": 36,
                       "kept_row": 42, "notice_word": 12, "notice_title": 20,
                       "notice_action": 12}
    assert ps.ITEM_SENTENCE_ROWS == 2
    assert ps.NAME_LEN == 40 and ps.LONG_TRADES == 5


def test_long_rows_sit_exactly_at_their_caps():
    assert set(ps.LONG_ROWS) == set(ps.CAPS)
    for key, text in ps.LONG_ROWS.items():
        rows = text if isinstance(text, tuple) else (text,)
        if key == "item_sentence":
            assert len(rows) == ps.ITEM_SENTENCE_ROWS
        for row in rows:
            assert len(row) == ps.CAPS[key], (key, row)
            assert row.isascii() and row == row.strip() and "  " not in row, (key, row)
    names = (ps.LONG_CHARACTER,) + ps.LONG_BUYERS + ps.LONG_ITEMS
    assert len(names) == 1 + 2 * ps.LONG_TRADES
    assert len(set(names)) == len(names)
    for name in names:
        assert len(name) == ps.NAME_LEN and name.isascii() and name == name.strip(), name


def test_text_at_is_exact_for_every_length():
    for n in range(0, 80):
        for stop in (True, False):
            t = ps.text_at(n, stop=stop)
            assert len(t) == n, (n, t)
            if n:
                assert t == t.strip() and "  " not in t
            if stop and n >= 2:
                assert t.endswith(".") and t[-2] != " "


def test_longest_guide_entry_is_the_largest():
    doc = {"acts": {"G1": {"default": "x" * 5, "zones": {
        "Short": {"objective": "a"},
        "Long": {"objective": "b" * 10, "optional": [{"kind": "gem", "text": "c" * 10}]},
        "Default": {}}},
        "G2": {"zones": {"Tied": {"objective": "d" * 20}}}}}
    assert ps.longest_guide_entry(doc) == ("G1", "Long", 20)
    key, zone, size = ps.longest_guide_entry()
    assert size > 0 and zone
    from server.al import acts
    assert acts.act_of(ps.guide_area_id(key))["key"] == key


def test_every_recipe_names_its_fields():
    assert ps.STATES == ("a", "a2", "b", "c", "c2", "d", "e", "f", "g", "c5", "map", "long")
    for name, recipe in ps.RECIPES.items():
        lines = ps.fields_of(recipe)
        assert len(lines) >= 4, name


def test_check_fields_reports_a_wrong_line():
    def fake(st):
        """Fake.

        Fields:
            zone == 'Here'
            len(trade_requests) == 2
            build
            maps.count >= 1
            trade_requests.0.who == 'A'
            missing.part
        """
    snap = {"zone": "There", "trade_requests": [{"who": "A"}], "build": None,
            "maps": {"count": 1}}
    bad = ps.check_fields(fake, snap)
    assert [b.split(":")[0] for b in bad] == ["zone == 'Here'", "len(trade_requests) == 2",
                                             "build", "missing.part"]


def test_outside_flags_writes_live_state_and_other_logs(tmp_path):
    root = str(ps.ROOT)
    up = os.path.dirname(root)
    ev = [("open", str(tmp_path / "rt" / "x.json"), "w", 0),
          ("open", os.path.join(root, "server", "al", "data", "zone_guide.json"), "r", 0),
          ("open", os.path.join(root, "server", "al", "__pycache__", "x.pyc"), "wb", 0),
          ("open", os.path.join(root, "ops", "runtime", "consent.json"), "r", 0),
          ("open", os.path.join(root, "web", "x.txt"), "w", 0),
          ("open", os.path.join(up, "Game", "logs", "Client.txt"), "rb", 0),
          ("open", os.path.join(root, "server", "y.json"), "r", os.O_CREAT),
          ("os.mkdir", os.path.join(up, "elsewhere"), None, 0),
          ("open", 7, "r", 0)]
    bad = sorted(os.path.basename(b[1]) for b in ps.outside(ev, tmp_path))
    assert bad == ["client.txt", "consent.json", "elsewhere", "x.txt", "y.json"]


def test_watch_opens_sees_threads_started_inside(tmp_path):
    import threading
    target = ps.ROOT / "ROADMAP.md"  # repo text outside the read-only roots
    with ps.watch_opens() as events:
        t = threading.Thread(target=lambda: target.read_bytes())
        t.start()
        t.join()
        (tmp_path / "ok.txt").write_text("x", encoding="ascii")
    bad = ps.outside(events, tmp_path)
    assert [os.path.basename(b[1]) for b in bad] == ["roadmap.md"]
    before = len(events)
    target.read_bytes()  # after the block: not recorded
    assert len(events) == before


def test_port_8960_is_refused(tmp_path):
    with pytest.raises(ps.RecipeError):
        ps.PlayStack(tmp_path / "s", port=ports.AL_PORT)
    assert ps.state_mod.EVAL_CARD_S == 20  # restored after the refusal


@pytest.mark.parametrize("name", ps.STATES)
def test_recipe_builds_pinned_and_yields_its_fields(name, tmp_path):
    root = tmp_path / name
    with ps.watch_opens() as events:
        with ps.open_state(name, root) as st:
            assert st.port != ports.AL_PORT
            assert ports.AL_PORT < st.port <= ports.PORT_BLOCK[1]
            assert st.core.discover is False
            assert st.core.log_path == st.log and st.log.parent == root
            snap = st.state()
            st.pinned()
            assert ps.check_fields(ps.RECIPES[name], snap) == [], (name, st.notes)
            if name != "a" and name != "e":
                assert snap["tailer"]["reading"] is True
            assert st.fetch.calls == [] or name == "g", st.fetch.calls
            if name == "g":
                assert all(u.startswith(ps.ninja.BASE + "/") for u in st.fetch.calls)
    assert ps.state_mod.EVAL_CARD_S == 20
    assert ps.outside(events, tmp_path) == []
    # the recipe did read and write its own files
    assert any(e[0] == "open" and str(root) in str(e[1]) for e in events)


def test_states_swap_under_one_port(tmp_path):
    with ps.open_state("a", tmp_path / "one") as st:
        port, url = st.port, st.url
        assert st.state()["tailer"]["consented"] is False
    with ps.open_state("a2", tmp_path / "two", port=port) as st:
        assert st.port == port and st.url == url
        assert st.state()["tailer"]["consented"] is True
