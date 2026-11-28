#!/usr/bin/env python3
"""Release publish gates (REL-PUBLISH-GATES, DEP-12, F-074, decision 0073).

Loaded by tools/release.py for two sub-commands:

    release.py publish --version X.Y.Z --go "release X.Y.Z" [--rehearse]
                       [--out DIR] [--owner ID] [--root DIR]
    release.py prepush-check [REMOTE [URL]] [--stage-root DIR] [--root DIR]
                       (pre-push ref lines on stdin)

publish runs every gate below (all of them, so every refusal is named at
once) and only when every gate passes does it make one annotated tag
vX.Y.Z on the stage commit, whose message carries
'sums-sha256: <hex of the staged SHA256SUMS.txt>', and one push of that
one ref, `git push origin refs/tags/vX.Y.Z`, through the kit git lock
(fleet_gitlock.py run --owner ID -- ...). Never --tags, --all or --mirror,
never a branch: main is pushed under the go-public push policy, not here.
A refusal changes nothing. A failed push deletes the local tag again.

    phrase     --go equals 'release ' + the version, typed by the operator
    headless   no headless marker: the kit progress-owner variable
               (FLEET_PROGRESS_OWNER) is unset and no lane lock names this
               worktree; lanes, loop ticks and inbox responders never publish
    remote     a remote named origin exists and names the repository of
               config/public_repo.json (the one address source); with none
               the gate refuses with 'no remote'
    stage      <out>/stage.json exists, verdict PASS, the asked version, HEAD
               as its commit, created at most 24 h ago, a sums_sha256,
               build_python equal to release.yml's CPython pin (decision
               0064 amendment 2026-11-28)
    tree       the tree is clean (tracked changes and untracked files)
    notes      docs/releases/<version>.md exists without its STUB mark and
               CHANGELOG.md is current (tools/rel_notes.py)
    tag        refs/tags/vX.Y.Z exists neither locally nor on origin
    origin     origin's refs/heads/main (one ls-remote read) is HEAD
    committer  HEAD's committer is an operator identity (local git config
               fleet.operatorIdent, the kit identity rule)
    immutable  the repository's immutable-releases setting reads enabled
               through gh, else config/release.json holds a dated
               immutable_confirmed value from the operator act

`--rehearse` runs every gate, prints each one and the remote line, and
makes no tag and no push; origin is only read (one ls-remote). It exits 0
only when every gate passes. It never runs the read-back.

After a pushed tag, publish makes one call to tools/rel_readback.py
read_back() (REL-PUBLISH-READBACK): bounded polling until the release is
published and immutable, the tag targets the stage commit, every asset
digest equals the staged one and the app zip's attestation verifies; the
verdict lands in publish.json under read_back and a FAIL exits 1.

prepush-check (for the guarded pre-push hook; the hook call itself rides
the go-public push package): a pushed refs/tags/v* ref passes only with a
PASS stage report of that version whose commit is the tag's commit; a tag
delete is refused; every other ref passes untouched.

git, gh, the push, the clock, the environment and the lane locks are
injected (tests). Floor: no game access of any kind and no upload; the only
network use is git's read of origin and gh's settings read. Stdlib only.
"""
import argparse
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent

CONFIG_REL = "config/release.json"
PUBLIC_REPO_REL = "config/public_repo.json"
KIT_REL = "ops/fleet_kit"
GITLOCK_REL = KIT_REL + "/fleet_gitlock.py"
LANES_REL = "ops/loop/control/lanes"
STAGE_NAME = "stage.json"
PUBLISH_NAME = "publish.json"
REMOTE = "origin"
MAX_AGE_S = 24 * 3600
HEADLESS_ENV = "FLEET_PROGRESS_OWNER"
OWNER_ENV = "FLEET_CLAIM_OWNER"
DEFAULT_OWNER = "release-publish"
IDENT_KEY = "fleet.operatorIdent"
GIT_TIMEOUT_S = 60
CREATE_NO_WINDOW = 0x08000000
ZERO_SHA = "0" * 40
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REPO_IN_URL = re.compile(r"github\.com[:/]+([^/\s]+/[^/\s]+?)(?:\.git)?/?$", re.I)


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(
        "rel_publish_" + name, str(TOOLS / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rb = _load_tool("rel_build")
rv = rb.rv
rr = _load_tool("rel_readback")


class Refuse(Exception):
    """One gate refused; the text names why."""


# --- the default effects ---------------------------------------------------

def _quiet_env():
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"   # never ask for a password
    env["GCM_INTERACTIVE"] = "never"   # never pop a credential window
    return env


def _proc_kw():
    kw = {"capture_output": True, "check": False, "env": _quiet_env(),
          "timeout": GIT_TIMEOUT_S}
    if sys.platform == "win32":
        kw["creationflags"] = CREATE_NO_WINDOW
    return kw


def default_git(root):
    """git(*args) -> (exit code, stdout text) in root; no prompt."""
    def git(*args):
        try:
            proc = subprocess.run(["git", *args], cwd=str(root), **_proc_kw())
        except (OSError, subprocess.SubprocessError) as exc:
            return 127, "", str(exc)
        return (proc.returncode, proc.stdout.decode("utf-8", "replace"),
                proc.stderr.decode("utf-8", "replace"))
    return git


def default_gh(root):
    """gh(*args) -> (exit code, stdout text); 127 when gh is not installed."""
    def gh(*args):
        try:
            proc = subprocess.run(["gh", *args], cwd=str(root), **_proc_kw())
        except (OSError, subprocess.SubprocessError) as exc:
            return 127, "", str(exc)
        return (proc.returncode, proc.stdout.decode("utf-8", "replace"),
                proc.stderr.decode("utf-8", "replace"))
    return gh


def default_push(root):
    """push(argv) -> exit code; argv is the whole fleet_gitlock command."""
    def push(argv):
        try:
            return subprocess.call(list(argv), cwd=str(root))
        except OSError:
            return 127
    return push


def _git3(ctx, *args):
    got = ctx["git"](*args)
    if len(got) == 2:
        return got[0], got[1], ""
    return got


def default_lane_locks(ctx):
    """Payload dicts of the lane lock files in the main checkout."""
    rc, out, _err = _git3(ctx, "rev-parse", "--path-format=absolute",
                          "--git-common-dir")
    if rc != 0 or not out.strip():
        return []
    folder = Path(out.strip()).parent / LANES_REL
    found = []
    if folder.is_dir():
        for path in sorted(folder.glob("*.lock")):
            try:
                found.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                found.append({"worktree": None, "unreadable": path.name})
    return found


def created_text(seconds):
    stamp = datetime.datetime.fromtimestamp(float(seconds),
                                            tz=datetime.timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_created(text):
    try:
        stamp = datetime.datetime.strptime(str(text), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return stamp.replace(tzinfo=datetime.timezone.utc).timestamp()


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_config(root):
    """config/release.json; missing or broken reads as empty."""
    doc = _read_json(Path(root) / CONFIG_REL)
    return doc if isinstance(doc, dict) else {}


def repository(root, config=None):
    """owner/name: config/public_repo.json first (the one source), else the
    repository field of config/release.json, else None."""
    doc = _read_json(Path(root) / PUBLIC_REPO_REL)
    if isinstance(doc, dict) and str(doc.get("repo") or "").strip():
        return str(doc["repo"]).strip()
    cfg = read_config(root) if config is None else config
    value = str(cfg.get("repository") or "").strip()
    return value or None


def repo_of_url(url):
    m = _REPO_IN_URL.search(str(url or "").strip())
    return m.group(1) if m else None


# --- the gates -------------------------------------------------------------

def gate_phrase(ctx):
    version = ctx["version"]
    try:
        rv.parse(version)
    except rv.VersionError as exc:
        raise Refuse(str(exc))
    want = "release " + version
    if ctx["go"] != want:
        raise Refuse("the phrase differs: --go must be %r" % want)
    return "operator phrase %r" % want


def _same_place(a, b):
    try:
        return os.path.normcase(str(Path(a).resolve())) == \
            os.path.normcase(str(Path(b).resolve()))
    except (OSError, ValueError):
        return False


def gate_headless(ctx):
    raw = str(ctx["env"].get(HEADLESS_ENV) or "").strip()
    if raw:
        raise Refuse("a headless marker is set (%s); lanes, loop ticks and "
                     "inbox responders never publish" % HEADLESS_ENV)
    for lock in ctx["lane_locks"](ctx):
        wt = lock.get("worktree") if isinstance(lock, dict) else None
        if wt and _same_place(wt, ctx["root"]):
            raise Refuse("a headless marker is set (lane lock %s holds this "
                         "worktree)" % lock.get("lane", "?"))
    return "interactive"


def gate_remote(ctx):
    rc, out, _err = _git3(ctx, "remote", "get-url", REMOTE)
    url = out.strip()
    if rc != 0 or not url:
        ctx["remote"] = None
        raise Refuse("no remote: %s is not configured" % REMOTE)
    ctx["remote"] = url
    want = ctx["repository"]
    if not want:
        raise Refuse("no repository address in %s" % PUBLIC_REPO_REL)
    have = repo_of_url(url)
    if not have or have.lower() != want.lower():
        raise Refuse("%s does not name %s" % (REMOTE, want))
    return "%s (%s)" % (REMOTE, want)


def _head(ctx):
    if ctx.get("head") is None:
        rc, out, _err = _git3(ctx, "rev-parse", "-q", "--verify",
                              "HEAD^{commit}")
        ctx["head"] = out.strip() if rc == 0 else ""
    return ctx["head"]


def load_stage(folder):
    return _read_json(Path(folder) / STAGE_NAME)


def check_stage(rep, version, commit, now=None, pin=None):
    """Refuse unless rep is a PASS stage report of version at commit; with
    now (epoch seconds) it must also be at most 24 h old; with pin (the
    release.yml CPython version) its builds must have run on it."""
    if not isinstance(rep, dict):
        raise Refuse("no stage report (run release.py stage %s)" % version)
    if rep.get("verdict") != "PASS":
        raise Refuse("the stage report is %s, not PASS" % rep.get("verdict"))
    if rep.get("version") != version:
        raise Refuse("the stage report is for another version (%s)"
                     % rep.get("version"))
    if not commit or rep.get("commit") != commit:
        raise Refuse("the stage report is for another commit; HEAD is not "
                     "the stage commit")
    made = parse_created(rep.get("created"))
    if made is None or (now is not None and (now - made > MAX_AGE_S
                                             or made - now > 300)):
        raise Refuse("the stage report is older than 24 h (or undated)")
    if not _HEX64.match(str(rep.get("sums_sha256") or "")):
        raise Refuse("the stage report has no sums_sha256")
    if pin is not None and rep.get("build_python") != pin:
        raise Refuse("the stage builds ran on Python %s, release.yml pins %s "
                     "(CI's rebuild would not match the sums); re-run the "
                     "stage" % (rep.get("build_python"), pin))
    return rep


def gate_stage(ctx):
    try:
        pin = rb.pinned_python()
    except rb.BuildError as exc:
        raise Refuse(str(exc))
    rep = check_stage(load_stage(ctx["out"]), ctx["version"], _head(ctx),
                      ctx["now"](), pin=pin)
    ctx["stage"] = rep
    return "PASS %s at %s, created %s" % (rep["version"], rep["commit"][:12],
                                         rep["created"])


def gate_tree(ctx):
    rc, out, _err = _git3(ctx, "status", "--porcelain=v1",
                          "--untracked-files=normal")
    if rc != 0:
        raise Refuse("git status failed")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if lines:
        raise Refuse("the tree is dirty (%d path(s), first: %s)"
                     % (len(lines), lines[0][3:]))
    return "clean"


def gate_notes(ctx):
    root, version = ctx["root"], ctx["version"]
    path = Path(root) / rv.notes_rel(version)
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        raise Refuse("no notes file %s" % rv.notes_rel(version))
    if rv.STUB_MARK in text:
        raise Refuse("the notes file still has its STUB mark")
    if not ctx["changelog_current"](root):
        raise Refuse("CHANGELOG.md is stale (release.py notes)")
    return "notes written, CHANGELOG.md current"


def _ls_remote(ctx):
    """{ref: sha} of origin's main and the tag; one read, cached."""
    if "advertised" not in ctx:
        tag = "refs/tags/" + rv.tag_for(ctx["version"])
        rc, out, _err = _git3(ctx, "ls-remote", REMOTE, "refs/heads/main",
                              tag, tag + "^{}")
        if rc != 0:
            ctx["advertised"] = None
        else:
            found = {}
            for line in out.splitlines():
                parts = line.split()
                if len(parts) == 2:
                    found[parts[1]] = parts[0]
            ctx["advertised"] = found
    return ctx["advertised"]


def gate_tag(ctx):
    tag = rv.tag_for(ctx["version"])
    rc, _out, _err = _git3(ctx, "rev-parse", "-q", "--verify",
                           "refs/tags/" + tag)
    if rc == 0:
        raise Refuse("the tag %s exists locally" % tag)
    if not ctx.get("remote"):
        raise Refuse("no remote to check %s against" % tag)
    adv = _ls_remote(ctx)
    if adv is None:
        raise Refuse("%s could not be read" % REMOTE)
    if ("refs/tags/" + tag) in adv:
        raise Refuse("the tag %s exists on the remote" % tag)
    return "%s is new" % tag


def gate_origin(ctx):
    if not ctx.get("remote"):
        raise Refuse("no remote: origin/main cannot be read")
    adv = _ls_remote(ctx)
    if adv is None:
        raise Refuse("%s could not be read" % REMOTE)
    head = _head(ctx)
    if not head or adv.get("refs/heads/main") != head:
        raise Refuse("origin/main is not HEAD (push main first)")
    return "origin/main is HEAD"


def operator_idents(text):
    found = set()
    for value in (text or "").splitlines():
        value = value.strip().lower()
        if not value:
            continue
        found.add(value)
        m = re.search(r"<([^>]+)>", value)
        if m:
            found.add(m.group(1).strip())
    return found


def gate_committer(ctx):
    rc, out, _err = _git3(ctx, "log", "-1", "--format=%cn%x00%ce", "HEAD")
    if rc != 0 or "\x00" not in out:
        raise Refuse("HEAD's committer could not be read")
    name, addr = out.strip("\r\n").split("\x00", 1)
    rc, idents, _err = _git3(ctx, "config", "--local", "--get-all", IDENT_KEY)
    known = operator_idents(idents if rc == 0 else "")
    full = "%s <%s>" % (name.strip().lower(), addr.strip().lower())
    if not known or (full not in known and addr.strip().lower() not in known):
        raise Refuse("the committer is not the operator identity (%s)"
                     % IDENT_KEY)
    return "operator"


def gate_immutable(ctx):
    repo = ctx["repository"]
    if repo:
        rc, out, _err = ctx_gh(ctx, "api", "repos/%s/immutable-releases" % repo)
        if rc == 0:
            try:
                doc = json.loads(out)
            except ValueError:
                doc = None
            if isinstance(doc, dict) and doc.get("enabled") is True:
                return "enabled (gh)"
    value = ctx["config"].get("immutable_confirmed")
    if isinstance(value, str) and _DATE.match(value):
        return "confirmed %s (operator act)" % value
    raise Refuse("immutable releases not confirmed (gh, or "
                 "immutable_confirmed in %s)" % CONFIG_REL)


def ctx_gh(ctx, *args):
    got = ctx["gh"](*args)
    if len(got) == 2:
        return got[0], got[1], ""
    return got


GATES = [
    ("phrase", gate_phrase),
    ("headless", gate_headless),
    ("remote", gate_remote),
    ("stage", gate_stage),
    ("tree", gate_tree),
    ("notes", gate_notes),
    ("tag", gate_tag),
    ("origin", gate_origin),
    ("committer", gate_committer),
    ("immutable", gate_immutable),
]


# --- publish ---------------------------------------------------------------

def _changelog_current(root):
    try:
        rn = _load_tool("rel_notes")
        return bool(rn.changelog(check=True, root=Path(root)))
    except Exception:  # an unreadable notes set is a stale changelog
        return False


def make_ctx(version, go, root=ROOT, out=None, git=None, gh=None, push=None,
             now=None, env=None, lane_locks=None, owner=None,
             changelog_current=None, read_back=None, sleep=None):
    root = Path(root)
    config = read_config(root)
    return {
        "root": root, "version": version, "go": go,
        "out": Path(out) if out is not None else None,
        "git": git or default_git(root), "gh": gh or default_gh(root),
        "push": push or default_push(root), "now": now or time.time,
        "env": os.environ if env is None else env,
        "lane_locks": lane_locks or default_lane_locks,
        "owner": owner or (os.environ if env is None else env).get(OWNER_ENV)
        or DEFAULT_OWNER,
        "config": config, "repository": repository(root, config),
        "changelog_current": changelog_current or _changelog_current,
        "read_back": read_back or rr.read_back,
        "sleep": sleep or time.sleep,
        "remote": None, "head": None, "stage": None,
    }


def gates(ctx):
    """Run every gate; [(name, 'pass' | 'refused', detail)]."""
    if ctx["out"] is None:
        try:
            rv.parse(ctx["version"])
            ctx["out"] = rb.default_out(ctx["version"])
        except rv.VersionError:
            ctx["out"] = Path(ctx["root"]) / "_no_stage_folder_"
    rows = []
    for name, fn in GATES:
        try:
            rows.append((name, "pass", str(fn(ctx) or "")))
        except (Refuse, rv.VersionError) as exc:
            rows.append((name, "refused", str(exc)))
    return rows


def push_argv(ctx, tag):
    return [sys.executable, str(Path(ctx["root"]) / GITLOCK_REL), "run",
            "--owner", ctx["owner"], "--", "git", "push", REMOTE,
            "refs/tags/" + tag]


def tag_message(version, sums):
    return "AshLight %s\n\nsums-sha256: %s\n" % (version, sums)


def _write_atomic(path, data):
    tmp = path.with_name(path.name + ".partial")
    tmp.write_bytes(data)
    os.replace(str(tmp), str(path))


def run(ctx, rehearse=False):
    """{rows, refusals, tagged, pushed, remote_line} after the gates and,
    when every gate passed and this is not a rehearsal, the tag and push."""
    rows = gates(ctx)
    refusals = [(n, d) for n, s, d in rows if s != "pass"]
    url = ctx.get("remote")
    remote_line = ("remote: %s (%s)" % (REMOTE, ctx["repository"] or url)
                   if url else "remote: none")
    result = {"rows": rows, "refusals": refusals, "tagged": False,
              "pushed": False, "remote_line": remote_line, "error": None,
              "read_back": None}
    if refusals or rehearse:
        return result
    version = ctx["version"]
    tag = rv.tag_for(version)
    rep = ctx["stage"]
    rc, _out, err = _git3(ctx, "tag", "-a", tag, "-m",
                          tag_message(version, rep["sums_sha256"]),
                          rep["commit"])
    if rc != 0:
        result["error"] = "git tag failed: %s" % (err.strip() or rc)
        return result
    result["tagged"] = True
    if ctx["push"](push_argv(ctx, tag)) != 0:
        _git3(ctx, "tag", "-d", tag)
        result["tagged"] = False
        result["error"] = "the push of refs/tags/%s failed; the local tag " \
                          "was removed" % tag
        return result
    result["pushed"] = True
    doc = {"version": version, "tag": tag, "commit": rep["commit"],
           "sums_sha256": rep["sums_sha256"], "pushed": True,
           "created": created_text(ctx["now"]()),
           "read_back": "pending (CI publishes the release on the tag)"}
    try:
        _write_atomic(Path(ctx["out"]) / PUBLISH_NAME,
                      (json.dumps(doc, indent=1, sort_keys=True) + "\n")
                      .encode("ascii"))
    except OSError:
        pass
    # REL-PUBLISH-READBACK: the one read-back call, after the push only.
    result["read_back"] = ctx["read_back"](
        version, gh=ctx["gh"], now=ctx["now"], sleep=ctx["sleep"],
        out=ctx["out"], repo=ctx["repository"])
    return result


# --- prepush-check ---------------------------------------------------------

def prepush_check(lines, stage_dir, git):
    """[refusal text] for pre-push stdin lines; empty means the push passes.
    stage_dir(version) -> folder of that version's stage.json."""
    refusals = []
    for line in lines:
        parts = line.split()
        if len(parts) != 4:
            continue
        _local_ref, local_sha, remote_ref, _remote_sha = parts
        if not remote_ref.startswith("refs/tags/v"):
            continue
        version = remote_ref[len("refs/tags/v"):]
        if local_sha == ZERO_SHA:
            refusals.append("%s: a release tag is never deleted" % remote_ref)
            continue
        try:
            rv.parse(version)
        except rv.VersionError:
            refusals.append("%s: not a release version" % remote_ref)
            continue
        got = git("rev-parse", "-q", "--verify", local_sha + "^{commit}")
        rc, out = got[0], got[1]
        commit = out.strip() if rc == 0 else ""
        rep = load_stage(stage_dir(version))
        try:
            check_stage(rep, version, commit, pin=rb.pinned_python())
        except rb.BuildError as exc:
            refusals.append("%s: %s" % (remote_ref, exc))
        except Refuse as exc:
            refusals.append("%s: %s" % (remote_ref, exc))
    return refusals


# --- command line ----------------------------------------------------------

def _publish_parser():
    p = argparse.ArgumentParser(
        prog="release.py publish",
        description="Tag and push one release after every gate passes, on "
                    "the operator's phrase. --rehearse: gates only.")
    p.add_argument("--version", required=True)
    p.add_argument("--go", required=True, help='the phrase "release X.Y.Z"')
    p.add_argument("--rehearse", action="store_true",
                   help="run every gate; no tag, no push")
    p.add_argument("--out", help="stage folder (default "
                                 "<sidecar>/Build/release/<version>)")
    p.add_argument("--owner", help="git lock owner (default env %s)"
                                   % OWNER_ENV)
    p.add_argument("--root", default=str(ROOT), help="the repository")
    return p


def _prepush_parser():
    p = argparse.ArgumentParser(prog="release.py prepush-check")
    p.add_argument("remote", nargs="?")
    p.add_argument("url", nargs="?")
    p.add_argument("--stage-root", help="folder holding <version>/stage.json "
                                        "(default <sidecar>/Build/release)")
    p.add_argument("--root", default=str(ROOT), help="the repository")
    return p


def main(command, argv):
    """Entry from tools/release.py; the exit code."""
    if command == "publish":
        try:
            args = _publish_parser().parse_args(list(argv))
        except SystemExit as exc:
            return 0 if exc.code == 0 else 2
        ctx = make_ctx(args.version, args.go, root=args.root, out=args.out,
                       owner=args.owner)
        res = run(ctx, rehearse=args.rehearse)
        word = "rehearse" if args.rehearse else "publish"
        for name, status, detail in res["rows"]:
            print("%s: %-9s %-7s %s" % (word, name, status, detail))
        print(res["remote_line"])
        if res["refusals"]:
            print("%s: refused (%d): %s" % (
                word, len(res["refusals"]),
                "; ".join(n for n, _d in res["refusals"])))
            print("%s: nothing changed (0 tags, 0 pushes)" % word)
            return 1
        if args.rehearse:
            print("rehearse: every gate passes (0 tags, 0 pushes)")
            return 0
        if res["error"]:
            print("publish: %s" % res["error"], file=sys.stderr)
            return 1
        print("publish: tagged and pushed %s" % rv.tag_for(args.version))
        back = res["read_back"] or {}
        print("publish: %s" % (back.get("hand_off") or "read-back missing"))
        return 0 if back.get("verdict") == "PASS" else 1
    if command == "prepush-check":
        try:
            args = _prepush_parser().parse_args(list(argv))
        except SystemExit as exc:
            return 0 if exc.code == 0 else 2
        if args.stage_root:
            base = Path(args.stage_root)

            def stage_dir(version):
                return base / version
        else:
            stage_dir = rb.default_out
        git = default_git(Path(args.root))
        found = prepush_check(sys.stdin.read().splitlines(), stage_dir, git)
        for text in found:
            print("prepush-check: refused: %s" % text, file=sys.stderr)
        return 1 if found else 0
    print("rel_publish: unknown sub-command %r" % command, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main("publish", sys.argv[1:]))
