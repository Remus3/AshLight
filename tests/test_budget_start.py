"""RUN-PERF-PARSE-ONCE (F-178, F-108, research 0048 B6): the bytes the core
parses as JSON while it starts are at most 1.2 times the bytes of the JSON
files it opened.

Deterministic, no timing: a counting JSON parser (json.loads wrapped, which
json.load also goes through) sums the text handed to the parser while one
test core is built, and an audit hook collects the .json files opened in
that window; their sizes on disk are the base. The fixture's cached
world_areas and base_items snapshots are large on purpose, so a second
parse of either (the old check-then-load double read, or two tables each
parsing one file) breaks the bound at once.
"""

import json
import os
import sys
from pathlib import Path

from server.al import acts, hotreload
from server.al.core import Core
from server.al.plug import dataage
from server.al.theorycraft import basetypes

PARSE_RATIO_MAX = 1.2  # B6

_OPENS = []
_COUNTING = [False]


def _audit(event, args):
    if _COUNTING[0] and event == "open" and isinstance(args[0], (str, os.PathLike)):
        _OPENS.append(os.fspath(args[0]))


sys.addaudithook(_audit)


def _data_files(tmp):
    """local.json plus cached world_areas / base_items snapshots of a few
    hundred KB each (an mtime an hour back, as a settled cache)."""
    rt = tmp / "rt"
    gd = rt / "gamedata"
    gd.mkdir(parents=True)
    areas = {f"G{1 + i % 4}_{i}": {"name": f"Area {i}", "area_level": 1 + i % 60,
                                    "is_town": i % 17 == 0, "has_waypoint": i % 3 == 0,
                                    "connections": [f"G{1 + i % 4}_{i + 1}"]}
             for i in range(3000)}
    bases = {f"Metadata/Items/Synthetic/Base{i}": {
        "name": f"Synthetic Base {i}",
        "item_class": ("LifeFlask", "ManaFlask", "Ring")[i % 3],
        "drop_level": 1 + i % 80, "release_state": "released"} for i in range(4000)}
    cfg = tmp / "local.json"
    for path, doc in ((gd / acts.FILE_NAME, areas), (gd / basetypes.FILE_NAME, bases),
                      (cfg, {})):
        path.write_text(json.dumps(doc) + "\n", encoding="ascii")
    return rt, cfg


def test_bytes_parsed_at_start_at_most_1_2_times_disk(tmp_path, monkeypatch):
    """B6: one parse per data file at core start."""
    monkeypatch.setattr(hotreload, "REGISTRY", hotreload.Registry())
    rt, cfg = _data_files(tmp_path)
    parsed = []
    real_loads = json.loads

    def counting_loads(s, *args, **kwargs):
        parsed.append(len(s))
        return real_loads(s, *args, **kwargs)

    monkeypatch.setattr(json, "loads", counting_loads)
    del _OPENS[:]
    _COUNTING[0] = True
    try:
        core = Core(runtime=rt, config_path=cfg, tail=False)
    finally:
        _COUNTING[0] = False
        monkeypatch.setattr(json, "loads", real_loads)
    try:
        opened = {os.path.normcase(os.path.abspath(p)) for p in _OPENS
                  if p.lower().endswith(".json")}
        disk = sum(os.stat(p).st_size for p in opened if os.path.isfile(p))
        big = {os.path.normcase(os.path.abspath(str(rt / "gamedata" / n)))
               for n in (acts.FILE_NAME, basetypes.FILE_NAME)}
        assert big <= opened, "the fixture snapshots were not read at start"
        assert core.state.zone_table and core.state.flask_table
        # RUN-DATAAGE-SHARED-PARSE: the data age area list joins the one
        # world_areas parse at start and a Checks pass parses nothing more
        assert core.data_age.ids._share is core.zone_table._share
        assert len(core.data_age.ids.get()) == 3000
        before = len(parsed)
        monkeypatch.setattr(json, "loads", counting_loads)
        try:
            dataage.facts(core, 0.0)
        finally:
            monkeypatch.setattr(json, "loads", real_loads)
        assert len(parsed) == before, "the data age check parsed by itself"
        total = sum(parsed)
        assert total <= PARSE_RATIO_MAX * disk, (
            f"parsed {total} bytes for {disk} bytes on disk "
            f"({total / disk:.2f}x, budget {PARSE_RATIO_MAX}x)")
    finally:
        close = getattr(core, "close", None)
        if callable(close):
            close()
