"""`installer status` (REL-INSTALL-HOME): mode, version and previous.

Prints `key: value` lines and no path at all, so nothing outside the home
(or the home itself) is named. In a checkout: mode, the code's version and
previous none, exit 0. In an install: the marker's fields, exit 0; a
refused home or a missing / invalid marker prints one line and exits 1.
"""

import sys

from .. import VERSION, paths
from . import home as homemod


def lines(environ=None):
    """(exit code, the status lines)."""
    mode = paths.install_mode(environ)
    if mode != "installed":
        return 0, ["mode: checkout", f"version: {VERSION}", "previous: none"]
    try:
        home = paths.install_home(environ)
    except paths.HomeRefused as exc:
        return 1, ["mode: installed", f"home: refused, {exc}"]
    doc = homemod.read_marker(home)
    if doc is None:
        return 1, ["mode: installed", "marker: missing or invalid"]
    return 0, [
        "mode: installed",
        f"version: {doc['version']}",
        f"previous: {doc['previous'] or 'none'}",
        f"channel: {doc['channel']}",
        f"pending_confirm: {'true' if doc['pending_confirm'] else 'false'}",
        f"start_attempts: {doc['start_attempts']}",
        f"old_versions: {len(homemod.cleanup_plan(home, doc))}",
    ]


def main(argv=None, environ=None, out=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out or sys.stdout
    if argv:
        print("usage: python -m server.al.install status", file=sys.stderr)
        return 2
    code, text = lines(environ)
    for line in text:
        out.write(line + "\n")
    return code
