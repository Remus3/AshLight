"""The installer's fixed command table (REL-INSTALL-HOME, DEP-09).

Every command maps to one module of this package, imported only when the
command runs; the module's main(argv) returns the exit code. A command
whose module is not in this build prints 'not available in this build'
and exits 2, so a later installer package adds its module file and never
edits this table. An unknown command exits 2 as well.
"""

import importlib
import importlib.util
import sys

# command -> module name under server/al/install/ (the ONE table)
COMMANDS = {
    "install": "install",
    "repair": "repair",
    "status": "status",
    "calc": "calc",
    "update": "update",
    "apply-staged": "apply_staged",
    "rollback": "rollback",
    "confirm": "confirm",
    "migrate": "migrate",
}

EXIT_USAGE = 2
NOT_AVAILABLE = "not available in this build"


def usage():
    return ("usage: python -m server.al.install <command> [args]\n"
            "commands: " + ", ".join(COMMANDS))


def module_name(command):
    """The full module name of a command, or None for an unknown one."""
    mod = COMMANDS.get(command)
    return f"{__package__}.{mod}" if mod is not None else None


def load(command):
    """The command's module, or None when it is unknown or not in this build
    (no module file, or a module without main)."""
    full = module_name(command)
    if full is None:
        return None
    try:
        if importlib.util.find_spec(full) is None:
            return None
    except (ImportError, ValueError):
        return None
    module = importlib.import_module(full)
    return module if callable(getattr(module, "main", None)) else None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(usage(), file=sys.stderr)
        return EXIT_USAGE
    command, rest = argv[0], argv[1:]
    if command not in COMMANDS:
        print(f"installer: unknown command {command!r}", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return EXIT_USAGE
    module = load(command)
    if module is None:
        print(f"installer: {command}: {NOT_AVAILABLE}", file=sys.stderr)
        return EXIT_USAGE
    code = module.main(rest)
    return code if isinstance(code, int) else 0
