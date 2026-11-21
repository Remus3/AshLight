"""DS-REVIEW-HOOK: warn-only design-review reminder for pre-commit.

Adjudicator ruling (docs/design/0003-second-audit.md, DS-REVIEW-HOOK): a
staged change to a UI path (web/, app/overlay/, app/shared/, or the card and
event text package server/al/text/, where all event wording lives since
TEST-STATE-TEXT-PINS) without a staged review record (a docs/design/*.md
audit or a docs/design/reviews.log line) prints ONE line and exits 0. It
never blocks: the design-reviewer is an agent and cannot run inside a hook,
and a refusal would stall headless lanes. The binding rule lives in the lane
prompts (tools/loop_prompts.py GATES and verify_prompt). Stdlib only.
"""

import subprocess
import sys

UI_PREFIXES = ("web/", "app/overlay/", "app/shared/", "server/al/text/")
UI_FILES = ()
RECORD_PREFIX = "docs/design/"


def is_ui_path(path):
    p = path.replace("\\", "/")
    return p.startswith(UI_PREFIXES) or p in UI_FILES


def has_record(paths):
    for p in paths:
        p = p.replace("\\", "/")
        if p.startswith(RECORD_PREFIX) and (p.endswith(".md") or p.endswith("reviews.log")):
            return True
    return False


def check(paths):
    """The one-line warning for these staged paths, or "" when quiet."""
    ui = [p for p in paths if is_ui_path(p)]
    if not ui or has_record(paths):
        return ""
    shown = ", ".join(ui[:3]) + (f" (+{len(ui) - 3} more)" if len(ui) > 3 else "")
    return ("[design-gate] UI change without a design review record: " + shown
            + " - run the design-reviewer agent and add a docs/design/reviews.log line")


def staged_paths():
    try:
        r = subprocess.run(["git", "diff", "--cached", "--name-only"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def main():
    msg = check(staged_paths())
    if msg:
        print(msg, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
