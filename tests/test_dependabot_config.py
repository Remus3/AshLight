"""Key lint for .github/dependabot.yml (GP-08). Text parse, stdlib only."""
import re
from pathlib import Path

CFG = Path(__file__).resolve().parent.parent / ".github" / "dependabot.yml"


def _text():
    return CFG.read_text(encoding="utf-8")


def _blocks():
    parts = re.split(r"(?m)^  - package-ecosystem: ", _text())
    return {p.split("\n", 1)[0].strip().strip('"'): p for p in parts[1:]}


def test_version_two():
    assert re.search(r"(?m)^version: 2$", _text())


def test_two_ecosystems():
    b = _blocks()
    assert set(b) == {"npm", "github-actions"}
    assert 'directory: "/app"' in b["npm"]
    assert 'directory: "/"' in b["github-actions"]


def test_weekly_monday_limit_two():
    for name, blk in _blocks().items():
        assert 'interval: "weekly"' in blk, name
        assert 'day: "monday"' in blk, name
        assert re.search(r"(?m)^    open-pull-requests-limit: 2$", blk), name


def test_cooldown_keys():
    b = _blocks()
    assert re.search(r"(?m)^    cooldown:\n      default-days: 3$", b["npm"])
    assert re.search(r"(?m)^      semver-major-days: 14$", b["npm"])
    assert re.search(r"(?m)^      default-days: 3$", b["github-actions"])
    assert "semver-major-days" not in b["github-actions"]


def test_one_group_per_ecosystem():
    b = _blocks()
    assert len(re.findall(r"(?m)^      [\w-]+:\n        patterns:", b["npm"])) == 1
    assert len(re.findall(r"(?m)^      [\w-]+:\n        patterns:", b["github-actions"])) == 1


def test_exclude_path_for_actions_only():
    b = _blocks()
    assert '- ".github/workflows/fleet-identity-guard.yml"' in b["github-actions"]
    assert "exclude-paths" not in b["npm"]
