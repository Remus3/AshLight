"""TEST-WAVE-GATE-POLICY (decision 0060, ruling Q-17): the wave gate rule is
written once in a decision, and the lane prompt and the /done ritual point
at it. Stdlib only."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import loop_prompts  # noqa: E402

DONE_MD = ROOT / ".claude" / "commands" / "done.md"


def _flat(text):
    return " ".join(text.split())


def _decision():
    found = sorted((ROOT / "docs" / "decisions").glob("*-wave-gate-policy.md"))
    assert len(found) == 1, found
    return found[0].read_text(encoding="ascii")


def test_lane_gates_name_test_select_and_still_forbid_the_whole_suite():
    g = _flat(loop_prompts.GATES.format(task="t"))
    assert "tools/test_select.py" in g
    assert "run-ungated" in g and "gated list" in g
    assert "Do NOT run the whole pytest suite" in g
    assert "fleet_suite_gate.py run" not in g
    assert "touched" in g and "authoritative" in g


def test_lane_prompts_carry_the_rule():
    p = loop_prompts.plan_prompt({"id": "012", "title": "x"})
    assert "tools/test_select.py" in p
    h = loop_prompts.handoff_prompt({"id": "h1", "text": "x"})
    assert "tools/test_select.py" in h


def test_done_local_gate_names_suite_gate_and_batch_rule():
    text = DONE_MD.read_text(encoding="ascii")
    assert "\r" not in text
    gate = _flat(text[text.index("### 1. Local gate"):text.index("### 2.")])
    assert "fleet_suite_gate.py run --owner" in gate
    assert "tools/test_select.py" in gate
    assert "once per merge batch" in gate
    assert "decision 0060" in gate


def test_decision_has_its_sections():
    text = _decision()
    assert "\r" not in text
    lines = text.splitlines()
    assert lines[0].startswith("# ") and "Wave gate policy" in lines[0]
    for head in ("## Decision", "## Alternatives", "## Why", "## Reverses if"):
        assert head in lines, head
    flat = _flat(text)
    assert "Q-17" in flat and "tools/test_select.py" in flat
    assert "once" in flat and "merge batch" in flat
