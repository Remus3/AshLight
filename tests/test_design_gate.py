"""DS-REVIEW-HOOK (adjudicator ruling, design 0003): a warn-only pre-commit
reminder plus a lane-prompt rule. A staged UI change without a staged
design-review record prints one line and never blocks the commit."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import design_gate  # noqa: E402
import loop_prompts  # noqa: E402


def test_ui_paths_are_detected():
    for p in ("web/app.js", "web/status.js", "app/overlay/overlay.css",
              "app/shared/format.js", "server/al/state.py"):
        assert design_gate.is_ui_path(p), p
    for p in ("server/al/http.py", "scripts/run.ps1", "app/main.js",
              "tests/test_x.py", "docs/design/0003-second-audit.md"):
        assert not design_gate.is_ui_path(p), p


def test_warns_on_ui_change_without_a_review_record():
    msg = design_gate.check(["web/app.js", "tests/test_x.py"])
    assert msg.startswith("[design-gate] ")
    assert "web/app.js" in msg
    assert "design-reviewer" in msg
    assert "\n" not in msg


def test_quiet_with_a_review_record_or_no_ui_change():
    assert design_gate.check(["web/app.js", "docs/design/reviews.log"]) == ""
    assert design_gate.check(["web/app.js", "docs/design/0003-second-audit.md"]) == ""
    assert design_gate.check(["server/al/http.py"]) == ""
    assert design_gate.check([]) == ""


def test_main_never_blocks(tmp_path):
    # Outside a git repo the staged list is empty: still rc 0.
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "design_gate.py")],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0


def test_pre_commit_chains_the_gate_before_the_leak_sweep():
    hook = (ROOT / ".githooks" / "pre-commit").read_text(encoding="ascii")
    assert "tools/design_gate.py" in hook
    assert hook.index("design_gate.py") < hook.index("leak_sweep.py")
    assert 'exec "$PY" "$ROOT/tools/leak_sweep.py" --staged' in hook


def test_lane_prompts_name_the_rule():
    g = loop_prompts.GATES.format(task="t")
    assert "design-reviewer" in g and "docs/design/reviews.log" in g
    v = loop_prompts.verify_prompt({"label": "x"}, 1)
    assert "docs/design/reviews.log" in v


def test_ledger_exists_with_its_format_line():
    log = (ROOT / "docs" / "design" / "reviews.log").read_text(encoding="ascii")
    assert log.splitlines()[0].startswith("# ")
    rows = [ln for ln in log.splitlines() if ln and not ln.startswith("#")]
    assert rows
    for ln in rows:
        parts = [p.strip() for p in ln.split("|")]
        assert len(parts) == 5, ln
        assert parts[1].startswith("scope=") and parts[2].startswith("verdict=")
        assert parts[4].startswith("audit=")
