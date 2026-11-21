#!/usr/bin/env python3
"""Release assets (REL-BUILD-ASSETS, F-048, DEP-08, F-148, decision 0064).

tools/rel_build.py calls stage() once from build(), after every app-zip
check and before anything is written, so a refusal here leaves no output
folder. stage() returns every asset of the release beside the app zip, in
memory:

    install.ps1                  the tracked bootstrap scripts/install.ps1 at
                                 the ref with the version stamped in; absent,
                                 with a note, while that file does not exist
    release.json                 name, version, channel, commit, created (the
                                 commit time), bootstrap_protocol 1, the two
                                 runtime pins and the asset list (name, size,
                                 sha256 of every other asset but the sums)
    AshLight-<ver>-notes.md      a byte copy of docs/releases/<ver>.md
    AshLight-<ver>.sbom.json     tools/sbom.py output for the commit
    SHA256SUMS.txt               one '<sha256>  <name>' line per asset, sorted

The release inputs are config/runtime_pins.json, config/electron_pin.json
and app/package-lock.json at the ref. All present: the full set is built
and a missing notes file refuses. None present (a stand-in tree, such as the
scratch repos of the installer tests): only the zip and SHA256SUMS.txt, with
a note. Some present: a refusal.

Refusals of the staged tree, every time (the stand-in case included):
- sweep_staged(): tools/leak_sweep.py's two arms over every staged file and
  asset name and its bytes; a finding refuses, naming the file, line and
  kind, never the matched text. Without a needle config (CI) the structural
  arm still runs and a note says so; a broken config refuses.
- ninja_gate(): a staged server/al/ninja.py must hold exactly one top-level
  `RELEASE_POLLING = True|False` (the decision 0072 contract). True refuses
  unless a decision file docs/decisions/NNNN-*.md at the ref holds a line
  that starts `Release polling: allowed by ` followed by `poe.ninja's
  written yes`, `an approved mirror` or `the operator's written ruling`
  (decision 0072 item 5).

Reproducible: bytes come from git blobs at the ref; nothing reads the clock,
the host name or a random source; no network; nothing is written here.
Stdlib only.
"""
import ast
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent

NAME = "AshLight"
BOOTSTRAP_PROTOCOL = 1
SCHEMA = 1
INSTALLER_REL = "scripts/install.ps1"
INSTALLER_NAME = "install.ps1"
RELEASE_NAME = "release.json"
SUMS_NAME = "SHA256SUMS.txt"
NOTES_DIR_REL = "docs/releases"
RUNTIME_REL = "config/runtime_pins.json"
ELECTRON_REL = "config/electron_pin.json"
LOCK_REL = "app/package-lock.json"
RELEASE_INPUTS = (RUNTIME_REL, ELECTRON_REL, LOCK_REL)
NINJA_REL = "server/al/ninja.py"
NINJA_CONSTANT = "RELEASE_POLLING"
DECISIONS_REL = "docs/decisions"
ELECTRON_ARCH = "x64"
PYTHON_ARCH = "amd64"
# The bootstrap's stamp point: every occurrence becomes the version.
VERSION_TOKEN = "__AL_VERSION__"
STAMP_MARKER = "al-version-stamp"  # tools/rel_version.py MARKER

_DECISION_FILE = re.compile(r"^docs/decisions/\d{4}-[A-Za-z0-9._-]+\.md$")
_POLLING_RECORD = re.compile(
    r"^Release polling: allowed by (poe\.ninja's written yes|an approved "
    r"mirror|the operator's written ruling)\b", re.M)
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_STAMP_LINE = re.compile(r"(?:<!--|#|//|;)[ \t]*" + re.escape(STAMP_MARKER)
                         + r"(?![\w-])")


class AssetError(Exception):
    """A refusal; nothing has been written."""


def _load(name):
    spec = importlib.util.spec_from_file_location(
        "rel_assets_" + name, str(TOOLS / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- git -------------------------------------------------------------------

def _git(root, *args):
    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          check=False)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise AssetError("git %s failed: %s" % (args[0], err[-1] if err else
                                                 "exit %d" % proc.returncode))
    return proc.stdout


def _show(root, commit, rel):
    """The blob bytes of rel at the commit, or None when it is absent."""
    proc = subprocess.run(["git", "cat-file", "blob", "%s:%s" % (commit, rel)],
                          cwd=str(root), capture_output=True, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def commit_time(root, commit):
    return int(_git(root, "show", "-s", "--format=%ct", commit)
               .decode("ascii").strip())


def decision_texts(root, commit):
    """{rel: text} of every decision file under docs/decisions at the ref."""
    out = _git(root, "ls-tree", "-r", "-z", "--name-only", "--full-tree",
               commit, "--", DECISIONS_REL)
    texts = {}
    for rel in sorted(p for p in out.decode("utf-8", "replace").split("\0") if p):
        if not _DECISION_FILE.match(rel):
            continue
        data = _show(root, commit, rel)
        if data is not None:
            texts[rel] = data.decode("utf-8", "replace")
    return texts


# --- helpers ---------------------------------------------------------------

def _json_bytes(obj):
    return (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True)
            + "\n").encode("ascii")


def _json(data, rel):
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise AssetError("%s is not JSON" % rel)
    if not isinstance(doc, dict):
        raise AssetError("%s is not an object" % rel)
    return doc


def notes_name(version):
    return "%s-%s-notes.md" % (NAME, version)


def sbom_name(version):
    return "%s-%s.sbom.json" % (NAME, version)


def channel(version):
    """'rc' for an X.Y.Z-rc.N version, 'stable' for X.Y.Z."""
    return "rc" if "-" in version else "stable"


def _entry(name, data):
    return {"name": name, "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data)}


# --- runtime pins ----------------------------------------------------------

def _check_pin(name, pin):
    for key in ("version", "file", "url", "sha256", "size", "licence"):
        if key not in pin or pin[key] in (None, ""):
            raise AssetError("%s runtime pin has no %s" % (name, key))
    for key in ("version", "file", "url", "licence"):
        if not isinstance(pin[key], str):
            raise AssetError("%s runtime pin: %s is not text" % (name, key))
    if not pin["url"].startswith("https://") \
            or not pin["url"].endswith("/" + pin["file"]):
        raise AssetError("%s runtime pin: url does not end with the pinned "
                         "file name" % name)
    if not isinstance(pin["sha256"], str) or not _HEX64.match(pin["sha256"]):
        raise AssetError("%s runtime pin: sha256 is not 64 lower-case hex" % name)
    size = pin["size"]
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise AssetError("%s runtime pin: size is not a positive integer" % name)
    return pin


def runtime_pins(runtime_data, electron_data):
    """{python, electron} pins {version, file, url, sha256, size, licence}
    from the two pin files' bytes, the shape pinfetch.load_runtime_pin and
    the installer's payload.pins_from_release use (Electron for x64)."""
    doc = _json(runtime_data, RUNTIME_REL)
    runtimes = doc.get("runtimes")
    if not isinstance(runtimes, dict):
        raise AssetError("%s has no runtimes table" % RUNTIME_REL)
    py = runtimes.get("python")
    if not isinstance(py, dict) or py.get("arch") != PYTHON_ARCH:
        raise AssetError("%s: no python pin for %s" % (RUNTIME_REL, PYTHON_ARCH))
    el = runtimes.get("electron")
    if not isinstance(el, dict) or el.get("pin_file") != ELECTRON_REL:
        raise AssetError("%s: electron must name %s" % (RUNTIME_REL, ELECTRON_REL))
    edoc = _json(electron_data, ELECTRON_REL)
    spec = (edoc.get("arch") or {}).get(ELECTRON_ARCH) \
        if isinstance(edoc.get("arch"), dict) else None
    if not isinstance(spec, dict):
        raise AssetError("%s: no pin for %s" % (ELECTRON_REL, ELECTRON_ARCH))
    pins = {
        "python": {k: py.get(k) for k in ("version", "file", "url", "sha256",
                                          "size", "licence")},
        "electron": {"version": edoc.get("version"), "file": spec.get("zip_name"),
                     "url": spec.get("zip_url"), "sha256": spec.get("zip_sha256"),
                     "size": spec.get("zip_size"), "licence": el.get("licence")},
    }
    for name in ("python", "electron"):
        _check_pin(name, pins[name])
    return pins


# --- the assets ------------------------------------------------------------

def stamp_installer(data, version):
    """The bootstrap bytes with VERSION_TOKEN replaced by the version. A
    bootstrap without the token must carry stamp lines (tools/rel_version.py
    marker) that already hold the version; one with neither refuses."""
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise AssetError("%s is not ASCII" % INSTALLER_REL)
    if VERSION_TOKEN in text:
        return text.replace(VERSION_TOKEN, version).encode("ascii")
    stamps = [ln for ln in text.split("\n") if _STAMP_LINE.search(ln)]
    if not stamps:
        raise AssetError("%s has no version stamp point (%s or a %s line)"
                         % (INSTALLER_REL, VERSION_TOKEN, STAMP_MARKER))
    held = re.compile(r"(?<![\w.-])" + re.escape(version) + r"(?![\w-]|\.\d)")
    for ln in stamps:
        if not held.search(ln):
            raise AssetError("%s: a stamped line does not hold %s"
                             % (INSTALLER_REL, version))
    return data


def copy_notes(root, commit, version):
    """The bytes of docs/releases/<version>.md at the ref; refuses when absent."""
    rel = "%s/%s.md" % (NOTES_DIR_REL, version)
    data = _show(root, commit, rel)
    if data is None:
        raise AssetError("%s is missing at %s (release.py notes %s --write)"
                         % (rel, commit[:12], version))
    return data


def run_sbom(root, commit):
    """tools/sbom.py output for the commit, byte for byte."""
    sbom = _load("sbom")
    try:
        full, when = sbom.resolve(root, commit)
        return sbom.render(sbom.build(sbom.read_inputs(root, full), full, when))
    except sbom.SbomError as exc:
        raise AssetError("sbom: %s" % exc)


def release_json(version, commit, created, pins, assets):
    """release.json bytes; assets is [(name, bytes)] of every other asset
    the release.json lists (all but itself and SHA256SUMS.txt)."""
    if not _HEX40.match(commit or ""):
        raise AssetError("commit must be a full 40-hex id")
    listed = sorted((_entry(n, d) for n, d in assets), key=lambda e: e["name"])
    return _json_bytes({
        "assets": listed,
        "bootstrap_protocol": BOOTSTRAP_PROTOCOL,
        "channel": channel(version),
        "commit": commit,
        "created": created,
        "name": NAME,
        "runtimes": pins,
        "schema": SCHEMA,
        "version": version,
    })


def sums(assets):
    """SHA256SUMS.txt bytes: one '<sha256>  <name>' line per asset, sorted
    by name; assets is {name: bytes}."""
    return "".join("%s  %s\n" % (hashlib.sha256(assets[n]).hexdigest(), n)
                   for n in sorted(assets)).encode("ascii")


# --- refusals of the staged tree -------------------------------------------

def sweep_staged(staged, needles=None, notes=None):
    """tools/leak_sweep.py over {name: bytes}: each name and its bytes
    (text: both arms; binary: the needle arm). needles None loads the
    sweep's own config (worktree first, then the main checkout; env
    AL_LEAK_NEEDLES replaces it). Refuses on a finding or a broken config;
    returns the number of files scanned."""
    ls = _load("leak_sweep")
    mode = "ARMED"
    if needles is None:
        config, _source = ls.resolve_config(ROOT)
        try:
            needles, mode = ls.load_needles(config)
        except (ValueError, OSError) as exc:
            raise AssetError("leak sweep could not run: %s" % exc)
    if mode != "ARMED" and notes is not None:
        notes.append("leak sweep DEGRADED: no needle config, structural arm "
                     "only")
    rx = ls.compile_needles(needles)
    findings = []
    for name in sorted(staged):
        findings += ls.scan_text(name, "path", rx)
        findings += ls.scan_blob(staged[name], name, rx)
    if findings:
        where, line, kind = findings[0]
        raise AssetError("leak sweep: %d finding(s) in the staged tree, first "
                         "%s:%s %s" % (len(findings), where, line, kind))
    return len(staged)


def release_polling(source):
    """The literal value of the one top-level RELEASE_POLLING assignment of
    ninja.py's source; refuses when there is none, more than one, or a
    value that is not a plain True or False."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        raise AssetError("%s does not parse" % NINJA_REL)
    values = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == NINJA_CONSTANT for t in targets):
            values.append(node.value if not isinstance(node, ast.AugAssign) else None)
    if len(values) != 1:
        raise AssetError("%s: expected one top-level %s assignment, found %d"
                         % (NINJA_REL, NINJA_CONSTANT, len(values)))
    value = values[0]
    if not isinstance(value, ast.Constant) or not isinstance(value.value, bool):
        raise AssetError("%s: %s must be a plain True or False"
                         % (NINJA_REL, NINJA_CONSTANT))
    return value.value


def ninja_gate(staged, decisions, notes=None):
    """Decision 0072's release switch: a staged ninja.py with RELEASE_POLLING
    True refuses unless a decision records the yes. staged is {path: bytes}
    of the app tree, decisions {rel: text}. Returns the constant's value, or
    None when ninja.py is not shipped."""
    data = staged.get(NINJA_REL)
    if data is None:
        if notes is not None:
            notes.append("poe.ninja gate: %s is not shipped" % NINJA_REL)
        return None
    on = release_polling(data.decode("utf-8", "replace"))
    if on and not any(_POLLING_RECORD.search(t) for t in decisions.values()):
        raise AssetError("%s ships with %s = True and no decision records "
                         "poe.ninja's yes (decision 0072)"
                         % (NINJA_REL, NINJA_CONSTANT))
    return on


# --- the one entry from rel_build.build() ----------------------------------

def stage(root, ready, needles=None):
    """Every refusal, then every asset but the zip in memory. ready is
    rel_build.prepare()'s dict. Returns {"assets": {name: bytes} (the zip
    excluded, SHA256SUMS.txt included), "order": names to write (the sums
    last), "notes": [text]}; raises AssetError."""
    root = Path(root)
    commit, version = ready["commit"], ready["version"]
    files, notes = ready["files"], []
    present = {rel: _show(root, commit, rel) for rel in RELEASE_INPUTS}
    missing = [rel for rel in RELEASE_INPUTS if present[rel] is None]
    assets = {}
    if len(missing) == len(RELEASE_INPUTS):
        notes.append("release assets skipped: no release inputs (%s) at %s"
                     % (", ".join(RELEASE_INPUTS), commit[:12]))
    elif missing:
        raise AssetError("incomplete release inputs at %s: %s missing"
                         % (commit[:12], ", ".join(missing)))
    else:
        pins = runtime_pins(present[RUNTIME_REL], present[ELECTRON_REL])
        installer = _show(root, commit, INSTALLER_REL)
        if installer is None:
            notes.append("install.ps1 not built: %s does not exist at %s"
                         % (INSTALLER_REL, commit[:12]))
        else:
            assets[INSTALLER_NAME] = stamp_installer(installer, version)
        assets[notes_name(version)] = copy_notes(root, commit, version)
        assets[sbom_name(version)] = run_sbom(root, commit)
        listed = [(ready["zip_name"], ready["zip"])] + sorted(assets.items())
        assets[RELEASE_NAME] = release_json(version, commit, ready["created"],
                                            pins, listed)
    staged = dict(files)
    for name, data in assets.items():
        staged["release/" + name] = data
    ninja_gate(files, decision_texts(root, commit), notes)
    sweep_staged(staged, needles=needles, notes=notes)
    everything = dict(assets)
    everything[ready["zip_name"]] = ready["zip"]
    assets[SUMS_NAME] = sums(everything)
    order = sorted(n for n in assets if n != SUMS_NAME) + [SUMS_NAME]
    for text in notes:
        print("build: note: %s" % text, file=sys.stderr)
    return {"assets": assets, "order": order, "notes": notes}
