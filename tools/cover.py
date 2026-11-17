"""TEST-COVER: stdlib line coverage of AshLight's own code.

    python tools/cover.py [--out docs/audit/test-coverage.md] [pytest args ...]

Runs pytest in this process under a line tracer (sys.settrace and
threading.settrace, stdlib only; no coverage package) that records lines
only for frames whose file is under server/ or tools/, so the rest of the
run stays fast. The denominator is every line that starts a bytecode range
in the module's compiled code objects (co_lines), the same notion the trace
module uses. Code that runs in a child process (a spawned core, the
supervisor, PowerShell) is not counted; the report says so.

Writes a Markdown report (per-module percent, missed line ranges, modules
with no test import) and prints one summary line. Exit code: pytest's.
Run it through the suite gate (FLEET-COMMON 16 c), it is a whole suite:

    python ops/fleet_kit/fleet_suite_gate.py run --owner <id> -- python tools/cover.py
"""

import argparse
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("server", "tools")
DEFAULT_OUT = ROOT / "docs" / "audit" / "test-coverage.md"
# modules exercised only in a child process (their tests exist; the tracer
# cannot see them)
CHILD_ONLY_NOTE = (
    "Driven only in a child process, so low here but tested: "
    "tools/wt_sidecar_hook.py (tests/test_wt_sidecar_hook.py runs it as the "
    "harness hook), tools/install_hooks.py (one hooks-path config call), the "
    "core main loop in server/al/__main__.py (tests/test_keepalive.py end to "
    "end) and tools/lane_samples.py (lane fixtures run through subprocess "
    "lanes).")


def own_files(root=ROOT):
    """Every .py file under server/ and tools/ (relative posix path -> abs)."""
    out = {}
    for pkg in PACKAGES:
        for p in sorted((root / pkg).rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            out[p.relative_to(root).as_posix()] = str(p.resolve())
    return out


def executable_lines(path):
    """Line numbers that start code in the module (all nested code objects).
    Docstring-only and blank lines are not counted."""
    src = Path(path).read_text(encoding="utf-8")
    try:
        code = compile(src, str(path), "exec")
    except SyntaxError:
        return set()
    lines = set()
    stack = [code]
    while stack:
        co = stack.pop()
        for _start, _end, line in co.co_lines():
            if line is not None and line > 0:
                lines.add(line)
        stack.extend(c for c in co.co_consts if hasattr(c, "co_lines"))
    # a bare docstring expression at module / class / def level is a
    # constant load, not logic; drop lines that are only string literals
    text = src.splitlines()
    return {n for n in lines
            if n <= len(text) and not _is_string_only(text[n - 1])}


def _is_string_only(line):
    s = line.strip()
    return s.startswith(('"""', "'''", 'r"""')) or s in ('"""', "'''")


class Tracer:
    """Records (file, line) for frames in the wanted files only."""

    def __init__(self, files):
        self.wanted = {os.path.normcase(v): k for k, v in files.items()}
        self.hits = {k: set() for k in files}
        self._skip = {}

    def _local(self, rel):
        hits = self.hits[rel]

        def local(frame, event, arg):
            if event == "line":
                hits.add(frame.f_lineno)
            return local
        return local

    def global_trace(self, frame, event, arg):
        if event != "call":
            return None
        fn = frame.f_code.co_filename
        rel = self._skip.get(fn, False)
        if rel is False:
            rel = self.wanted.get(os.path.normcase(os.path.abspath(fn)))
            self._skip[fn] = rel
        if rel is None:
            return None
        self.hits[rel].add(frame.f_lineno)  # the def line counts when called
        return self._local(rel)

    def start(self):
        threading.settrace(self.global_trace)
        sys.settrace(self.global_trace)

    def stop(self):
        sys.settrace(None)
        threading.settrace(None)


def ranges(nums):
    """[3, 4, 5, 9] -> "3-5, 9"."""
    out, run = [], []
    for n in sorted(nums):
        if run and n == run[-1] + 1:
            run.append(n)
            continue
        if run:
            out.append(f"{run[0]}-{run[-1]}" if len(run) > 1 else str(run[0]))
        run = [n]
    if run:
        out.append(f"{run[0]}-{run[-1]}" if len(run) > 1 else str(run[0]))
    return ", ".join(out)


def imported_by_tests(rel, tests_dir=ROOT / "tests"):
    """True when any test file names the module (import path or file name)."""
    mod = rel[:-3].replace("/", ".")
    if mod.endswith(".__init__"):
        mod = mod[:-9]
    leaf = mod.rsplit(".", 1)[-1]
    for t in tests_dir.glob("*.py"):
        text = t.read_text(encoding="utf-8", errors="replace")
        if mod in text or f"import {leaf}" in text or f"{leaf}.py" in text \
                or f" {leaf}," in text or f", {leaf}" in text:
            return True
    return False


def summarize(files, hits):
    rows = []
    for rel, path in files.items():
        exe = executable_lines(path)
        if not exe:
            continue
        hit = hits.get(rel, set()) & exe
        rows.append({"module": rel, "lines": len(exe), "hit": len(hit),
                     "pct": 100.0 * len(hit) / len(exe), "missed": sorted(exe - hit)})
    rows.sort(key=lambda r: (r["pct"], -r["lines"]))
    return rows


def render(rows, rc, took_s, date, note=""):
    total = sum(r["lines"] for r in rows)
    hit = sum(r["hit"] for r in rows)
    pct = 100.0 * hit / total if total else 0.0
    server = [r for r in rows if r["module"].startswith("server/")]
    s_total = sum(r["lines"] for r in server)
    s_pct = 100.0 * sum(r["hit"] for r in server) / s_total if s_total else 0.0
    untested = [r for r in rows if r["hit"] == 0]
    weak = [r for r in rows if 0 < r["pct"] < 60.0]
    out = [
        "# Test coverage (TEST-COVER)",
        "",
        f"Generated {date} by `python tools/cover.py` (stdlib line tracer, no",
        "coverage package). Lines run in a child process (a spawned core, the",
        "keepalive supervisor, PowerShell scripts, the Electron overlay) are not",
        "counted, so modules driven only that way read lower than they are.",
        f"pytest exit code {rc}; run took {took_s:.0f} s.",
        "",
        f"- total: {pct:.1f}% of {total} executable lines (server/ {s_pct:.1f}% of "
        f"{s_total}, tools/ the rest)",
        f"- modules with no line run: {len(untested)}",
        f"- modules under 60%: {len(weak)}",
    ]
    if note:
        out += ["", note]
    out += ["", "## Untested modules (no line run in the suite)", ""]
    out += [f"- {r['module']}: {r['lines']} lines" for r in untested] or ["- none"]
    out += ["", "## Weakest modules (under 60%)", ""]
    out += [f"- {r['module']}: {r['pct']:.1f}% of {r['lines']}" for r in weak] or ["- none"]
    out += ["", "## Every module (lowest first)", "",
            "One line per module: percent, executable lines, missed line ranges.", ""]
    for r in rows:
        miss = ranges(r["missed"])
        if len(miss) > 300:
            miss = miss[:300].rsplit(",", 1)[0] + ", ..."
        out.append(f"- {r['module']}: {r['pct']:.1f}% of {r['lines']}"
                   + (f"; missed {miss}" if miss else ""))
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--note", default=CHILD_ONLY_NOTE)
    args, rest = ap.parse_known_args(argv)
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    import pytest  # noqa: PLC0415 - only the runner needs it

    files = own_files()
    tracer = Tracer(files)
    t0 = time.monotonic()
    tracer.start()
    try:
        rc = pytest.main(["-q", "-p", "no:cacheprovider"] + (rest or []))
    finally:
        tracer.stop()
    took = time.monotonic() - t0
    rows = summarize(files, tracer.hits)
    text = render(rows, int(rc), took, time.strftime("%Y-%m-%d"), args.note)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    print(text.splitlines()[8][2:] + f" -> {Path(args.out).name}")
    return int(rc)


if __name__ == "__main__":
    sys.exit(main())
