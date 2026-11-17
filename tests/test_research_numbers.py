"""FOLLOWUP11: research notes keep unique 4-digit numbers and plain names.

The headless loop once merged a research note numbered "0028b" next to an
existing 0028 (renumbered to 0029 in cf7f63c). Lanes run the full suite as
their gate, so this test makes the loop refuse the next clash. Decisions
have the same guard in tests/test_audit_pass2.py.
"""

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs" / "research"
NAME = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")


def problems(folder):
    """(bad names, duplicate numbers) for the research notes in folder."""
    names = sorted(p.name for p in Path(folder).iterdir()
                   if p.is_file() and p.name != "README.md")
    bad = [n for n in names if not NAME.match(n)]
    nums = Counter(n[:4] for n in names if NAME.match(n))
    dup = sorted(n for n, c in nums.items() if c > 1)
    return bad, dup


def test_research_names_and_numbers():
    bad, dup = problems(RESEARCH)
    assert not bad, f"research file names must match NNNN-topic.md: {bad}"
    assert not dup, f"duplicate research numbers: {dup}"


def test_checker_catches_a_clash_and_a_bad_name(tmp_path):
    for name in ("README.md", "0001-a.md", "0028-next.md", "0028b-clash.md",
                 "0029-x.md", "0029-y.md", "0030-Upper.md", "0031-ok.txt"):
        (tmp_path / name).write_text("x\n", encoding="ascii")
    bad, dup = problems(tmp_path)
    assert bad == ["0028b-clash.md", "0030-Upper.md", "0031-ok.txt"]
    assert dup == ["0029"]
