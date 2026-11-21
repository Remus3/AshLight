"""RUN-CALC-PRIORITY (F-107): AshLight's heavy child processes start with
the below-normal priority class, so a calc or a batch job never competes
with the game for the CPU.

The children that get the flag: luajit (the calc bridge), the hot reload
code preflight, the drift trial and its test run, and the snapshot build
step. The core and the client stay at normal. Only processes AshLight
itself starts get a creation flag; nothing here opens, reads or changes
any other process (CLAUDE.md ToS floor). Off Windows the flag is 0 and the
children run at the inherited priority.

`python -m server.al.prio <server.al module> [args]` runs one AshLight
module as a below-normal child with this process's standard streams and
returns its exit code (scripts/build.ps1's snapshot step); it refuses any
module outside server.al.
"""

import os
import subprocess
import sys

BELOW_NORMAL = 0x00004000          # BELOW_NORMAL_PRIORITY_CLASS
NORMAL = 0x00000020                # NORMAL_PRIORITY_CLASS
_QUERY_LIMITED = 0x1000            # PROCESS_QUERY_LIMITED_INFORMATION
MODULE_PREFIX = "server.al."


def below_normal(flags=0):
    """`flags` plus the below-normal priority class on Windows."""
    return int(flags) | (BELOW_NORMAL if os.name == "nt" else 0)


def priority_class(pid):
    """The priority class of AshLight's own child `pid` (Windows), else
    None. A query-only handle; nothing in the process is read."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes as w
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = w.HANDLE
    k.OpenProcess.argtypes = (w.DWORD, w.BOOL, w.DWORD)
    k.GetPriorityClass.restype = w.DWORD
    k.GetPriorityClass.argtypes = (w.HANDLE,)
    k.CloseHandle.argtypes = (w.HANDLE,)
    handle = k.OpenProcess(_QUERY_LIMITED, False, int(pid))
    if not handle:
        return None
    try:
        value = k.GetPriorityClass(handle)
        return int(value) or None
    finally:
        k.CloseHandle(handle)


def run_module(module, args=(), popen=subprocess.Popen):
    """Run `python -m <module> <args>` below normal; its exit code."""
    if not str(module).startswith(MODULE_PREFIX):
        raise ValueError("only AshLight's own modules run here")
    child = popen([sys.executable, "-m", str(module), *[str(a) for a in args]],
                  creationflags=below_normal())
    return child.wait()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or not argv[0].startswith(MODULE_PREFIX):
        print("usage: python -m server.al.prio server.al.<module> [args]",
              file=sys.stderr)
        return 2
    return run_module(argv[0], argv[1:])


if __name__ == "__main__":
    sys.exit(main())
