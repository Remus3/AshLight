"""REL-SUBJECT-CHECK (F-101, DEP-04): every commit subject carries a type.

The commit-msg hook runs this after the identity strip and the leak sweep,
so the changelog generator can group commits by type. Only the subject
line (the first line that is not blank and not a git comment) is read,
never the body or the trailers (FLEET item 17 owns those).

Accepted shapes:
  <type>: <text>
  <type>(<scope>): <text>      (a `!` before the colon marks a breaking change)
  git's own subjects: Merge branch / remote-tracking branch / branches /
  commit / tag ..., Revert "...", Reapply "..."

Usage: python tools/commit_subject.py <message file>
Exit 0 = typed (or empty: git refuses an empty message itself), 1 = refused
with one line naming the fix.
"""

import re
import sys

TYPES = ("feat", "fix", "perf", "refactor", "data", "docs", "test", "chore",
         "ops", "security", "deps", "merge", "release", "audit", "design",
         "verify", "revert", "done", "kit", "tools", "loop")

_TYPED_RX = re.compile(r"^([a-z]+)(?:\(([^()\s][^()]*)\))?!?: (\S.*)$")
# git writes these itself (merge, revert, revert of a revert)
_GIT_OWN = (
    (re.compile(r"^Merge (?:branch|branches|remote-tracking branch|commit|tag) \S.*$"),
     "merge"),
    (re.compile(r'^Revert ".+"$'), "revert"),
    (re.compile(r'^Reapply ".+"$'), "revert"),
)

REFUSAL = ("commit subject needs a type: write '<type>: <text>' or "
           "'<type>(<scope>): <text>' with <type> one of " + ", ".join(TYPES))


def parse(subject):
    """(type, scope, text) of a typed subject, else None; git's own merge /
    revert subjects map to ("merge" | "revert", None, subject)."""
    if not isinstance(subject, str):
        return None
    line = subject.strip("\r\n")
    m = _TYPED_RX.match(line)
    if m and m.group(1) in TYPES:
        scope = m.group(2).strip() if m.group(2) is not None else None
        return m.group(1), scope or None, m.group(3)
    for rx, kind in _GIT_OWN:
        if rx.match(line):
            return kind, None, line
    return None


def subject_of(message):
    """The subject line of a commit message: the first line that is not
    blank and not a git comment ('#'); "" when there is none."""
    for line in message.splitlines():
        if line.strip() and not line.startswith("#"):
            return line.rstrip()
    return ""


def check(message):
    """None when the message's subject is typed (or empty), else REFUSAL."""
    subject = subject_of(message)
    if not subject or parse(subject) is not None:
        return None
    return REFUSAL


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: commit_subject.py <message file>", file=sys.stderr)
        return 2
    try:
        with open(argv[0], "rb") as fh:
            message = fh.read().decode("utf-8", "replace")
    except OSError as exc:
        print(f"commit_subject: cannot read the message ({type(exc).__name__})",
              file=sys.stderr)
        return 2
    problem = check(message)
    if problem:
        print(problem, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
