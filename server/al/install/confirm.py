"""`installer confirm [--wait]` (REL-UPDATE-SWITCH, DEP-11): the first
/api/health answer of the active version clears pending_confirm, then the
folders that are neither `version`, `previous` nor staged (and runtimes
none of them needs) are removed (docs/plan/05-deployment.md "How an
update swaps versions" step 5). The logic is switch.confirm; this module
is the command line only.

The answer comes from THIS home's own core on the loopback port of its
core.alive, after the hello proof (decision 0054). --wait polls it every
second up to --timeout seconds (the launcher's hidden helper). Exit
codes: 0 confirmed (or nothing to confirm), 1 no answer or failed, 2
usage or a refused home.
"""

import argparse
import sys

from . import switch


def build_parser():
    p = argparse.ArgumentParser(
        prog="python -m server.al.install confirm",
        description="confirm the active AshLight version from its health "
                    "answer and remove old version folders")
    p.add_argument("--wait", action="store_true",
                   help="poll the health answer until it comes or --timeout ends")
    p.add_argument("--timeout", type=float, default=switch.CONFIRM_WAIT_S,
                   help="seconds to wait with --wait (default %(default)g)")
    p.add_argument("--home", help="the install home (default: AL_HOME, else "
                   "%%LOCALAPPDATA%%\\Programs\\AshLight)")
    return p


def main(argv=None, environ=None, out=None, health=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return switch.EXIT_USAGE if exc.code else switch.EXIT_OK
    if not 0 <= args.timeout <= 3600:
        print("confirm: --timeout is 0 to 3600 seconds", file=sys.stderr)
        return switch.EXIT_USAGE
    home = switch.resolve_home(args.home, environ)
    code, _result = switch.confirm(home, health=health,
                                   wait_s=args.timeout if args.wait else 0.0,
                                   out=out or sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
