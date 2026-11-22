"""TEST-CORE-TICKS (F-193, research 0047 R7): the core's tick list and its
one-name-per-line import.

The core keeps a list of (name, callable) ticks (Core.ticks, filled at the
end of Core.__init__ in the order of the old __main__ loop) and the entry
point's loop runs it through Core.tick_all with one try / except per tick.
A new tick is one add_tick call; __main__.py is not edited. A raising tick
is logged with its name and the ticks after it still run. The grouped
`from . import (...)` of core.py lists one name per line, sorted.

Each test points plug.__path__ at an empty folder under tmp_path, so only
the built-in ticks are in the list and no real plug module runs.
"""

import ast
import logging
from pathlib import Path

import pytest

from server.al import core as core_mod
from server.al import plug
from server.al.core import Core

ROOT = Path(__file__).resolve().parents[1]

# Today's order of the core loop's built-in ticks (the ten calls of the old
# __main__ loop, kept by RUN-SEAMS in core.TICK_ORDER).
ORDER = ["ensure_tailing", "tick_build", "tick_summary", "tick_calc", "tick_sources",
         "tick_guide", "tick_history", "tick_watch", "tick_diag", "tick_reload"]


@pytest.fixture
def no_plugs(tmp_path):
    """An empty plug folder in place of the real one."""
    folder = tmp_path / "plugs"
    folder.mkdir()
    saved = list(plug.__path__)
    plug.__path__[:] = [str(folder)]
    plug.reset()
    try:
        yield folder
    finally:
        plug.__path__[:] = saved
        plug.reset()


@pytest.fixture
def core(tmp_path, no_plugs):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    try:
        yield c
    finally:
        c.close()


def _stub_builtins(core, ran):
    """Replace each built-in tick with a recorder (looked up per pass)."""
    for name in ORDER:
        setattr(core, name, (lambda n: lambda: ran.append(n))(name))


def _main_func():
    tree = ast.parse((ROOT / "server" / "al" / "__main__.py").read_text(encoding="ascii"))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")


# -- tests ------------------------------------------------------------------

def test_tick_names_in_todays_order(core):
    assert list(core_mod.TICK_ORDER) == ORDER
    assert [name for name, _ in core.ticks] == ORDER
    # the consent gate lives in ensure_tailing, and it stays the first tick
    assert core.ticks[0][0] == "ensure_tailing"
    ran = []
    _stub_builtins(core, ran)
    core.tick_all(logging.getLogger("al.test.core_ticks.order"))
    assert ran == ORDER
    assert set(core.tick_ms) == set(ORDER)


def test_a_new_tick_needs_no_edit_to_main(core):
    main_text = (ROOT / "server" / "al" / "__main__.py").read_bytes()
    ran = []
    _stub_builtins(core, ran)
    core.add_tick("zzq_new_tick", lambda: ran.append("zzq_new_tick"))
    assert [name for name, _ in core.ticks] == ORDER + ["zzq_new_tick"]
    core.tick_all()
    core.tick_all()
    assert ran == (ORDER + ["zzq_new_tick"]) * 2
    assert "zzq_new_tick" in core.tick_ms
    # registering it touched no file; the entry point's loop is one tick_all
    # call and names no tick of its own
    assert (ROOT / "server" / "al" / "__main__.py").read_bytes() == main_text
    calls = [n.func.attr for n in ast.walk(_main_func())
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "core"]
    assert calls.count("tick_all") == 1
    assert not set(calls) & set(ORDER)
    # a duplicate or a non-callable is refused
    with pytest.raises(ValueError):
        core.add_tick("zzq_new_tick", lambda: None)
    with pytest.raises(ValueError):
        core.add_tick("zzq_other", fn="not callable")


def test_raising_tick_is_logged_by_name_and_later_ticks_run(core, caplog):
    ran = []
    _stub_builtins(core, ran)

    def boom():
        ran.append("tick_summary")
        raise RuntimeError("zzq boom")

    core.tick_summary = boom
    core.add_tick("zzq_raises", lambda: (ran.append("zzq_raises"), 1 / 0))
    core.add_tick("zzq_after", lambda: ran.append("zzq_after"))
    log = logging.getLogger("al.test.core_ticks.raise")
    with caplog.at_level(logging.ERROR, logger=log.name):
        core.tick_all(log)
    # every tick ran, in order, though two of them raised
    assert ran == ORDER + ["zzq_raises", "zzq_after"]
    failed = [r for r in caplog.records if r.name == log.name]
    assert [r.getMessage() for r in failed] == ["tick_summary failed", "zzq_raises failed"]
    assert all(r.exc_info for r in failed)  # the first failure keeps its traceback
    assert "zzq boom" in caplog.text
    assert set(core.tick_ms) >= set(ORDER) | {"zzq_raises", "zzq_after"}


def test_grouped_import_is_one_name_per_line_sorted():
    path = ROOT / "server" / "al" / "core.py"
    text = path.read_text(encoding="ascii")
    tree = ast.parse(text)
    grouped = [n for n in tree.body
               if isinstance(n, ast.ImportFrom) and n.level == 1 and n.module is None
               and n.end_lineno > n.lineno]
    assert len(grouped) == 1
    node = grouped[0]
    names = [a.name for a in node.names]
    assert names == sorted(names)
    lines = text.splitlines()[node.lineno - 1:node.end_lineno]
    assert lines[0] == "from . import ("
    assert lines[-1] == ")"
    assert lines[1:-1] == [f"    {name}," for name in names]
