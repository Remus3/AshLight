#!/usr/bin/env python3
"""Docs fresh (AUTO-14, F-146): facts the docs quote, computed from the tree.

    docs_fresh.py check [--root DIR]
    docs_fresh.py index (--check | --write) [--root DIR]
    docs_fresh.py stale [--root DIR] [--days N] [--today YYYY-MM-DD]

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
- default hotkeys (TEST-DOCS-FACTS-UI): the built-in default of each
  shortcut, the first entry of server/al/hotkeys.py FALLBACKS (the core's
  copy; app/hotkey.js mirrors it), -> the README.md item check and overlay
  toggle quotes, and the config/local.example.json value when it is set.
  Read from the core, never from web/ text (the dashboard prints the keys
  the snapshot carries).
- budget numbers: the numbers tests/test_budgets.py asserts (the literal
  in fleet_test_guard.budget(<s>) or <share> * load_factor() of each named
  test) -> the README.md 'Budgets' section and the 'Budgets' section of
  docs/decisions/0002-stack.md.
- settings keys: the player keys of config/local.example.json (every
  top-level key not starting with '_', minus server/al/install/firstrun.py
  DEV_KEYS) -> each is read by the core (a quoted literal in a
  server/al .py file) and named in the README.md config/local.json
  paragraph; a key that paragraph names must be one of them.
- tab names: the dashboard tabs (web/tabs.js TABS, each label read from its
  tab button in web/index.html) -> every '<Label> tab' quote of README.md.
- index (TEST-DOCS-INDEX, F-195 c): every NNNN-<topic>.md under
  docs/decisions/ and docs/research/ has its index line in that folder's
  README.md ('- NNNN:' for decisions, '- NNNN ' for research). Files in
  EXPECTED_STALE (the lines missing at the package base) are let through
  while missing; the list is shrink-only and empties once the integrator
  has run 'index --write'.

index --check: exit 0 when no line is missing (beyond EXPECTED_STALE),
else 1 with one line per missing file. index --write: inserts every
missing line (title from the file's '# NNNN - <title>' heading, wrapped
at 72 columns) at its place in the list's own number order and changes
nothing else; it is the one subcommand that writes, and only the two
README files.

stale: lists every line of docs/**/*.md holding a PENDING or UNVERIFIED
marker and a YYYY-MM-DD date whose newest date on that line is more than
--days (default 30) days before --today (default the local date). Prints
nothing and exits 0 when there is none; else one line per marker, exit 1.

Reads tracked files only and makes no request; only index --write writes.
Stdlib only.
"""
import argparse
import ast
import datetime
import json
import re
import sys
import textwrap
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
HOTKEYS_REL = "server/al/hotkeys.py"
BUDGETS_REL = "tests/test_budgets.py"
EXAMPLE_REL = "config/local.example.json"
FIRSTRUN_REL = "server/al/install/firstrun.py"
TABS_REL = "web/tabs.js"
INDEX_HTML_REL = "web/index.html"
# The core's Python sources: a settings key is read there.
CORE_DIR = "server/al"
SCRIPTS = ("setup.ps1", "build.ps1", "run.ps1")
DECISIONS_DIR = "docs/decisions"
RESEARCH_DIR = "docs/research"
# Folders whose NNNN-<topic>.md files each need an index line in README.md.
INDEX_DIRS = (DECISIONS_DIR, RESEARCH_DIR)

# Index lines missing at the TEST-DOCS-INDEX base. Shrink-only: an entry is
# let through only while its line is still missing; the integrator's
# 'index --write' adds them all, after which this tuple should be emptied.
EXPECTED_STALE = tuple(
    f"{DECISIONS_DIR}/{name}" for name in (
        "0001-name-ashlight.md", "0002-stack.md", "0003-read-policy.md",
        "0004-scope-theorycraft.md", "0005-core-keepalive.md",
        "0006-fps-measurement-method.md", "0007-tc-code.md",
        "0008-live-resume-backward-scan.md", "0009-data-license.md",
        "0010-process-registry.md", "0011-core-autostart.md",
        "0012-worktree-sidecar-hook.md", "0013-web-data.md",
        "0014-ui-build-eval-gfx.md", "0015-price-check-and-contact.md",
        "0016-price-ui-contract.md",
        "0017-trade-no-app-calls-and-floor-wording.md", "0018-tc-pin.md",
        "0019-trade-close-on-accept-cancel.md", "0020-act-zone-levels.md",
        "0021-tc-code-real.md", "0022-tc-bridge.md",
        "0023-act-splits-resume.md", "0024-tc-delta.md",
        "0025-tc-drift.md", "0026-price-book-and-league-rollover.md",
        "0027-tc-toolchain.md", "0028-tc-live-proof-and-budgets.md",
        "0029-game-exit-log-staleness.md",
        "0030-player-helpers-waystone-search-zone-notes.md",
        "0031-loot-filter-download.md",
        "0032-swap-compare-sanity-filter-tiers.md",
        "0033-loot-filter-merge.md", "0034-build-file-download.md",
        "0036-run-history-file.md", "0037-trade-stat-ids-source.md"))

# Every file a fact reads (the test copies these into a fixture root, plus
# the .py files under CORE_DIR).
INPUTS = (INIT_REL, PORTS_REL, PKG_REL, LOCK_REL, MAIN_JS_REL, STACK_REL,
          SETUP_REL, README_REL, MANIFEST_REL, CLAUDE_REL, DESIGN_REL,
          HOTKEYS_REL, BUDGETS_REL, EXAMPLE_REL, FIRSTRUN_REL, TABS_REL,
          INDEX_HTML_REL, *(f"scripts/{name}" for name in SCRIPTS))

_DOTTED = r"(\d+(?:\.\d+)+)"
_NUMBERED = re.compile(r"^(\d{4})-[\w.-]+\.md$")


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

    def numbered(self, rel_dir):
        """Sorted names of the NNNN-<topic>.md files directly in rel_dir."""
        folder = self.root / rel_dir
        if not folder.is_dir():
            return []
        return sorted(p.name for p in folder.iterdir()
                      if p.is_file() and _NUMBERED.match(p.name))

    def py_files(self, rel_dir):
        """Sorted rel paths of the .py files under rel_dir, recursively."""
        folder = self.root / rel_dir
        if not folder.is_dir():
            return []
        return sorted(p.relative_to(self.root).as_posix()
                      for p in folder.rglob("*.py") if p.is_file())


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


def _md_section(heading, prefix=False):
    """The body of the '## <heading>' section; with prefix, of the first
    section whose heading starts with that word."""
    tail = r"\b[^\n]*$" if prefix else r"\s*$"

    def region(text):
        m = re.search(rf"^## {re.escape(heading)}{tail}", text, re.M)
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


def _ws(pattern):
    """A doc pattern whose spaces also match a line wrap."""
    return pattern.replace(" ", r"\s+")


# shortcut name (hotkeys.FALLBACKS) -> its README.md quote pattern.
_HOTKEY_QUOTES = {
    "eval": _ws(r"the item check hotkey \(([A-Za-z0-9+]+)\)"),
    "toggle": _ws(r"overlay toggles with ([A-Za-z0-9+]+) by default"),
}


def fact_default_hotkeys(tree):
    fact = "default hotkey"
    consts = tree.py_constants(HOTKEYS_REL) or {}
    chains, keys = consts.get("FALLBACKS"), consts.get("CONFIG_KEYS")
    if not (isinstance(chains, dict) and isinstance(keys, dict)):
        return [_missing(HOTKEYS_REL, fact, "no FALLBACKS / CONFIG_KEYS")]
    problems = []
    example = tree.json(EXAMPLE_REL)
    if not isinstance(example, dict):
        problems.append(_missing(EXAMPLE_REL, fact, "unreadable"))
    for name, pattern in _HOTKEY_QUOTES.items():
        chain = chains.get(name)
        if not (isinstance(chain, (tuple, list)) and chain
                and isinstance(chain[0], str) and name in keys):
            problems.append(_missing(HOTKEYS_REL, fact, f"no {name} default"))
            continue
        default = chain[0]
        problems += _match(tree, README_REL, fact, pattern, default,
                           what=f"{name} hotkey")
        got = example.get(keys[name]) if isinstance(example, dict) else None
        if isinstance(got, str) and got and got != default:
            problems.append(f"{EXAMPLE_REL}: {fact}: \"{keys[name]}\" reads "
                            f"{got!r}, the tree has {default!r}")
    return problems


def _budget_literal(fn):
    """The budget number a test function asserts: the literal argument of a
    budget(...) call, else the literal of '<n> * ...load_factor()'."""
    def num(node):
        return (node.value if isinstance(node, ast.Constant)
                and isinstance(node.value, (int, float))
                and not isinstance(node.value, bool) else None)

    def called(node, attr):
        if not isinstance(node, ast.Call):
            return False
        f = node.func
        return ((isinstance(f, ast.Attribute) and f.attr == attr)
                or (isinstance(f, ast.Name) and f.id == attr))

    scaled = None
    for node in ast.walk(fn):
        if called(node, "budget") and node.args and num(node.args[0]) is not None:
            return num(node.args[0])
        if (scaled is None and isinstance(node, ast.BinOp)
                and isinstance(node.op, ast.Mult)):
            for a, b in ((node.left, node.right), (node.right, node.left)):
                if num(a) is not None and called(b, "load_factor"):
                    scaled = num(a)
    return scaled


def budget_values(tree):
    """{test function name: asserted budget number} of tests/test_budgets.py;
    None when the file is missing or does not parse."""
    text = tree.text(BUDGETS_REL)
    if text is None:
        return None
    try:
        module = ast.parse(text)
    except SyntaxError:
        return None
    out = {}
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            value = _budget_literal(node)
            if value is not None:
                out[node.name] = value
    return out


# budget -> (test function name prefix, unit scale). The number in the doc
# is the asserted literal times the scale (seconds -> ms, share -> percent).
_BUDGET_TESTS = {
    "parse 10k lines": ("test_parse_10k_lines", 1000),
    "tail burst": ("test_tail_1000_line_burst", 1000),
    "tailer idle": ("test_tailer_idle_cpu", 100),
    "core idle": ("test_core_idle_cpu", 100),
}
# (doc, region, budget, pattern with the number as group 1).
_BUDGET_QUOTES = (
    (README_REL, _md_section("Budgets"), "parse 10k lines",
     _ws(r"parses 10,000 log lines in under (\d+) ms")),
    (README_REL, _md_section("Budgets"), "tail burst",
     _ws(r"a 1,000-line burst in under (\d+) ms")),
    (README_REL, _md_section("Budgets"), "core idle",
     _ws(r"idle tailing under (\d+) to \d+ percent")),
    (README_REL, _md_section("Budgets"), "tailer idle",
     _ws(r"idle tailing under \d+ to (\d+) percent")),
    (STACK_REL, _md_section("Budgets", prefix=True), "core idle",
     _ws(r"Core idle: under (\d+) percent")),
    (STACK_REL, _md_section("Budgets", prefix=True), "tail burst",
     _ws(r"1,000-line burst parsed in under (\d+) ms")),
)


def _plain(number):
    value = round(number, 6)
    return str(int(value)) if value == int(value) else f"{value:g}"


def fact_budgets(tree):
    fact = "budget"
    values = budget_values(tree)
    if values is None:
        return [_missing(BUDGETS_REL, fact, "missing or unreadable")]
    expected, problems = {}, []
    for label, (prefix, scale) in _BUDGET_TESTS.items():
        hits = [v for name, v in values.items() if name.startswith(prefix)]
        if len(hits) != 1:
            problems.append(_missing(BUDGETS_REL, fact,
                                     f"no single {prefix}* budget"))
            continue
        expected[label] = _plain(hits[0] * scale)
    for rel, region, label, pattern in _BUDGET_QUOTES:
        if label in expected:
            problems += _match(tree, rel, fact, pattern, expected[label],
                               region=region, what=f"{label} budget")
    return problems


_KEY_TOKEN = re.compile(r"`([a-z][a-z0-9_]*)`")
_KEY_VALUES = ("true", "false", "null")


def _settings_paragraph(text):
    """The README.md paragraph that lists the config/local.json keys."""
    m = re.search(r"^Optional per-computer settings live in `config/local\.json`",
                  text, re.M)
    if not m:
        return None
    end = text.find("\n\n", m.start())
    return text[m.start():] if end < 0 else text[m.start():end]


def fact_settings_keys(tree):
    fact = "settings keys"
    example = tree.json(EXAMPLE_REL)
    if not isinstance(example, dict):
        return [_missing(EXAMPLE_REL, fact, "unreadable")]
    dev = (tree.py_constants(FIRSTRUN_REL) or {}).get("DEV_KEYS")
    if not isinstance(dev, (tuple, list)):
        return [_missing(FIRSTRUN_REL, fact, "no DEV_KEYS")]
    keys = [k for k in example if not k.startswith("_") and k not in dev]
    problems = []
    core = "\n".join(tree.text(rel) or "" for rel in tree.py_files(CORE_DIR))
    for key in keys:
        if f'"{key}"' not in core and f"'{key}'" not in core:
            problems.append(f"{EXAMPLE_REL}: {fact}: \"{key}\" is not read by "
                            f"the core ({CORE_DIR})")
    text = tree.text(README_REL)
    if text is None:
        return problems + [_missing(README_REL, fact)]
    para = _settings_paragraph(text)
    if para is None:
        return problems + [_missing(README_REL, fact,
                                    "no config/local.json settings paragraph")]
    named = [k for k in _KEY_TOKEN.findall(para) if k not in _KEY_VALUES]
    problems += [f"{README_REL}: {fact}: `{key}` is not listed (the tree has "
                 f"it in {EXAMPLE_REL})" for key in keys if key not in named]
    problems += [f"{README_REL}: {fact}: names `{key}`, which is not a "
                 f"setting in {EXAMPLE_REL}" for key in dict.fromkeys(named)
                 if key not in keys]
    return problems


def tab_labels(tree):
    """[(tab id, label or None)] of the dashboard in web/tabs.js order;
    None when web/tabs.js has no TABS list."""
    js = tree.text(TABS_REL)
    m = re.search(r"\bvar\s+TABS\s*=\s*\[([^\]]*)\]", js or "")
    if not m:
        return None
    html = tree.text(INDEX_HTML_REL) or ""
    out = []
    for tab in re.findall(r"[\"']([\w-]+)[\"']", m.group(1)):
        b = re.search(rf"<button\b[^>]*\bid=\"tab-{re.escape(tab)}\"[^>]*>"
                      r"\s*([^<]*?)\s*<", html)
        out.append((tab, b.group(1) if b and b.group(1) else None))
    return out


def fact_tab_names(tree):
    fact = "tab names"
    tabs = tab_labels(tree)
    if tabs is None:
        return [_missing(TABS_REL, fact, "no TABS list")]
    if tree.text(INDEX_HTML_REL) is None:
        return [_missing(INDEX_HTML_REL, fact)]
    problems = [f"{INDEX_HTML_REL}: {fact}: no tab button for {tab!r}"
                for tab, label in tabs if label is None]
    labels = {label for _tab, label in tabs if label}
    text = tree.text(README_REL)
    if text is None:
        return problems + [_missing(README_REL, fact)]
    quoted = re.findall(r"\b([A-Z][a-z]+(?:\s+and\s+[a-z]+)?)\s+tab\b", text)
    problems += [f"{README_REL}: {fact}: names the {got!r} tab, the "
                 f"dashboard has {sorted(labels)!r}"
                 for got in dict.fromkeys(re.sub(r"\s+", " ", q)
                                          for q in quoted)
                 if got not in labels]
    return problems


# ------------------------------------------------------------------ index

_INDEX_LINE = {DECISIONS_DIR: r"^- (\d{4}):", RESEARCH_DIR: r"^- (\d{4})\b"}
_WRAP = 72


def _readme(rel_dir):
    return f"{rel_dir}/README.md"


def index_missing(tree, rel_dir):
    """The files of rel_dir (rel paths) with no index line in its README;
    None when the README is missing or unreadable."""
    text = tree.text(_readme(rel_dir))
    if text is None:
        return None
    have = set(re.findall(_INDEX_LINE[rel_dir], text, re.M))
    return [f"{rel_dir}/{name}" for name in tree.numbered(rel_dir)
            if name[:4] not in have]


def index_problems(tree, expected=EXPECTED_STALE):
    """One problem per missing index line, minus the expected-stale ones."""
    problems = []
    for rel_dir in INDEX_DIRS:
        missing = index_missing(tree, rel_dir)
        if missing is None:
            problems.append(_missing(_readme(rel_dir), "index"))
            continue
        problems += [f"{_readme(rel_dir)}: index: no index line for {rel}"
                     for rel in missing if rel not in expected]
    return problems


def _title(tree, rel):
    text = tree.text(rel) or ""
    first = text.splitlines()[0] if text else ""
    m = re.match(r"^#\s+\d{4}\s*[-:]\s*(.+?)\s*$", first)
    if m:
        return m.group(1)
    m = re.match(r"^#\s+(.+?)\s*$", first)
    return m.group(1) if m else Path(rel).stem[5:].replace("-", " ")


def index_entry(tree, rel):
    """The index entry for one file, as wrapped lines (no newlines)."""
    name = Path(rel).name
    title = _title(tree, rel)
    if rel.startswith(RESEARCH_DIR + "/"):
        body = f"- {name[:4]} {title} ([{name}]({name}))"
    else:
        body = f"- {name[:4]}: {title}"
        if not body.endswith("."):
            body += "."
    return textwrap.wrap(body, _WRAP, subsequent_indent="  ",
                         break_long_words=False, break_on_hyphens=False)


def _entries(lines):
    """[(number, start, end)] of the '- NNNN' entries; end is exclusive and
    covers the entry's indented continuation lines."""
    out = []
    i = 0
    while i < len(lines):
        m = re.match(r"^- (\d{4})\b", lines[i])
        if not m:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j].startswith("  ") and lines[j].strip():
            j += 1
        out.append((int(m.group(1)), i, j))
        i = j
    return out


def _insert_at(lines, num):
    """Where an entry numbered num goes: before the first entry it precedes
    in the list's own order (descending when the first number is above the
    last), else after the last entry."""
    entries = _entries(lines)
    nums = [n for n, _s, _e in entries]
    descending = len(nums) > 1 and nums[0] > nums[-1]
    for n, start, _end in entries:
        if (n < num) if descending else (n > num):
            return start
    if entries:
        return entries[-1][2]
    at = len(lines)
    while at > 0 and lines[at - 1] == "":
        at -= 1
    return at


def index_write(root):
    """Insert every missing index line into the two READMEs; returns the rel
    paths of the files that got a line. Nothing else in a README changes."""
    tree = Tree(root)
    added = []
    for rel_dir in INDEX_DIRS:
        missing = index_missing(tree, rel_dir)
        if not missing:
            continue
        lines = tree.text(_readme(rel_dir)).split("\n")
        for rel in missing:
            at = _insert_at(lines, int(Path(rel).name[:4]))
            lines[at:at] = index_entry(tree, rel)
            added.append(rel)
        (Path(root) / _readme(rel_dir)).write_bytes(
            "\n".join(lines).encode("utf-8"))
    return added


def fact_index(tree):
    return index_problems(tree)


# ------------------------------------------------------------------ stale

_MARKER = re.compile(r"\b(?:PENDING|UNVERIFIED)\b")
_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")


def stale_markers(root, today, days=30):
    """[(rel, line number, newest date, age in days, text)] for each line of
    docs/**/*.md with a PENDING / UNVERIFIED marker whose newest date is
    more than `days` days before `today`."""
    out = []
    docs = Path(root) / "docs"
    if not docs.is_dir():
        return out
    for path in sorted(docs.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for no, line in enumerate(text.splitlines(), 1):
            if not _MARKER.search(line):
                continue
            dates = []
            for y, m, d in _DATE.findall(line):
                try:
                    dates.append(datetime.date(int(y), int(m), int(d)))
                except ValueError:
                    continue
            if not dates:
                continue
            newest = max(dates)
            age = (today - newest).days
            if age > days:
                out.append((path.relative_to(root).as_posix(), no,
                            newest.isoformat(), age, line.strip()))
    return out


FACTS = [
    fact_electron_pin,
    fact_version,
    fact_python_floor,
    fact_node_floor,
    fact_port_block,
    fact_kit_version,
    fact_script_names,
    fact_disclaimer,
    fact_default_hotkeys,
    fact_budgets,
    fact_settings_keys,
    fact_tab_names,
    fact_index,
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


def _cmd_index(root, args):
    if args.write:
        added = index_write(root)
        for rel in added:
            print(f"docs_fresh: index line added for {rel}")
        print(f"docs_fresh: index --write added {len(added)} line(s)")
        return 0
    tree = Tree(root)
    problems = index_problems(tree)
    for line in problems:
        print(line)
    still = set()
    for rel_dir in INDEX_DIRS:
        still.update(index_missing(tree, rel_dir) or [])
    resolved = [rel for rel in EXPECTED_STALE if rel not in still]
    if resolved:
        print(f"docs_fresh: note: {len(resolved)} EXPECTED_STALE "
              f"entr{'y is' if len(resolved) == 1 else 'ies are'} indexed "
              f"now; drop them from the list")
    if problems:
        print(f"docs_fresh: {len(problems)} missing index line(s)")
        return 1
    print("docs_fresh: index ok")
    return 0


def _cmd_stale(root, args):
    if args.today:
        try:
            today = datetime.date.fromisoformat(args.today)
        except ValueError:
            print(f"docs_fresh: bad --today: {args.today}", file=sys.stderr)
            return 2
    else:
        today = datetime.date.today()
    found = stale_markers(root, today, args.days)
    for rel, no, date, age, text in found:
        print(f"{rel}:{no}: {date} ({age} days): {text[:160]}")
    return 1 if found else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check", help="match every fact against the docs")
    idx = sub.add_parser("index", help="decision and research index lines")
    mode = idx.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="exit 1 when a file has no index line")
    mode.add_argument("--write", action="store_true",
                      help="insert every missing index line")
    stl = sub.add_parser("stale", help="dated PENDING / UNVERIFIED markers")
    stl.add_argument("--days", type=int, default=30,
                     help="older than this many days (default 30)")
    stl.add_argument("--today", default="",
                     help="reference date YYYY-MM-DD (default: today)")
    for p in (chk, idx, stl):
        p.add_argument("--root", default=str(ROOT),
                       help="tree to read (default: this checkout)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"docs_fresh: no such folder: {root}", file=sys.stderr)
        return 2
    if args.cmd == "index":
        return _cmd_index(root, args)
    if args.cmd == "stale":
        return _cmd_stale(root, args)
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
