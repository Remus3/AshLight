"""RUN-NO-DEAD-ENDS (research 0042 R4, F3, F12, F20; finding F-133): no
player-facing sentence sends the player to a script or to a "settings
file" they cannot find.

Every sentence that sends the player away names the control and its exact
place (Settings, Checks; Settings, Reading and web data; the Start Menu
shortcut). The settings export is the "settings backup". Design 0001
section 8 rule 4 and checklist P2 hold the rule; this test holds the line:
the words "settings file", "scripts" and ".ps1" appear in no player-facing
string. Player-facing strings are the string literals of the modules and
pages listed below (comments, docstrings and log calls are not player
text). A developer note may be allowed by adding its exact text to
DEV_NOTES with the reason; none is allowed today.
"""
import ast
import json
import re
from pathlib import Path

import htmlscan

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN = (
    ("settings file", re.compile(r"settings\s+file", re.I)),
    ("scripts", re.compile(r"\bscripts\b", re.I)),
    (".ps1", re.compile(r"\.ps1\b", re.I)),
)

# Python modules whose string literals are player text (cards, Checks rows,
# fix lines, empty states, API error replies).
PY_FILES = (
    "server/al/diag.py",
    "server/al/state.py",
    "server/al/acts.py",
    "server/al/settingsio.py",
    "server/al/http.py",
    "server/al/hints.py",
    "server/al/playview.py",
    "server/al/playcards.py",
)
PY_GLOBS = ("server/al/text/*.py", "server/al/plug/*.py")
# JSON data whose values are player text (keys starting "_" are notes).
JSON_FILES = ("server/al/data/status_words.json",)
# Pages and page scripts (comments stripped first).
JS_GLOBS = ("web/*.js", "app/shared/*.js", "app/overlay/*.js")
HTML_FILES = ("web/index.html", "app/client/starting.html")

# exact string -> reason; empty: no developer note is shown to players yet
DEV_NOTES = {}

LOG_NAMES = {"log", "logger", "_log", "logging"}


def _hits(text):
    return [name for name, rx in FORBIDDEN if rx.search(text)]


def _py_files():
    out = [ROOT / p for p in PY_FILES]
    for g in PY_GLOBS:
        out += sorted(ROOT.glob(g))
    return [p for p in out if p.is_file()]


def _docstring_ids(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def _log_call_ids(tree):
    """String constants inside log.<level>(...) calls: log text, not player
    text."""
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = node.func.value
            if isinstance(base, ast.Name) and base.id in LOG_NAMES:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Constant):
                        ids.add(id(sub))
    return ids


def py_strings(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstring_ids(tree) | _log_call_ids(tree)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in skip:
            out.append((node.lineno, node.value))
    # adjacent literals ("a " "b") are one Constant already; f-strings keep
    # their literal parts as Constants inside JoinedStr
    return out


def json_strings(doc, out):
    if isinstance(doc, dict):
        for k, v in doc.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            json_strings(v, out)
    elif isinstance(doc, list):
        for v in doc:
            json_strings(v, out)
    elif isinstance(doc, str):
        out.append(doc)
    return out


def js_strings(text):
    """The string literals of a JavaScript source (quotes and template
    literals), comments skipped. A '/' that does not start a comment is
    taken as code (division or a regex literal)."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c == "/" and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif c in "\"'`":
            j, buf = i + 1, []
            while j < n and text[j] != c:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j:j + 2])
                    j += 2
                    continue
                if text[j] == "\n" and c != "`":
                    break
                buf.append(text[j])
                j += 1
            out.append("".join(buf))
            i = j + 1
        else:
            i += 1
    return out


def html_text(text):
    """text with comments and script elements cut (html.parser, decision
    0087: no tag regex)."""
    return htmlscan.cut(text)


def player_strings():
    """(where, text) for every player-facing string in scope."""
    out = []
    for p in _py_files():
        rel = p.relative_to(ROOT).as_posix()
        out += [(f"{rel}:{ln}", s) for ln, s in py_strings(p)]
    for rel in JSON_FILES:
        doc = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        out += [(rel, s) for s in json_strings(doc, [])]
    for g in JS_GLOBS:
        for p in sorted(ROOT.glob(g)):
            rel = p.relative_to(ROOT).as_posix()
            out += [(rel, s) for s in js_strings(p.read_text(encoding="utf-8"))]
    for rel in HTML_FILES:
        out.append((rel, html_text((ROOT / rel).read_text(encoding="utf-8"))))
    return out


def test_no_player_string_names_settings_file_scripts_or_ps1():
    bad = []
    for where, s in player_strings():
        if s in DEV_NOTES:
            continue
        for name in _hits(s):
            bad.append(f"{where}: {name!r} in {s[:90]!r}")
    assert not bad, "\n".join(bad)


def test_the_scanner_sees_every_kind_of_source():
    # a scanner that reads nothing would pass the test above
    found = player_strings()
    kinds = {w.split(":")[0].rsplit(".", 1)[-1] for w, _ in found}
    assert {"py", "json", "js", "html"} <= kinds
    assert len(found) > 1000
    # the comment and docstring rules: code-side mentions are not player text
    assert js_strings('/* run scripts\\x.ps1 */ var a = "ok"; // .ps1\n') == ["ok"]
    assert _hits("Run scripts\\setup.ps1") == ["scripts", ".ps1"]
    assert _hits("Import a Settings File") == ["settings file"]
    assert _hits("transcripts.ps1x") == []


def test_export_is_called_settings_backup():
    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert '<button id="settings-export" type="button">Download settings backup</button>' in page
    assert '<label for="settings-import-file">Import a settings backup</label>' in page
    sio = (ROOT / "web" / "settingsio.js").read_text(encoding="utf-8")
    for name in ("TOO_BIG", "NOT_JSON", "SAVED"):
        m = re.search(r"var %s = (.+?);\n" % name, sio, re.S)
        assert m and "settings backup" in m.group(1), name
    assert '"Download settings backup"' in sio and '"Import a settings backup"' in sio
    from server.al import settingsio
    for doc in ({"kind": "nope"}, {"kind": settingsio.KIND, "schema": 999},
                {"kind": settingsio.KIND, "schema": 1}):
        try:
            settingsio.parse_import(doc, {})
        except settingsio.SettingsError as e:
            assert "settings backup" in str(e), doc
        else:
            raise AssertionError(doc)


def test_calc_pointer_names_the_rows_button():
    # the words that send the player to the calc name the Checks row's
    # button, and the button really carries that label (web/checks.js)
    from server.al import diag
    from server.al.text import explain, itemcheck
    checks = (ROOT / "web" / "checks.js").read_text(encoding="utf-8")
    assert f'var CALC_BUTTON = "{diag.CALC_BUTTON}";' in checks
    quoted = f'"{diag.CALC_BUTTON}" under Settings, Checks'
    assert quoted in diag.FIX_CALC and explain.FIX_CALC_SETUP == diag.FIX_CALC
    assert quoted in itemcheck.CALC_NOTICE_TEXT["off"]
    sio = (ROOT / "web" / "settingsio.js").read_text(encoding="utf-8")
    assert quoted.replace('"', '\\"') in sio
    assert "again" not in diag.FIX_CALC  # F20 c: it may never have been installed


def test_places_named_exist_on_the_page():
    # "Settings, Checks" and "Settings, Reading and web data" are real places
    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'id="tab-settings"' in page and ">Settings <span" in page
    assert '<h3 id="checks-title">Checks</h3>' in page
    assert '<h3 id="reading-title" tabindex="-1">Reading and web data</h3>' in page
    reading = page.index('id="reading-title"')
    for control in ('id="webdata-on"', 'id="webdata-contact"', 'id="logpath-in"'):
        assert page.index(control) > reading, control
    assert "Use web data</label>" in page and ">Use</button>" in page
