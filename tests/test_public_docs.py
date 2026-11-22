"""PUB-README-PLAYERS (F-020) and GP-07: the public documents tell a player
and a stranger today's real steps.

- The README quick start names exactly one setup command, then the
  AshLight shortcut, and has Stop, Update, Uninstall and Troubleshooting
  sub-sections with the steps that exist today.
- The README explains how the repository is run (the development files a
  reader may ignore, the gates, the unattended loop reads) between
  "How it works" and "Disclaimer", with no repository address yet.
- SECURITY.md speaks in the present tense.
- CONTRIBUTING.md states the re-apply policy and what the hooks are.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SECURITY = ROOT / "SECURITY.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"


def _section(text, heading):
    start = text.index(heading + "\n")
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else len(text)]


def test_readme_quick_start_update_uninstall_shortcut():
    text = README.read_text(encoding="ascii")
    qs = _section(text, "## Quick start (Windows)")
    setup = re.findall(r"^powershell .*-File scripts\\setup\.ps1.*$", qs, re.M)
    assert len(setup) == 1, setup
    for word in ("Update", "Uninstall", "shortcut"):
        assert word in text, word
    subs = re.findall(r"^### (.+)$", qs, re.M)
    assert subs == ["Stop", "Update", "Uninstall", "Troubleshooting"], subs
    flat = " ".join(qs.split())
    # the shortcut is the start, written by setup; -NoShortcut skips it
    assert "start AshLight from its shortcut" in flat
    assert "-NoShortcut" in qs
    assert "Start Menu" in qs and "desktop" in qs
    # client / tray wording and the run.ps1 switch meanings
    assert "Quit AshLight" in flat
    assert "X keeps AshLight running in the tray" in flat
    assert re.search(r"-NoOverlay\s+# no client", qs)
    assert re.search(r"-NoBrowser\s+# no window at all", qs)
    # Update / Uninstall / Troubleshooting carry today's steps
    assert "Releases: none yet" in qs
    assert "git pull" in qs
    assert "python -m server.al.paths" in qs
    # DEP14-UNINSTALL-LINE: the uninstall step is the checkout script
    # (decision 0066), not the old by-hand list
    assert "There is no uninstall script yet" not in flat
    assert re.search(r"^powershell -ExecutionPolicy Bypass -File "
                     r"scripts\\uninstall\.ps1 -Checkout$", qs, re.M)
    for word in ("-DryRun", "-Purge", "PURGE", "Recycle Bin"):
        assert word in qs, word
    assert "Checks" in qs and "Copy report" in qs
    assert '"port"' in qs and "Windowed Fullscreen" in qs
    assert "http" not in qs


def test_readme_explains_how_the_repository_is_run():
    text = README.read_text(encoding="ascii")
    heads = re.findall(r"^## (.+)$", text, re.M)
    i = heads.index("How this repository is run")
    assert heads[i - 1] == "How it works" and heads[i + 1] == "Disclaimer"
    sec = _section(text, "## How this repository is run")
    for name in ("`CLAUDE.md`", "`ops/`", "`AL-NEXT-SESSION.txt`",
                 "`ROADMAP.md`", "`docs/`"):
        assert name in sec, name
    assert "AI-assisted" in sec and "operator-reviewed" in sec
    for gate in ("test suite", "identity check", "leak sweep"):
        assert gate in sec, gate
    assert "ignore them" in sec
    assert "not the app" in sec and "unattended" in sec
    assert "decision 0025" in sec and "decision 0044" in sec
    assert "Releases: none yet, install from source" in sec
    # no repository address yet (GP-10 adds it)
    assert "http" not in sec and "github.com" not in sec.lower()


def test_security_policy_is_present_tense():
    text = SECURITY.read_text(encoding="ascii")
    assert "Once this repository is public" not in text
    assert "Please report security issues privately" in text
    assert "Report a" in text and "vulnerability" in text


def test_contributing_states_the_reapply_policy():
    text = CONTRIBUTING.read_text(encoding="ascii")
    flat = " ".join(text.split())
    assert "A pull request is a proposal" in flat
    assert "Nothing is merged on GitHub" in flat
    assert "re-applies it locally" in flat
    assert "closed with a link" in flat
    assert "credited in the release notes" in flat
    assert "`.githooks/`" in flat
    assert "A clone does not install them" in flat
    assert "CI runs the same checks" in flat
    assert "`.claude/settings.json`" in flat
    assert "only to Claude Code users" in flat and "trust prompt" in flat
