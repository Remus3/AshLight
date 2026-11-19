#!/usr/bin/env python3
"""Test select - the test files a package must run for its diff (TEST-SELECT).

    test_select.py [--base REV]

REV defaults to `git merge-base main HEAD` (the wave base). The tool reads the
diff itself (git diff --name-only --no-renames REV, so committed and
uncommitted changes count, plus untracked files) and prints:

    base: <rev>
    changed: <n> path(s)
    ungated: <test files>            run file-named, outside the suite gate
    gated: <test files>              run file-named, THROUGH the suite gate
    env: AL_FUZZ_S=0.1               set for both runs above, never the batch
    args: -m "not calc" | none       pytest args for both runs above
    npm: npm test --prefix app | none   ungated, when app/ or web/ changed
    estimate: ungated <s> s, gated <s> s
    run-ungated: <the full command, or none>
    run-gated: <the full command with --owner <OWNER>, or none>

How a builder uses it: run the run-ungated command as printed, then the
run-gated command with its own owner id, then the npm line if it is not
none. An empty list prints "none" and is skipped.

Method (research 0049 F6, R1, R9, R11; decision 0077):
- Direct map: an ast pass over tests/ maps each test file to the product
  files it names: first-order imports (server.al.x, bare tool modules such
  as al_loop), dotted module strings, path literals (single strings, ROOT /
  "a" / "b" chains and os.path.join calls; a bare file name or a path tail
  matches at most three files), one hop through the helper modules under
  tests/ (al_loopkit, tc_live_util, tc_fixtures, tc_eval_fixtures,
  math_item_fixtures, math_live_items, play_states, srcpaths, ...), and a
  folder named by a test that walks a folder (rglob, os.walk, glob,
  iterdir) covers every file under it.
- A changed or new test file is always selected; a changed helper module
  selects its importers; a changed tests/conftest.py selects every test.
- An unknown path (no test names it) selects its whole area: the tests that
  name any file under its nearest folder that has one, up to the top folder;
  for a root file, the tests that name any root file, or every test when
  none does.
- Always run: tests/test_floor_static.py, tests/test_overlay_smoke.py
  (static part; the live smoke stays opt-in), tests/test_ascii_lf.py and
  tests/test_leak_sweep.py ungated; tests/test_budgets.py gated.
- Marks are read statically from the file text. A `timing` file is always
  gated (ruling Q-17). `calc` tests join only when the diff touches
  server/al/theorycraft/, config/tc_pins.json, a calc test file or a calc
  helper, and then every calc test file joins; otherwise a file whose module
  pytestmark is calc is dropped and the args line deselects the calc tests
  of the mixed files.
- The ungated list carries a static estimate (pytest start, per test, and
  extra for slow / git / server marked tests); over 90 s it moves into the
  gated list as a whole.
- The direct map is not sound: the merge batch's whole suite stays the
  authority. This tool never records escape rates (the wave integrator does).

Stdlib only; reads the tree and git, writes nothing. Exit 0 with the lines
above; exit 2 when git cannot give the diff.
"""

import argparse
import ast
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALWAYS_UNGATED = (
    "tests/test_floor_static.py",
    "tests/test_overlay_smoke.py",
    "tests/test_ascii_lf.py",
    "tests/test_leak_sweep.py",
)
ALWAYS_GATED = ("tests/test_budgets.py",)
CALC_TRIGGERS = ("server/al/theorycraft/", "config/tc_pins.json")
UNGATED_CAP_S = 90.0
ENV = "AL_FUZZ_S=0.1"
NOT_CALC = '-m "not calc"'
NPM = "npm test --prefix app"
NPM_AREAS = ("app/", "web/")

# Static cost model (seconds). Calibrated on research 0049 (RUN 238 s under
# load, 191 s median green; git tests about 57 s, live calc about 64 s) and a
# file-named run of the always-run list on 2026-11-19 (64 s): the whole tree
# estimates about 300 s, so the model errs on the slow side.
COST_START = 1.5       # one pytest process: start and collection
COST_FILE = 0.05       # import of one test module
COST_TEST = 0.005      # one plain test
COST_SLOW = 1.5        # extra per test marked slow (the mark's own floor)
COST_GIT = 0.3         # extra per test marked git
COST_SERVER = 0.1      # extra per test marked server
COST_CALC_FILE = 8.0   # extra per file that starts the live calc
# Seconds per case for a file whose cases are heavy but carry no mark:
# test_floor_static re-runs the whole-tree scan per case (measured 1.4 to
# 1.7 s per case in a file-named run on 2026-11-19). Research 0049 R2
# memoises the scan; drop the entry when it lands.
MEASURED_CASE_S = {"tests/test_floor_static.py": 1.5}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache"}
SKIP_REL = {"ops/runtime", "ops/loop/control"}
MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
TEST_RE = re.compile(r"^tests/test_[^/]*\.py$")
BASENAME_MAX = 3
STDLIB = set(getattr(sys, "stdlib_module_names", ())) | set(sys.builtin_module_names)


def _git(root, *args):
    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=60, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def default_base(root=ROOT):
    """The wave base: git merge-base main HEAD."""
    return _git(root, "merge-base", "main", "HEAD").strip()


def changed_paths(root=ROOT, base=None, head=None):
    """Repo-relative '/' paths changed from base to head (head None: the
    working tree plus untracked files). Renames count as delete + add."""
    if head is None:
        out = _git(root, "diff", "--name-only", "--no-renames", base)
        out += _git(root, "ls-files", "--others", "--exclude-standard")
    else:
        out = _git(root, "diff", "--name-only", "--no-renames", base, head)
    return sorted({line.strip().replace("\\", "/") for line in out.splitlines()
                   if line.strip()})


# ---------------------------------------------------------------- the index

def file_index(root):
    """Every file under root (repo-relative '/'), skipping caches, deps and
    the runtime folders."""
    found = []
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and (f"{rel_dir}/{d}" if rel_dir else d) not in SKIP_REL)
        for name in filenames:
            found.append(f"{rel_dir}/{name}" if rel_dir else name)
    return sorted(found)


class Index:
    """Lookups over the file list: exact path, basename, path tail, module."""

    def __init__(self, root, files):
        self.root = Path(root)
        self.files = set(files)
        self.by_name = {}
        self.by_stem = {}
        self.by_tail = {}
        for rel in files:
            parts = rel.split("/")
            for i in range(1, len(parts) - 1):
                self.by_tail.setdefault("/".join(parts[i:]), []).append(rel)
            name = rel.rsplit("/", 1)[-1]
            self.by_name.setdefault(name, []).append(rel)
            if name.endswith(".py"):
                self.by_stem.setdefault(name[:-3], []).append(rel)
        self.dirs = set()
        for rel in files:
            parts = rel.split("/")[:-1]
            for i in range(1, len(parts) + 1):
                self.dirs.add("/".join(parts[:i]))

    def resolve_path(self, text):
        """(files, dirs) a path literal names."""
        s = text.strip().replace("\\", "/")
        while s.startswith("./"):
            s = s[2:]
        s = s.strip("/")
        if not s or len(s) > 200 or "\n" in s or " " in s or "*" in s:
            return set(), set()
        if s in self.files:
            return {s}, set()
        if s in self.dirs:
            return set(), {s}
        if "/" in s:
            hits = self.by_tail.get(s, [])
        else:
            hits = self.by_name.get(s, []) if "." in s else []
        if 0 < len(hits) <= BASENAME_MAX:
            return set(hits), set()
        return set(), set()

    def resolve_module(self, dotted):
        """Files a dotted module name maps to (module file or package init)."""
        rel = dotted.replace(".", "/")
        for cand in (rel + ".py", rel + "/__init__.py"):
            if cand in self.files:
                return {cand}
        return set()

    def resolve_bare(self, name):
        """A top-level import name that is not a package: the repo's own
        module files of that stem (tools/x.py, tests/x.py, ...), at most
        three; stdlib names never match."""
        if name in STDLIB:
            return set()
        hits = self.by_stem.get(name, [])
        if 0 < len(hits) <= BASENAME_MAX:
            return set(hits)
        return set()


# ------------------------------------------------------------- the ast pass

def _div_chain(node):
    """The string parts of an `a / "b" / "c"` chain (outermost node)."""
    parts = []
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        if isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
            parts.append(node.right.value)
        else:
            return []
        node = node.left
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        parts.append(node.value)
    return list(reversed(parts))


def _strings(tree):
    """Path-like strings: every str constant, every / chain and every
    os.path.join(...) of constants."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            parts = _div_chain(node)
            if len(parts) > 1:
                out.add("/".join(parts))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "join":
                parts = [a.value for a in node.args
                         if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                if len(parts) > 1:
                    out.add("/".join(parts))
    return out


def _imports(tree):
    """(dotted names, bare top-level names) imported by the module."""
    dotted, bare = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "." in alias.name:
                    dotted.add(alias.name)
                else:
                    bare.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            if "." in node.module or node.module == "server":
                dotted.add(node.module)
                for alias in node.names:
                    dotted.add(f"{node.module}.{alias.name}")
            else:
                bare.add(node.module)
    return dotted, bare


WALK_ATTRS = {"rglob", "glob", "iterdir", "walk"}


def _assignments(tree):
    """name -> [value expr] for plain `name = expr` and for-loop targets over
    a literal tuple or list."""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.setdefault(t.id, []).append(node.value)
        elif isinstance(node, (ast.For, ast.comprehension)):
            target, it = node.target, node.iter
            if isinstance(target, ast.Name) and isinstance(it, (ast.Tuple, ast.List)):
                out.setdefault(target.id, []).extend(it.elts)
    return out


def _resolve(expr, assigns, depth=0):
    """The repo-relative path strings an expression can stand for: '' is the
    repo root (an unresolved UPPER-case name such as ROOT), nothing when it
    is unknown (a tmp_path, a parameter)."""
    if depth > 6:
        return []
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return [expr.value]
    if isinstance(expr, ast.Name):
        out = []
        for v in assigns.get(expr.id, ()):
            out += _resolve(v, assigns, depth + 1)
        if not out and expr.id.isupper():
            out = [""]
        return out
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div):
        lefts = _resolve(expr.left, assigns, depth + 1)
        rights = _resolve(expr.right, assigns, depth + 1)
        return [f"{a}/{b}".strip("/") for a in lefts for b in rights]
    if isinstance(expr, ast.Call):
        func = expr.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in ("Path", "PurePath", "str") and expr.args:
            return _resolve(expr.args[0], assigns, depth + 1)
    return []


def _walked(tree):
    """Folders the module walks: the receiver of .rglob / .glob / .iterdir /
    .walk and the first argument of os.walk / glob.glob, when it resolves to
    a repo folder other than the root."""
    assigns = _assignments(tree)
    out = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        func = node.func
        if func.attr not in WALK_ATTRS:
            continue
        mod = getattr(func.value, "id", "")
        if mod in ("os", "glob"):
            target = node.args[0] if node.args else None
        else:
            target = func.value
        if target is None:
            continue
        for s in _resolve(target, assigns):
            s = s.split("*", 1)[0].rstrip("/")
            if s:
                out.add(s)
    return out


def _mark_names(tree):
    """Marks the code itself uses (never words inside a string): the X of
    every `<...>.mark.X` attribute, plus the calc helper names CALC_MARKS and
    LIVE_CALC."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)                 and node.value.attr == "mark":
            out.add(node.attr)
        elif isinstance(node, ast.Name) and node.id in ("CALC_MARKS", "LIVE_CALC"):
            out.add(node.id)
        elif isinstance(node, ast.alias) and node.name in ("CALC_MARKS", "LIVE_CALC"):
            out.add(node.name)
    return out


class Info:
    """What one tests/ module names, and its static marks and cost."""

    def __init__(self, rel):
        self.rel = rel
        self.files = set()
        self.dirs = set()
        self.helpers = set()
        self.timing = False
        self.calc = False
        self.calc_only = False
        self.cost = 0.0


PARAM_UNKNOWN = 3  # cases assumed for a parametrize list the ast cannot size


def _cases(dec, sizes):
    """How many cases one decorator adds (1 unless it is a parametrize)."""
    if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
            and dec.func.attr == "parametrize"):
        return 1
    values = dec.args[1] if len(dec.args) > 1 else next(
        (k.value for k in dec.keywords if k.arg == "argvalues"), None)
    if isinstance(values, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return max(1, len(values.elts if not isinstance(values, ast.Dict) else values.keys))
    if isinstance(values, ast.Name) and values.id in sizes:
        return max(1, sizes[values.id])
    return PARAM_UNKNOWN


def _count_marks(text, tree):
    """(test cases, {mark: marked cases}) with parametrize lists expanded."""
    sizes = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(
                node.value, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            n = len(node.value.keys if isinstance(node.value, ast.Dict) else node.value.elts)
            for t in node.targets:
                if isinstance(t, ast.Name):
                    sizes[t.id] = n
    tests = 0
    marked = {"slow": 0, "git": 0, "server": 0}
    module = {"slow": False, "git": False, "server": False}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            seg = ast.get_source_segment(text, node) or ""
            for key in module:
                if f"mark.{key}" in seg:
                    module[key] = True
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and                 node.name.startswith("test"):
            cases = 1
            for dec in node.decorator_list:
                cases *= _cases(dec, sizes)
            tests += cases
            for dec in node.decorator_list:
                seg = ast.get_source_segment(text, dec) or ""
                for key in marked:
                    if f"mark.{key}" in seg:
                        marked[key] += cases
    for key in marked:
        if module[key]:
            marked[key] = tests
    return tests, marked


def scan_module(index, rel):
    """The Info of one module under tests/."""
    info = Info(rel)
    path = index.root / rel
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text, filename=rel)
    except (OSError, SyntaxError, ValueError):
        return info
    dotted, bare = _imports(tree)
    for name in dotted:
        info.files |= index.resolve_module(name)
    for name in bare:
        hits = index.resolve_bare(name)
        for hit in hits:
            if hit.startswith("tests/") and hit != rel:
                info.helpers.add(hit)
        info.files |= hits
    for s in _strings(tree):
        if MODULE_RE.match(s) and "/" not in s:
            hits = index.resolve_module(s)
            if hits:
                info.files |= hits
                continue
        files, _dirs = index.resolve_path(s)
        info.files |= files
    for s in _walked(tree):
        files, dirs = index.resolve_path(s)
        info.dirs |= dirs
        info.files |= files
    info.files.discard(rel)
    marks = _mark_names(tree)
    info.timing = "timing" in marks
    info.calc = bool(marks & {"calc", "CALC_MARKS", "LIVE_CALC"})
    module_calc = False
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            seg = ast.get_source_segment(text, node) or ""
            if "CALC_MARKS" in seg or "mark.calc" in seg:
                module_calc = True
    info.calc_only = module_calc
    tests, marked = _count_marks(text, tree)
    per_case = MEASURED_CASE_S.get(rel, COST_TEST)
    info.cost = (COST_FILE + per_case * tests + COST_SLOW * marked["slow"]
                 + COST_GIT * marked["git"] + COST_SERVER * marked["server"]
                 + (COST_CALC_FILE if info.calc else 0.0))
    return info


class DirectMap:
    """The direct map of every test file under root/tests."""

    def __init__(self, root=ROOT, files=None):
        self.root = Path(root)
        files = file_index(self.root) if files is None else sorted(files)
        self.index = Index(self.root, files)
        self.modules = {}
        for rel in files:
            if rel.startswith("tests/") and rel.count("/") == 1 and rel.endswith(".py"):
                self.modules[rel] = scan_module(self.index, rel)
        self.tests = sorted(r for r in self.modules if TEST_RE.match(r))
        # One hop through helper modules (and the allowed test-to-test
        # imports): a test names what its helpers name.
        self.covers = {}
        for rel in self.tests:
            info = self.modules[rel]
            files, dirs = set(info.files), set(info.dirs)
            for helper in info.helpers:
                h = self.modules.get(helper)
                if h is not None:
                    files |= h.files
                    dirs |= h.dirs
            self.covers[rel] = (files, dirs)

    def importers(self, helper):
        """Test files that import the helper module, directly or through
        other helper modules."""
        reach = {helper}
        grew = True
        while grew:
            grew = False
            for rel, info in self.modules.items():
                if rel not in reach and not TEST_RE.match(rel) and info.helpers & reach:
                    reach.add(rel)
                    grew = True
        return {rel for rel in self.tests if self.modules[rel].helpers & reach}

    def tests_for(self, path):
        """Test files that name path directly (file, or a walked folder)."""
        out = set()
        for rel, (files, dirs) in self.covers.items():
            if path in files or any(path == d or path.startswith(d + "/") for d in dirs):
                out.add(rel)
        return out

    def tests_under(self, prefix):
        """Test files that name any file under the folder prefix."""
        out = set()
        pre = prefix + "/"
        for rel, (files, dirs) in self.covers.items():
            if any(f.startswith(pre) for f in files) or any(
                    d == prefix or d.startswith(pre) or pre.startswith(d + "/")
                    for d in dirs):
                out.add(rel)
        return out

    def tests_at_root(self):
        """Test files that name a file in the repo root."""
        return {rel for rel, (files, _d) in self.covers.items()
                if any("/" not in f for f in files)}

    def area(self, path):
        """The tests of path's nearest folder that has any, up to the top
        folder; a root file with none selects every test."""
        parts = path.split("/")[:-1]
        while parts:
            hit = self.tests_under("/".join(parts))
            if hit:
                return hit
            parts.pop()
        hit = self.tests_at_root() if "/" not in path else set()
        return hit or set(self.tests)


# -------------------------------------------------------------- the select

class Selection:
    def __init__(self):
        self.ungated = []
        self.gated = []
        self.args = ""
        self.npm = False
        self.est_ungated = 0.0
        self.est_gated = 0.0
        self.moved = False
        self.calc_on = False


def select(changed, tmap):
    """The Selection for a list of changed repo-relative paths."""
    picked = set()
    calc_on = False
    for path in changed:
        if any(path.startswith(t) or path == t for t in CALC_TRIGGERS):
            calc_on = True
        if path == "tests/conftest.py":
            picked |= set(tmap.tests)
            continue
        if TEST_RE.match(path):
            if path in tmap.modules:
                picked.add(path)
                if tmap.modules[path].calc:
                    calc_on = True
            continue
        if path in tmap.modules:  # a helper module under tests/
            if tmap.modules[path].calc:
                calc_on = True
            picked |= tmap.importers(path) or set(tmap.tests)
            continue
        direct = tmap.tests_for(path)
        picked |= direct if direct else tmap.area(path)
    if calc_on:  # the calc leg is what a trigger is for: every calc file joins
        picked |= {r for r in tmap.tests if tmap.modules[r].calc}
    picked |= {t for t in ALWAYS_UNGATED + ALWAYS_GATED if t in tmap.modules}
    sel = Selection()
    sel.calc_on = calc_on
    mixed_calc = False
    ungated, gated = [], []
    for rel in sorted(picked):
        info = tmap.modules[rel]
        if info.calc and not calc_on:
            if info.calc_only:
                continue
            mixed_calc = True
        if rel in ALWAYS_GATED or info.timing:
            gated.append(rel)
        else:
            ungated.append(rel)
    sel.args = NOT_CALC if mixed_calc else ""

    def est(files):
        if not files:
            return 0.0
        return COST_START + sum(tmap.modules[f].cost for f in files)

    sel.est_ungated = est(ungated)
    if sel.est_ungated > UNGATED_CAP_S:
        gated = sorted(set(gated) | set(ungated))
        ungated = []
        sel.moved = True
        sel.est_ungated = 0.0
    sel.ungated, sel.gated = ungated, gated
    sel.est_gated = est(gated)
    sel.npm = any(p.startswith(NPM_AREAS) for p in changed)
    return sel


def render(base, changed, sel):
    """The printed lines."""
    def joined(files):
        return " ".join(files) if files else "none"

    args = (sel.args + " ") if sel.args else ""
    lines = [
        f"base: {base}",
        f"changed: {len(changed)} path(s)",
        f"ungated: {joined(sel.ungated)}",
        f"gated: {joined(sel.gated)}",
        f"env: {ENV}",
        f"args: {sel.args or 'none'}",
        f"npm: {NPM if sel.npm else 'none'}",
        f"estimate: ungated {sel.est_ungated:.1f} s, gated {sel.est_gated:.1f} s"
        + (" (ungated list over 90 s moved to gated)" if sel.moved else ""),
        "run-ungated: " + (f"{ENV} python -m pytest -q {args}{joined(sel.ungated)}"
                           if sel.ungated else "none"),
        "run-gated: " + (
            f"{ENV} python ops/fleet_kit/fleet_suite_gate.py run --owner <OWNER> -- "
            f"python -m pytest -q {args}{joined(sel.gated)}" if sel.gated else "none"),
    ]
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="test_select.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=None,
                    help="the diff base (default: git merge-base main HEAD)")
    ns = ap.parse_args(argv)
    try:
        base = ns.base or default_base(ROOT)
        changed = changed_paths(ROOT, base)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"test_select: {exc}", file=sys.stderr)
        return 2
    sel = select(changed, DirectMap(ROOT))
    for line in render(base, changed, sel):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
