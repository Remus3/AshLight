"""`installer rollback` (REL-UPDATE-SWITCH, DEP-11): go back to the
marker's previous version by hand (docs/plan/05-deployment.md
"Rollback"), the same switch the launcher runs by itself at the second
start without a confirm. The logic is switch.rollback; this module is the
command line only.

The version left lands in <home>/data/update_skip.json (never applied or
offered again; a newer release is). Exit codes: 10 rolled back (relaunch
from the marker), 3 a core of this home runs (stop it first), 1 failed
(no previous version, or a step did not read back), 2 usage or a refused
home.
"""

import argparse
import sys

from . import switch


def build_parser():
    p = argparse.ArgumentParser(
        prog="python -m server.al.install rollback",
        description="make the previous AshLight version the active one again")
    p.add_argument("--home", help="the install home (default: AL_HOME, else "
                   "%%LOCALAPPDATA%%\\Programs\\AshLight)")
    p.add_argument("--effect-root", help=argparse.SUPPRESS)  # al_shell -EffectRoot
    return p


def main(argv=None, environ=None, out=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return switch.EXIT_USAGE if exc.code else switch.EXIT_OK
    home = switch.resolve_home(args.home, environ)
    code, _result = switch.rollback(home, reason="by hand",
                                    effect_root=args.effect_root,
                                    out=out or sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
