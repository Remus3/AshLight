"""Go-public gate 6 blob size check (decision 0079).

Walks every object reachable from a ref (`git rev-list --objects <ref>`),
sizes each blob with `git cat-file --batch-check`, and reads the content
(`git cat-file --batch`) only of blobs between the two limits to tell text
from binary. Text = valid UTF-8 with no NUL byte; everything else is binary.

Limits (docs/plan/04-go-public.md gate 6): a binary blob may be at most
500 KB, a text blob at most 2 MB (1 KB = 1000 bytes).

Exit 0: no offender (one summary line). Exit 1: one line per offender, or
a one-line fault when git fails (fail closed). Stdlib only.
"""
import argparse
import subprocess
import sys

BINARY_MAX = 500 * 1000
TEXT_MAX = 2 * 1000 * 1000
_TIMEOUT = 600


class GateFault(Exception):
    """git could not be read; the gate fails closed."""


def _git(repo, args, data=None):
    try:
        proc = subprocess.run(["git", *args], cwd=str(repo), input=data,
                              capture_output=True, timeout=_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateFault(f"git {args[0]} failed: {exc}") from None
    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise GateFault(f"git {args[0]} rc {proc.returncode}: "
                        f"{msg[-1] if msg else 'no message'}")
    return proc.stdout


def is_text(data):
    """Text = valid UTF-8 with no NUL byte."""
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _reachable(repo, ref):
    """[(sha, path)] of every object reachable from ref, first path only."""
    out = _git(repo, ["rev-list", "--objects", ref, "--"])
    objs = []
    for line in out.decode("utf-8", "replace").splitlines():
        sha, _, path = line.partition(" ")
        if sha:
            objs.append((sha, path))
    return objs


def _sizes(repo, shas):
    """{sha: size} for the blobs among shas."""
    fmt = "--batch-check=%(objectname) %(objecttype) %(objectsize)"
    out = _git(repo, ["cat-file", fmt], "".join(s + "\n" for s in shas).encode())
    sizes = {}
    for line in out.decode("ascii", "replace").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob":
            sizes[parts[0]] = int(parts[2])
    return sizes


def _contents(repo, shas):
    """{sha: bytes} read with one `git cat-file --batch` call."""
    out = _git(repo, ["cat-file", "--batch"], "".join(s + "\n" for s in shas).encode())
    found, pos = {}, 0
    while pos < len(out):
        nl = out.index(b"\n", pos)
        head = out[pos:nl].decode("ascii", "replace").split()
        if len(head) != 3:
            raise GateFault(f"cat-file --batch: unexpected header {head!r}")
        size = int(head[2])
        found[head[0]] = out[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
    return found


def scan(repo, ref="main", binary_max=BINARY_MAX, text_max=TEXT_MAX):
    """Return (findings, stats). Each finding is (sha, size, kind, limit, path)."""
    objs = _reachable(repo, ref)
    paths = {}
    for sha, path in objs:
        paths.setdefault(sha, path)
    sizes = _sizes(repo, list(paths))
    big = [s for s, n in sizes.items() if n > binary_max]
    data = _contents(repo, big) if big else {}
    findings = []
    for sha in big:
        size = sizes[sha]
        kind = "text" if is_text(data[sha]) else "binary"
        limit = text_max if kind == "text" else binary_max
        if size > limit:
            findings.append((sha, size, kind, limit, paths[sha]))
    findings.sort(key=lambda f: (-f[1], f[4]))
    stats = {"blobs": len(sizes), "largest": max(sizes.values(), default=0)}
    return findings, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", default="main")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--binary-max", type=int, default=BINARY_MAX)
    ap.add_argument("--text-max", type=int, default=TEXT_MAX)
    args = ap.parse_args(argv)
    try:
        findings, stats = scan(args.repo, args.ref, args.binary_max, args.text_max)
    except GateFault as exc:
        print(f"blob-gate: FAULT {exc}")
        return 1
    for sha, size, kind, limit, path in findings:
        print(f"blob-gate: {kind} blob {sha[:12]} {size} B over {limit} B: {path}")
    if findings:
        return 1
    print(f"blob-gate: ok ref={args.ref} blobs={stats['blobs']} "
          f"largest={stats['largest']} B (binary max {args.binary_max} B, "
          f"text max {args.text_max} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
