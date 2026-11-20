"""Shared tools/al_loop.py test helpers (plan 156, TESTS-A-17 / -19).

test_al_loop, test_al_loop_merge, test_al_loop_lanes, test_al_loop_routes,
test_al_loop_gate_cache and test_usage_ledger import these from here instead of from test_al_loop.

TESTS-A-19: `isolate_git(monkeypatch)` hides the machine's git global and
system config (GIT_CONFIG_GLOBAL -> os.devnull, GIT_CONFIG_NOSYSTEM=1) and
supplies a fixed identity through the environment, so a host `merge.ff=only`,
commit signing or global hooksPath cannot change a tmp_path git world - in
the test's own git calls and in the al_loop code under test alike."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402

# TEST-LOOP-STUB-GIT: with AL_GIT_COUNT=1 every real git process this test
# process starts is counted (subprocess.Popen with argv[0] "git") and the
# total is printed once at exit as "git spawns: <n>".
GIT_SPAWNS = {"n": 0}


def _install_git_counter():
    import atexit
    orig = subprocess.Popen.__init__

    def counting(self, args, *a, **kw):
        first = args[0] if isinstance(args, (list, tuple)) and args else args
        if isinstance(first, str) and Path(first).stem.lower() == "git":
            GIT_SPAWNS["n"] += 1
        return orig(self, args, *a, **kw)

    subprocess.Popen.__init__ = counting
    atexit.register(lambda: print(f"\ngit spawns: {GIT_SPAWNS['n']}", flush=True))


if os.environ.get("AL_GIT_COUNT") == "1" and not getattr(subprocess, "_al_git_count", False):
    subprocess._al_git_count = True
    _install_git_counter()

GIT_TIMEOUT_S = 60  # plan 150: a git stuck on a lock / prompt fails, never hangs
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}

ROADMAP = """# AshLight roadmap

- [x] 001 Skeleton -- done 2026-10-04
- [ ] 012 Grind spot recommender
- [ ] 013 Season pass tracker
"""

HANDOFF = """AL NEXT SESSION
---------------
Next action: x

Carried forward (not acted on yet):
- OPERATOR (physical): press Ctrl+Alt+E and confirm the overlay toggles.
- OPERATOR: set profile.family in config.
- MAIN to record AL's port block in the registry.
- NOTE: OCR residual accepted.
- NOTE (new, operator 2026-10-06): one character, no alts.
- Fix the OCR cache key so a same-second rewrite is
  re-read.

Context: CLAUDE.md
"""


def isolate_git(monkeypatch):
    """TESTS-A-19: no host git config reaches any git the test spawns."""
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)


class FakeSpawn:
    def __init__(self, results=None):
        self.calls = []
        self.results = list(results or [])

    def __call__(self, root, code, prompt, **kw):
        self.calls.append(dict(kw, prompt=prompt, code=code))
        if self.results:
            r = self.results.pop(0)
            return r(kw) if callable(r) else r
        return {"rc": 0, "error": None, "result": "ok"}


def make_root(tmp_path, roadmap=ROADMAP, handoff=HANDOFF, local=None):
    root = tmp_path / "repo"
    # LOOP-ROWFILES-WORK: a row's optional brief is docs/plan/briefs/<ID>.md
    (root / "docs" / "plan" / "briefs").mkdir(parents=True)
    (root / "docs" / "research").mkdir(parents=True)
    (root / "ROADMAP.md").write_text(roadmap, newline="\n")
    (root / "docs" / "plan" / "briefs" / "012.md").write_text(
        "# Brief 012 - Grind spot recommender by AP/DP\n", newline="\n")
    (root / "AL-NEXT-SESSION.txt").write_text(handoff, newline="\n")
    if local is not None:
        (root / "config").mkdir()
        (root / "config" / "local.json").write_text(json.dumps(local))
    return root


# TEST-LOOP-STUB-GIT: the tick tests that do not test git opt in (stub_git)
# and then deps() defaults to two no-spawn stand-ins; a test that passes its
# own git= or tree_key= keeps it. Off for every other user of deps().
_STUB = {"on": False}
NOT_A_REPO = "fatal: not a git repository (al_loopkit stub)"


def stub_git(monkeypatch):
    """Opt this test into the no-spawn git defaults of deps()."""
    monkeypatch.setitem(_STUB, "on", True)


def stub_default_git(args, cwd, input=None, lock=None):
    """The default tick git runner without a process for a root that is not a
    repo (what real git answers there: rc 128, no output; `config <key>` is
    rc 1, the key unset, as with no host global config); a repo root goes to
    the real runner unchanged."""
    if not (Path(cwd) / ".git").exists():
        if args and args[0] == "config":
            return subprocess.CompletedProcess(["git", *args], 1, "", "")
        return subprocess.CompletedProcess(["git", *args], 128, "", NOT_A_REPO)
    return al_loop._git(args, cwd, input, lock)


def _ignore_rules(top):
    try:
        text = (top / ".gitignore").read_text(encoding="utf-8")
    except OSError:
        return []
    return [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith(("#", "!"))]


def _ignored(rel, rules):
    import fnmatch
    parts = rel.split("/")
    for rule in rules:
        pat = rule.strip("/")
        if "/" in pat:
            if rel == pat or rel.startswith(pat + "/") or fnmatch.fnmatch(rel, pat):
                return True
        elif any(fnmatch.fnmatch(p, pat) for p in parts[:-1]) or (
                not rule.endswith("/") and fnmatch.fnmatch(parts[-1], pat)):
            return True
    return False


def py_tree_key(cwd):
    """A no-spawn stand-in for al_loop.tree_key with the same equality: None
    unless cwd is a work tree root (holds .git), else one hash over every
    non-ignored file's path and bytes, so a clean and a dirty tree with the same
    content share a key and any content change makes a new one (the top-level
    .gitignore's plain and glob lines are honoured; the git_world trees ignore
    ops/ only). Not git's tree id, and never compared with one."""
    import hashlib
    top = Path(cwd)
    if not (top / ".git").exists():
        return None
    rules = _ignore_rules(top)
    h = hashlib.sha1()
    for dirpath, dirnames, filenames in os.walk(top):
        base = Path(dirpath).relative_to(top).as_posix()
        pre = "" if base == "." else base + "/"
        dirnames[:] = sorted(n for n in dirnames if not (pre == "" and n == ".git")
                             and not _ignored(pre + n + "/x", rules))
        for name in sorted(filenames):
            p = Path(dirpath) / name
            rel = p.relative_to(top).as_posix()
            if rel == ".git" or _ignored(rel, rules):
                continue
            h.update(rel.encode() + b"\0" + p.read_bytes() + b"\0")
    return "py" + h.hexdigest()


def deps(root, **over):
    seen = {"launch": [], "record": []}
    if _STUB["on"]:
        over.setdefault("git", stub_default_git)
        over.setdefault("tree_key", py_tree_key)
    base = dict(
        spawn=FakeSpawn(),
        lane_state=lambda: [{"index": i, "state": "FREE", "lane": None} for i in range(3)],
        pid_alive=lambda pid: True,
        main_tree=root,
        launch=lambda iid: seen["launch"].append(iid) or 4242,
        gates=lambda cwd: (True, "green"),
        leak_pre_push=lambda cwd, line: True,
        estimate=lambda kind, default=None: 2700.0,
        record=lambda kind, s, ok=True: seen["record"].append(kind),
        clock=lambda: 1_790_000_000.0,
        roster_path=None,  # plan 093: never the machine roster from FLEET_ROSTER
        should_yield=lambda: False,  # kit v25: never the live governor
        lane_cap=lambda: 3,
        drift=lambda root, now: None,  # TC-DRIFT: never the network in tests
        docs_watch=lambda root, now: None,  # decision 0044: never the network
    )
    base.update(over)
    d = al_loop.Deps(root, **base)
    d.seen = seen
    # plan 098: the detached review / push workers run inline in tests (same
    # process, same deps), so a tick's observable end state is unchanged
    if "launch_review" not in over:
        d.launch_review = lambda iid: al_loop.review_worker(iid, deps=d) or 4243
    if "launch_push" not in over:
        d.launch_push = lambda: al_loop.push_worker(deps=d) or 4244
    return d


def _inbox_root(tmp_path, roadmap="", local_extra=None):
    inbox, outbox = tmp_path / "in", tmp_path / "out"
    inbox.mkdir()
    outbox.mkdir()
    loop = {"inbox_dir": str(inbox), "outbox_dir": str(outbox)}
    loop.update(local_extra or {})
    root = make_root(tmp_path, roadmap=roadmap, handoff="", local={"loop": loop})
    return root, inbox, outbox


def git(cwd, *args):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                        "-c", "core.hooksPath=/dev/null", *args], cwd=str(cwd),
                       capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def real_git(args, cwd, input=None):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                           "-c", "core.hooksPath=/dev/null", *args], cwd=str(cwd),
                          capture_output=True, text=True, input=input, timeout=GIT_TIMEOUT_S)


# TEST-LOOP-GIT-TEMPLATE: git_world's committed main repo is built ONCE per
# test session (this process) and copied per test, so a world costs one
# `worktree add` instead of init + add + commit. The template sits next to the
# first caller's tmp_path (pytest's session basetemp) and is rebuilt only when
# it is gone. Built under GIT_ENV, so no host config shapes it.
_TEMPLATE = {"dir": None, "builds": 0}


def template_builds():
    """How many times this session built the git_world template (tests)."""
    return _TEMPLATE["builds"]


def _git_template(tmp_path):
    tdir = _TEMPLATE["dir"]
    if tdir is not None and (tdir / "repo" / ".git" / "HEAD").is_file():
        return tdir / "repo"
    tdir = Path(tmp_path).parent / f"al-git-template-{os.getpid()}-{_TEMPLATE['builds']}"
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)
    root = make_root(tdir, handoff="")
    env = dict(os.environ, **GIT_ENV)

    def tgit(*args):
        r = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=str(root),
                           capture_output=True, text=True, env=env, timeout=GIT_TIMEOUT_S)
        assert r.returncode == 0, r.stderr

    tgit("init", "-q", "-b", "main")
    # LF on every host: al_loop.tree_key drops GIT_* env, so it alone reads the
    # host config; a CRLF file would hash differently under a host autocrlf
    (root / ".gitignore").write_text("ops/\n", newline="\n")
    tgit("add", "-A")
    tgit("commit", "-q", "-m", "init")
    _TEMPLATE["dir"] = tdir
    _TEMPLATE["builds"] += 1
    return root


def git_world(tmp_path, kind="plan"):
    root = Path(tmp_path) / "repo"
    shutil.copytree(_git_template(tmp_path), root)
    wt = tmp_path / "al-worktrees" / "lane-1"
    git(root, "worktree", "add", "-q", "--detach", str(wt))
    (wt / "feature.txt").write_text("work\n", newline="\n")
    rec = {"id": "012", "kind": kind, "title": "Grind spot recommender",
           "label": "plan 012: Grind spot recommender", "state": "ran",
           "worktree": str(wt), "rc": 0, "lane": "build", "rounds": 0}
    al_loop.Items(root).put(rec)
    return root, wt


# TEST-LOOP-SPLIT-MERGE: shared by tests/test_al_loop.py and
# tests/test_al_loop_merge.py, moved here verbatim.

class FakeGit:
    def __init__(self, ahead="1", dirty=""):
        self.calls, self.ahead, self.dirty = [], ahead, dirty

    def __call__(self, args, cwd, input=None):
        self.calls.append(list(args))
        out = {"rev-parse": "main" if "--abbrev-ref" in args else "abc",
               "status": self.dirty, "rev-list": self.ahead}.get(args[0], "")
        return subprocess.CompletedProcess(args, 0, out, "")


def _lane(root, tmp_path, name, iid, edit):
    wt = tmp_path / "al-worktrees" / name
    git(root, "worktree", "add", "-q", "--detach", str(wt))
    edit(wt)
    al_loop.Items(root).put({"id": iid, "kind": "plan", "title": f"plan {iid}",
                             "label": f"plan {iid}: t", "state": "ran", "worktree": str(wt),
                             "rc": 0, "lane": name, "rounds": 0})
    return wt


def _two_lane_world(tmp_path, edit_a, edit_b):
    root = make_root(tmp_path, handoff="")
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("ops/\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    _lane(root, tmp_path, "lane-0", "012", edit_a)
    _lane(root, tmp_path, "lane-1", "013", edit_b)
    sp = FakeSpawn([{"rc": 0, "error": None, "result": "VERDICT: PASS"}] * 2)
    d = deps(root, spawn=sp, git=real_git,
             lane_state=lambda: [{"index": i, "state": "RUNNING", "lane": n}
                                 for i, n in enumerate(("build", "data", "review"))])
    al_loop.tick(deps=d, no_push=True)
    return root


# TEST-LOOP-SPLIT-LANES: shared by tests/test_al_loop.py and
# tests/test_al_loop_lanes.py, moved here verbatim.

def progress(root):
    return json.loads((root / "ops/loop/control/progress/loop.json").read_text())
