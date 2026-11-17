"""TEST-COVER: the stdlib coverage tool (tools/cover.py) counts the right
lines. The tracer test saves and restores any active tracer, so a suite run
under tools/cover.py keeps measuring."""

import importlib.util
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cover  # noqa: E402

SAMPLE = '''"""Module docstring."""

import os


def used(x):
    """Doc."""
    if x:
        return 1
    return 2


def unused():
    return os.sep
'''


def test_ranges():
    assert cover.ranges([]) == ""
    assert cover.ranges([9, 3, 4, 5]) == "3-5, 9"
    assert cover.ranges([1, 3]) == "1, 3"


def test_executable_lines_skip_docstrings_and_blanks(tmp_path):
    p = tmp_path / "sample.py"
    p.write_text(SAMPLE, encoding="ascii")
    lines = cover.executable_lines(p)
    assert 1 not in lines and 7 not in lines  # docstrings
    assert {3, 8, 9, 10, 14} <= lines
    assert 2 not in lines and 4 not in lines  # blank


def test_tracer_records_only_wanted_files_in_threads_too(tmp_path):
    p = tmp_path / "sample.py"
    p.write_text(SAMPLE, encoding="ascii")
    tracer = cover.Tracer({"sample.py": str(p)})
    old, old_thread = sys.gettrace(), threading.gettrace()
    tracer.start()
    try:
        spec = importlib.util.spec_from_file_location("al_cover_sample", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        t = threading.Thread(target=mod.used, args=(1,))
        t.start()
        t.join()
    finally:
        sys.settrace(old)
        threading.settrace(old_thread)
    hits = tracer.hits["sample.py"]
    assert {3, 8, 9} <= hits  # import, the branch taken in the thread
    assert 10 not in hits and 14 not in hits
    rows = cover.summarize({"sample.py": str(p)}, tracer.hits)
    assert rows[0]["missed"] == [10, 14]
    text = cover.render(rows, 0, 1.0, "2026-11-17")
    assert "sample.py" in text and "missed 10, 14" in text
    text.encode("ascii")
