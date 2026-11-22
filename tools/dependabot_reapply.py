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
bump goes to apply_actions (PUB-DEPBOT-ACTIONS), an npm bump to the apply_npm
seam (PUB-DEPBOT-NPM). A seam that returns None is empty: the pull request
stays open and one line `needs <package id>` is reported. Any other pull
request stays open with one `needs review` line.

apply_npm (PUB-DEPBOT-NPM): a lockfile-only bump is re-applied through the
pin procedure (F-037, decision 0068): a release under 3 days old (npm view
<pkg> time) leaves the pull request open with one line; else the pull
request's lockfile is read from its head commit, regenerated with
`npm install --prefix app --package-lock-only --ignore-scripts` under
app/.npmrc, checked (the package at the new version, electron unchanged),
`npm audit signatures` must pass, then the same gate / commit / push / close
path. A pull request that bumps electron itself yields no commit: it is
closed with one line naming the Electron bump procedure (decision 0070) once
that procedure's files exist, and left open and reported before then.

apply_actions: re-read the new tag's commit with
`gh api repos/<owner>/<name>/commits/v<tag> --jq .sha`, rewrite the `uses:`
SHA and its `# v<tag>` comment in the workflow files the pull request
touches, run the gates of ops/loop/gates.txt (a red gate restores the files,
commits nothing, leaves the pull request open and reports one line), make
one commit as the operator through the kit git lock (no trailer; the subject
names the dependency and both versions), push main through the git lock (the
guarded pre-push hook applies) and close the pull request with
'Applied locally as <sha>.'. The gate runner is injected like git and gh.

The repository is read from the checkout's own origin remote, never from a
tracked constant. With no origin remote every sub-command is a no-op that
exits 0. Runs in the MAIN checkout like the loop's push worker, never in a lane
worktree (lanes get no gh; tests/test_p163_lane_tools.py). git, gh, npm and
the clock are injected (tests use recording fakes; no network in tests).

Exit codes: 0 done (bumps left open included), 1 a git or gh call failed or
the pull request is not an open Dependabot one, 2 usage.
"""

import argparse
import json
import os
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


GITLOCK_REL = "ops/fleet_kit/fleet_gitlock.py"
OWNER_DEFAULT = "al-dependabot.main"


def owner_id():
    """The git-lock owner: FLEET_CLAIM_OWNER when set (a session passes its
    own id), else a fixed id like the loop's."""
    return os.environ.get("FLEET_CLAIM_OWNER") or OWNER_DEFAULT


def git_argv(args, root):
    """argv of one git call; a commit or push runs through the kit git lock
    (FLEET item 16a), so the guarded hooks of the checkout apply to it."""
    args = list(args)
    if args and args[0] in ("commit", "push"):
        return [sys.executable, str(Path(root) / GITLOCK_REL), "run", "--owner",
                owner_id(), "--", "git"] + args
    return ["git"] + args


def default_git(root):
    return lambda args: _run(git_argv(args, root), root)


def default_gates(root):
    """[(cmd, ok, detail)]: every command of ops/loop/gates.txt run once, in
    order, the whole suite through the kit suite gate (loop_preflight's
    runner, imported only when a bump is applied)."""
    sys.path.insert(0, str(ROOT / "tools"))
    import loop_preflight
    return loop_preflight.run_gates(root)


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


# "Bump <owner>/<name>[/<path>] from <old> to <new>[ in <dir>]", optionally
# behind a conventional prefix ("build(deps): bump ...").
_BUMP = re.compile(
    r"(?:^|:\s*)[Bb]ump ([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?) "
    r"from v?([0-9][0-9A-Za-z.+-]*) to v?([0-9][0-9A-Za-z.+-]*)(?: in \S+)?(?: in the \S+ group)?\s*$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
WORKFLOWS = ".github/workflows/"


def parse_bump(title):
    """(dependency, old, new) of a Dependabot bump title, else None. Versions
    lose a leading 'v'; the pin comment always writes 'v<version>'."""
    m = _BUMP.search((title or "").strip())
    if not m:
        return None
    dep = m.group(1).rstrip("/")
    if ".." in dep:
        return None
    return dep, m.group(2), m.group(3)


def rewrite_uses(text, dep, sha, new):
    """(text, count): every `uses: <dep>@<40 hex>[ # v<tag>]` line re-pinned
    to `<dep>@<sha> # v<new>`, the line's indent and '- ' kept."""
    rx = re.compile(r"^(\s*(?:-\s+)?uses:\s+)" + re.escape(dep)
                    + r"@[0-9a-f]{40}(?:[ \t]+#[^\n]*)?[ \t]*$", re.M)
    return rx.subn(lambda m: "%s%s@%s # v%s" % (m.group(1), dep, sha, new), text)


def apply_actions(ctx, pr):
    """Re-apply one github-actions bump as one operator commit on main, push
    it through the guarded hook and close the pull request with
    'Applied locally as <sha>.'. Returns the one result line. A red gate, a
    refused commit or push, or anything it cannot do safely leaves the pull
    request open (ctx.left_open); a failed git or gh call sets ctx.seam_rc 1."""
    n = pr["number"]

    def leave(why, rc=0):
        ctx.left_open.append(n)
        ctx.seam_rc = max(getattr(ctx, "seam_rc", 0), rc)
        return "left open, " + why

    bump = parse_bump(pr.get("title"))
    if bump is None:
        return leave("needs review (title names no bump)")
    dep, old, new = bump
    paths = sorted({p for p in pr_paths(pr)
                    if p.startswith(WORKFLOWS) and p != GUARD_PATH
                    and "/../" not in "/" + p + "/"})
    if not paths:
        return leave("needs review (no workflow file)")
    rc, out = ctx.git(["rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0 or out.strip() != "main":
        return leave("checkout is not on main", 1 if rc else 0)
    rc, out = ctx.git(["status", "--porcelain", "--"] + paths)
    if rc != 0:
        return leave("git status failed (rc %d)" % rc, 1)
    if out.strip():
        return leave("local edits in the workflow files")
    owner_name = "/".join(dep.split("/")[:2])
    rc, out = ctx.gh(["api", "repos/%s/commits/v%s" % (owner_name, new),
                      "--jq", ".sha"])
    sha = (out or "").strip()
    if rc != 0 or not _SHA.match(sha):
        return leave("gh api gave no commit for %s v%s (rc %d)" % (dep, new, rc), 1)
    originals, changed = {}, 0
    for rel in paths:
        f = ctx.root / rel
        try:
            raw = f.read_bytes()
        except OSError:
            continue
        text, count = rewrite_uses(raw.decode("utf-8"), dep, sha, new)
        if count:
            originals[f] = raw
            f.write_bytes(text.encode("utf-8"))
            changed += count
    edited = sorted(rel for rel in paths if (ctx.root / rel) in originals)

    def restore():
        for f, raw in originals.items():
            f.write_bytes(raw)

    if not changed:
        return leave("no pinned uses line for %s" % dep)
    rc, out = ctx.git(["status", "--porcelain", "--"] + edited)
    if rc == 0 and not out.strip():
        restore()
        return leave("%s v%s is already pinned" % (dep, new))
    for cmd, ok, detail in ctx.gates(ctx.root):
        if not ok:
            restore()
            return leave("gate red: %s (%s)" % (cmd, detail))
    subject = "deps(actions): bump %s from v%s to v%s" % (dep, old, new)
    rc, _out = ctx.git(["commit", "-q", "-m", subject, "--"] + edited)
    if rc != 0:
        restore()
        return leave("commit refused (rc %d)" % rc, 1)
    rc, out = ctx.git(["rev-parse", "HEAD"])
    head = (out or "").strip()
    if rc != 0 or not _SHA.match(head):
        return leave("committed, HEAD unreadable (rc %d)" % rc, 1)
    rc, _out = ctx.git(["push", "origin", "main"])
    if rc != 0:
        return leave("committed %s, push refused (rc %d)" % (head, rc), 1)
    rc, _out = ctx.gh(["pr", "close", str(n), "--repo", ctx.repo, "--comment",
                       "Applied locally as %s." % head])
    if rc != 0:
        return leave("applied as %s and pushed, gh pr close failed (rc %d)"
                     % (head, rc), 1)
    return "applied locally as %s, pushed, closed" % head


# npm titles: "Bump <name>|@<scope>/<name> from <old> to <new>[ in /app]",
# optionally behind a conventional prefix. A group title names no package.
_NPM_BUMP = re.compile(
    r"(?:^|:\s*)[Bb]ump (@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?) "
    r"from v?([0-9][0-9A-Za-z.+-]*) to v?([0-9][0-9A-Za-z.+-]*)(?: in \S+)?(?: in the \S+ group)?\s*$")
# "Bump the <group> group across N directories with M updates": several bumps.
_MULTI_GROUP = re.compile(r"[Bb]ump the \S+ group (?:across|with|in)")
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?Z$")
NPM_AGE_S = 3 * 86400
NPM_LOCK = "app/package-lock.json"
NPM_PKG = "app/package.json"
NPM_PREFIX = ["--prefix", "app"]
NPM_REGEN = ["install", "--prefix", "app", "--package-lock-only", "--ignore-scripts"]
NPM_AUDIT = ["audit", "signatures", "--prefix", "app"]
ELECTRON = "electron"
# The Electron bump procedure: decision 0070's policy plus the ELECTRON-WATCH
# row templates (AUTO-09). It exists when both tracked files do.
ELECTRON_PROCEDURE = "the Electron bump procedure (decision 0070)"
ELECTRON_PROCEDURE_FILES = ("docs/decisions/0070-electron-upgrade-policy.md",
                            "ops/loop/watch_rows/electron.json")
ELECTRON_COMMENT = ("Electron moves only through the Electron bump procedure "
                    "(decision 0070); this pull request was a signal.")


def default_npm(root):
    """npm(args) -> (rc, stdout), run in the checkout root; npm.cmd on
    Windows is resolved by its full path."""
    import shutil
    exe = shutil.which("npm") or "npm"
    return lambda args: _run([exe] + list(args), root)


def parse_npm_bump(title):
    """(package, old, new) of a Dependabot npm bump title, else None."""
    m = _NPM_BUMP.search((title or "").strip())
    if not m or ".." in m.group(1):
        return None
    return m.group(1), m.group(2), m.group(3)


def iso_epoch(text):
    """Epoch seconds of an npm 'time' stamp (UTC, 'Z'), else None."""
    m = _ISO.match((text or "").strip())
    if not m:
        return None
    import calendar
    try:
        return calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0))
    except (OverflowError, ValueError):
        return None


def lock_version(text, name):
    """The version the lockfile resolves for a top-level node_modules/<name>,
    else None (also for a lockfile that is not JSON)."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    pkgs = data.get("packages") if isinstance(data, dict) else None
    entry = pkgs.get("node_modules/" + name) if isinstance(pkgs, dict) else None
    v = entry.get("version") if isinstance(entry, dict) else None
    return v if isinstance(v, str) else None


def electron_signal(ctx, pr, new, leave):
    """An electron bump yields no commit: closed with one line naming the
    Electron bump procedure once it exists, left open and reported before."""
    n = pr["number"]
    if not all((ctx.root / rel).is_file() for rel in ELECTRON_PROCEDURE_FILES):
        return leave("electron %s waits for %s" % (new, ELECTRON_PROCEDURE))
    rc, _out = ctx.gh(["pr", "close", str(n), "--repo", ctx.repo, "--comment",
                       ELECTRON_COMMENT])
    if rc != 0:
        return leave("electron signal, gh pr close failed (rc %d)" % rc, 1)
    return "closed, electron %s moves only through %s" % (new, ELECTRON_PROCEDURE)


def land(ctx, n, edited, subject, restore, leave):
    """The shared gate / commit / push / close path (GP-14): every gate of
    ops/loop/gates.txt, one operator commit of the named paths through the
    kit git lock, push main, close with 'Applied locally as <sha>.'."""
    for cmd, ok, detail in ctx.gates(ctx.root):
        if not ok:
            restore()
            return leave("gate red: %s (%s)" % (cmd, detail))
    rc, _out = ctx.git(["commit", "-q", "-m", subject, "--"] + edited)
    if rc != 0:
        restore()
        return leave("commit refused (rc %d)" % rc, 1)
    rc, out = ctx.git(["rev-parse", "HEAD"])
    head = (out or "").strip()
    if rc != 0 or not _SHA.match(head):
        return leave("committed, HEAD unreadable (rc %d)" % rc, 1)
    rc, _out = ctx.git(["push", "origin", "main"])
    if rc != 0:
        return leave("committed %s, push refused (rc %d)" % (head, rc), 1)
    rc, _out = ctx.gh(["pr", "close", str(n), "--repo", ctx.repo, "--comment",
                       "Applied locally as %s." % head])
    if rc != 0:
        return leave("applied as %s and pushed, gh pr close failed (rc %d)"
                     % (head, rc), 1)
    return "applied locally as %s, pushed, closed" % head


def apply_npm(ctx, pr):
    """Re-apply one npm lockfile bump through the pin procedure (F-037,
    decision 0068): the 3-day age rule first (`npm view <pkg> time --json`;
    a release under 3 days old leaves the pull request open with one line),
    then the pull request's lockfile is read from its head commit and
    regenerated with `npm install --prefix app --package-lock-only
    --ignore-scripts`, checked (the package at the new version, electron
    unchanged), `npm audit signatures` must pass, then the shared gate /
    commit / push / close path. An electron bump is only a signal for the
    Electron bump procedure (electron_signal). Returns the one result line."""
    n = pr["number"]

    def leave(why, rc=0):
        ctx.left_open.append(n)
        ctx.seam_rc = max(getattr(ctx, "seam_rc", 0), rc)
        return "left open, " + why

    bump = parse_npm_bump(pr.get("title"))
    if bump is None:
        if _MULTI_GROUP.search((pr.get("title") or "").strip()):
            return leave("needs review (group title names several bumps; "
                         "one bump is re-applied at a time)")
        return leave("needs review (title names no bump)")
    dep, old, new = bump
    if dep == ELECTRON:
        return electron_signal(ctx, pr, new, leave)
    paths = pr_paths(pr)
    if NPM_PKG in paths or NPM_LOCK not in paths:
        return leave("needs review (%s changes beyond the lockfile)" % dep)
    npm = getattr(ctx, "npm", None) or default_npm(ctx.root)
    rc, out = ctx.git(["rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0 or out.strip() != "main":
        return leave("checkout is not on main", 1 if rc else 0)
    rc, out = ctx.git(["status", "--porcelain", "--"] + list(NPM_PATHS))
    if rc != 0:
        return leave("git status failed (rc %d)" % rc, 1)
    if out.strip():
        return leave("local edits in the npm files")
    # the 3-day age rule, before anything is changed
    rc, out = npm(["view", dep, "time", "--json"] + NPM_PREFIX)
    try:
        times = json.loads(out or "") if rc == 0 else None
    except ValueError:
        times = None
    published = iso_epoch(times.get(new)) if isinstance(times, dict) else None
    if published is None:
        return leave("npm view gave no publish time for %s %s (rc %d)"
                     % (dep, new, rc), 1)
    age = ctx.clock() - published
    if age < NPM_AGE_S:
        return leave("%s %s is under 3 days old (published %s), waits"
                     % (dep, new, times.get(new)))
    sha = str(pr.get("headRefOid") or "")
    if not _SHA.match(sha):
        return leave("needs review (no head commit)")
    rc, _out = ctx.git(["fetch", "-q", "origin", sha])
    if rc != 0:
        return leave("git fetch of the head commit failed (rc %d)" % rc, 1)
    rc, pr_lock = ctx.git(["show", "%s:%s" % (sha, NPM_LOCK)])
    if rc != 0 or not pr_lock:
        return leave("head commit has no %s (rc %d)" % (NPM_LOCK, rc), 1)
    lock = ctx.root / NPM_LOCK
    try:
        original = lock.read_bytes()
    except OSError:
        return leave("no %s in the checkout" % NPM_LOCK, 1)
    pin = lock_version(original.decode("utf-8", "replace"), ELECTRON)

    def restore():
        lock.write_bytes(original)

    lock.write_bytes(pr_lock.encode("utf-8"))
    rc, _out = npm(list(NPM_REGEN))
    if rc != 0:
        restore()
        return leave("npm lockfile regeneration failed (rc %d)" % rc, 1)
    try:
        regen = lock.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        restore()
        return leave("regenerated lockfile unreadable", 1)
    got = lock_version(regen, dep)
    if got != new:
        restore()
        return leave("regenerated lockfile has %s %s, not %s" % (dep, got, new))
    if lock_version(regen, ELECTRON) != pin:
        restore()
        return leave("regenerated lockfile moves electron; needs %s"
                     % ELECTRON_PROCEDURE)
    rc, out = ctx.git(["status", "--porcelain", "--", NPM_LOCK])
    if rc == 0 and not out.strip():
        restore()
        return leave("%s %s is already locked" % (dep, new))
    rc, _out = npm(list(NPM_AUDIT))
    if rc != 0:
        restore()
        return leave("npm audit signatures failed (rc %d)" % rc, 1)
    subject = "deps(npm): bump %s from %s to %s" % (dep, old, new)
    return land(ctx, n, [NPM_LOCK], subject, restore, leave)


SEAMS = {
    "actions": (ACTIONS_PACKAGE, "apply_actions"),
    "npm": (NPM_PACKAGE, "apply_npm"),
}


class Reapply:
    """One run against one checkout. git(args), gh(args) and npm(args)
    return (rc, stdout); clock() returns epoch seconds; say(line) reports;
    gates(root) returns [(cmd, ok, detail)]."""

    def __init__(self, root=ROOT, git=None, gh=None, clock=time.time, say=print,
                 seams=None, gates=None, npm=None):
        self.root = Path(root)
        self.git = git or default_git(self.root)
        self.gh = gh or default_gh(self.root)
        self.npm = npm or default_npm(self.root)
        self.gates = gates or default_gates
        self.seam_rc = 0
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
            self.seam_rc = 0
            line = fn(self, pr) if fn else None
            if line is None:
                self.left_open.append(n)
                self.say("#%d: left open, needs %s" % (n, pkg))
                return 0
            self.say("#%d: %s" % (n, line))
            return self.seam_rc
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
