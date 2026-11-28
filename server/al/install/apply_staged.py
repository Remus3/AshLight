"""`installer apply-staged [--if-due]` (REL-UPDATE-SWITCH, DEP-11): the
launcher's step before every client start (docs/plan/05-deployment.md
"How an update swaps versions" step 4). The logic is switch.apply; this
module is the command line only.

Exit codes: 0 start as usual (nothing staged, not due, or a start of a
version still waiting for its confirm counted), 10 the marker moved
(switched, or rolled back at the third start without a confirm):
relaunch from the marker, 3 a core of this home runs (nothing switched),
1 failed, 2 usage or a refused home. With nothing staged it costs one
folder listing and the marker read.
"""

import argparse
import sys

from . import switch


def build_parser():
    p = argparse.ArgumentParser(
        prog="python -m server.al.install apply-staged",
        description="switch to a staged AshLight version before the client "
                    "starts; roll back a version that never confirmed")
    p.add_argument("--if-due", action="store_true",
                   help="apply only once the staged version's hold has passed "
                        "(the launcher's form; without it: Update now)")
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
    code, _result = switch.apply(home, if_due=args.if_due,
                                 effect_root=args.effect_root,
                                 out=out or sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
