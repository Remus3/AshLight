#!/usr/bin/env python3
"""AL leak sweep - refuses to publish machine paths, emails, secrets, sibling names.

This repository is PUBLIC. Same design as the sibling-name sweep the fleet
already runs, reduced to AL's size:

* NEEDLE arm - literal strings (sibling project names, account ids, user names)
  loaded at RUN TIME from the gitignored `config/leak_needles.json`
  (`{"needles": [...]}`) or env `AL_LEAK_NEEDLES` (`;`-separated). This file and
  its tests never spell a real needle, and a finding prints the needle's SLOT
  NUMBER, never its text (hook output lands in logs and transcripts).
  `--explain N` prints slot N locally, on demand.
* STRUCTURAL arm - config-free: drive-rooted Windows paths, user-profile paths,
  e-mail addresses, and secret shapes (API key prefixes, private key blocks).
  It still runs in a fresh clone and on CI, where no needle file exists.

Modes: `--tree` (every tracked file), `--staged` (pre-commit, added lines),
`--pre-push` (stdin ref lines; every OBJECT the push sends that the remote
lacks: full blob bytes, tree entry names, commit and tag messages, ref names;
no diff, so no diff config, rename, empty file, -diff attribute or binary
file hides anything - GP-02 review). Exit 0 clean, 2 HALT (finding), 3 FAULT
(could not run). DEGRADED (no needle config) is announced on every run and
is not silent; it is not a FAULT, because CI legitimately has no config -
except in `--pre-push`, where it is a FAULT and env AL_LEAK_NEEDLES only adds
needles to the file, never replaces it. LEAK-WT: a linked worktree without its
own config reads the main checkout's (parent of `git rev-parse
--git-common-dir`); the run line names the source, never a needle.

Escape rate is above zero: `--no-verify` bypasses the hooks, and a needle
spelled in a shape nobody listed passes. A clean run is not proof.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "leak_needles.json"
ZERO = "0" * 40

# Byte-pinned shared files that legitimately carry a drive-rooted DEFAULT path.
STRUCT_ALLOW_FILES = {"ops/loop/slots.py"}
# Paths the structural arm never flags (generic, identify nobody). Sidecars is
# the fleet kit's generic sidecar root default (kit v22 fleet_lanes.SIDECAR_DEFAULT).
STRUCT_ALLOW_PATHS = re.compile(
    r"^[A-Za-z]:[\\/]+((ProgramData|Program Files( \(x86\))?|Windows)([\\/]|$)"
    r"|Sidecars\b)", re.I)
EMAIL_ALLOW = re.compile(r"@(example\.(com|org|net)|users\.noreply\.github\.com)$", re.I)

STRUCTURAL = [
    ("drive-path", re.compile(r"(?<![A-Za-z0-9\\])[A-Za-z]:[\\/]{1,2}[^\s\"'`<>|*?]+")),
    ("user-profile", re.compile(r"(?i)[\\/]Users[\\/](?!Example|<|%|\{)[A-Za-z0-9._-]+")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")),
    ("github-token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]


def main_checkout(root=ROOT):
    """The main checkout of `root`'s repository (LEAK-WT), or None.

    `git rev-parse --git-common-dir` names the shared .git dir; in a linked
    worktree its parent is the main checkout. None when git fails, the repo is
    bare-like, or `root` already is the main checkout."""
    try:
        out = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=str(root),
                             capture_output=True)
    except OSError:
        return None
    if out.returncode != 0:
        return None
    raw = out.stdout.decode("utf-8", "replace").strip()
    if not raw:
        return None
    common = Path(raw)
    if not common.is_absolute():
        common = Path(root) / common
    common = common.resolve()
    if common.name != ".git":
        return None
    main = common.parent
    try:
        if main == Path(root).resolve():
            return None
    except OSError:
        return None
    return main


def resolve_config(root=ROOT):
    """(path, source) of the needle config. The worktree's own file wins; a
    linked worktree without one reads the main checkout's (LEAK-WT). source is
    "local", "main-checkout" or "none" (path then is the local candidate)."""
    local = Path(root) / "config" / "leak_needles.json"
    if local.is_file():
        return local, "local"
    main = main_checkout(root)
    if main is not None:
        shared = main / "config" / "leak_needles.json"
        if shared.is_file():
            return shared, "main-checkout"
    return local, "none"


def load_needles(config=None, environ=None, push=False):
    """Return (needles, mode). mode is ARMED, DEGRADED or raises ValueError (FAULT).
    config None resolves it via resolve_config() (worktree first, then main).
    push=True (GP-02 review B-ENV-OVERRIDE): the config file is required and
    env AL_LEAK_NEEDLES only ADDS needles to it, never replaces it."""
    if config is None:
        config, _ = resolve_config()
    env = os.environ if environ is None else environ
    raw = env.get("AL_LEAK_NEEDLES")
    extra = [n.strip() for n in raw.split(";") if n.strip()] if raw else []
    if push and not Path(config).is_file():
        return [], "DEGRADED"
    if extra and not push:
        needles = extra
    elif Path(config).is_file():
        doc = json.loads(Path(config).read_text(encoding="utf-8"))
        raw_list = doc.get("needles") if isinstance(doc, dict) else None
        if not isinstance(raw_list, list):  # plan 149 TOOLS-05: FAULT, not a traceback
            raise ValueError("needle config is not {\"needles\": [...]}")
        needles = [n.strip() for n in raw_list if isinstance(n, str) and n.strip()]
        if not needles:
            raise ValueError("needle config present but holds no usable needle")
        if push:
            needles += [n for n in extra if n not in needles]
    else:
        return [], "DEGRADED"
    short = [i for i, n in enumerate(needles) if len(n) < 3]
    if short:
        raise ValueError(f"needle slot(s) {short} shorter than 3 chars")
    return needles, "ARMED"


def _variants(needle):
    """Spaced, hyphenated, underscored, tight spellings of a needle."""
    words = re.split(r"[\s_-]+", needle.strip())
    out = {needle}
    for sep in (" ", "-", "_", ""):
        out.add(sep.join(words))
    return sorted(out, key=len, reverse=True)


def compile_needles(needles):
    return [(i, re.compile("|".join(re.escape(v) for v in _variants(n)), re.I))
            for i, n in enumerate(needles)]


def scan_text(text, where, needles_rx, rel_path=""):
    """Findings for one blob of text: list of (where, line_no, kind)."""
    findings = []
    for ln, line in enumerate(text.splitlines(), 1):
        for slot, rx in needles_rx:
            if rx.search(line):
                findings.append((where, ln, f"needle-slot-{slot}"))
        if rel_path in STRUCT_ALLOW_FILES:
            continue
        for kind, rx in STRUCTURAL:
            for m in rx.finditer(line):
                hit = m.group(0)
                # the allow list reads from the hit on, past its first space
                # (a drive-path hit stops at the space of "Program Files (x86)")
                if kind == "drive-path" and STRUCT_ALLOW_PATHS.match(line[m.start():]):
                    continue
                if kind == "email" and EMAIL_ALLOW.search(hit):
                    continue
                findings.append((where, ln, kind))
    return findings


def _git(*args, cwd=ROOT):
    out = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed")
    return out.stdout.decode("utf-8", "replace")


def _is_text(data):
    return b"\0" not in data[:8192]


def scan_tree(needles_rx, cwd=ROOT):
    findings = []
    files = [f for f in _git("ls-files", "-z", cwd=cwd).split("\0") if f]
    for rel in files:
        findings += scan_text(rel, "path", needles_rx)  # the path itself publishes
        p = Path(cwd) / rel
        try:
            data = p.read_bytes()
        except OSError:
            continue
        if _is_text(data):
            findings += scan_text(data.decode("utf-8", "replace"), rel, needles_rx, rel)
    return findings, len(files)


_C_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13,
              '"': 34, "\\": 92}


def _unquote_path(text):
    """A git C-quoted path (`"b/caf\\303\\251.md"`, core.quotePath) as text."""
    body, out, i = text[1:-1], bytearray(), 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt, octal = body[i + 1], body[i + 1:i + 4]
            if len(octal) == 3 and all(ch in "01234567" for ch in octal):
                out.append(int(octal, 8) & 0xFF)
                i += 4
                continue
            out.append(_C_ESCAPES.get(nxt, ord(nxt) if ord(nxt) < 128 else 63))
            i += 2
            continue
        out += c.encode("utf-8")
        i += 1
    return out.decode("utf-8", "replace")


def _added_lines(diff_text):
    """{path: text of added lines} from a unified diff. Plan 149 TOOLS-04: a
    C-quoted header path (non-ASCII or special bytes) is unquoted, so its
    added lines are scanned like any other file's."""
    out, cur = {}, None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            head = line[4:]
            if head.startswith('"') and head.endswith('"') and len(head) >= 2:
                head = _unquote_path(head)
            cur = head[2:] if head.startswith("b/") else None
            if cur is not None:
                out.setdefault(cur, [])
        elif cur is not None and line.startswith("+") and not line.startswith("+++"):
            out[cur].append(line[1:])
    return {k: "\n".join(v) for k, v in out.items()}


def scan_diff(diff_text, needles_rx):
    findings = []
    for rel, text in _added_lines(diff_text).items():
        findings += scan_text(rel, "path", needles_rx)
        findings += scan_text(text, rel, needles_rx, rel)
    return findings


_ZERO_RX = re.compile(r"^0+$")
_SHA_RX = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


def _git_raw(args, cwd=ROOT, stdin=b""):
    """git with bytes in and out; the caller's GIT_* env and `git -c` values
    (GIT_CONFIG_PARAMETERS) are dropped, so a push-time config never reshapes
    what the sweep reads (GP-02 review B-NOPREFIX / B-DSTPREFIX)."""
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith("GIT_") or k.upper() in ("GIT_EXEC_PATH",)}
    env["GIT_TERMINAL_PROMPT"] = "0"
    out = subprocess.run(["git", *args], cwd=str(cwd), input=stdin, capture_output=True,
                         env=env, timeout=600)
    if out.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed")
    return out.stdout


def _present(shas, cwd=ROOT):
    """The subset of shas this object store holds (any object type)."""
    shas = sorted({s for s in shas if _SHA_RX.match(s)})
    if not shas:
        return []
    out = _git_raw(["cat-file", "--batch-check=%(objectname) %(objecttype)"], cwd,
                   ("\n".join(shas) + "\n").encode("ascii")).decode("ascii", "replace")
    return [ln.split()[0] for ln in out.splitlines()
            if len(ln.split()) == 2 and ln.split()[1] != "missing"]


def remote_advertised(remote, cwd=ROOT):
    """Shas `git ls-remote <remote>` advertises (public already), [] on any
    failure: an unread advertisement only widens the scan, never narrows it.
    Local remote-tracking refs are never trusted as "public"."""
    if not remote:
        return []
    try:
        out = _git_raw(["ls-remote", "--", remote], cwd).decode("utf-8", "replace")
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return []
    return [ln.split()[0] for ln in out.splitlines()
            if ln.split() and _SHA_RX.match(ln.split()[0])]


def _ref_lines(ref_lines):
    """[(lref, lsha, rref, rsha)] for well-formed stdin lines."""
    return [tuple(ln.split()) for ln in ref_lines if len(ln.split()) == 4]


def pushed_objects(ref_lines, cwd=ROOT, remote=None, advertised=None):
    """GP-02 review: every object a push would send that the remote does not
    hold already - commits, annotated tags, trees and blobs, whatever the ref
    points at (a blob or tree tag too). Returns [(sha, type, data, path_hint)].
    Excluded: objects reachable from the pushed refs' old remote tips and
    from the remote's advertised refs, when present locally; nothing else."""
    rows = _ref_lines(ref_lines)
    tips = [lsha for _l, lsha, _r, _o in rows if not _ZERO_RX.match(lsha)]
    if not tips:
        return []
    if advertised is None:
        advertised = remote_advertised(remote, cwd)
    olds = [o for _l, _s, _r, o in rows if not _ZERO_RX.match(o)]
    exclude = _present(olds + list(advertised), cwd)
    spec = "\n".join(tips + ["^" + s for s in exclude]) + "\n"
    listing = _git_raw(["rev-list", "--objects", "--stdin"], cwd, spec.encode("ascii"))
    order, hints = [], {}
    if listing.endswith(b"\n"):
        listing = listing[:-1]
    for raw in listing.split(b"\n") if listing else []:
        line = raw.decode("utf-8", "replace")
        head = line[:64].split(" ", 1)[0]
        if _SHA_RX.match(head) and (len(line) == len(head) or line[len(head)] == " "):
            if head not in hints:
                order.append(head)
                hints[head] = line[len(head) + 1:]
        elif order:  # a path holding a newline continues the previous row
            hints[order[-1]] += "\n" + line
    if not order:
        return []
    batch = _git_raw(["cat-file", "--batch"], cwd, ("\n".join(order) + "\n").encode("ascii"))
    out, pos = [], 0
    for sha in order:
        nl = batch.index(b"\n", pos)
        head = batch[pos:nl].decode("ascii", "replace").split()
        if len(head) != 3 or head[1] == "missing":
            raise RuntimeError("cat-file missing object")
        size = int(head[2])
        data = batch[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
        out.append((head[0], head[1], data, hints.get(sha, "")))
    return out


def object_message(data):
    """(header text, message text) of a commit or tag object."""
    head, _, body = data.partition(b"\n\n")
    return head.decode("utf-8", "replace"), body.decode("utf-8", "replace")


def tree_names(data, hash_len):
    """Entry names of a raw tree object."""
    names, pos = [], 0
    while pos < len(data):
        sp = data.index(b" ", pos)
        nul = data.index(b"\0", sp)
        names.append(data[sp + 1:nul].decode("utf-8", "replace"))
        pos = nul + 1 + hash_len
    return names


def scan_blob(data, rel, needles_rx):
    """A blob's bytes, text or binary. Text gets both arms. Binary (a NUL in
    its first 8 KB, or a -diff attribute, which no longer matters) gets the
    needle arm over its UTF-8, UTF-16LE and UTF-16BE readings; the structural
    arm is skipped on binary (image bytes form drive and mail shapes by chance)."""
    where = rel or "blob"
    if _is_text(data):
        return scan_text(data.decode("utf-8", "replace"), where, needles_rx, rel)
    findings = []
    texts = [data.decode("utf-8", "replace").replace("\0", "\n")]
    for codec in ("utf-16-le", "utf-16-be"):  # both byte alignments of each
        texts += [data[:len(data) // 2 * 2].decode(codec, "ignore"),
                  data[1:][:(len(data) - 1) // 2 * 2].decode(codec, "ignore")]
    seen = set()
    for text in texts:
        for f in scan_text(text, where, needles_rx, rel):
            if f[2].startswith("needle-slot-") and (f[0], f[2]) not in seen:
                seen.add((f[0], f[2]))
                findings.append(f)
    return findings


def scan_pre_push(ref_lines, needles_rx, cwd=ROOT, remote=None, advertised=None):
    """GP-02 review: the pushed OBJECTS, not a diff. Every new blob's full
    bytes, every new tree's entry names, every new commit and tag message,
    and the pushed ref names. Returns (findings, bytes scanned)."""
    findings, scanned = [], 0
    rows = _ref_lines(ref_lines)
    for lref, lsha, rref, _rsha in rows:
        if _ZERO_RX.match(lsha):
            continue
        for name in {lref, rref}:
            findings += scan_text(name, "ref-name", needles_rx)
            scanned += len(name)
    objs = pushed_objects(ref_lines, cwd, remote, advertised)
    hash_len = 32 if any(len(s) == 64 for _l, s, _r, _o in rows) else 20
    # A message byte-identical to one already reachable from a pushed ref's
    # old remote tip is public already (a history rewrite re-pushes old
    # messages under new SHAs). A new ref gets no such exemption.
    olds = _present([o for _l, _s, _r, o in rows if not _ZERO_RX.match(o)], cwd)
    public = set()
    if olds:
        logs = _git_raw(["log", "-z", "--format=%B", *olds], cwd).decode("utf-8", "replace")
        public = {m.strip() for m in logs.split("\0")}
    for sha, kind, data, hint in objs:
        scanned += len(data) + 1
        if kind == "blob":
            findings += scan_blob(data, hint, needles_rx)
        elif kind == "tree":
            for name in tree_names(data, hash_len):
                findings += scan_text(name, "path", needles_rx)
            if hint:
                findings += scan_text(hint, "path", needles_rx)
        elif kind == "commit":
            _head, msg = object_message(data)
            if msg.strip() not in public:
                findings += scan_text(msg, "commit-message", needles_rx)
        elif kind == "tag":
            head, msg = object_message(data)
            names = [ln[4:] for ln in head.splitlines() if ln.startswith("tag ")]
            findings += scan_text("\n".join(names), "tag-name", needles_rx)
            findings += scan_text(msg, "tag-message", needles_rx)
    return findings, scanned


def scan_message(text, needles_rx):
    """AUDIT-LEAK-MSG: a commit message as git hands it to commit-msg; its
    '#' comment lines (git's own template text) are not part of the commit."""
    body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("#"))
    return scan_text(body, "commit-message", needles_rx)


def scan_history(needles_rx, cwd=ROOT):
    """AUDIT-LEAK-MSG: every commit reachable from any ref - its added lines,
    file paths and message (author / committer headers are not scanned; the
    operator identity is fleet_identity's job). Returns (findings, commits)."""
    commits = _git("rev-list", "--all", cwd=cwd).split()
    findings = []
    for c in commits:
        diff = _git("show", "--format=", "--no-color", "-p", "--root", c, cwd=cwd)
        findings += scan_diff(diff, needles_rx)
        findings += scan_text(_git("log", "-1", "--format=%B", c, cwd=cwd),
                              "commit-message", needles_rx)
    return findings, len(commits)


def report(findings, mode, n_needles, source=""):
    tail = f" config={source}" if source else ""
    print(f"[leak-sweep] {mode} needles={n_needles}{tail}", file=sys.stderr)
    if mode == "DEGRADED":
        print("[leak-sweep] DEGRADED: no needle config - the needle arm proved nothing; "
              "structural arm ran", file=sys.stderr)
    for where, ln, kind in findings[:200]:
        print(f"[leak-sweep] HALT {where}:{ln} {kind}", file=sys.stderr)
    if findings:
        print(f"[leak-sweep] {len(findings)} finding(s). Fix the bytes; never print the "
              "matched text into a tracked file or a note.", file=sys.stderr)
    return 2 if findings else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--tree", action="store_true")
    g.add_argument("--staged", action="store_true")
    g.add_argument("--pre-push", nargs="*", metavar="ARG")
    g.add_argument("--explain", type=int)
    g.add_argument("--message", metavar="FILE", help="commit-msg hook: sweep the message")
    g.add_argument("--history", action="store_true", help="every commit and message")
    args = ap.parse_args(argv)
    push = args.pre_push is not None
    config, source = resolve_config()
    if os.environ.get("AL_LEAK_NEEDLES"):
        source = source + "+env" if push else "env"
    try:
        needles, mode = load_needles(config, push=push)
    except (ValueError, OSError) as exc:
        print(f"[leak-sweep] FAULT config: {exc}", file=sys.stderr)
        return 3
    if push and mode != "ARMED":
        # GP-02 review B-CONFIG-MISSING: a push never runs DEGRADED.
        print("[leak-sweep] FAULT: pre-push needs config/leak_needles.json; nothing is "
              "pushed without the needle arm", file=sys.stderr)
        return 3
    if args.explain is not None:
        if 0 <= args.explain < len(needles):
            print(needles[args.explain])
            return 0
        return 3
    rx = compile_needles(needles)
    try:
        if args.tree:
            findings, n = scan_tree(rx)
            if n == 0:
                print("[leak-sweep] FAULT: zero tracked files scanned", file=sys.stderr)
                return 3
        elif args.staged:
            findings = scan_diff(_git("diff", "--cached", "--no-color"), rx)
        elif args.message is not None:
            try:
                text = Path(args.message).read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"[leak-sweep] FAULT message: {exc.__class__.__name__}", file=sys.stderr)
                return 3
            findings = scan_message(text, rx)
        elif args.history:
            findings, n = scan_history(rx)
            if n == 0:
                print("[leak-sweep] FAULT: zero commits scanned", file=sys.stderr)
                return 3
        else:
            refs = [ln for ln in sys.stdin.read().splitlines() if ln.strip()]
            remote = args.pre_push[0] if args.pre_push else None
            findings, scanned = scan_pre_push(refs, rx, remote=remote)
            if refs and scanned == 0 and any(r.split()[1] != ZERO for r in refs
                                             if len(r.split()) == 4):
                print("[leak-sweep] FAULT: zero bytes scanned for a non-empty push",
                      file=sys.stderr)
                return 3
    except RuntimeError as exc:
        print(f"[leak-sweep] FAULT: {exc}", file=sys.stderr)
        return 3
    return report(findings, mode, len(needles), source)


if __name__ == "__main__":
    sys.exit(main())
