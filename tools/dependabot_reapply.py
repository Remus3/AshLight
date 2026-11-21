#!/usr/bin/env python3
"""Dependabot re-apply tool: list, close and the run loop (GP-14, F-081).

Nothing is ever merged on GitHub (CLAUDE.md, Public-repo hygiene; FLEET item
17). An open Dependabot pull request is either re-applied locally as an
operator commit and then closed, or closed with one line, or left open with
one report line:

    python tools/dependabot_reapply.py list
    python tools/dependabot_reapply.py apply <n>
    python tools/dependabot_reapply.py close <n>
    python tools/dependabot_reapply.py run

* list  - the open pull requests of app/dependabot, one line each with the
          kind the dispatch gives it (guard, actions, npm, other).
* apply - dispatch one open Dependabot pull request.
* close - close one open Dependabot pull request that touches the vendored
          identity-guard copy, with the one-line comment GUARD_COMMENT.
* run   - list, then dispatch every open Dependabot pull request.

Dispatch: a pull request that touches .github/workflows/fleet-identity-guard.yml
(a byte copy of the kit's file) yields no commit; it is closed with
GUARD_COMMENT and listed as `upstream: #<n>` for the note to MAIN. An actions
bump goes to the apply_actions seam (PUB-DEPBOT-ACTIONS fills it), an npm bump
to the apply_npm seam (PUB-DEPBOT-NPM). A seam that returns None is empty: the
pull request stays open and one line `needs <package id>` is reported. Any
other pull request stays open with one `needs review` line.

The repository is read from the checkout's own origin remote, never from a
tracked constant. With no origin remote every sub-command is a no-op that
exits 0. Runs in the MAIN checkout like the loop's push worker, never in a lane
worktree (lanes get no gh; tests/test_p163_lane_tools.py). git, gh and the
clock are injected (tests use recording fakes; no network in tests).

Exit codes: 0 done (bumps left open included), 1 a git or gh call failed or
the pull request is not an open Dependabot one, 2 usage.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GUARD_PATH = ".github/workflows/fleet-identity-guard.yml"
GUARD_COMMENT = "This file is vendored; the change is reported upstream."
AUTHOR = "app/dependabot"
LIST_FIELDS = "number,title,headRefOid,files"
ACTIONS_PACKAGE = "PUB-DEPBOT-ACTIONS"
NPM_PACKAGE = "PUB-DEPBOT-NPM"
NPM_PATHS = ("app/package.json", "app/package-lock.json")

# github.com remotes: https://github.com/<owner>/<name>(.git), the scp-like
# ssh form (user git, host github.com, ':<owner>/<name>') or an ssh:// URL.
_REMOTE = re.compile(
    r"^(?:https?://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def _run(cmd, cwd):
    """Run a command; return (rc, stdout). A missing tool is rc 127."""
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except OSError as e:
        return 127, str(e)
    return p.returncode, p.stdout


def default_git(root):
    return lambda args: _run(["git"] + list(args), root)


def default_gh(root):
    return lambda args: _run(["gh"] + list(args), root)


def repo_from_url(url):
    """'<owner>/<name>' for a github.com remote URL, else None."""
    m = _REMOTE.match((url or "").strip())
    if not m:
        return None
    return m.group(1) + "/" + m.group(2)


def origin_repo(git):
    """The origin remote's '<owner>/<name>', or None when there is no
    github.com origin remote."""
    rc, out = git(["remote", "get-url", "origin"])
    if rc != 0:
        return None
    return repo_from_url(out)


def pr_paths(pr):
    out = []
    for f in pr.get("files") or []:
        p = f.get("path") if isinstance(f, dict) else f
        if isinstance(p, str):
            out.append(p.replace("\\", "/"))
    return out


def kind(pr):
    """guard | actions | npm | other, from the paths the pull request touches.
    The guard copy wins over every other path."""
    paths = pr_paths(pr)
    if GUARD_PATH in paths:
        return "guard"
    if paths and all(p.startswith(".github/workflows/") for p in paths):
        return "actions"
    if paths and all(p in NPM_PATHS for p in paths):
        return "npm"
    return "other"


def apply_actions(ctx, pr):
    """Seam for an actions bump (PUB-DEPBOT-ACTIONS fills it). Returns the
    one result line when it handled the pull request, None while empty."""
    return None


def apply_npm(ctx, pr):
    """Seam for an npm bump (PUB-DEPBOT-NPM fills it). Returns the one result
    line when it handled the pull request, None while empty."""
    return None


SEAMS = {
    "actions": (ACTIONS_PACKAGE, "apply_actions"),
    "npm": (NPM_PACKAGE, "apply_npm"),
}


class Reapply:
    """One run against one checkout. git(args) and gh(args) return
    (rc, stdout); clock() returns epoch seconds; say(line) reports."""

    def __init__(self, root=ROOT, git=None, gh=None, clock=time.time, say=print,
                 seams=None):
        self.root = Path(root)
        self.git = git or default_git(self.root)
        self.gh = gh or default_gh(self.root)
        self.clock = clock
        self.say = say
        self.seams = seams if seams is not None else {
            k: globals()[name] for k, (_pkg, name) in SEAMS.items()}
        self.repo = None
        self.upstream = []
        self.left_open = []

    def stamp(self):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock()))

    def open_repo(self):
        self.repo = origin_repo(self.git)
        if self.repo is None:
            self.say("dependabot_reapply: no origin remote, nothing to do")
        return self.repo

    def list_prs(self):
        """The open Dependabot pull requests, or None when gh failed."""
        rc, out = self.gh(["pr", "list", "--repo", self.repo, "--author", AUTHOR,
                           "--state", "open", "--json", LIST_FIELDS])
        if rc != 0:
            self.say("dependabot_reapply: gh pr list failed (rc %d)" % rc)
            return None
        try:
            data = json.loads(out or "[]")
        except ValueError:
            self.say("dependabot_reapply: gh pr list gave no JSON")
            return None
        if not isinstance(data, list):
            self.say("dependabot_reapply: gh pr list gave no list")
            return None
        return [p for p in data if isinstance(p, dict)
                and isinstance(p.get("number"), int)]

    def find(self, number):
        prs = self.list_prs()
        if prs is None:
            return None, 1
        for p in prs:
            if p["number"] == number:
                return p, 0
        self.say("#%d: not an open Dependabot pull request" % number)
        return None, 1

    def close_guard(self, pr):
        n = pr["number"]
        rc, _out = self.gh(["pr", "close", str(n), "--repo", self.repo,
                            "--comment", GUARD_COMMENT])
        if rc != 0:
            self.say("#%d: gh pr close failed (rc %d), left open" % (n, rc))
            self.left_open.append(n)
            return 1
        self.upstream.append(n)
        self.say("#%d: closed, vendored guard file (upstream: #%d)" % (n, n))
        return 0

    def dispatch(self, pr):
        n = pr["number"]
        k = kind(pr)
        if k == "guard":
            return self.close_guard(pr)
        if k in SEAMS:
            pkg = SEAMS[k][0]
            fn = self.seams.get(k)
            line = fn(self, pr) if fn else None
            if line is None:
                self.left_open.append(n)
                self.say("#%d: left open, needs %s" % (n, pkg))
                return 0
            self.say("#%d: %s" % (n, line))
            return 0
        self.left_open.append(n)
        self.say("#%d: left open, needs review (mixed or unknown paths)" % n)
        return 0

    # sub-commands ---------------------------------------------------------

    def cmd_list(self):
        if self.open_repo() is None:
            return 0
        prs = self.list_prs()
        if prs is None:
            return 1
        for p in prs:
            self.say("#%d %s: %s" % (p["number"], kind(p), p.get("title", "")))
        self.say("open: %d" % len(prs))
        return 0

    def cmd_close(self, number):
        if self.open_repo() is None:
            return 0
        pr, rc = self.find(number)
        if pr is None:
            return rc
        if kind(pr) != "guard":
            self.say("#%d: does not touch %s, not closed (apply re-applies it)"
                     % (number, GUARD_PATH))
            return 1
        return self.close_guard(pr)

    def cmd_apply(self, number):
        if self.open_repo() is None:
            return 0
        pr, rc = self.find(number)
        if pr is None:
            return rc
        return self.dispatch(pr)

    def cmd_run(self):
        if self.open_repo() is None:
            return 0
        prs = self.list_prs()
        if prs is None:
            return 1
        self.say("dependabot_reapply run %s: %d open" % (self.stamp(), len(prs)))
        rc = 0
        for p in sorted(prs, key=lambda x: x["number"]):
            rc = max(rc, self.dispatch(p))
        if self.upstream:
            self.say("upstream: " + " ".join("#%d" % n for n in self.upstream))
        self.say("left open: %d" % len(self.left_open))
        return rc


def main(argv=None, **deps):
    ap = argparse.ArgumentParser(
        prog="dependabot_reapply.py",
        description="Re-apply, close or report open Dependabot pull requests; "
                    "nothing is merged on GitHub.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("apply", "close"):
        sp = sub.add_parser(name)
        sp.add_argument("number", type=int)
    sub.add_parser("run")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    r = Reapply(**deps)
    if a.cmd == "list":
        return r.cmd_list()
    if a.cmd == "close":
        return r.cmd_close(a.number)
    if a.cmd == "apply":
        return r.cmd_apply(a.number)
    return r.cmd_run()


if __name__ == "__main__":
    sys.exit(main())
