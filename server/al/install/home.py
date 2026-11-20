"""The install home and its marker (REL-INSTALL-HOME, DEP-09, decision 0059;
docs/plan/05-deployment.md "Installed-mode layout").

- layout(home): every fixed path of a home, by name (no file access).
- make_layout(home): makes the folders an install needs and gives
  <home>/data the private ACL of decision 0051 (server/al/acl.py).
- read_marker(home): <home>/install.json as a dict when it parses and
  passes validate(), else None; a torn marker is restored from its .bak.
- write_marker(home, doc): validates, writes through server/al/jsonfile.py
  (unique temp file, fsync, replace, one .bak) and reads the file back;
  a read-back that differs raises MarkerError.
- switch_marker(home, new): previous = the current version, version =
  new, pending_confirm = True, start_attempts = 0; written and read back.
- version_dirs(home), cleanup_plan(home): the version folders under
  <home>/app, and the ones that are neither `version` nor `previous`
  (listed only; this module deletes nothing).

Every entry point refuses a home whose path text has a `steamapps` or
`Path of Exile 2` component (paths.home_refusal, path text only). No
registry read, no game folder is listed or opened.
"""

import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

from .. import NAME, jsonfile, paths

SCHEMA = 1
CHANNELS = ("stable", "rc")
MARKER_FIELDS = ("schema", "name", "version", "previous", "channel",
                 "installed_at", "updated_at", "python", "electron",
                 "pending_confirm", "start_attempts")
# SemVer 0.y.z with an optional pre-release (X.Y.Z-rc.N); one plain folder
# name, so a version never names a path out of <home>/app
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                        r"(?:-([0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*))?$")
# the folders make_layout creates (build only with the optional calc,
# staged and downloads on first use by their own commands)
LAYOUT_DIRS = ("app", "runtime", "data", "cache", "logs", "temp")


class MarkerError(Exception):
    """The marker is missing, invalid, or did not read back as written."""


def check_home(home):
    """The home as an absolute Path; raises paths.HomeRefused for a home in
    a Steam library or the game's folder (path text only, no stat)."""
    home = Path(os.path.abspath(str(home)))
    reason = paths.home_refusal(home)
    if reason:
        raise paths.HomeRefused(reason)
    return home


def layout(home):
    """Every fixed path of an install home, by name. No file access."""
    home = check_home(home)
    return {
        "home": home,
        "marker": home / paths.MARKER_NAME,
        "uninstall": home / "uninstall.ps1",
        "app": home / "app",
        "runtime": home / paths.RUNTIME_FOLDER,
        "data": home / paths.DATA_DIR,
        "local_config": home / paths.DATA_DIR / "local.json",
        "cache": home / "cache",
        "downloads": home / "cache" / "downloads",
        "logs": home / "logs",
        "reports": home / "logs" / "reports",
        "temp": home / "temp",
        "build": home / "build",
        "staged": home / "staged",
    }


def make_layout(home, private=None):
    """Create the folders of LAYOUT_DIRS (idempotent) and give <home>/data
    the private ACL (decision 0051). private is the ACL call (default
    acl.make_private); its result is returned (None off Windows)."""
    lay = layout(home)
    for name in LAYOUT_DIRS:
        lay[name].mkdir(parents=True, exist_ok=True)
    if private is None:
        from .. import acl  # late: only the installer applies an ACL
        private = acl.make_private
    return private(lay["data"])


def now_text(now=None):
    """An ISO 8601 UTC time stamp (seconds), from a datetime or the clock."""
    when = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_version(text):
    return isinstance(text, str) and VERSION_RE.match(text) is not None


def channel_of(version):
    """'rc' for a pre-release version, else 'stable'."""
    return "rc" if "-" in version else "stable"


def version_key(version):
    """A sort key: X.Y.Z-rc.N sorts below X.Y.Z (SemVer precedence)."""
    m = VERSION_RE.match(version)
    if m is None:
        raise ValueError(f"not a version: {version!r}")
    core = tuple(int(m.group(i)) for i in (1, 2, 3))
    pre = m.group(4)
    if pre is None:
        return core + (1, ())
    ids = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split("."))
    return core + (0, ids)


def _plain_name(value):
    """A runtime folder name: one plain name, never a path (the rule of
    paths._marker_runtime)."""
    return (isinstance(value, str) and bool(value.strip(". "))
            and not any(c in value for c in "\\/:"))


def validate(doc):
    """The problems of a marker document, as short texts; [] when valid.
    Keys beyond MARKER_FIELDS are kept as they are."""
    if not isinstance(doc, dict):
        return ["not an object"]
    out = []
    missing = [k for k in MARKER_FIELDS if k not in doc]
    if missing:
        out.append("missing " + ", ".join(missing))
    if "schema" in doc and (doc["schema"] != SCHEMA or isinstance(doc["schema"], bool)):
        out.append(f"schema is not {SCHEMA}")
    if "name" in doc and doc["name"] != NAME:
        out.append(f"name is not {NAME}")
    version = doc.get("version")
    if "version" in doc and not is_version(version):
        out.append("version is not X.Y.Z")
    previous = doc.get("previous")
    if previous is not None and not is_version(previous):
        out.append("previous is not X.Y.Z or null")
    elif previous is not None and previous == version:
        out.append("previous equals version")
    if "channel" in doc and doc["channel"] not in CHANNELS:
        out.append("channel is not stable or rc")
    for key in ("installed_at", "updated_at"):
        if key in doc and not (isinstance(doc[key], str) and doc[key]):
            out.append(f"{key} is not a time stamp")
    for key in ("python", "electron"):
        if key in doc and not _plain_name(doc[key]):
            out.append(f"{key} is not a runtime folder name")
    if "pending_confirm" in doc and not isinstance(doc["pending_confirm"], bool):
        out.append("pending_confirm is not true or false")
    attempts = doc.get("start_attempts")
    if "start_attempts" in doc and (not isinstance(attempts, int)
                                    or isinstance(attempts, bool) or attempts < 0):
        out.append("start_attempts is not a count")
    return out


def new_marker(version, python, electron, channel=None, now=None):
    """A first-install marker: no previous version, nothing to confirm."""
    stamp = now_text(now)
    return {
        "schema": SCHEMA,
        "name": NAME,
        "version": version,
        "previous": None,
        "channel": channel or (channel_of(version) if is_version(version) else "stable"),
        "installed_at": stamp,
        "updated_at": stamp,
        "python": python,
        "electron": electron,
        "pending_confirm": False,
        "start_attempts": 0,
    }


def read_marker(home):
    """The marker as a dict, or None when it is missing, unreadable or
    invalid. A torn marker is restored from its one .bak (jsonfile)."""
    path = layout(home)["marker"]
    doc = jsonfile.read_json(path, max_bytes=paths.MARKER_MAX_BYTES, kind=dict,
                             default=None, backup=True)
    if doc is None or validate(doc):
        return None
    return doc


def write_marker(home, doc):
    """Validate doc, write it through the hardened write path (temp file,
    fsync, replace, one .bak) and read it back. Returns the read-back
    document; raises MarkerError on an invalid doc or a differing read."""
    problems = validate(doc)
    if problems:
        raise MarkerError("marker refused: " + "; ".join(problems))
    path = layout(home)["marker"]
    text = jsonfile.dumps(doc)
    if len(text) > paths.MARKER_MAX_BYTES:
        raise MarkerError("marker refused: too large")
    jsonfile.write_text(path, text, backup=True)
    try:
        back = json.loads(path.read_text(encoding="ascii"))
    except (OSError, ValueError) as exc:
        raise MarkerError(f"marker read-back failed: {exc.__class__.__name__}") from None
    if back != doc:
        raise MarkerError("marker read-back differs from what was written")
    return back


def switch_marker(home, new, python=None, electron=None, pending_confirm=True,
                  now=None):
    """Make version `new` the active one: previous = the current version,
    pending_confirm set, start_attempts = 0, updated_at = now; python and
    electron change only when given. <home>/app/<new> must be a folder.
    Written and read back; returns the read-back marker."""
    if not is_version(new):
        raise MarkerError(f"not a version: {new!r}")
    lay = layout(home)
    doc = read_marker(lay["home"])
    if doc is None:
        raise MarkerError("no valid marker to switch")
    if doc["version"] == new:
        raise MarkerError(f"{new} is already the active version")
    if not _is_plain_dir(lay["app"] / new):
        raise MarkerError(f"no version folder for {new}")
    doc = dict(doc)
    doc["previous"] = doc["version"]
    doc["version"] = new
    doc["channel"] = channel_of(new)
    if python is not None:
        doc["python"] = python
    if electron is not None:
        doc["electron"] = electron
    doc["pending_confirm"] = bool(pending_confirm)
    doc["start_attempts"] = 0
    doc["updated_at"] = now_text(now)
    return write_marker(lay["home"], doc)


def _is_plain_dir(path):
    """A real folder: not a link or junction (lstat only)."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return False
    if getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    return stat.S_ISDIR(st.st_mode)


def version_dirs(home):
    """The version folder names under <home>/app, oldest first. A name that
    is not X.Y.Z (a .partial extract), a file, a link or a junction is not
    a version folder."""
    app = layout(home)["app"]
    try:
        names = os.listdir(app)
    except OSError:
        return []
    found = [n for n in names if is_version(n) and _is_plain_dir(app / n)]
    return sorted(found, key=version_key)


def cleanup_plan(home, marker=None):
    """The version folders that are neither the marker's `version` nor its
    `previous`, as paths, oldest first. Listed only, never deleted here.
    With no valid marker nothing is listed (what to keep is unknown)."""
    lay = layout(home)
    doc = marker if marker is not None else read_marker(lay["home"])
    if doc is None or validate(doc):
        return []
    keep = {doc["version"], doc.get("previous")}
    return [lay["app"] / n for n in version_dirs(lay["home"]) if n not in keep]
