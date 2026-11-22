#!/usr/bin/env python3
"""Release stage (DEP-12, F-074, decision 0064): the PASS / FAIL report.

Loaded by tools/release.py for the `stage` sub-command:

    release.py stage [VERSION] [--sandbox] [--owner ID] [--out DIR] [--root DIR]

VERSION defaults to the source VERSION. The static gates run in order; the
first refusal stops the run and every later step reads `skipped`:

    1 clean     the tree is clean (tracked changes and untracked files)
    2 version   VERSION is SemVer, equals the asked version, and every
                version-bearing place holds it (tools/rel_version.py check)
    3 suite     the Python suite, always through the kit suite gate:
                python ops/fleet_kit/fleet_suite_gate.py run --owner ID --
                python tools/suite_run.py
    4 node      npm test --prefix app
    5 builds    two builds of HEAD (tools/rel_build.py build) into two
                scratch folders; every asset must be byte-identical
    6 sweep     tools/leak_sweep.py over the staged tree as written: every
                app zip member and every asset, names and bytes
    7 roundtrip plan step (6), REL-STAGE-ROUNDTRIP: a scratch home under
                <sidecar>/Temp, the real pinned runtimes from the sidecar
                Cache (runtimes/, then electron/; size and SHA-256 checked; a
                miss fails the step, never a download), then in order:
                install N-1 (the newest v* tag below VERSION, else a
                synthetic N-1 built from a local --shared clone with the
                version swapped down), update to N (installer update +
                apply-staged), rollback, uninstall (only data/ stays),
                reinstall N and uninstall -Purge (the scratch data/ goes to
                the Recycle Bin, adjudicator ruling). Every child runs hidden
                at below-normal priority with AL_SHELL_ROOT on a scratch
                root, so shortcuts, the uninstall key and the logon task are
                never the operator's real ones; a read of AshLight's own real
                entry names before and after must be equal. The shipped
                self-test ports must lie in 8970-8975 (never 8960) and the
                scratch home's web data must read off after every install.
    8 sandbox   plan step (7), REL-STAGE-SANDBOX, ONLY with --sandbox (off
                by default; operator act OA-14): the staged assets and the
                cached runtimes in a read-only mapped folder, a .wsb file
                with networking, clipboard, GPU, audio, video and printers
                off, and inside Windows Sandbox an install, a read-back of
                the per-user uninstall key, shortcuts and home, an
                uninstall and a second read-back; one result file comes
                back through the one writable mapped folder. A machine
                without WindowsSandbox.exe fails the step with that reason:
                the tool never turns a Windows feature on and never asks
                for elevation.

On PASS the first build's assets move into the release folder
<sidecar>/Build/release/<version>/ (or --out). Every run, PASS or FAIL,
writes <out>/stage.json: schema, version, commit, verdict, steps (name,
status pass | fail | skipped, detail), assets (name, size, sha256),
sums_sha256 (of SHA256SUMS.txt), created (the injected clock, UTC) and
sandbox ("skipped" without --sandbox, else the sandbox step's status). A FAIL leaves the tree and every release asset as they were: the
scratch build folders are removed and nothing moves.

Steps are a list of callables (STEPS); a later package adds one step by
appending to it. The "sandbox" entry is dropped from the run unless
`--sandbox` was given.

Floor: the tool never looks for the game - no process list, no window
query, no game log access; it reads the repository and its own scratch.
It never uploads, tags or pushes, and commits only inside the round trip's
throw-away clone; no network. Heavy steps (suite, node, builds) run
at below-normal priority. Stdlib only.
"""
import argparse
import datetime
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent

STAGE_NAME = "stage.json"
SCRATCH_NAME = "_stage"
SCHEMA = 1
GATE_REL = "ops/fleet_kit/fleet_suite_gate.py"
SUITE_REL = "tools/suite_run.py"
NODE_ARGV = ("npm", "test", "--prefix", "app")
OWNER_ENV = "FLEET_CLAIM_OWNER"
DEFAULT_OWNER = "release-stage"
BELOW_NORMAL = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
PASS, FAIL = "PASS", "FAIL"


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(
        "rel_stage_" + name, str(TOOLS / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rb = _load_tool("rel_build")
rv = rb.rv


class StepFail(Exception):
    """One step refused; the text is the step's detail."""


# --- the default runner and clock ------------------------------------------

def default_run(argv, cwd):
    """Run argv in cwd at below-normal priority; the exit code. The program
    is resolved on PATH first (npm is npm.cmd on Windows)."""
    argv = list(argv)
    found = shutil.which(argv[0])
    if found:
        argv[0] = found
    kw = {"cwd": str(cwd)}
    if sys.platform == "win32":
        kw["creationflags"] = BELOW_NORMAL
    return subprocess.call(argv, **kw)


def created_text(seconds):
    stamp = datetime.datetime.fromtimestamp(float(seconds),
                                            tz=datetime.timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


# --- the steps -------------------------------------------------------------

def step_clean(ctx):
    lines = rb.dirty(ctx["root"])
    if lines:
        raise StepFail("the tree is dirty (%d path(s), first: %s)"
                       % (len(lines), lines[0][3:]))
    return "clean"


def step_version(ctx):
    want = ctx["version"]
    try:
        rv.parse(want)
    except rv.VersionError as exc:
        raise StepFail(str(exc))
    try:
        have = rv.source_version(ctx["root"])
    except (rv.VersionError, OSError) as exc:
        raise StepFail(str(exc))
    if have != want:
        raise StepFail("VERSION is %s, stage asked for %s" % (have, want))
    problems = rv.check(ctx["root"])
    if problems:
        raise StepFail("%d version problem(s), first: %s"
                       % (len(problems), problems[0]))
    return "VERSION %s everywhere" % want


def suite_argv(owner, python=None):
    """The suite command: always through the kit suite gate."""
    py = python or sys.executable
    return [py, GATE_REL, "run", "--owner", owner, "--", py, SUITE_REL]


def _call(ctx, argv, label):
    try:
        rc = ctx["run"](argv, ctx["root"])
    except OSError as exc:
        raise StepFail("%s could not start: %s" % (label, exc))
    if rc != 0:
        raise StepFail("%s exit %s" % (label, rc))
    return "%s exit 0" % label


def step_suite(ctx):
    return _call(ctx, suite_argv(ctx["owner"]), "suite gate")


def step_node(ctx):
    return _call(ctx, list(NODE_ARGV), "npm test")


def _asset_bytes(folder):
    """{name: bytes} of the plain files in a build folder."""
    return {p.name: p.read_bytes() for p in sorted(Path(folder).iterdir())
            if p.is_file()}


def step_builds(ctx):
    scratch = ctx["scratch"]
    results = []
    for label in ("a", "b"):
        try:
            res = ctx["build"](root=ctx["root"], out=scratch / label)
        except rb.BuildError as exc:
            raise StepFail("build %s refused: %s" % (label, exc))
        results.append(res)
    if results[0]["version"] != ctx["version"]:
        raise StepFail("the build made %s, stage asked for %s"
                       % (results[0]["version"], ctx["version"]))
    first, second = _asset_bytes(scratch / "a"), _asset_bytes(scratch / "b")
    if sorted(first) != sorted(second):
        raise StepFail("the two builds made different asset sets")
    differ = [n for n in sorted(first) if first[n] != second[n]]
    if differ:
        raise StepFail("the two builds differ: %s" % ", ".join(differ))
    if rb.SUMS_NAME not in first:
        raise StepFail("the build wrote no %s" % rb.SUMS_NAME)
    ctx["staged"] = first
    ctx["zip_name"] = results[0]["zip"].name
    return "two identical builds, %d asset(s)" % len(first)


def staged_tree(assets, zip_name):
    """{name: bytes}: every member of the app zip and every other asset."""
    tree = {}
    with zipfile.ZipFile(io.BytesIO(assets[zip_name])) as zf:
        for name in zf.namelist():
            tree[name] = zf.read(name)
    for name, data in assets.items():
        if name != zip_name:
            tree["release/" + name] = data
    return tree


def step_sweep(ctx):
    ra = _load_tool("rel_assets")
    notes = []
    try:
        count = ra.sweep_staged(staged_tree(ctx["staged"], ctx["zip_name"]),
                                notes=notes)
    except (ra.AssetError, zipfile.BadZipFile) as exc:
        raise StepFail(str(exc))
    ctx["notes"].extend(notes)
    return "%d staged file(s) clean%s" % (count, "; " + notes[0] if notes else "")


# --- the scratch-home round trip (REL-STAGE-ROUNDTRIP) ---------------------

RT_PREFIX = "al-stage-rt-"
RT_SUBSTEPS = ("install", "update", "rollback", "uninstall", "purge")
RUNTIME_CACHE_SUBS = ("runtimes", "electron")
RELEASE_JSON = "release.json"
INSTALLER_PS1 = "install.ps1"
LINK_NAME = "AshLight.lnk"
TASK_NAME = "AshLight Autostart"
REAL_UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\AshLight"
SCRATCH_KEY_BASE = r"Software\AshLightShellScratch"
SELFTEST_BLOCK = (8970, 8975)  # ports.SELFTEST_PORTS; never the core's 8960
CORE_PORT = 8960
EXIT_SWITCHED = 10             # apply-staged / rollback: the marker moved
RT_TIMEOUT_S = 900             # one installer or uninstall child
CREATE_NO_WINDOW = 0x08000000
CSIDL_PROGRAMS, CSIDL_DESKTOPDIRECTORY = 0x0002, 0x0010
# the caller's overrides never reach the installer children of the round trip
RT_DROP_ENV = ("AL_HOME", "AL_INSTALL_DIR", "AL_RUNTIME_DIR", "AL_PORT",
               "AL_DEV", "AL_TC_PINS_FILE", "AL_HOT_RELOAD", "AL_UNINSTALL_FAKE",
               "NODE_OPTIONS", "ELECTRON_RUN_AS_NODE", "PYTHONPATH",
               "PYTHONHOME", "PYTHONSTARTUP")
_SELFTEST_LINE = re.compile(
    rb"^SELFTEST_PORTS\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", re.M)


def _server_al():
    """server.al.paths and server.al.autostart_entry of this checkout."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from server.al import autostart_entry, paths  # noqa: E402
    return paths, autostart_entry


def previous_version(version):
    """The synthetic N-1: X.Y.Z-rc.N -> X.Y.Z-rc.(N-1) when N > 0, else the
    core one lower: X.Y.(Z-1), else X.(Y-1).0, else (X-1).0.0; None for
    0.0.0 (nothing sorts below it)."""
    core, _sep, pre = version.partition("-")
    m = re.match(r"^rc\.(\d+)$", pre)
    if m and int(m.group(1)) > 0:
        return "%s-rc.%d" % (core, int(m.group(1)) - 1)
    x, y, z = (int(p) for p in core.split("."))
    if z > 0:
        return "%d.%d.%d" % (x, y, z - 1)
    if y > 0:
        return "%d.%d.0" % (x, y - 1)
    if x > 0:
        return "%d.0.0" % (x - 1)
    return None


def selftest_ports(zip_bytes):
    """(low, high) of SELFTEST_PORTS in the shipped server/al/ports.py."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = [n for n in zf.namelist() if n.endswith("/server/al/ports.py")]
        if len(names) != 1:
            return None
        m = _SELFTEST_LINE.search(zf.read(names[0]))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _sha256_file(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def pin_file_name(pin):
    url = str(pin.get("url") or "")
    name = pin.get("file") or url.rsplit("/", 1)[-1]
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    return name


def find_runtimes(release, cache_dirs):
    """{file name: cached path} for both pinned runtimes of release.json,
    each matched by size and SHA-256; StepFail naming the first miss.
    Nothing is ever requested: a miss is the step's verdict."""
    runtimes = release.get("runtimes") if isinstance(release, dict) else None
    if not isinstance(runtimes, dict) or not runtimes:
        raise StepFail("release.json names no runtimes")
    found = {}
    for key in sorted(runtimes):
        pin = runtimes[key]
        name = pin_file_name(pin) if isinstance(pin, dict) else None
        if name is None or not isinstance(pin.get("size"), int) \
                or not isinstance(pin.get("sha256"), str):
            raise StepFail("release.json: the %s pin is malformed" % key)
        hit = None
        for folder in cache_dirs:
            cand = Path(folder) / name
            try:
                if cand.is_file() and cand.stat().st_size == pin["size"] \
                        and _sha256_file(cand) == pin["sha256"].lower():
                    hit = cand
                    break
            except OSError:
                continue
        if hit is None:
            raise StepFail("runtimes not cached: %s (put the pinned publisher "
                           "zip in the sidecar Cache/runtimes; the stage never "
                           "downloads)" % name)
        found[name] = hit
    return found


def _link_or_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(str(src), str(dst))
    except OSError:
        shutil.copyfile(str(src), str(dst))


def scratch_key_id(root):
    """al_shell's <id> for an effect root: the first 8 bytes of SHA-256 of
    the full, lower-cased root path, as hex."""
    full = os.path.abspath(str(root)).rstrip("\\/")
    return hashlib.sha256(full.lower().encode("utf-8")).hexdigest()[:16]


def _known_folder(csidl):
    if sys.platform != "win32":
        return None
    import ctypes  # noqa: E402 - Windows only
    buf = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) != 0:
        return None
    return buf.value or None


def _file_print(path):
    try:
        st = path.stat()
        return [st.st_size, st.st_mtime_ns, _sha256_file(path)]
    except OSError:
        return None


def _key_values(subkey):
    """{name: repr(value)} of an HKCU key, or None when it is absent."""
    if sys.platform != "win32":
        return None
    import winreg  # noqa: E402 - Windows only
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey)
    except OSError:
        return None
    out = {}
    with key:
        i = 0
        while True:
            try:
                name, value, kind = winreg.EnumValue(key, i)
            except OSError:
                break
            out[name] = "%d:%r" % (kind, value)
            i += 1
    return out


def _task_print(run=None):
    """SHA-256 of the real logon task's XML, or None when there is none.
    A query of AshLight's own task name only."""
    if sys.platform != "win32":
        return None
    run = run or subprocess.run
    try:
        res = run(["schtasks.exe", "/Query", "/TN", "\\" + TASK_NAME, "/XML"],
                  capture_output=True, timeout=60, stdin=subprocess.DEVNULL,
                  creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return "unreadable"
    if res.returncode != 0:
        return None
    return hashlib.sha256(res.stdout or b"").hexdigest()


def real_shell_snapshot():
    """AshLight's own real shell entries, by name only: the two AshLight.lnk
    files (Start Menu Programs, Desktop), the per-user uninstall key and the
    logon task. Read only; no listing of any folder, key or task list."""
    snap = {}
    for label, csidl in (("start_menu", CSIDL_PROGRAMS),
                         ("desktop", CSIDL_DESKTOPDIRECTORY)):
        folder = _known_folder(csidl)
        snap[label] = _file_print(Path(folder) / LINK_NAME) if folder else None
    snap["uninstall_key"] = _key_values(REAL_UNINSTALL_KEY)
    snap["logon_task"] = _task_print()
    return snap


def _read_json(path):
    try:
        doc = json.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


class RoundTripEffects:
    """The real effects of the round trip. Every child runs hidden at
    below-normal priority with AL_SHELL_ROOT = <base>/shell (shortcuts,
    uninstall key and logon task go to the scratch root) and TEMP / TMP =
    <base>/temp. Tests pass a stand-in with the same methods."""

    def __init__(self, ctx, base):
        self.ctx = ctx
        self.base = Path(base)
        self.home = self.base / "home"
        self.shell = self.base / "shell"
        self.temp = self.base / "temp"
        self.rtdir = self.base / "runtimes"
        self.snapshot = ctx.get("snapshot") or real_shell_snapshot

    # --- inputs ---
    def cache_dirs(self):
        if self.ctx.get("runtime_cache") is not None:
            return [Path(p) for p in self.ctx["runtime_cache"]]
        paths, _ae = _server_al()
        cache = paths.sidecar_dir("Cache")
        return [cache / sub for sub in RUNTIME_CACHE_SUBS]

    def runtimes(self, release):
        found = find_runtimes(release, self.cache_dirs())
        for name, src in found.items():
            _link_or_copy(src, self.rtdir / name)
        return sorted(found)

    def write_release(self, label, assets):
        folder = self.base / ("release-" + label)
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in assets.items():
            (folder / name).write_bytes(data)
        return folder

    def previous(self, version):
        """(N-1 version, its assets): the newest v* tag below `version`, else
        a synthetic N-1 built from a local clone with the version swapped
        down (adjudicator ruling, REL-STAGE-ROUNDTRIP Q3)."""
        root, build = self.ctx["root"], self.ctx["build"]
        tag = newest_tag_below(root, version)
        out = self.base / "prev-build"
        try:
            if tag is not None:
                res = build(root=root, out=out, tag=tag)
            else:
                prev = previous_version(version)
                if prev is None:
                    raise StepFail("no version below %s for a synthetic N-1" % version)
                clone = synthetic_clone(root, self.base / "prev-src", version, prev)
                res = build(root=clone, out=out)
        except rb.BuildError as exc:
            raise StepFail("the N-1 build refused: %s" % exc)
        return res["version"], _asset_bytes(out)

    # --- children ---
    def env(self):
        env = dict(os.environ)
        for key in list(env):
            if key.upper() in RT_DROP_ENV:
                del env[key]
        self.temp.mkdir(parents=True, exist_ok=True)
        self.shell.mkdir(parents=True, exist_ok=True)
        env["AL_SHELL_ROOT"] = str(self.shell)
        env["TEMP"] = env["TMP"] = str(self.temp)
        return env

    def _run(self, argv):
        flags = (CREATE_NO_WINDOW | BELOW_NORMAL) if sys.platform == "win32" else 0
        try:
            res = subprocess.run([str(a) for a in argv], cwd=str(self.temp),
                                 env=self.env(), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 timeout=RT_TIMEOUT_S, creationflags=flags)
        except subprocess.TimeoutExpired:
            return -1
        except OSError as exc:
            raise StepFail("could not start %s (%s)" % (Path(str(argv[0])).name,
                                                        exc.__class__.__name__))
        return res.returncode

    def _powershell(self):
        _paths, ae = _server_al()
        exe = ae.powershell_exe()
        if exe is None:
            raise StepFail("SystemRoot is not set; Windows PowerShell not found")
        return [str(exe), "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                "Bypass", "-File"]

    def install(self, folder, version):
        zip_path = Path(folder) / rb.zip_name(version)
        return self._run(self._powershell() + [
            Path(folder) / INSTALLER_PS1, "-Zip", zip_path, "-RuntimeDir",
            self.rtdir, "-InstallDir", self.home, "-NoStart"])

    def installer(self, command, *args):
        """<home python> <active payload>/boot.py server.al.install <command>
        --home <home> [args]: the active version's own installer."""
        marker = _read_json(self.home / "install.json") or {}
        payload = self.home / "app" / str(marker.get("version") or "")
        paths, _ae = _server_al()
        argv = paths.python_cmd("server.al.install", command, "--home",
                                str(self.home), *[str(a) for a in args],
                                root=payload, environ={paths.HOME_ENV: str(self.home),
                                                       "SystemRoot": os.environ.get(
                                                           "SystemRoot", "")})
        return self._run(argv)

    def uninstall(self, purge):
        argv = self._powershell() + [self.home / "uninstall.ps1", "-Quiet"]
        if purge:
            argv += ["-Purge", "-Yes"]
        return self._run(argv)

    # --- read-backs ---
    def scratch_left(self):
        """Scratch shell entries still present (names only)."""
        left = [sub + "/" + LINK_NAME for sub in ("Programs", "Desktop")
                if (self.shell / sub / LINK_NAME).exists()]
        key = SCRATCH_KEY_BASE + "\\" + scratch_key_id(self.shell) + \
            r"\Uninstall\AshLight"
        if _key_values(key) is not None:
            left.append("scratch uninstall key")
        return left

    def cleanup(self):
        _remove_empty_scratch_keys(scratch_key_id(self.shell))
        # the base holds only this run's scratch: its own home, release
        # copies, links of cached runtimes and a clone, all regenerable
        _rmtree_scratch(self.base)


def _rmtree_scratch(path):
    """Remove a scratch tree of this run; git marks some of its files
    read-only, so a refused unlink clears the flag and tries once more."""
    import stat  # noqa: E402

    def retry(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass
    if Path(path).exists():
        shutil.rmtree(str(path), onerror=retry)


def _remove_empty_scratch_keys(key_id):
    """Remove al_shell's scratch registry keys of this effect root when they
    are empty (no values, no subkeys), deepest first; never another key."""
    if sys.platform != "win32":
        return
    import winreg  # noqa: E402 - Windows only
    chain = [SCRATCH_KEY_BASE + "\\" + key_id + r"\Uninstall\AshLight",
             SCRATCH_KEY_BASE + "\\" + key_id + r"\Uninstall",
             SCRATCH_KEY_BASE + "\\" + key_id]
    for sub in chain:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as key:
                subs, values, _t = winreg.QueryInfoKey(key)
            if subs or values:
                return
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
        except OSError:
            continue


def newest_tag_below(root, version):
    """The newest v<X.Y.Z> tag whose version sorts below `version`, else None."""
    try:
        out = rb._git(root, "tag", "--list", "v*")
    except Exception:  # noqa: BLE001 - no tags is the common case
        return None
    text = out.decode("ascii", "replace") if isinstance(out, bytes) else str(out or "")
    best = None
    for tag in text.split():
        ver = tag[1:]
        try:
            rv.parse(ver)
        except rv.VersionError:
            continue
        if rv.compare(ver, version) < 0 and (best is None or rv.compare(ver, best[1]) > 0):
            best = (tag, ver)
    return best[0] if best else None


def downgrade_plan(root, old, new):
    """{rel path: text}: every version-bearing place of `root` moved from
    `old` to the lower `new`, plus the notes stub of `new` (rel_version's
    bump, which refuses a lower version, done the other way)."""
    out = {}
    out[rv.INIT_REL] = rv._swap_once(rv._INIT_LINE, rv._read(root, rv.INIT_REL),
                                     old, new, rv.INIT_REL)
    out[rv.PKG_REL] = rv._swap_once(rv._TOP_VERSION, rv._read(root, rv.PKG_REL),
                                    old, new, rv.PKG_REL)
    lock = rv._read(root, rv.LOCK_REL)
    span = rv._lock_root_span(lock)
    if span is None:
        raise StepFail('%s: packages[""] block not found' % rv.LOCK_REL)
    head = rv._swap_once(rv._TOP_VERSION, lock[:span[0]], old, new, rv.LOCK_REL)
    block = rv._swap_once(rv._ROOT_PKG_VERSION, lock[span[0]:span[1]], old, new,
                          rv.LOCK_REL)
    out[rv.LOCK_REL] = head + block + lock[span[1]:]
    by_file = {}
    for rel, n, _line in rv.stamp_lines(root):
        by_file.setdefault(rel, []).append(n)
    for rel, numbers in by_file.items():
        lines = out.get(rel, rv._read(root, rel)).split("\n")
        for n in numbers:
            lines[n - 1] = rv._swap_on_line(lines[n - 1], old, new)
        out[rel] = "\n".join(lines)
    out[rv.notes_rel(new)] = rv.notes_stub(new)
    return out


def _clone_git(cwd, *args):
    cmd = ["git", "-c", "core.hooksPath=", "-c", "core.autocrlf=false",
           "-c", "commit.gpgsign=false"] + list(args)
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True,
                          stdin=subprocess.DEVNULL, check=False)
    if proc.returncode != 0:
        tail = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        raise StepFail("synthetic N-1: git %s failed%s"
                       % (args[0], ": " + tail[-1][:200] if tail else ""))
    return proc.stdout


def synthetic_clone(root, dest, old, new):
    """A local --shared clone of HEAD under `dest` with one commit that
    moves every version-bearing place to `new`; the clone path. The clone
    is never pushed and is removed with the round trip's scratch; its
    commit carries the operator's own git identity (FLEET item 17)."""
    root, dest = Path(root), Path(dest)
    commit = rb._rev(root, "HEAD^{commit}")
    if not commit:
        raise StepFail("synthetic N-1: no HEAD commit")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _clone_git(dest.parent, "clone", "-q", "--shared", "--no-tags",
               "--no-checkout", str(root), dest.name)
    _clone_git(dest, "checkout", "-q", "--detach", commit)
    plan = downgrade_plan(dest, old, new)
    for rel in sorted(plan):
        rv._write(dest, rel, plan[rel])
    ident = []
    for key in ("user.name", "user.email"):
        proc = subprocess.run(["git", "config", "--get", key], cwd=str(root),
                              capture_output=True, stdin=subprocess.DEVNULL)
        value = (proc.stdout or b"").decode("utf-8", "replace").strip()
        if value:
            ident += ["-c", "%s=%s" % (key, value)]
    _clone_git(dest, "add", "--", *sorted(plan))
    _clone_git(dest, *(ident + ["commit", "-q", "-m",
                                "chore: synthetic %s for the stage round trip" % new]))
    return dest


def _expect(rc, want, label):
    if rc != want:
        raise StepFail("%s exit %s (want %s)" % (label, rc, want))


def _marker(home, label, version, **want):
    doc = _read_json(Path(home) / "install.json")
    if doc is None:
        raise StepFail("%s: no readable install.json" % label)
    if doc.get("version") != version:
        raise StepFail("%s: the marker names %s, want %s"
                       % (label, doc.get("version"), version))
    for key, value in want.items():
        if doc.get(key) != value:
            raise StepFail("%s: marker %s is %r, want %r"
                           % (label, key, doc.get(key), value))
    return doc


def _web_data_off(home, label):
    doc = _read_json(Path(home) / "data" / "local.json")
    if doc is None:
        raise StepFail("%s: no readable data/local.json" % label)
    if doc.get("web_data") is not False:
        raise StepFail("%s: web data is not off in the scratch home" % label)


def _links(fx, label, present):
    have = [sub for sub in ("Programs", "Desktop")
            if (Path(fx.shell) / sub / LINK_NAME).is_file()]
    if present and len(have) != 2:
        raise StepFail("%s: the scratch shortcuts were not written" % label)
    if not present:
        left = fx.scratch_left()
        if left:
            raise StepFail("%s: left behind: %s" % (label, ", ".join(left)))


def default_roundtrip(ctx):
    """The real effects, in a fresh scratch folder under <sidecar>/Temp."""
    paths, _ae = _server_al()
    temp = paths.sidecar_dir("Temp")
    temp.mkdir(parents=True, exist_ok=True)
    import tempfile  # noqa: E402
    base = Path(tempfile.mkdtemp(prefix=RT_PREFIX + ctx["version"] + "-",
                                 dir=str(temp)))
    return RoundTripEffects(ctx, base)


def step_roundtrip(ctx):
    """Plan step (6): install N-1, update to N, rollback, uninstall, purge
    in a scratch home with the real pinned runtimes from the sidecar cache;
    every shell effect goes to a scratch root and the real entries must read
    the same before and after. A runtime that is not cached fails the step
    (never a download)."""
    staged = ctx.get("staged")
    if not staged or RELEASE_JSON not in staged:
        raise StepFail("the build made no %s" % RELEASE_JSON)
    try:
        release = json.loads(staged[RELEASE_JSON].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise StepFail("%s is unreadable" % RELEASE_JSON)
    version, zip_name = ctx["version"], ctx["zip_name"]
    block = selftest_ports(staged[zip_name])
    if block is None or block[0] > block[1] or block[0] < SELFTEST_BLOCK[0] \
            or block[1] > SELFTEST_BLOCK[1] or block[0] <= CORE_PORT <= block[1]:
        raise StepFail("the shipped self-test ports are not inside %d-%d"
                       % SELFTEST_BLOCK)
    fx = ctx["roundtrip"](ctx)
    done = ctx["roundtrip_done"] = []
    try:
        fx.runtimes(release)
        if INSTALLER_PS1 not in staged:
            raise StepFail("the build made no %s" % INSTALLER_PS1)
        before = fx.snapshot()
        prev, prev_assets = fx.previous(version)
        if rv.compare(prev, version) >= 0:
            raise StepFail("the N-1 build is %s, not below %s" % (prev, version))
        new_dir = fx.write_release("new", staged)
        prev_dir = fx.write_release("prev", prev_assets)

        _expect(fx.install(prev_dir, prev), 0, "install %s" % prev)
        _marker(fx.home, "install", prev)
        _web_data_off(fx.home, "install")
        _links(fx, "install", True)
        done.append("install")

        _expect(fx.installer("update", "--zip", new_dir / zip_name,
                             "--runtime-dir", fx.rtdir), 0, "update")
        _expect(fx.installer("apply-staged"), EXIT_SWITCHED, "apply-staged")
        _marker(fx.home, "update", version, previous=prev, pending_confirm=True)
        _web_data_off(fx.home, "update")
        done.append("update")

        _expect(fx.installer("rollback"), EXIT_SWITCHED, "rollback")
        _marker(fx.home, "rollback", prev)
        skip = _read_json(Path(fx.home) / "data" / "update_skip.json") or {}
        rows = skip.get("versions") if isinstance(skip.get("versions"), list) else []
        if version not in [r.get("version") for r in rows if isinstance(r, dict)]:
            raise StepFail("rollback: %s is not in update_skip.json" % version)
        done.append("rollback")

        _expect(fx.uninstall(False), 0, "uninstall")
        kept = sorted(p.name for p in Path(fx.home).iterdir()) \
            if Path(fx.home).is_dir() else []
        if kept != ["data"]:
            raise StepFail("uninstall: the home holds %s, want only data"
                           % (", ".join(kept) or "nothing"))
        _links(fx, "uninstall", False)
        done.append("uninstall")

        _expect(fx.install(new_dir, version), 0, "reinstall %s" % version)
        _marker(fx.home, "reinstall", version)
        _web_data_off(fx.home, "reinstall")
        _expect(fx.uninstall(True), 0, "purge")
        if Path(fx.home).exists() and any(Path(fx.home).iterdir()):
            raise StepFail("purge: the home is not empty")
        _links(fx, "purge", False)
        done.append("purge")

        after = fx.snapshot()
        if after != before:
            changed = sorted(k for k in set(before) | set(after)
                             if before.get(k) != after.get(k))
            raise StepFail("the real shell entries changed: %s" % ", ".join(changed))
    finally:
        fx.cleanup()
    return ("install %s, update to %s, rollback, uninstall, purge; self-test "
            "ports %d-%d, web data off, real shell entries unchanged"
            % ((prev, version) + tuple(block)))


# --- the optional Windows Sandbox phases (REL-STAGE-SANDBOX) ---------------
#
# Plan step (7), only on the operator's explicit --sandbox flag (operator act
# OA-14): the staged assets and the cached pinned runtimes go into a
# read-only mapped folder, a .wsb file turns networking, the clipboard, the
# GPU, audio, video and printers off, and a phase script inside the sandbox
# installs, reads back, uninstalls, reads back, writes one result file into
# the one writable mapped folder and shuts the sandbox down. The sandbox is
# a throw-away VM, so the real per-user uninstall key, shortcuts and home of
# a fresh Windows user are what is checked there. The tool only looks for
# WindowsSandbox.exe by path: it never turns a Windows feature on and never
# asks for elevation; a missing feature is the step's reported verdict.

SANDBOX_STEP = "sandbox"
SB_PREFIX = "al-stage-sb-"
SB_EXE = ("System32", "WindowsSandbox.exe")
# A mapped folder with no SandboxFolder lands on the sandbox user's desktop
# under its host folder name (every Windows Sandbox build supports that), so
# no guest drive path is written anywhere.
SB_ASSETS = "AshLightStage"
SB_RESULTS = "AshLightResults"
SB_SCRIPT = "sandbox_phase.ps1"
SB_RESULT = "result.json"
SB_WSB = "stage.wsb"
SB_TIMEOUT_S = 1800            # the whole sandbox run, boot to shutdown
SB_POLL_S = 5
SB_RESULT_CAP = 64 * 1024
SB_OFF = ("VGpu", "Networking", "ClipboardRedirection", "AudioInput",
          "VideoInput", "PrinterRedirection")
SB_PHASES = ("install", "uninstall")


def _xml(text):
    from xml.sax.saxutils import escape  # noqa: E402
    return escape(str(text))


def wsb_text(assets_dir, results_dir, command):
    """The .wsb configuration: every redirection off, the assets folder
    mapped read-only, the results folder the one writable mapping, one
    logon command."""
    lines = ["<Configuration>"]
    lines += ["  <%s>Disable</%s>" % (k, k) for k in SB_OFF]
    lines += ["  <ProtectedClient>Enable</ProtectedClient>",
              "  <MappedFolders>"]
    for host, ro in ((assets_dir, "true"), (results_dir, "false")):
        lines += ["    <MappedFolder>",
                  "      <HostFolder>%s</HostFolder>" % _xml(host),
                  "      <ReadOnly>%s</ReadOnly>" % ro,
                  "    </MappedFolder>"]
    lines += ["  </MappedFolders>",
              "  <LogonCommand>",
              "    <Command>%s</Command>" % _xml(command),
              "  </LogonCommand>",
              "</Configuration>"]
    return "\n".join(lines) + "\n"


def write_wsb(path, assets_dir, results_dir, command):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(wsb_text(assets_dir, results_dir, command).encode("utf-8"))
    return path


def sandbox_command():
    """The logon command: the phase script from the mapped assets folder on
    the sandbox user's desktop."""
    return ("powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass "
            "-Command \"& (Join-Path $env:USERPROFILE 'Desktop\\%s\\%s')\""
            % (SB_ASSETS, SB_SCRIPT))


def _ps_quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def sandbox_script(version, zip_name):
    """The phase script run inside the sandbox (ASCII, Windows PowerShell
    5.1): install, read back, uninstall, read back, one result file, then
    shut the sandbox down."""
    return "\n".join([
        "# AshLight release stage: sandbox phases (generated; no network)",
        "$ErrorActionPreference = 'Continue'",
        "$assets = Join-Path $env:USERPROFILE %s" % _ps_quote(
            "Desktop\\" + SB_ASSETS),
        "$out = Join-Path $env:USERPROFILE %s" % _ps_quote(
            "Desktop\\" + SB_RESULTS),
        "$alHome = Join-Path $env:LOCALAPPDATA 'Programs\\AshLight'",
        "$key = %s" % _ps_quote("HKCU:\\" + REAL_UNINSTALL_KEY),
        "$links = @((Join-Path ([Environment]::GetFolderPath('Programs')) "
        "%s), (Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) "
        "%s))" % (_ps_quote(LINK_NAME), _ps_quote(LINK_NAME)),
        "$ps = Join-Path $env:SystemRoot "
        "'System32\\WindowsPowerShell\\v1.0\\powershell.exe'",
        "function Get-AlStageState {",
        "    $names = @()",
        "    if (Test-Path -LiteralPath $alHome) {",
        "        $names = @(Get-ChildItem -LiteralPath $alHome -Force -Name)",
        "    }",
        "    return [ordered]@{ key = [bool](Test-Path -LiteralPath $key);",
        "        links = @($links | Where-Object { Test-Path -LiteralPath $_ }).Count;",
        "        home = $names }",
        "}",
        "$r = [ordered]@{ schema = 1; version = %s }" % _ps_quote(version),
        "& $ps -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "
        "(Join-Path $assets 'install.ps1') -Zip (Join-Path $assets %s) "
        "-RuntimeDir (Join-Path $assets 'runtimes') -InstallDir $alHome "
        "-NoStart" % _ps_quote(zip_name),
        "$r.install = [ordered]@{ rc = $LASTEXITCODE; state = (Get-AlStageState) }",
        "$un = Join-Path $alHome 'uninstall.ps1'",
        "if (Test-Path -LiteralPath $un) {",
        "    & $ps -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $un -Quiet",
        "    $rc = $LASTEXITCODE",
        "} else { $rc = -2 }",
        "$r.uninstall = [ordered]@{ rc = $rc; state = (Get-AlStageState) }",
        "$tmp = Join-Path $out 'result.partial'",
        "$r | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $tmp -Encoding Ascii",
        "Move-Item -LiteralPath $tmp -Destination (Join-Path $out %s) -Force"
        % _ps_quote(SB_RESULT),
        "& (Join-Path $env:SystemRoot 'System32\\shutdown.exe') /s /t 0",
        ""])


class SandboxEffects:
    """The real effects of the sandbox phases: a scratch base under
    <sidecar>/Temp holding AshLightStage/ (mapped read-only),
    AshLightResults/ (the one writable mapping) and the .wsb file. Tests pass a stand-in with the same
    methods; nothing here turns a feature on or asks for elevation."""

    def __init__(self, ctx, base):
        self.ctx = ctx
        self.base = Path(base)
        self.assets = self.base / SB_ASSETS
        self.results = self.base / SB_RESULTS
        self.proc = None

    def exe(self):
        root = os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT")
        return Path(root, *SB_EXE) if root else None

    def feature_present(self):
        """WindowsSandbox.exe exists: a path check only, no query of the
        Windows feature store (that needs elevation)."""
        exe = self.exe()
        return bool(exe and exe.is_file())

    def cache_dirs(self):
        if self.ctx.get("runtime_cache") is not None:
            return [Path(p) for p in self.ctx["runtime_cache"]]
        paths, _ae = _server_al()
        cache = paths.sidecar_dir("Cache")
        return [cache / sub for sub in RUNTIME_CACHE_SUBS]

    def runtimes(self, release):
        """{file name: cached path} of both pinned runtimes (StepFail on a
        miss; never a download)."""
        return find_runtimes(release, self.cache_dirs())

    def put_assets(self, staged, runtimes):
        self.assets.mkdir(parents=True, exist_ok=True)
        self.results.mkdir(parents=True, exist_ok=True)
        for name, data in staged.items():
            (self.assets / name).write_bytes(data)
        for name, src in runtimes.items():
            _link_or_copy(src, self.assets / "runtimes" / name)

    def launch(self, wsb):
        flags = BELOW_NORMAL if sys.platform == "win32" else 0
        try:
            self.proc = subprocess.Popen([str(self.exe()), str(wsb)],
                                         stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL,
                                         creationflags=flags)
        except OSError as exc:
            raise StepFail("could not start Windows Sandbox (%s)"
                           % exc.__class__.__name__)

    def wait_result(self, timeout=SB_TIMEOUT_S):
        """The result file's bytes, or None after the timeout."""
        path = self.results / SB_RESULT
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if path.is_file():
                return path.read_bytes()[:SB_RESULT_CAP]
            time.sleep(SB_POLL_S)
        return None

    def cleanup(self):
        # the base holds only this run's copies of the staged assets, links
        # of cached runtimes and the sandbox's result: all regenerable
        _rmtree_scratch(self.base)


def default_sandbox(ctx):
    """The real effects, in a fresh scratch folder under <sidecar>/Temp."""
    paths, _ae = _server_al()
    temp = paths.sidecar_dir("Temp")
    temp.mkdir(parents=True, exist_ok=True)
    import tempfile  # noqa: E402
    base = Path(tempfile.mkdtemp(prefix=SB_PREFIX + ctx["version"] + "-",
                                 dir=str(temp)))
    return SandboxEffects(ctx, base)


def _home_names(state):
    names = state.get("home")
    if isinstance(names, str):  # ConvertTo-Json flattens a one-item list
        names = [names]
    return sorted(str(n) for n in names) if isinstance(names, list) else None


def check_sandbox_result(raw, version):
    """The phase script's result, read back; StepFail naming the first
    phase that did not read back."""
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError, AttributeError):
        raise StepFail("sandbox: the result file is unreadable")
    if not isinstance(doc, dict) or doc.get("version") != version:
        raise StepFail("sandbox: the result names another version")
    for phase in SB_PHASES:
        row = doc.get(phase)
        state = row.get("state") if isinstance(row, dict) else None
        if not isinstance(state, dict):
            raise StepFail("sandbox %s: no read-back" % phase)
        if row.get("rc") != 0:
            raise StepFail("sandbox %s exit %s (want 0)" % (phase, row.get("rc")))
        names = _home_names(state)
        if phase == "install":
            if state.get("key") is not True:
                raise StepFail("sandbox install: no per-user uninstall key")
            if state.get("links") != 2:
                raise StepFail("sandbox install: the shortcuts were not written")
            if not names or "install.json" not in names:
                raise StepFail("sandbox install: the home holds no install.json")
        else:
            if state.get("key") is not False:
                raise StepFail("sandbox uninstall: the uninstall key is left")
            if state.get("links") != 0:
                raise StepFail("sandbox uninstall: a shortcut is left")
            if names not in ([], ["data"]):
                raise StepFail("sandbox uninstall: the home holds %s, want "
                               "only data" % ", ".join(names or ["?"]))
    return doc


def sandbox_phases(ctx):
    """Plan step (7), only with --sandbox: install and uninstall inside
    Windows Sandbox with networking and the clipboard off and the assets in
    a read-only mapped folder. A missing feature is reported, never turned
    on; a runtime that is not cached fails the step (never a download)."""
    staged = ctx.get("staged")
    if not staged or RELEASE_JSON not in staged or INSTALLER_PS1 not in staged:
        raise StepFail("the build made no %s / %s" % (RELEASE_JSON, INSTALLER_PS1))
    try:
        release = json.loads(staged[RELEASE_JSON].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise StepFail("%s is unreadable" % RELEASE_JSON)
    fx = ctx["sandbox_fx"](ctx)
    try:
        if not fx.feature_present():
            raise StepFail("Windows Sandbox is not available on this machine; "
                           "it is an optional Windows feature that needs "
                           "elevation and a restart (operator act OA-14). "
                           "The stage never turns it on")
        runtimes = fx.runtimes(release)
        staged = dict(staged)
        staged[SB_SCRIPT] = sandbox_script(
            ctx["version"], ctx["zip_name"]).encode("ascii")
        fx.put_assets(staged, runtimes)
        wsb = write_wsb(fx.base / SB_WSB, fx.assets, fx.results,
                        sandbox_command())
        fx.launch(wsb)
        raw = fx.wait_result()
        if raw is None:
            raise StepFail("sandbox: no result within %d s" % SB_TIMEOUT_S)
        check_sandbox_result(raw, ctx["version"])
    finally:
        fx.cleanup()
    return ("install and uninstall in Windows Sandbox (networking and "
            "clipboard off, assets read-only): uninstall key and shortcuts "
            "written, then removed")


# The append point: (name, callable). "sandbox" runs only with --sandbox.
STEPS = [
    ("clean", step_clean),
    ("version", step_version),
    ("suite", step_suite),
    ("node", step_node),
    ("builds", step_builds),
    ("sweep", step_sweep),
    ("roundtrip", step_roundtrip),
    (SANDBOX_STEP, sandbox_phases),
]


# --- the report ------------------------------------------------------------

def _entry(name, data):
    return {"name": name, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def _write_atomic(path, data):
    tmp = path.with_name(path.name + ".partial")
    tmp.write_bytes(data)
    os.replace(str(tmp), str(path))


def _remove_scratch(scratch):
    # The scratch folder holds only this run's regenerable build output.
    if scratch.exists():
        shutil.rmtree(str(scratch), ignore_errors=True)


def _sandbox_status(sandbox, rows):
    """stage.json "sandbox": "skipped" without the flag (or with no sandbox
    step), else the sandbox step's status (pass | fail | skipped)."""
    if sandbox:
        for row in rows:
            if row["name"] == SANDBOX_STEP:
                return row["status"]
    return "skipped"


def stage(version, sandbox=False, run=None, now=None, root=ROOT, out=None,
          owner=None, build=None, steps=None, roundtrip=None,
          sandbox_fx=None):
    """Run the gates; write <out>/stage.json; return the report dict (plus
    "out", the folder). run(argv, cwd) -> exit code and now() -> epoch
    seconds are injected; build defaults to rel_build.build; roundtrip(ctx)
    -> the round trip's effects (default: RoundTripEffects in a fresh
    scratch folder under <sidecar>/Temp); sandbox_fx(ctx) -> the sandbox
    phases' effects (default: SandboxEffects). The "sandbox" step runs only
    when sandbox is true; stage.json's "sandbox" is "skipped" without the
    flag, else that step's status."""
    root = Path(root)
    out = Path(out) if out is not None else rb.default_out(version)
    ctx = {
        "root": root, "version": version, "sandbox": bool(sandbox),
        "run": run or default_run, "build": build or rb.build,
        "owner": owner or os.environ.get(OWNER_ENV) or DEFAULT_OWNER,
        "scratch": out / SCRATCH_NAME, "notes": [], "staged": None,
        "zip_name": None, "roundtrip": roundtrip or default_roundtrip,
        "sandbox_fx": sandbox_fx or default_sandbox,
    }
    clock = now or time.time
    commit = rb._rev(root, "HEAD^{commit}") or ""
    plan = [(name, fn) for name, fn in (steps if steps is not None else STEPS)
            if sandbox or name != SANDBOX_STEP]
    if sandbox and SANDBOX_STEP not in [name for name, _fn in plan]:
        ctx["notes"].append("sandbox asked; this step list has no sandbox step")
    rows, verdict = [], PASS
    out.mkdir(parents=True, exist_ok=True)
    _remove_scratch(ctx["scratch"])
    try:
        for name, fn in plan:
            if verdict == FAIL:
                rows.append({"name": name, "status": "skipped", "detail": ""})
                continue
            try:
                detail = fn(ctx)
                rows.append({"name": name, "status": "pass",
                             "detail": str(detail or "")})
            except StepFail as exc:
                verdict = FAIL
                rows.append({"name": name, "status": "fail", "detail": str(exc)})
        assets, sums_sha = [], None
        if verdict == PASS and ctx["staged"]:
            for name in sorted(ctx["staged"]):
                _write_atomic(out / name, ctx["staged"][name])
            assets = [_entry(n, ctx["staged"][n]) for n in sorted(ctx["staged"])
                      if n != rb.SUMS_NAME]
            sums_sha = hashlib.sha256(ctx["staged"][rb.SUMS_NAME]).hexdigest()
    finally:
        _remove_scratch(ctx["scratch"])
    report = {
        "schema": SCHEMA, "version": version, "commit": commit,
        "verdict": verdict, "steps": rows, "assets": assets,
        "sums_sha256": sums_sha, "created": created_text(clock()),
        "sandbox": _sandbox_status(sandbox, rows), "notes": list(ctx["notes"]),
    }
    _write_atomic(out / STAGE_NAME,
                  (json.dumps(report, indent=1, sort_keys=True,
                              ensure_ascii=True) + "\n").encode("ascii"))
    report = dict(report)
    report["out"] = out
    return report


# --- command line ----------------------------------------------------------

def _parser():
    p = argparse.ArgumentParser(
        prog="release.py stage",
        description="Run the release gates and write stage.json (PASS / "
                    "FAIL). No upload, no tag, no network.")
    p.add_argument("version", nargs="?", help="default: the source VERSION")
    p.add_argument("--sandbox", action="store_true", default=False,
                   help="off by default: also install and uninstall inside "
                        "Windows Sandbox (networking and clipboard off, "
                        "assets read-only; operator act OA-14). The feature "
                        "is never turned on by this tool")
    p.add_argument("--owner", help="suite gate owner id (default env %s)"
                                   % OWNER_ENV)
    p.add_argument("--out", help="release folder (default "
                                 "<sidecar>/Build/release/<version>)")
    p.add_argument("--root", default=str(ROOT), help="the repository")
    return p


def main(command, argv):
    """Entry from tools/release.py; returns the exit code (0 PASS, 1 FAIL)."""
    if command != "stage":
        print("rel_stage: unknown sub-command %r" % command, file=sys.stderr)
        return 2
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    version = args.version
    if version is None:
        try:
            version = rv.source_version(Path(args.root))
        except (rv.VersionError, OSError) as exc:
            print("stage: refused: %s" % exc, file=sys.stderr)
            return 1
    rep = stage(version, sandbox=args.sandbox, root=args.root, out=args.out,
                owner=args.owner)
    for row in rep["steps"]:
        print("stage: %-8s %-7s %s" % (row["name"], row["status"], row["detail"]))
    for text in rep["notes"]:
        print("stage: note: %s" % text)
    print("stage: %s %s -> %s" % (rep["verdict"], version,
                                   rep["out"] / STAGE_NAME))
    return 0 if rep["verdict"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main("stage", sys.argv[1:]))
