#!/usr/bin/env python3
"""Plan check - validates docs/plan/packages.json and prints its ROADMAP rows.

    plan_check.py check [--file F]              exit 0 "plan_check: ok <n> packages,
                                                <w> waves", else exit 1, one line
                                                per problem
    plan_check.py rows [--file F] [--wave N]    one ROADMAP row per package, wave
                                                then merge order, wrapped at 100
    plan_check.py wave N [--file F] [--json]    that wave's packages in merge order

rows and wave refuse (exit 1, problems on stderr) when the plan does not pass
check. Stdlib only; reads the file, writes nothing.

FILE SCHEMA (schema 1), one JSON object:

    {"schema": 1, "generated": "<date>",
     "integrator_files": [path, ...],
     "hotspots": [...],
     "waves": [{"n": int, "title": str, "goal": str,
                "merge_order": [package id, ...], "gate": str}],
     "packages": [{PACKAGE FIELDS, "wave": int}],
     "coverage": {unit id: [package id, ...] | "not_adopted: ..." |
                  "operator: ..." | "done: ..."}}

PACKAGE FIELDS:
    id              str, ^[A-Z0-9]+(-[A-Z0-9]+)*$ (loop-safe), unique
    title, goal     str (title non-empty)
    units           [unit id] - input units this package delivers
    files           [path] - tracked files it edits (repo-relative, "/")
    new_files       [path] - files it creates
    integrator_edits [{"file", "change"}] - edits to the shared files only the
                    wave integrator makes (INTEGRATOR_FILES plus the plan's
                    integrator_files); those files never sit in files or
                    new_files. A new decision gives its title, the Settled
                    bullet text and its Reverses if in "change".
    tests           [str] non-empty - test files or functions added / changed
    accept          str non-empty - one sentence, checkable by a command
    zero_click      str non-empty - how it runs with no player click in play,
                    or how the dev step runs itself; never bends the ToS floor
    size            "S" | "M" | "L" (under 30, 30-60, 60-90 minutes)
    est_min         int, 1..90
    deps            [package id]
    serial_group    str, may be empty; packages editing one file share it
    agent           str
    isolation       "worktree" | "none"
    lane            "build" | "data" | "review"
    design_review   bool
    blocked         null | {"on", "who", "unblock"} (all non-empty str)
    operator_act    str, may be empty
    notes           str, may be empty
    wave            int, the n of a listed wave (99 = parked)

CHECKS: required fields present and typed; every string ASCII; ids unique and
loop-safe; paths repo-relative with forward slashes; every dep is a package id;
no dependency cycle; a dep sits in a strictly earlier wave (a package in the
parked wave 99 is exempt); inside a wave no path shared by two packages across
files and new_files and no non-empty serial_group shared; no integrator file
in files or new_files; integrator_edits name only integrator files; tests,
accept and zero_click non-empty; size in S M L and est_min at most 90; lane in
build data review; blocked has on, who and unblock and a blocked package sits
in wave 99; each wave's merge_order is exactly its packages; every package
unit appears in coverage (and a coverage list for it names the package);
every coverage list names existing packages; coverage strings start with
"not_adopted:", "operator:" or "done:".
"""

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "docs" / "plan" / "packages.json"
SCHEMA = 1
PARKED_WAVE = 99
WIDTH = 100
ID_RE = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)*$")
INTEGRATOR_FILES = (
    "ROADMAP.md",
    "CLAUDE.md",
    "AL-NEXT-SESSION.txt",
    "docs/decisions/README.md",
    "docs/research/README.md",
    "docs/plan/README.md",
)
SIZES = ("S", "M", "L")
LANES = ("build", "data", "review")
ISOLATIONS = ("worktree", "none")
COVERAGE_PREFIXES = ("not_adopted:", "operator:", "done:")
MAX_EST_MIN = 90

TOP_FIELDS = {
    "schema": int, "generated": str, "integrator_files": list,
    "hotspots": list, "waves": list, "packages": list, "coverage": dict,
}
WAVE_FIELDS = {"n": int, "title": str, "goal": str, "merge_order": list,
               "gate": str}
# "strlist" = list of str; None for blocked is checked by hand
PACKAGE_FIELDS = {
    "id": str, "title": str, "goal": str, "units": "strlist",
    "files": "strlist", "new_files": "strlist", "integrator_edits": list,
    "tests": "strlist", "accept": str, "zero_click": str, "size": str,
    "est_min": int, "deps": "strlist", "serial_group": str, "agent": str,
    "isolation": str, "lane": str, "design_review": bool, "blocked": "blocked",
    "operator_act": str, "notes": str, "wave": int,
}


def _typed(value, kind):
    if kind == "strlist":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if kind == "blocked":
        return value is None or isinstance(value, dict)
    if kind is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, kind)


def _kind_name(kind):
    if kind == "strlist":
        return "a list of strings"
    if kind == "blocked":
        return "null or an object"
    return {int: "an integer", str: "a string", bool: "a boolean", list: "a list",
            dict: "an object"}[kind]


def _non_ascii(obj, where, out):
    if isinstance(obj, str):
        if not obj.isascii():
            out.append(f"{where}: non-ASCII text")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _non_ascii(v, f"{where}[{i}]", out)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and not k.isascii():
                out.append(f"{where}: non-ASCII key")
            _non_ascii(v, f"{where}.{k}", out)


def _path_problem(path):
    if not path:
        return "empty path"
    if "\\" in path:
        return "backslash in path"
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return "absolute path"
    if any(part in ("", ".", "..") for part in path.split("/")):
        return "path not normalized"
    return ""


def _strs(p, key):
    v = p.get(key)
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def _wave_of(p):
    w = p.get("wave")
    return w if _typed(w, int) else None


def check_package(p, integrator):
    """Problems of one package on its own (fields, types, values)."""
    out = []
    pid = p.get("id") if isinstance(p.get("id"), str) else "?"
    tag = f"package {pid}"
    for key, kind in PACKAGE_FIELDS.items():
        if key not in p:
            out.append(f"{tag}: missing field {key}")
        elif not _typed(p[key], kind):
            out.append(f"{tag}: field {key} must be {_kind_name(kind)}")
    if isinstance(p.get("id"), str) and not ID_RE.match(p["id"]):
        out.append(f"{tag}: id is not loop-safe (^[A-Z0-9]+(-[A-Z0-9]+)*$)")
    if isinstance(p.get("title"), str) and not p["title"].strip():
        out.append(f"{tag}: title is empty")
    for key in ("accept", "zero_click"):
        if isinstance(p.get(key), str) and not p[key].strip():
            out.append(f"{tag}: {key} is empty")
    if _typed(p.get("tests"), "strlist") and not [t for t in p["tests"] if t.strip()]:
        out.append(f"{tag}: tests is empty")
    if isinstance(p.get("size"), str) and p["size"] not in SIZES:
        out.append(f"{tag}: size {p['size']!r} not in S M L")
    est = p.get("est_min")
    if _typed(est, int) and not 1 <= est <= MAX_EST_MIN:
        out.append(f"{tag}: est_min {est} outside 1..{MAX_EST_MIN}")
    if isinstance(p.get("lane"), str) and p["lane"] not in LANES:
        out.append(f"{tag}: lane {p['lane']!r} not in build data review")
    if isinstance(p.get("isolation"), str) and p["isolation"] not in ISOLATIONS:
        out.append(f"{tag}: isolation {p['isolation']!r} not in worktree none")
    for key in ("files", "new_files"):
        for path in _strs(p, key):
            why = _path_problem(path)
            if why:
                out.append(f"{tag}: {key} {path!r}: {why}")
            if path in integrator:
                out.append(f"{tag}: integrator file {path} in {key}"
                           " (use integrator_edits)")
    edits = p.get("integrator_edits")
    if isinstance(edits, list):
        for i, e in enumerate(edits):
            if not isinstance(e, dict) or not isinstance(e.get("file"), str) \
                    or not isinstance(e.get("change"), str):
                out.append(f"{tag}: integrator_edits[{i}] needs file and change strings")
                continue
            if e["file"] not in integrator:
                out.append(f"{tag}: integrator_edits names {e['file']}, not an"
                           " integrator file")
            if not e["change"].strip():
                out.append(f"{tag}: integrator_edits[{i}] change is empty")
    blocked = p.get("blocked")
    if isinstance(blocked, dict):
        for key in ("on", "who", "unblock"):
            v = blocked.get(key)
            if not isinstance(v, str) or not v.strip():
                out.append(f"{tag}: blocked needs a non-empty {key}")
        if _wave_of(p) is not None and _wave_of(p) != PARKED_WAVE:
            out.append(f"{tag}: blocked but in wave {_wave_of(p)}, not {PARKED_WAVE}")
    return out


def _cycles(graph):
    """One line per back edge found: 'A -> B -> A'."""
    out, color, stack = [], {}, []

    def visit(node):
        color[node] = 1
        stack.append(node)
        for nxt in graph.get(node, ()):
            if color.get(nxt) == 1:
                ring = stack[stack.index(nxt):] + [nxt]
                out.append(" -> ".join(ring))
            elif nxt not in color:
                visit(nxt)
        stack.pop()
        color[node] = 2

    for node in sorted(graph):
        if node not in color:
            visit(node)
    return out


def check_plan(plan):
    """All problems of a parsed plan, one string each; [] when it passes."""
    if not isinstance(plan, dict):
        return ["plan: top level must be a JSON object"]
    out = []
    for key, kind in TOP_FIELDS.items():
        if key not in plan:
            out.append(f"plan: missing field {key}")
        elif not _typed(plan[key], kind):
            out.append(f"plan: field {key} must be {_kind_name(kind)}")
    if _typed(plan.get("schema"), int) and plan["schema"] != SCHEMA:
        out.append(f"plan: schema {plan['schema']} is not {SCHEMA}")
    _non_ascii(plan, "plan", out)
    integrator = set(INTEGRATOR_FILES)
    if isinstance(plan.get("integrator_files"), list):
        integrator.update(f for f in plan["integrator_files"] if isinstance(f, str))

    packages, by_id = [], {}
    for i, p in enumerate(plan.get("packages") or []
                          if isinstance(plan.get("packages"), list) else []):
        if not isinstance(p, dict):
            out.append(f"packages[{i}]: must be an object")
            continue
        packages.append(p)
        out.extend(check_package(p, integrator))
        pid = p.get("id")
        if isinstance(pid, str):
            if pid in by_id:
                out.append(f"package {pid}: duplicate id")
            else:
                by_id[pid] = p

    waves, wave_ns = [], set()
    for i, w in enumerate(plan.get("waves") or []
                          if isinstance(plan.get("waves"), list) else []):
        if not isinstance(w, dict):
            out.append(f"waves[{i}]: must be an object")
            continue
        tag = f"wave {w.get('n', '?')}"
        for key, kind in WAVE_FIELDS.items():
            if key not in w:
                out.append(f"{tag}: missing field {key}")
            elif not _typed(w[key], kind):
                out.append(f"{tag}: field {key} must be {_kind_name(kind)}")
        if _typed(w.get("n"), int):
            if w["n"] in wave_ns:
                out.append(f"{tag}: duplicate wave number")
            wave_ns.add(w["n"])
            waves.append(w)

    # deps: known ids, no cycle, strictly earlier wave
    graph = {}
    for pid, p in by_id.items():
        deps = _strs(p, "deps")
        graph[pid] = [d for d in deps if d in by_id]
        for d in deps:
            if d not in by_id:
                out.append(f"package {pid}: dep {d} is not a package id")
                continue
            pw, dw = _wave_of(p), _wave_of(by_id[d])
            if pw is None or dw is None or pw == PARKED_WAVE:
                continue
            if not dw < pw:
                out.append(f"package {pid}: dep {d} is in wave {dw}, not before"
                           f" wave {pw}")
    for ring in _cycles(graph):
        out.append(f"dependency cycle: {ring}")

    # per wave: membership, merge order, shared paths and serial groups
    members = {}
    for pid, p in by_id.items():
        pw = _wave_of(p)
        if pw is None:
            continue
        if pw not in wave_ns:
            out.append(f"package {pid}: wave {pw} is not a listed wave")
        members.setdefault(pw, []).append(pid)
    for w in waves:
        n = w["n"]
        order = w.get("merge_order")
        if not _typed(order, "strlist"):
            continue
        for d in sorted({x for x in order if order.count(x) > 1}):
            out.append(f"wave {n}: merge_order lists {d} twice")
        expected = set(members.get(n, []))
        for x in order:
            if x not in expected:
                out.append(f"wave {n}: merge_order names {x}, not a package of"
                           " this wave")
        for x in sorted(expected - set(order)):
            out.append(f"wave {n}: package {x} missing from merge_order")
    for n, ids in sorted(members.items()):
        owner, groups = {}, {}
        for pid in ids:
            p = by_id[pid]
            for path in dict.fromkeys(_strs(p, "files") + _strs(p, "new_files")):
                if path in owner:
                    out.append(f"wave {n}: {owner[path]} and {pid} both touch {path}")
                else:
                    owner[path] = pid
            sg = p.get("serial_group")
            if isinstance(sg, str) and sg.strip():
                if sg in groups:
                    out.append(f"wave {n}: {groups[sg]} and {pid} share serial_group"
                               f" {sg}")
                else:
                    groups[sg] = pid

    # coverage
    coverage = plan.get("coverage") if isinstance(plan.get("coverage"), dict) else {}
    for unit, v in coverage.items():
        if isinstance(v, list):
            if not v:
                out.append(f"coverage {unit}: empty package list")
            for x in v:
                if not isinstance(x, str) or x not in by_id:
                    out.append(f"coverage {unit}: {x!r} is not a package id")
        elif isinstance(v, str):
            if not v.startswith(COVERAGE_PREFIXES):
                out.append(f"coverage {unit}: string must start with not_adopted:,"
                           " operator: or done:")
        else:
            out.append(f"coverage {unit}: must be a package list or a string")
    for pid, p in by_id.items():
        for unit in _strs(p, "units"):
            if unit not in coverage:
                out.append(f"package {pid}: unit {unit} missing from coverage")
            elif isinstance(coverage[unit], list) and pid not in coverage[unit]:
                out.append(f"package {pid}: coverage {unit} does not name it")
    return out


def load(path):
    """(plan, problems): problems is non-empty when the file is unreadable."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, [f"plan: cannot read {path.name}: {e.__class__.__name__}"]
    try:
        return json.loads(text), []
    except ValueError as e:
        return None, [f"plan: invalid JSON: {e}"]


def ordered(plan, wave=None):
    """Packages in wave order, then each wave's merge order."""
    by_id = {p["id"]: p for p in plan["packages"]}
    out = []
    for w in sorted(plan["waves"], key=lambda w: w["n"]):
        if wave is not None and w["n"] != wave:
            continue
        out.extend(by_id[x] for x in w["merge_order"])
    return out


def _sentence(text):
    text = " ".join(text.split())
    return text if text.endswith((".", "!", "?")) else text + "."


def row(p):
    """One ROADMAP row, wrapped at 100 columns with 2-space continuations."""
    title = " ".join(p["title"].split()).rstrip(".")
    text = (f"- [ ] {p['id']} ({p['lane']}) {title}. ACCEPT: {_sentence(p['accept'])}"
            f" ZERO-CLICK: {_sentence(p['zero_click'])}")
    b = p.get("blocked")
    if b:
        on = " ".join(b["on"].split()).rstrip(".")
        unblock = " ".join(b["unblock"].split()).rstrip(".")
        who = " ".join(b["who"].split())
        text += f" BLOCKED: {on}; unblocks when {unblock} ({who})."
    return textwrap.fill(text, width=WIDTH, subsequent_indent="  ",
                         break_long_words=False, break_on_hyphens=False)


def wave_info(plan, n):
    w = next((w for w in plan["waves"] if w["n"] == n), None)
    if w is None:
        return None
    keys = ("id", "title", "lane", "files", "new_files", "deps", "tests", "agent",
            "size", "est_min", "design_review", "isolation", "serial_group")
    return {"n": n, "title": w["title"], "goal": w["goal"], "gate": w["gate"],
            "packages": [{k: p[k] for k in keys} for p in ordered(plan, n)]}


def _valid(path):
    plan, problems = load(path)
    if not problems:
        problems = check_plan(plan)
    for line in problems:
        print(line, file=sys.stderr)
    return None if problems else plan


def main(argv=None):
    ap = argparse.ArgumentParser(prog="plan_check",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--file", default=str(DEFAULT_FILE))
    r = sub.add_parser("rows")
    r.add_argument("--file", default=str(DEFAULT_FILE))
    r.add_argument("--wave", type=int)
    w = sub.add_parser("wave")
    w.add_argument("n", type=int)
    w.add_argument("--file", default=str(DEFAULT_FILE))
    w.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "check":
        plan, problems = load(a.file)
        if not problems:
            problems = check_plan(plan)
        if problems:
            for line in problems:
                print(line)
            return 1
        print(f"plan_check: ok {len(plan['packages'])} packages,"
              f" {len(plan['waves'])} waves")
        return 0
    plan = _valid(a.file)
    if plan is None:
        return 1
    if a.cmd == "rows":
        if a.wave is not None and a.wave not in {w["n"] for w in plan["waves"]}:
            print(f"plan_check: no wave {a.wave}", file=sys.stderr)
            return 1
        for p in ordered(plan, a.wave):
            print(row(p))
        return 0
    info = wave_info(plan, a.n)
    if info is None:
        print(f"plan_check: no wave {a.n}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(info, indent=2))
        return 0
    print(f"wave {info['n']}: {info['title']} (gate: {info['gate']})")
    for p in info["packages"]:
        print(f"{p['id']} ({p['lane']}, {p['size']} {p['est_min']}m, agent"
              f" {p['agent']}, design_review {str(p['design_review']).lower()})")
        print(f"  files: {', '.join(p['files'] + p['new_files']) or '-'}")
        print(f"  deps: {', '.join(p['deps']) or '-'}")
        print(f"  tests: {', '.join(p['tests']) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
