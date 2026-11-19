"""GP-06 (F-075): community files exist, the issue forms have the shape GitHub
needs, bug reports ask for the redacted Checks report and never game files,
and no file carries an address."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / ".github" / "ISSUE_TEMPLATE"
COC = ROOT / "CODE_OF_CONDUCT.md"
PR = ROOT / ".github" / "pull_request_template.md"
ALL = [COC, PR, TPL / "bug.yml", TPL / "feature.yml", TPL / "config.yml"]
ADDRESS = re.compile(r"[A-Za-z0-9._%+-]*@[A-Za-z0-9-]")


def _read(path):
    return path.read_text(encoding="ascii")


def _top_keys(text):
    return {m.group(1) for m in re.finditer(r"(?m)^([a-z_]+):", text)}


def test_issue_forms_have_name_and_body():
    for form in ("bug.yml", "feature.yml"):
        keys = _top_keys(_read(TPL / form))
        assert {"name", "body"} <= keys, form


def test_bug_form_has_required_checkbox():
    text = _read(TPL / "bug.yml")
    block = text.split("- type: checkboxes", 1)
    assert len(block) == 2, "bug.yml has no checkboxes item"
    item = block[1].split("\n  - type:", 1)[0]
    assert "I read the report before pasting it" in item
    assert re.search(r"(?m)^\s+required: true\s*$", item)


def test_bug_form_asks_for_report_not_game_files():
    text = _read(TPL / "bug.yml")
    assert ("never attach Client.txt, game files, memory dumps or "
            "screenshots of the game") in text
    for label in ("AshLight version", "Windows version", "What happened",
                  "Checks report", "Ledger shape list"):
        assert label in text, label


def test_feature_form_asks_about_the_floor():
    assert "What AshLight never does" in _read(TPL / "feature.yml")


def test_config_disables_blank_issues():
    lines = [ln.strip() for ln in _read(TPL / "config.yml").splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    assert "blank_issues_enabled: false" in lines


def test_pr_template_gates_floor_and_merge_rule():
    text = _read(PR)
    assert "python -m pytest -q" in text
    assert "npm test --prefix app" in text
    assert "Floor checklist" in text
    assert "Pull requests are proposals" in text


def test_conduct_route_is_private():
    text = _read(COC)
    assert "Security tab" in text and "privately" in text


def test_no_address_in_community_files():
    for path in ALL:
        assert path.is_file(), path.name
        assert not ADDRESS.search(_read(path)), path.name


def test_no_funding_file():
    assert not (ROOT / ".github" / "FUNDING.yml").exists()
    assert not (ROOT / "FUNDING.yml").exists()
