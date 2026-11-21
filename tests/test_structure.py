"""Structure guard for server/al (TEST-STRUCTURE-GUARD, research 0047 R10 d).

Rule 1 (imports): the import-time module graph of server/al has no cycle.
An edge is a module-level import of another server/al module (an import
inside a function runs later and is the usual way to break a cycle, so it is
not an edge); importing a submodule also imports each package between
server.al and it. One deliberate mutual import is allowed by exact edge in
CYCLE_ALLOW; with those edges removed the graph must sort.

Rule 2 (player text): a server/al module with SENTENCE_MIN or more sentence
literals sits under a design-gate path (tools/design_gate.py UI_PREFIXES,
read from its source) or is on EXEMPT with a one-line reason. EXEMPT is
shrink-only: an entry that no longer holds SENTENCE_MIN sentences, moved
under the gate or was deleted fails with 'remove it'.

A sentence literal is a heuristic: a string constant or f-string that is not
a docstring, starts with a capital letter, has at least three words, is
mostly letters and spaces and has no line break inside. It reads source
files only (ast); it imports nothing from server/ and reads no game data.
"""
import ast
import graphlib
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = "server.al"
SENTENCE_MIN = 4

CYCLE_RULE = (
    "server/al module-level imports must not form a cycle: move the shared "
    "helper to a third module or import inside the function that needs it"
)
TEXT_RULE = (
    "a server module with %d or more player sentences must sit under a "
    "design-gate path (server/al/text/): move the text there" % SENTENCE_MIN
)

# (importer, imported) module-level edges that close a known cycle.
CYCLE_ALLOW = {
    ("server.al.playcards", "server.al.playview"):
        "PLAY-TD-07B: playcards reads playview's _dict helpers through the "
        "module at call time, so either module may be imported first",
}

# Modules outside the gate that hold player text today; shrink-only.
EXEMPT = {
    "server/al/__main__.py":
        "command-line usage and refusal lines for the developer",
    "server/al/acts.py":
        "act split empty-state lines published with the act view",
    "server/al/campaign.py":
        "campaign hint lines (boots, flask, boss element) built with the hint",
    "server/al/diag.py":
        "Checks row titles, states and fixes, written with each check",
    "server/al/gfx.py":
        "graphics advisor verdict lines tied to its spec thresholds",
    "server/al/hints.py":
        "new-character tip lines published with the hint state",
    "server/al/http.py":
        "API error sentences returned with each route's refusal",
    "server/al/install/payload.py":
        "installer refusal lines for a bad release payload",
    "server/al/logshapes.py":
        "game log line prefixes matched by the ledger, not AshLight text",
    "server/al/mapladder.py":
        "map ladder empty-state and column notes published with the ladder",
    "server/al/playcards.py":
        "Play region C card sentences composed at the source (PLAY-TD-07B)",
    "server/al/playview.py":
        "Play view sentences and caps composed at the source",
    "server/al/pricewatch.py":
        "price watch paused and empty-state lines published with the list",
    "server/al/runhistory.py":
        "run history on, off and empty-state lines published with the store",
    "server/al/runs.py":
        "map and death empty-state lines published with the run view",
    "server/al/settingsio.py":
        "settings import refusal lines returned with the import result",
    "server/al/theorycraft/buildfile.py":
        "the .build file note and its no-passives reasons",
    "server/al/theorycraft/calcwire.py":
        "PoB weapon disableReason texts matched from the bridge",
    "server/al/theorycraft/cardparts/buildload.py":
        "build load card sentences for share-link and paste outcomes",
    "server/al/theorycraft/cardparts/keep.py":
        "keep or vendor card sentences from the level-band rule result",
    "server/al/theorycraft/charjson.py":
        "ascendancy names mapped from the GGG character export",
    "server/al/theorycraft/health.py":
        "build health labels and empty-state lines next to their PoB outputs",
    "server/al/theorycraft/lootfilter.py":
        "filter merge refusals and the snippet disclaimer line",
    "server/al/theorycraft/searchstr.py":
        "search string titles and explanations next to their regex parts",
    "server/al/theorycraft/weights.py":
        "game mod templates matched against item text, not AshLight text",
    "server/al/verdicts.py":
        "in-game check names for the Worked / Refused record",
    "server/al/webfetch.py":
        "research fetch refusal reasons for the developer tool",
    "server/al/zoneguide.py":
        "zone guide level-gap and note lines composed with the guide view",
}


def gate_prefixes(root):
    """UI_PREFIXES from tools/design_gate.py, read by ast (never imported)."""
    src = (root / "tools" / "design_gate.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "UI_PREFIXES"
                for t in node.targets):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("tools/design_gate.py has no UI_PREFIXES")


def modules(root):
    """{dotted name: Path} for every .py file under server/al."""
    out = {}
    base = root / "server" / "al"
    for p in sorted(base.rglob("*.py")):
        parts = list(p.relative_to(root).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out[".".join(parts)] = p
    return out


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _known(name, mods):
    while name and name not in mods:
        name = name.rpartition(".")[0]
    return name if name.startswith(PKG + ".") else ""


def _with_parents(target, importer, mods):
    """The target plus each package between server.al and it."""
    out = {target}
    parts = target.split(".")
    for i in range(3, len(parts)):
        pkg = ".".join(parts[:i])
        if pkg in mods and not (importer + ".").startswith(pkg + "."):
            out.add(pkg)
    return out


def module_imports(name, path, mods):
    """server/al modules that `name` imports at module level."""
    is_pkg = path.name == "__init__.py"
    found = set()

    def visit(node):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.Lambda)):
                continue
            targets = []
            if isinstance(ch, ast.Import):
                targets = [a.name for a in ch.names]
            elif isinstance(ch, ast.ImportFrom):
                if ch.level:
                    base = name.split(".")
                    if not is_pkg:
                        base = base[:-1]
                    if ch.level > 1:
                        base = base[:len(base) - (ch.level - 1)]
                    mod = ".".join(base + ([ch.module] if ch.module else []))
                else:
                    mod = ch.module or ""
                for a in ch.names:
                    full = mod + "." + a.name
                    targets.append(full if full in mods else mod)
            for t in targets:
                k = _known(t, mods)
                if k and k != name:
                    found.update(_with_parents(k, name, mods))
            visit(ch)

    visit(_parse(path))
    found.discard(name)
    return found


def import_graph(root):
    mods = modules(root)
    return {m: module_imports(m, p, mods) for m, p in mods.items()}


def check_cycles(root, allow):
    graph = import_graph(root)
    out = []
    for edge in sorted(allow):
        a, b = edge
        if b not in graph.get(a, ()):
            out.append("%s -> %s: no longer a module-level import, remove "
                       "it from CYCLE_ALLOW" % edge)
        else:
            graph[a] = graph[a] - {b}
    try:
        tuple(graphlib.TopologicalSorter(graph).static_order())
    except graphlib.CycleError as e:
        out.append("%s: %s" % (" -> ".join(e.args[1]), CYCLE_RULE))
    return out


_WORD = re.compile(r"[A-Za-z][A-Za-z']*")


def is_sentence(text):
    v = text.strip()
    if not v or "\n" in v or not ("A" <= v[0] <= "Z"):
        return False
    words = v.split()
    if len(words) < 3:
        return False
    letters = sum(1 for ch in v if ch.isalpha() or ch == " ")
    if letters < 0.8 * len(v):
        return False
    real = [w for w in words if _WORD.fullmatch(w.strip(".,;:!?()'\""))]
    return len(real) >= 3


def _docstrings(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                          ast.AsyncFunctionDef)) and n.body:
            first = n.body[0]
            if isinstance(first, ast.Expr) and isinstance(
                    first.value, ast.Constant) and isinstance(
                    first.value.value, str):
                out.add(id(first.value))
    return out


def sentence_count(path):
    tree = _parse(path)
    docs = _docstrings(tree)
    inner = set()
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            text = ""
            for part in node.values:
                inner.add(id(part))
                if isinstance(part, ast.Constant):
                    text += str(part.value)
                else:
                    text += "x"
            n += is_sentence(text)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docs and id(node) not in inner):
            n += is_sentence(node.value)
    return n


def text_modules(root):
    """{repo-relative path: sentence count} at or over SENTENCE_MIN."""
    out = {}
    for p in modules(root).values():
        c = sentence_count(p)
        if c >= SENTENCE_MIN:
            out[p.relative_to(root).as_posix()] = c
    return out


def check_text(root, exempt):
    gate = gate_prefixes(root)
    found = text_modules(root)
    out = []
    for path, c in sorted(found.items()):
        if path.startswith(gate) or path in exempt:
            continue
        out.append("%s (%d sentences): %s" % (path, c, TEXT_RULE))
    for path in sorted(exempt):
        if path.startswith(gate):
            out.append("%s: under the design gate now, remove it from "
                       "EXEMPT" % path)
        elif path not in found:
            out.append("%s: fewer than %d sentences or gone, remove it from "
                       "EXEMPT" % (path, SENTENCE_MIN))
    return out


# -- the rules on the tree --------------------------------------------------

def test_server_imports_have_no_cycle():
    assert check_cycles(ROOT, CYCLE_ALLOW) == []


def test_player_text_sits_under_the_gate_or_exempt():
    assert check_text(ROOT, EXEMPT) == []


def test_every_exception_has_a_reason():
    for table in (CYCLE_ALLOW, EXEMPT):
        for key, why in table.items():
            assert isinstance(why, str) and len(why.split()) >= 3, key
            assert "\n" not in why, key


def test_gate_prefixes_include_server_text():
    assert "server/al/text/" in gate_prefixes(ROOT)


def test_sentence_heuristic():
    assert is_sentence("Load a build to see its health.")
    assert is_sentence("Calc component changed, re-run setup")
    assert not is_sentence("Life")
    assert not is_sentence("Block chance")
    assert not is_sentence("load a build first")
    assert not is_sentence("GET /api/x?a=1&b=2 HTTP/1.1")
    assert not is_sentence("Line one\nline two of it")


# -- self-checks on a temp copy ---------------------------------------------

def _copy(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "server" / "al", root / "server" / "al",
                    ignore=shutil.ignore_patterns("__pycache__", "data"))
    (root / "server" / "__init__.py").write_text("", encoding="utf-8")
    (root / "tools").mkdir()
    shutil.copy2(ROOT / "tools" / "design_gate.py", root / "tools")
    return root


def test_copy_is_clean(tmp_path):
    root = _copy(tmp_path)
    assert check_cycles(root, CYCLE_ALLOW) == []
    assert check_text(root, EXEMPT) == []


def test_planted_cycle_fails(tmp_path):
    root = _copy(tmp_path)
    al = root / "server" / "al"
    (al / "zz_cycle_a.py").write_text(
        "from . import zz_cycle_b\n", encoding="utf-8")
    (al / "zz_cycle_b.py").write_text(
        "import server.al.zz_cycle_a\n", encoding="utf-8")
    out = check_cycles(root, CYCLE_ALLOW)
    assert len(out) == 1 and CYCLE_RULE in out[0]
    assert "zz_cycle_a" in out[0] and "zz_cycle_b" in out[0]


def test_function_level_import_is_not_an_edge(tmp_path):
    root = _copy(tmp_path)
    al = root / "server" / "al"
    (al / "zz_cycle_a.py").write_text(
        "from . import zz_cycle_b\n", encoding="utf-8")
    (al / "zz_cycle_b.py").write_text(
        "def f():\n    from . import zz_cycle_a\n    return zz_cycle_a\n",
        encoding="utf-8")
    assert check_cycles(root, CYCLE_ALLOW) == []


def test_planted_text_module_outside_the_gate_fails(tmp_path):
    root = _copy(tmp_path)
    body = "".join('S%d = "This is player sentence number %d here."\n'
                   % (i, i) for i in range(5))
    (root / "server" / "al" / "zz_text.py").write_text(body, encoding="utf-8")
    out = check_text(root, EXEMPT)
    assert out == ["server/al/zz_text.py (5 sentences): " + TEXT_RULE]
    # the same module under the gate passes
    (root / "server" / "al" / "zz_text.py").rename(
        root / "server" / "al" / "text" / "zz_text.py")
    assert check_text(root, EXEMPT) == []


def test_stale_exempt_entry_fails(tmp_path):
    root = _copy(tmp_path)
    stale = dict(EXEMPT)
    stale["server/al/zz_gone.py"] = "a module that does not exist"
    out = check_text(root, stale)
    assert out == ["server/al/zz_gone.py: fewer than %d sentences or gone, "
                   "remove it from EXEMPT" % SENTENCE_MIN]


def test_stale_cycle_allow_entry_fails(tmp_path):
    root = _copy(tmp_path)
    stale = dict(CYCLE_ALLOW)
    stale[("server.al.num", "server.al.state")] = "not a real import"
    out = check_cycles(root, stale)
    assert out == ["server.al.num -> server.al.state: no longer a "
                   "module-level import, remove it from CYCLE_ALLOW"]
