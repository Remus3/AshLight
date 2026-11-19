#!/usr/bin/env python3
"""Release tool dispatcher (DEP-03): a fixed sub-command table.

    release.py <sub-command> [args...]

Each sub-command lives in its own module tools/rel_<module>.py, loaded by
file path only when used. A later release package adds its module file and
never edits this one (research 0047 append-point rule). A module exposes

    main(command: str, argv: list[str]) -> int

and gets the sub-command name plus the remaining arguments. An unknown
sub-command, or one whose module is not built yet, prints a line and exits 2.
Stdlib only; this file does no work of its own.
"""
import importlib.util
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent

# Fixed table: sub-command -> module name (tools/rel_<name>.py).
COMMANDS = {
    "bump": "version",
    "notes": "notes",
    "build": "build",
    "stage": "stage",
    "publish": "publish",
    "prepush-check": "publish",
}


def usage():
    return "usage: release.py {%s} [args...]" % "|".join(COMMANDS)


def module_path(command):
    return TOOLS / ("rel_%s.py" % COMMANDS[command])


def load(command):
    """The module for a known sub-command, or None when it is not built yet."""
    path = module_path(command)
    if not path.is_file():
        return None
    name = "rel_%s" % COMMANDS[command]
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(usage(), file=sys.stderr if not argv else sys.stdout)
        return 2 if not argv else 0
    command, rest = argv[0], list(argv[1:])
    if command not in COMMANDS:
        print("release.py: unknown sub-command %r; %s" % (command, usage()),
              file=sys.stderr)
        return 2
    module = load(command)
    if module is None:
        print("release.py: %s: not built yet (%s missing)"
              % (command, module_path(command).name), file=sys.stderr)
        return 2
    return int(module.main(command, rest) or 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
