"""DATA-TRADESTAT-COVERAGE (F-155): one Checks line counting the default
weight keys and their " (Local)" twins per trade stat id source, so the PoB
TradeSiteStats fallback (decision 0037 amendment) is retired only once
repoe-fork carries the twins itself.

Fixtures are synthetic: the ids are invented (no real id table is bundled,
decision 0009) and the PoB file is self-made in its layout. Counts run
over cached local files only; no trade endpoint call (decision 0017)."""

import hashlib
import json
import os
import types

from server.al import diag, tradestats, upgrade
from server.al.core import Core
from server.al.theorycraft import weights

NOW = 1_800_000_000.0
ARCHIVE = "a" * 64
KEYS = list(weights.DEFAULT_WEIGHTS)
REPOE_KEYS = KEYS[:11]
POB_KEYS = KEYS[11:]
TWINS = ["+# to maximum Energy Shield", "+# to Armour", "+# to Evasion Rating",
         "#% increased Armour", "#% increased Evasion Rating",
         "#% increased Energy Shield", "#% increased Attack Speed",
         "+# to Accuracy Rating"]


def _repoe(path, keys, twins=()):
    rows = [{"id": "explicit.stat_%d" % (1000 + i), "text": k.lstrip("+"),
             "type": "explicit"} for i, k in enumerate(keys)]
    rows += [{"id": "explicit.stat_%d" % (5000 + i),
              "text": k.lstrip("+") + tradestats.LOCAL_SUFFIX, "type": "explicit"}
             for i, k in enumerate(twins)]
    path.write_text(json.dumps([{"trade_stats": rows}]), encoding="utf-8")
    return path


def _lua_entry(tid, text):
    return ("\t\t\t{\n"
            f'\t\t\t\t["id"] = "{tid}",\n'
            f'\t\t\t\t["text"] = "{text}",\n'
            '\t\t\t\t["type"] = "explicit",\n'
            "\t\t\t},\n")


def _pob(tmp_path, keys, twins):
    body = "".join(_lua_entry("explicit.stat_%d" % (2000 + i), k.lstrip("+"))
                   for i, k in enumerate(keys))
    body += "".join(_lua_entry("explicit.stat_%d" % (3000 + i),
                               k.lstrip("+") + tradestats.LOCAL_SUFFIX)
                    for i, k in enumerate(twins))
    text = ("return {\n\t{\n\t\t[\"entries\"] = {\n" + body
            + "\t\t},\n\t\t[\"id\"] = \"explicit\",\n\t},\n}\n")
    root = tmp_path / "pob2" / "Top-1"
    lua = root / tradestats.POB_REL
    lua.parent.mkdir(parents=True)
    lua.write_text(text, encoding="utf-8", newline="\n")
    (root / tradestats.POB_MARKER).write_text(
        json.dumps({"archive_sha256": ARCHIVE}), encoding="ascii")
    pins = {"pob2": {"top_dir": "Top-1", "archive_sha256": ARCHIVE},
            "pob2_files": {tradestats.POB_REL: {
                "sha256": hashlib.sha256(lua.read_bytes()).hexdigest()}}}
    return lua, pins


def _core(cache, on=True):
    return types.SimpleNamespace(trade_ids=cache, web_data_enabled=lambda: on)


def _row(cache, on=True):
    f = dict(tradestats.diag_facts(_core(cache, on)), web_data=on)
    return tradestats.diag_rows(f, NOW)


def test_line_reads_keys_39_of_39_local_twins_0_of_8_repoe_and_8_of_8_merged(tmp_path):
    assert upgrade.LOCAL_SUFFIX is tradestats.LOCAL_SUFFIX == " (Local)"
    assert len(KEYS) == 39
    repoe = _repoe(tmp_path / tradestats.FILE_NAME, REPOE_KEYS)
    cache = tradestats.IndexCache(repoe, pob=_pob(tmp_path, POB_KEYS, TWINS))
    cache.get()  # computed at the index load
    assert cache.local == {"keys": 39, "mapped_primary": 11, "mapped_merged": 39,
                           "twins": 8, "twins_primary": 0, "twins_merged": 8}
    rows = _row(cache)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "trade_ids" and row["status"] == diag.NOTE
    assert row["label"] == "Trade stat ids"
    assert row["detail"] == ("39 of 39 weight keys have a trade id (11 from "
                             "repoe-fork). Local twins: 0 of 8 in repoe-fork, "
                             "8 of 8 with the PoB fallback.")
    assert "now carries" not in row["detail"]
    # the pure counter on its own
    primary = tradestats.load_index(repoe)
    merged, _ = tradestats.merge(primary, tradestats.load_pob_index(*_pob(
        tmp_path / "b", POB_KEYS, TWINS)))
    assert tradestats.local_coverage(primary, merged, KEYS) == cache.local
    assert tradestats.local_coverage(None, None, None) == {
        "keys": 0, "mapped_primary": 0, "mapped_merged": 0,
        "twins": 0, "twins_primary": 0, "twins_merged": 0}


def test_a_twin_in_repoe_fork_adds_the_upstream_note(tmp_path):
    repoe = _repoe(tmp_path / tradestats.FILE_NAME, REPOE_KEYS, twins=TWINS[:3])
    cache = tradestats.IndexCache(repoe, pob=_pob(tmp_path, POB_KEYS, TWINS))
    cache.get()
    assert cache.local["twins_primary"] == 3 and cache.local["twins"] == 8
    detail = _row(cache)[0]["detail"]
    assert "Local twins: 3 of 8 in repoe-fork, 8 of 8 with the PoB fallback." in detail
    assert detail.endswith("repoe-fork now carries 3 of the 8 local twins; the "
                           "PoB fallback stays until it carries all of them.")
    # all of them upstream: the fallback may retire
    full = _repoe(tmp_path / "full.json", KEYS, twins=TWINS)
    cache2 = tradestats.IndexCache(full)
    cache2.get()
    detail = _row(cache2)[0]["detail"]
    assert detail.startswith("39 of 39 weight keys have a trade id (39 from repoe-fork).")
    assert detail.endswith("repoe-fork carries every local twin; the PoB "
                           "fallback can retire.")
    # the counts follow a changed file at the next index load
    _repoe(full, REPOE_KEYS)
    st = os.stat(full)
    os.utime(full, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    cache2.get()
    assert cache2.local["mapped_primary"] == 11 and cache2.local["twins"] == 0
    assert "No source has a local twin id." in _row(cache2)[0]["detail"]


def test_no_line_while_web_data_is_off(tmp_path):
    repoe = _repoe(tmp_path / tradestats.FILE_NAME, REPOE_KEYS)
    cache = tradestats.IndexCache(repoe)
    assert tradestats.diag_facts(_core(cache, on=False)) == {}
    assert _row(cache, on=False) == []
    # a fact left over does not show while web data is off
    on = tradestats.diag_facts(_core(cache))
    assert tradestats.diag_rows(dict(on, web_data=False), NOW) == []
    assert tradestats.diag_rows({}, NOW) == []
    assert tradestats.diag_facts(object()) == {}
    # the real Checks view of a test core: off by default, no row
    core = Core(runtime=tmp_path / "rt", tail=False)
    try:
        ids = [r["id"] for r in diag.view(core.diag_facts(NOW), "1.0.0",
                                          now=NOW)["checks"]]
        assert "trade_ids" not in ids
        core.web_data_enabled = lambda: True
        view = diag.view(core.diag_facts(NOW), "1.0.0", now=NOW)
    finally:
        core.close()
    row = [r for r in view["checks"] if r["id"] == "trade_ids"]
    assert len(row) == 1
    assert row[0]["detail"].startswith("0 of 39 weight keys have a trade id")
