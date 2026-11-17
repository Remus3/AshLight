"""AUDIT-BUILDFILE: no code path writes under the game's BuildPlanner folder
(adjudicator ruling 2026-11-17 on TC-BUILDFILE: a `.build` file is offered as
a download the player saves; AshLight never writes into the game's user
folders - CLAUDE.md ToS floor, "never modify any game file").

Static guard: no AshLight source names the BuildPlanner folder or the game's
"My Games" user folder at all, so nothing can build a path there. When
TC-BUILDFILE lands it ships a download only; if a future change must name
the folder (e.g. to tell the player where to save), it goes in REFUSE_ONLY
with a test that the code refuses that path.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("server", "web", "app", "tools", "scripts")
SKIP = {"node_modules", "__pycache__", "out", "dist", "test"}
TEXT = {".py", ".js", ".html", ".ps1", ".cmd", ".vbs", ".lua", ".json"}
PATTERN = re.compile(r"build\s*planner|my\s*games", re.I)
REFUSE_ONLY = set()  # repo-relative files allowed to name it (refusal code only)


def _sources():
    for top in SCANNED:
        base = ROOT / top
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if (p.is_file() and p.suffix.lower() in TEXT
                    and not SKIP & set(p.relative_to(ROOT).parts)):
                yield p


def test_no_source_names_the_buildplanner_or_my_games_folder():
    bad = []
    for p in _sources():
        rel = p.relative_to(ROOT).as_posix()
        if rel in REFUSE_ONLY:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace")
                                 .splitlines(), 1):
            if PATTERN.search(line):
                bad.append(f"{rel}:{i}")
    assert bad == [], bad


def test_the_guard_sees_a_planted_reference(tmp_path):
    assert PATTERN.search('target = docs / "My Games" / "Path of Exile 2" / "BuildPlanner"')
    assert PATTERN.search("path.join(home, 'BuildPlanner')")
    assert not PATTERN.search("build plan for a planner")
