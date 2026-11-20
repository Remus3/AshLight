#!/usr/bin/env python3
"""Docs fresh (AUTO-14, F-146): facts the docs quote, computed from the tree.

    docs_fresh.py check [--root DIR]

Each fact reads its source value from the tree (a code pin, a constant, a
manifest field) and matches it where a doc quotes it. A quote that differs,
or a required quote that is gone, is stale. Exit 0 with one summary line
when every fact holds; exit 1 with one line per stale quote, each starting
with the file that holds it, then one line naming every stale file; exit 2
on a usage error.

The fact table is FACTS, a list of small functions `fact(tree) -> [problem]`
(problem = "<path>: <fact>: <text>"). Later packages append to it
(TEST-DOCS-INDEX, TEST-DOCS-FACTS-UI); every fact has its fixture test in
tests/test_docs_fresh.py.

Facts today (source -> docs matched):
- electron pin: app/package.json electron dependency -> the app/main.js
  header comment and the Decision section of docs/decisions/0002-stack.md.
  Dated 'Measured' sections and research notes are history, not checked.
- version: server/al/__init__.py VERSION -> app/package.json "version" and
  app/package-lock.json (top-level and packages[""]).
- python floor, node floor: the floors scripts/setup.ps1 checks -> the
  README.md quick start.
- port block: server/al/ports.py AL_PORT and PORT_BLOCK -> README.md.
- kit version: ops/fleet_kit/MANIFEST.json "version" -> the AL rules
  'Kit: v<N>' line of CLAUDE.md (when it still quotes one) and every
  'kit v<N>' of docs/design/0001-design-system.md.
- script names: scripts/setup.ps1, build.ps1 and run.ps1 exist, and every
  scripts\\<name>.ps1 README.md names exists.
- not-affiliated statement: server/al/__init__.py DISCLAIMER verbatim in
  README.md.

Reads named tracked files only; makes no request and writes nothing.
Stdlib only.
"""
import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INIT_REL = "server/al/__init__.py"
PORTS_REL = "server/al/ports.py"
PKG_REL = "app/package.json"
LOCK_REL = "app/package-lock.json"
MAIN_JS_REL = "app/main.js"
STACK_REL = "docs/decisions/0002-stack.md"
SETUP_REL = "scripts/setup.ps1"
README_REL = "README.md"
MANIFEST_REL = "ops/fleet_kit/MANIFEST.json"
CLAUDE_REL = "CLAUDE.md"
DESIGN_REL = "docs/design/0001-design-system.md"
SCRIPTS = ("setup.ps1", "build.ps1", "run.ps1")

# Every file a fact reads (the test copies these into a fixture root).
INPUTS = (INIT_REL, PORTS_REL, PKG_REL, LOCK_REL, MAIN_JS_REL, STACK_REL,
          SETUP_REL, README_REL, MANIFEST_REL, CLAUDE_REL, DESIGN_REL,
          *(f"scripts/{name}" for name in SCRIPTS))

_DOTTED = r"(\d+(?:\.\d+)+)"


class Tree:
    """Read access to one tree; a missing file reads as None."""

    def __init__(self, root):
        self.root = Path(root)
        self._cache = {}

    def text(self, rel):
        if rel not in self._cache:
            try:
                self._cache[rel] = (self.root / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                self._cache[rel] = None
        return self._cache[rel]

    def json(self, rel):
        text = self.text(rel)
        if text is None:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def py_constants(self, rel):
        """Module-level NAME = <literal> assignments of a Python file."""
        text = self.text(rel)
        if text is None:
            return None
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return None
        out = {}
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)):
                try:
                    out[node.targets[0].id] = ast.literal_eval(node.value)
                except ValueError:
                    continue
        return out

    def exists(self, rel):
        return (self.root / rel).is_file()


def _missing(rel, fact, what="file missing"):
    return f"{rel}: {fact}: {what}"


def _match(tree, rel, fact, pattern, expected, region=None, required=True,
           what="quote"):
    """Problems for every quote of `pattern` (group 1) in rel that is not
    `expected`; with required, a file without any quote is stale too."""
    text = tree.text(rel)
    if text is None:
        return [_missing(rel, fact)]
    if region is not None:
        text = region(text)
    found = re.findall(pattern, text)
    problems = [f"{rel}: {fact}: {what} reads {got!r}, the tree has "
                f"{expected!r}" for got in found if got != str(expected)]
    if required and not found:
        problems.append(f"{rel}: {fact}: no {what} found (the tree has "
                        f"{expected!r})")
    return problems


def _first_block_comment(text):
    start = text.find("/*")
    end = text.find("*/", start)
    return text[start:end] if start >= 0 and end > start else ""


def _md_section(heading):
    def region(text):
        m = re.search(rf"^## {re.escape(heading)}\s*$", text, re.M)
        if not m:
            return ""
        nxt = re.search(r"^## ", text[m.end():], re.M)
        return text[m.end():m.end() + nxt.start()] if nxt else text[m.end():]
    return region


# ------------------------------------------------------------------ facts

def fact_electron_pin(tree):
    fact = "electron pin"
    pkg = tree.json(PKG_REL)
    deps = {}
    if isinstance(pkg, dict):
        for key in ("devDependencies", "dependencies"):
            if isinstance(pkg.get(key), dict):
                deps.update(pkg[key])
    pin = deps.get("electron")
    if not isinstance(pin, str) or not pin:
        return [_missing(PKG_REL, fact, "no electron dependency")]
    return (_match(tree, MAIN_JS_REL, fact, r"Electron " + _DOTTED, pin,
                   region=_first_block_comment, what="header comment pin")
            + _match(tree, STACK_REL, fact, r"exact pin `([^`]+)`", pin,
                     region=_md_section("Decision"), what="Decision pin"))


def fact_version(tree):
    fact = "version"
    consts = tree.py_constants(INIT_REL)
    version = (consts or {}).get("VERSION")
    if not isinstance(version, str):
        return [_missing(INIT_REL, fact, "no VERSION constant")]
    problems = []
    pkg = tree.json(PKG_REL)
    if not isinstance(pkg, dict):
        problems.append(_missing(PKG_REL, fact, "unreadable"))
    elif pkg.get("version") != version:
        problems.append(f"{PKG_REL}: {fact}: \"version\" reads "
                        f"{pkg.get('version')!r}, the tree has {version!r}")
    lock = tree.json(LOCK_REL)
    if not isinstance(lock, dict):
        problems.append(_missing(LOCK_REL, fact, "unreadable"))
    else:
        root_pkg = (lock.get("packages") or {}).get("") or {}
        for where, got in (("top-level", lock.get("version")),
                           ('packages[""]', root_pkg.get("version"))):
            if got != version:
                problems.append(f"{LOCK_REL}: {fact}: {where} version reads "
                                f"{got!r}, the tree has {version!r}")
    return problems


def _setup_value(tree, fact, pattern):
    text = tree.text(SETUP_REL)
    if text is None:
        return None, [_missing(SETUP_REL, fact)]
    m = re.search(pattern, text)
    if not m:
        return None, [_missing(SETUP_REL, fact, "floor check not found")]
    return m.group(1), []


def fact_python_floor(tree):
    fact = "python floor"
    floor, problems = _setup_value(
        tree, fact, r"\[version\]\$pyVer\s+-lt\s+\[version\]'" + _DOTTED + "'")
    if problems:
        return problems
    return _match(tree, README_REL, fact,
                  r"Needs\s+Python\s+" + _DOTTED + r"\s+or\s+newer", floor,
                  what="Python floor")


def fact_node_floor(tree):
    fact = "node floor"
    floor, problems = _setup_value(
        tree, fact, r"\$nodeFloor\s*=\s*'" + _DOTTED + "'")
    if problems:
        return problems
    return _match(tree, README_REL, fact,
                  r"Node\.js\s+" + _DOTTED + r"\s+or\s+newer", floor,
                  what="Node.js floor")


def fact_port_block(tree):
    fact = "port block"
    consts = tree.py_constants(PORTS_REL) or {}
    port, block = consts.get("AL_PORT"), consts.get("PORT_BLOCK")
    if not isinstance(port, int) or not (isinstance(block, tuple)
                                         and len(block) == 2):
        return [_missing(PORTS_REL, fact, "no AL_PORT / PORT_BLOCK")]
    span = f"{block[0]}-{block[1]}"
    return (_match(tree, README_REL, fact, r"`port` \(default (\d+)\)", port,
                   what="default port")
            + _match(tree, README_REL, fact, r"Port (\d+) taken", port,
                     required=False, what="default port")
            + _match(tree, README_REL, fact, r"port\s+in\s+(\d+-\d+)", span,
                     what="port block"))


def fact_kit_version(tree):
    fact = "kit version"
    man = tree.json(MANIFEST_REL)
    version = man.get("version") if isinstance(man, dict) else None
    if not isinstance(version, int):
        return [_missing(MANIFEST_REL, fact, "no version")]
    problems = []
    if tree.text(CLAUDE_REL) is not None:
        # Optional: the AL rules line stops quoting the version once the
        # integrator edit of AUTO-14 lands; any quote left must match.
        problems += _match(tree, CLAUDE_REL, fact, r"Kit: v(\d+), vendored",
                           version, required=False, what="kit version")
    problems += _match(tree, DESIGN_REL, fact, r"\bkit v(\d+)\b", version,
                       required=False, what="kit version")
    return problems


def fact_script_names(tree):
    fact = "script names"
    problems = [_missing(f"scripts/{name}", fact) for name in SCRIPTS
                if not tree.exists(f"scripts/{name}")]
    text = tree.text(README_REL)
    if text is None:
        return problems + [_missing(README_REL, fact)]
    named = sorted(set(re.findall(r"scripts[\\/]([\w.-]+\.ps1)", text)))
    problems += [f"{README_REL}: {fact}: names scripts/{name}, which does "
                 f"not exist" for name in named
                 if not tree.exists(f"scripts/{name}")]
    return problems


def fact_disclaimer(tree):
    fact = "not-affiliated statement"
    disclaimer = (tree.py_constants(INIT_REL) or {}).get("DISCLAIMER")
    if not isinstance(disclaimer, str) or not disclaimer:
        return [_missing(INIT_REL, fact, "no DISCLAIMER constant")]
    text = tree.text(README_REL)
    if text is None:
        return [_missing(README_REL, fact)]
    if disclaimer not in text:
        return [f"{README_REL}: {fact}: the statement is not there verbatim "
                f"({disclaimer!r})"]
    return []


FACTS = [
    fact_electron_pin,
    fact_version,
    fact_python_floor,
    fact_node_floor,
    fact_port_block,
    fact_kit_version,
    fact_script_names,
    fact_disclaimer,
]


def check(root=ROOT):
    """Every stale-fact problem of the tree at root, in FACTS order."""
    tree = Tree(root)
    problems = []
    for fact in FACTS:
        problems.extend(fact(tree))
    return problems


def stale_files(problems):
    """The files named by problems, first-seen order, no repeats."""
    seen = []
    for line in problems:
        rel = line.split(": ", 1)[0]
        if rel not in seen:
            seen.append(rel)
    return seen


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check", help="match every fact against the docs")
    chk.add_argument("--root", default=str(ROOT),
                     help="tree to check (default: this checkout)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"docs_fresh: no such folder: {root}", file=sys.stderr)
        return 2
    problems = check(root)
    if not problems:
        print(f"docs_fresh: ok ({len(FACTS)} facts)")
        return 0
    for line in problems:
        print(line)
    print(f"docs_fresh: {len(problems)} stale quote(s) in: "
          f"{', '.join(stale_files(problems))}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
