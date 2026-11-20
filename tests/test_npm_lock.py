"""OVL-NPM-LOCK (F-037): npm never runs a package script, never installs
without the lockfile, and its requests name AshLight.

- app/.npmrc (tracked) sets ignore-scripts, engine-strict and save-exact to
  true and a user-agent naming AshLight with the app version; that line
  carries the release stamp so 'release.py bump' moves it with VERSION.
- scripts/setup.ps1 calls npm only as `npm ci --ignore-scripts` and refuses
  when the lockfile is missing (no `npm install` branch).
- app/package-lock.json holds no install script and exactly 13 packages;
  electron sits under dependencies (exact pin) in package.json and the lock.
- The loop's order prompt tells a dependency-bump lane to pass
  --ignore-scripts, to run `npm audit signatures` and to let a version
  published under 3 days ago wait.
Pure file reads; no npm, no network, no process.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
NPMRC = APP / ".npmrc"
PKG = APP / "package.json"
LOCK = APP / "package-lock.json"
SETUP = ROOT / "scripts" / "setup.ps1"

sys.path.insert(0, str(ROOT / "tools"))
import al_lane  # noqa: E402
import loop_inbox  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, str(ROOT / "tools" / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _version():
    text = (ROOT / "server" / "al" / "__init__.py").read_text(encoding="ascii")
    return re.search(r'^VERSION = "([^"]+)"$', text, re.M).group(1)


def _npmrc():
    """{key: value} as npm's ini reader sees it (inline ; or # comment cut)."""
    out = {}
    for line in NPMRC.read_text(encoding="ascii").split("\n"):
        s = line.strip()
        if not s or s[0] in ";#":
            continue
        key, sep, value = s.partition("=")
        assert sep, "not a key=value line: %r" % line
        value = re.split(r"[;#]", value, maxsplit=1)[0].strip()
        assert key.strip() not in out, "duplicate key " + key
        out[key.strip()] = value
    return out


# ---------------------------------------------------------------- .npmrc

def test_npmrc_is_ascii_lf_and_tracked_shape():
    data = NPMRC.read_bytes()
    data.decode("ascii")
    assert b"\r" not in data and data.endswith(b"\n")


def test_npmrc_locks_scripts_engines_and_exact_saves():
    rc = _npmrc()
    assert rc.get("ignore-scripts") == "true"
    assert rc.get("engine-strict") == "true"
    assert rc.get("save-exact") == "true"


def test_npmrc_user_agent_names_ashlight_and_the_app_version():
    rc = _npmrc()
    ua = rc.get("user-agent", "")
    version = _version()
    pkg = json.loads(PKG.read_text(encoding="utf-8"))
    assert pkg["version"] == version
    assert ua.startswith("AshLight/" + version + " "), ua
    assert "{npm-version}" in ua and "{node-version}" in ua


def test_npmrc_user_agent_line_is_a_release_stamp():
    rv = _load("rel_version")
    lines = [ln for ln in NPMRC.read_text(encoding="ascii").split("\n")
             if ln.startswith("user-agent=")]
    assert len(lines) == 1
    assert rv.is_stamp_line(lines[0])  # release.py bump moves it with VERSION


# ---------------------------------------------------------------- setup.ps1

def _setup():
    return SETUP.read_text(encoding="ascii")


def test_every_setup_npm_call_is_ci_with_ignore_scripts():
    calls = [ln for ln in _setup().splitlines()
             if re.search(r"\bnpm(\.cmd)?\b", ln) and "Invoke-AlLogged" in ln]
    assert calls, "setup.ps1 lost its npm step"
    for ln in calls:
        assert "'--ignore-scripts'" in ln, ln
        assert "@('ci'," in ln, ln


def test_setup_has_no_lockfile_less_install_branch():
    text = _setup()
    assert "'install'" not in text
    assert not re.search(r"npm(\.cmd)?'?\s+install\b", text, re.I)
    assert "no lockfile)" not in text
    i = text.index("if (-not (Test-Path $lock)) {")
    j = text.index("'npm.cmd'")
    assert i < j and "throw" in text[i:j]


# ---------------------------------------------------------------- package files

def test_electron_is_a_runtime_dependency_with_its_exact_pin():
    pkg = json.loads(PKG.read_text(encoding="utf-8"))
    assert "devDependencies" not in pkg
    assert re.fullmatch(r"\d+\.\d+\.\d+", pkg["dependencies"]["electron"])
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    root = lock["packages"][""]
    assert root["dependencies"] == pkg["dependencies"]
    assert "devDependencies" not in root
    assert lock["packages"]["node_modules/electron"]["version"] == \
        pkg["dependencies"]["electron"]


def test_lockfile_has_no_install_script_and_thirteen_packages():
    text = LOCK.read_text(encoding="utf-8")
    assert "hasInstallScript" not in text
    lock = json.loads(text)
    assert lock["lockfileVersion"] == 3
    pkgs = [k for k in lock["packages"] if k]
    assert len(pkgs) == 13, pkgs
    assert not any(v.get("dev") for v in lock["packages"].values())
    for key in pkgs:
        entry = lock["packages"][key]
        assert entry["resolved"].startswith("https://registry.npmjs.org/"), key
        assert entry["integrity"].startswith("sha512-"), key


# ---------------------------------------------------------------- lane prompt

def test_lane_bump_prompt_names_ignore_scripts_the_3_day_rule_and_signatures():
    p = loop_inbox.order_prompt({"id": "N1", "note": "x.md", "text": "bump"})
    assert "--ignore-scripts" in p
    assert "published under 3 days ago waits" in p
    assert "npm audit signatures" in p


def test_lane_may_run_npm_audit():
    assert "Bash(npm audit:*)" in al_lane.DEP_TOOLS
