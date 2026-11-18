#!/usr/bin/env python3
"""AL push guard - ref shape, tag objects and AI trailers (decision 0046).

Runs in .githooks/pre-push after the shell ref rule and before the kit
identity gate (fleet_identity.py pre-push) and the leak sweep. It closes the
gaps the GP-02 review found that the kit gate does not cover (the kit is
vendored and never edited here; its gaps are reported to MAIN):

* A pushed ref must point at what its name promises: refs/heads/main at a
  commit; refs/tags/v<SemVer> at a commit or at an annotated tag that peels
  to a commit. A tag on a blob or a tree is refused.
* A release tag name is SemVer: v<major>.<minor>.<patch>[-<pre>] (plan 05
  D4); `v1x` or `vendor-notes` are refused.
* Every annotated tag object the push sends: its tagger must be the operator
  identity (local git config fleet.operatorIdent) and not an AI or bot; its
  message gets the kit's forbidden-line test plus the wider trailer test.
* Every commit and tag message the push sends: any `<Key>-by:` trailer (and
  Assisted / Generated / AI / Model / Tool keys) naming an AI model, AI tool
  or bot is refused, not only the kit's three keys and names.

Exit 0 = pass, 1 = refused (nothing was pushed). Output never names an
identity or prints a message; it names the class and a short object id.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "ops" / "fleet_kit"))
import fleet_identity as fi  # noqa: E402
import leak_sweep as ls  # noqa: E402

SEMVER_TAG = re.compile(r"^refs/tags/v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
                        r"(-[0-9A-Za-z]+(\.[0-9A-Za-z]+)*)?$")
MAIN = "refs/heads/main"
# AI models, AI tools and bots, beyond the kit's claude / anthropic / bot set.
AI_NAME = re.compile(
    r"claude|anthropic|copilot|chatgpt|openai|\bgpt[-\s]?[0-9o]|gemini|\bbard\b|"
    r"\bopus\b|\bsonnet\b|\bhaiku\b|\bcodex\b|\bllm\b|\bai\b|cursor|devin|"
    r"codeium|tabnine|windsurf|\bgrok\b|mistral|llama|deepseek|\bqwen\b|"
    r"\[bot\]|\bbot\b|dependabot|renovate|github-actions", re.I)
TRAILER = re.compile(r"^\s*([A-Za-z][A-Za-z0-9-]*)\s*:\s*(.*)$")
TRAILER_KEYS = {"assisted", "generated", "ai", "ai-assisted", "ai-generated", "model",
                "tool", "with"}
TAGGER = re.compile(r"^tagger (.*?) <([^>]*)>")


def ai_trailer(line):
    """True when a message line is an attribution trailer naming an AI or bot."""
    m = TRAILER.match(line)
    if not m:
        return False
    key = m.group(1).lower()
    if not (key.endswith("-by") or key in TRAILER_KEYS):
        return False
    value = m.group(2)
    return bool(fi.is_ai_or_bot(value) or AI_NAME.search(value))


def message_classes(text):
    """Forbidden-line classes of one commit or tag message (kit test + wider)."""
    found = set(fi.message_violations(text))
    if any(ai_trailer(ln) for ln in text.split("\n")):
        found.add("ai-trailer")
    return sorted(found)


def _refuse(msg):
    print(f"pre-push: refused - {msg}", file=sys.stderr)


def check_refs(rows, cwd):
    """Ref shape problems as text lines (empty = fine)."""
    problems = []
    for _lref, lsha, rref, _rsha in rows:
        if ls._ZERO_RX.match(lsha):
            continue  # a delete; the shell rule already refused it
        try:
            kind = ls._git_raw(["cat-file", "-t", lsha], cwd).decode("ascii").strip()
        except RuntimeError:
            problems.append(f"{rref}: object {lsha[:10]} is not readable")
            continue
        if rref == MAIN:
            if kind != "commit":
                problems.append(f"{rref} must point at a commit, not a {kind}")
        elif rref.startswith("refs/tags/"):
            if not SEMVER_TAG.match(rref):
                problems.append(f"{rref} is not a release tag v<major>.<minor>.<patch>"
                                "[-<pre>]")
            elif kind not in ("commit", "tag"):
                problems.append(f"{rref} points at a {kind}; a release tag names a commit")
            else:
                try:
                    peeled = ls._git_raw(["cat-file", "-t", lsha + "^{commit}"], cwd)
                    if peeled.decode("ascii").strip() != "commit":
                        raise RuntimeError("not a commit")
                except RuntimeError:
                    problems.append(f"{rref} does not peel to a commit")
        else:
            problems.append(f"{rref}: only {MAIN} and release tags are pushed")
    return problems


def check_objects(objs, idents):
    """Tag identity and message problems over the pushed objects."""
    problems = []
    for sha, kind, data, _hint in objs:
        if kind not in ("commit", "tag"):
            continue
        head, msg = ls.object_message(data)
        if kind == "tag":
            types = [ln[5:] for ln in head.splitlines() if ln.startswith("type ")]
            if not types or types[0] not in ("commit", "tag"):
                problems.append(f"tag {sha[:10]} names a {types[0] if types else 'nothing'}")
            m = None
            for ln in head.splitlines():
                m = TAGGER.match(ln) or m
            if m is None:
                problems.append(f"tag {sha[:10]} has no tagger")
            elif fi.is_ai_or_bot(m.group(1)) or fi.is_ai_or_bot(m.group(2)):
                problems.append(f"tag {sha[:10]} ai-or-bot-tagger")
            elif not fi.is_operator(m.group(1), m.group(2), idents):
                problems.append(f"tag {sha[:10]} non-operator-tagger")
        for cls in message_classes(msg):
            problems.append(f"{kind} {sha[:10]} {cls}")
    return problems


def run(stdin_text, remote=None, cwd=ROOT, idents=None):
    rows = ls._ref_lines([ln for ln in stdin_text.splitlines() if ln.strip()])
    if not rows:
        return 0
    idents = fi.operator_idents(str(cwd)) if idents is None else idents
    if not idents:
        _refuse("no operator identity (git config --local fleet.operatorIdent)")
        return 1
    problems = check_refs(rows, cwd)
    if not problems:
        try:
            objs = ls.pushed_objects([" ".join(r) for r in rows], cwd, remote)
        except (RuntimeError, ValueError, OSError) as exc:
            _refuse(f"could not list the pushed objects ({exc.__class__.__name__})")
            return 1
        problems = check_objects(objs, idents)
    for p in problems[:50]:
        _refuse(p)
    if problems:
        print(f"pre-push: {len(problems)} problem(s); no AI or bot attribution, operator "
              "tagger only, release tags on commits (decision 0046).", file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    remote = argv[0] if argv else None
    return run(sys.stdin.read(), remote)


if __name__ == "__main__":
    sys.exit(main())
