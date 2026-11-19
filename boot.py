"""AshLight payload-root boot shim (DEP-06, F-047).

    <python> boot.py <module> [args ...]

An installed copy runs under the private embeddable CPython, whose ._pth
file makes the interpreter isolated: neither the current directory, nor the
script folder, nor PYTHON* variables reach sys.path, so `-m server.al` from
the payload folder finds nothing. This shim puts its own folder (the payload
root, <home>/app/<version>/) first on sys.path and runs the named module as
`__main__`, the way `-m` does. The runtime's ._pth stays the publisher's
file, so one runtime serves every version folder and version N+1 can
self-test while N runs (spike record docs/ops/runtime-spike-record.md).

The one command builder server/al/paths.py python_cmd() makes this command
line in an install and today's `-m` form in a checkout. Standard library
only; it imports nothing of AshLight before the module it is told to run.
"""

import os
import re
import runpy
import sys

_MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*")
USAGE = "usage: boot.py <module> [args ...]"


def payload_root():
    """The folder this file lies in: the payload root."""
    return os.path.dirname(os.path.abspath(__file__))


def put_first(path_list, folder):
    """folder first on path_list, once (a later copy is removed)."""
    norm = os.path.normcase(os.path.abspath(folder))
    path_list[:] = [p for p in path_list
                    if not p or os.path.normcase(os.path.abspath(p)) != norm]
    path_list.insert(0, folder)
    return path_list


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or not _MODULE.fullmatch(argv[0]):
        print(USAGE, file=sys.stderr)
        return 2
    module = argv[0]
    put_first(sys.path, payload_root())
    # as `-m` does: argv[0] becomes the module's file (run_module sets it)
    sys.argv = [module] + argv[1:]
    runpy.run_module(module, run_name="__main__", alter_sys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
