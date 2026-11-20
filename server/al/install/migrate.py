"""`installer migrate` (DEP-13, findings F-049 and F-050; docs/plan/05-deployment.md
"DEP-13 Cut-over"): copy a checkout's player data into an install home.

- plan(src_runtime, src_config, home): the list of (source, target) pairs,
  built from the ONE allow-list table below (RUNTIME_FILES, RUNTIME_TREES,
  CONFIG_KEYS). Nothing outside it is ever listed: never the token (or
  token.reuse), pid files, the heartbeat core.alive, stop.request, the
  keepalive / hot reload files, caches, game data snapshots or logs.
- run(plan, force=False): copies each pair. A copy reads the source and
  writes the target through server/al/jsonfile.py (unique temp, fsync,
  replace); the checkout's files are only read, never changed. A target
  that already exists is kept unless force; every target must lie inside
  the home's data folder, or nothing is written for it.

local.json is not copied as a file: only CONFIG_KEYS are taken from the
checkout's config/local.json, each checked by the settings allow-list
validator (server/al/settingsio.py ALLOWED) where it has one, and written
into <home>/data/local.json (gitignored player state, decision 0059). The
dev-only keys (loop, loop_push, hot_reload, tc_drift_live_unattended,
port) and any key not in CONFIG_KEYS never reach the home. The contact is
written only into that local.json. web_data never moves (decisions 0013
and 0036: nothing but the player's own click turns it on, as a settings
import): the home keeps its own value (off on a fresh home), and a
checkout that had it on is reported as `offered web_data`. A home local.json that still equals
the first-run document (install/firstrun.py, untouched by the player)
counts as fresh and takes the migrated keys; any other existing one is
kept unless force, which merges the migrated keys over it.

Exit codes: 0 done (copied, kept or offered), 1 a copy failed, 2 usage, a refused
home, a home that is not laid out, or no checkout to read. Prints
`migrate: <state> <name>` lines with names relative to the data folder and
no path. No game folder is read or written, nothing is sent anywhere, and
no core or client is started. Runs only in the installer's own process;
standard library only.
"""

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from .. import jsonfile, paths, settingsio
from . import firstrun
from . import home as homemod

# --- the ONE allow-list table (player data only) ---------------------------
# files directly under the runtime dir (ops/runtime -> <home>/data)
RUNTIME_FILES = (
    "consent.json",            # the floor's Client.txt opt-in (decision 0003)
    "run_history.json",        # decision 0036
    "map_ladder.json",
    "price_watch.json",        # decision 0036
    "zone_visits.json",        # decision 0043
    "session_summaries.json",
    "hints.json",              # decision 0039
    "verdicts.json",           # decision 0040 amendment
    "worn_gear.json",          # decision 0052
    "gen_builds.json",         # decision 0081 (Kindler tabs)
    "ui_layout.json",          # decision 0082 amendment
    "theorycraft/weights.json",  # TC-EVAL stat weights
)
# folders copied file by file, recursively (plain files only, no links)
RUNTIME_TREES = (
    "build",                   # the loaded builds, one per character (decision 0045)
)
# local.json keys never moved by a cut-over: web_data stays the player's own
# switch in the home (decisions 0013, 0036; settingsio never turns it on)
HELD_KEYS = ("web_data",)
# local.json keys: the settings allow-list (less HELD_KEYS) plus the two
# per-host player values a cut-over keeps (contact and the Client.txt path)
CONFIG_KEYS = tuple(k for k in settingsio.ALLOWED if k not in HELD_KEYS) + (
    "contact", "client_log")
# never copied, even if a later table edit names them (tests pin it)
NEVER_FILES = ("token", "token.reuse", "core.alive", "stop.request",
               "restart.request", "keepalive.json", "keepalive.lock",
               "hotreload.json", "overlay.pid", "core.pid", "supervisor.pid")
DEV_KEYS = firstrun.DEV_KEYS + ("port",)
NEVER_KEYS = DEV_KEYS + ("token", "poesessid", "consent")

CONFIG_TARGET = "local.json"
MAX_FILE_BYTES = 16 * 1024 * 1024  # a store larger than this is not player data

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


class MigrateError(Exception):
    """The migration cannot start (no laid-out home, a bad source)."""


def _plain_file(path):
    """A regular file that is not a link or junction (lstat only)."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return False
    if getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    return stat.S_ISREG(st.st_mode)


def _plain_dir(path):
    return homemod._is_plain_dir(path)


def _never(rel):
    name = Path(rel).name
    return (name in NEVER_FILES or name.endswith(".pid")
            or name.endswith(".tmp") or name.endswith(".bak"))


def _inside(path, root):
    """True when path (absolute) lies inside root, by text and, for the part
    that exists, by its real location (a link out of the home is refused)."""
    path = Path(os.path.abspath(str(path)))
    root = Path(os.path.abspath(str(root)))
    try:
        if os.path.commonpath([str(path), str(root)]) != str(root) or path == root:
            return False
    except ValueError:
        return False
    real_root = os.path.realpath(str(root))
    probe = path
    while not os.path.lexists(probe) and probe != root:
        probe = probe.parent
    real = os.path.realpath(str(probe))
    try:
        return os.path.commonpath([real, real_root]) == real_root
    except ValueError:
        return False


def _tree_files(src_runtime, top):
    """Every plain file under src_runtime/top as a relative posix name,
    sorted; links, junctions and NEVER names are left out."""
    out = []
    base = Path(src_runtime) / top
    if not _plain_dir(base):
        return out
    stack = [base]
    while stack:
        folder = stack.pop()
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for name in names:
            p = folder / name
            if _plain_dir(p):
                stack.append(p)
            elif _plain_file(p):
                rel = p.relative_to(src_runtime).as_posix()
                if not _never(rel):
                    out.append(rel)
    return sorted(out)


def data_folder(home):
    """<home>/data of a laid-out home; raises MigrateError otherwise and
    paths.HomeRefused for a home in a Steam library or the game's folder."""
    data = homemod.layout(home)["data"]
    if not _plain_dir(data):
        raise MigrateError("the home is not laid out (install AshLight first)")
    return data


def plan(src_runtime, src_config, home):
    """The (source, target) pairs of a migration, from the allow-list
    table; sources that do not exist (or are links) are left out. The
    local.json pair, when the checkout has one, is last."""
    data = data_folder(home)
    src_runtime = Path(os.path.abspath(str(src_runtime)))
    if _inside(src_runtime, homemod.layout(home)["home"]):
        raise MigrateError("the source lies inside the home")
    out = []
    names = [r for r in RUNTIME_FILES if not _never(r)]
    for top in RUNTIME_TREES:
        names.extend(_tree_files(src_runtime, top))
    for rel in names:
        src = src_runtime.joinpath(*rel.split("/"))
        if _plain_file(src):
            out.append((src, data.joinpath(*rel.split("/"))))
    if src_config is not None:
        src_config = Path(os.path.abspath(str(src_config)))
        if _plain_file(src_config):
            out.append((src_config, data / CONFIG_TARGET))
    return out


def config_keys(doc):
    """The keys of a checkout's local.json that move: CONFIG_KEYS only, each
    value passing its settings validator (contact and client_log: text)."""
    out = {}
    if not isinstance(doc, dict):
        return out
    for key in CONFIG_KEYS:
        if key in NEVER_KEYS or key in HELD_KEYS or key not in doc:
            continue
        value = doc[key]
        check = settingsio.ALLOWED.get(key)
        if check is not None:
            try:
                out[key] = check(value)
            except settingsio.SettingsError:
                continue
        elif isinstance(value, str) and len(value) <= 1024 and "\x00" not in value:
            out[key] = value
    return out


def _read_json(path):
    try:
        data = _read_capped(path)
        return json.loads(data.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def _read_capped(path):
    with open(path, "rb") as fh:
        data = fh.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("too large")
    return data


def web_data_offered(src_doc, home_doc):
    """True when the checkout had web data on and the home does not: the
    switch is offered to the player, never moved."""
    on = isinstance(src_doc, dict) and src_doc.get("web_data") is True
    return on and not (isinstance(home_doc, dict) and home_doc.get("web_data") is True)


def _copy_config(src, target, force):
    """Write the moving keys of src into target; returns (state, offered)."""
    src_doc = _read_json(src)
    moving = config_keys(src_doc)
    if os.path.lexists(target):
        current = _read_json(target) if _plain_file(target) else None
        if current == firstrun.first_run_config():
            doc = dict(current)
        elif force:
            doc = dict(current) if isinstance(current, dict) else firstrun.first_run_config()
        else:
            return "kept", web_data_offered(src_doc, current)
    else:
        doc = firstrun.first_run_config()
    doc.update(moving)
    jsonfile.write_text(target, jsonfile.dumps(doc), backup=True)
    back = _read_json(target)
    if back != doc:
        raise OSError("read-back differs")
    return "copied", web_data_offered(src_doc, back)


def _copy_file(src, target, force):
    if os.path.lexists(target) and not force:
        return "kept"
    if os.path.lexists(target) and not _plain_file(target):
        raise OSError("target is not a plain file")
    data = _read_capped(src)
    jsonfile.write_bytes(target, data)
    with open(target, "rb") as fh:
        if fh.read() != data:
            raise OSError("read-back differs")
    return "copied"


def run(pairs, force=False, home=None):
    """Copy every (source, target) pair. Returns a list of (name, state)
    with state "copied", "kept", "refused" (a target outside the data
    folder) or "failed: <reason>"; name is the target relative to the data
    folder (or its file name). A checkout with web data on that the home
    does not have on adds ("web_data", "offered"). The sources are only
    read."""
    results = []
    for src, target in pairs:
        target = Path(os.path.abspath(str(target)))
        data = (homemod.layout(home)["data"] if home is not None
                else _data_of(target))
        name = _name(target, data)
        if data is None or not _inside(target, data) or _never(name):
            results.append((name, "refused"))
            continue
        offered = False
        try:
            if target == data / CONFIG_TARGET:
                state, offered = _copy_config(src, target, force)
            else:
                state = _copy_file(src, target, force)
        except (OSError, ValueError) as exc:
            state = f"failed: {exc.__class__.__name__}"
        results.append((name, state))
        if offered:
            results.append(("web_data", "offered"))
    return results


def _data_of(target):
    """The home's data folder above target: the ancestor named `data` whose
    parent holds the marker, else the nearest ancestor named `data`."""
    named = [p for p in target.parents if p.name == paths.DATA_DIR]
    for parent in named:
        if (parent.parent / paths.MARKER_NAME).is_file():
            return parent
    return named[0] if named else None


def _name(target, data):
    try:
        return target.relative_to(data).as_posix() if data is not None else target.name
    except ValueError:
        return target.name


def default_sources():
    """The checkout's ops/runtime and config/local.json; MigrateError when
    this code is not a checkout (no .git at the repository root)."""
    root = paths.repo_root()
    if not os.path.lexists(root / ".git"):
        raise MigrateError("migrate reads a checkout; this copy is not one")
    return root / "ops" / "runtime", root / "config" / "local.json"


def main(argv=None, out=None, environ=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out or sys.stdout
    env = os.environ if environ is None else environ
    ap = argparse.ArgumentParser(prog="python -m server.al.install migrate",
                                 description="Copy a checkout's player data into an install home.")
    ap.add_argument("--home", help="the install home (default: AL_HOME)")
    ap.add_argument("--from-runtime", help="the checkout's runtime dir (default: ops/runtime)")
    ap.add_argument("--from-config", help="the checkout's local.json (default: config/local.json)")
    ap.add_argument("--force", action="store_true", help="replace files the home already has")
    ap.add_argument("--dry-run", action="store_true", help="list what would be copied")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    home = args.home or (env.get(paths.HOME_ENV) or "").strip().strip('"')
    if not home:
        print("migrate: name the install home with --home", file=sys.stderr)
        return EXIT_USAGE
    try:
        if args.from_runtime:
            src_runtime = Path(args.from_runtime)
            src_config = Path(args.from_config) if args.from_config else None
        else:
            src_runtime, src_config = default_sources()
            if args.from_config:
                src_config = Path(args.from_config)
        pairs = plan(src_runtime, src_config, home)
    except (MigrateError, paths.HomeRefused) as exc:
        print(f"migrate: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.dry_run:
        data = homemod.layout(home)["data"]
        for _src, target in pairs:
            out.write(f"migrate: would copy {_name(Path(target), data)}\n")
        return EXIT_OK
    results = run(pairs, force=args.force, home=home)
    for name, state in results:
        out.write(f"migrate: {state} {name}\n")
        if state == "offered":
            out.write("migrate: web data stays off here; turn it on in Settings "
                      "if you want it\n")
    failed = [s for _n, s in results if s not in ("copied", "kept", "offered")]
    out.write(f"migrate: {len(results) - len(failed)} of {len(results)} done\n")
    return EXIT_FAIL if failed else EXIT_OK
