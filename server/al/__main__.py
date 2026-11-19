"""AshLight core entry point.

    python -m server.al [--log PATH] [--port N] [--no-tail] [--replay FILE]
    python -m server.al --demo DIR [--port N] [--no-tail]

Prints the dashboard URL with the per-start token in the fragment
(#token=...), so it never reaches the server log or a Referer.

--demo DIR (decision 0049) starts an isolated demo instance on a fixture
folder: demo.prepare points the runtime, sidecar and config at a scratch
folder before logging starts, the port is the first free one of the demo
block (or --port, 0 allowed), config/local.json is never read, and the core
is a demo.DemoCore that can read only the folder's Client.txt.
"""

import argparse
import faulthandler
import json
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from . import DISCLAIMER, NAME, VERSION, acl, demo, hotreload, jsonfile, paths, ports
from .core import Core, write_private
from .http import new_token, serve


def build_parser():
    p = argparse.ArgumentParser(prog="python -m server.al",
                                description=f"{NAME} {VERSION} core server")
    p.add_argument("--log", help="path to Client.txt (default: config, then Steam scan)")
    p.add_argument("--port", type=int, default=None,
                   help=f"port (default: env {ports.PORT_ENV}, then config "
                        f"\"port\", then {ports.AL_PORT}; block "
                        f"{ports.PORT_BLOCK[0]}-{ports.PORT_BLOCK[1]})")
    p.add_argument("--no-tail", action="store_true", help="never tail Client.txt")
    p.add_argument("--replay", metavar="FILE",
                   help="feed a fixture file through the parser at start")
    p.add_argument("--character", help="character name to track")
    p.add_argument("--quiet", action="store_true", help="no console output")
    p.add_argument("--check", action="store_true",
                   help="HOT-RELOAD preflight: import the core and compile every "
                        "server .py file, then exit (0 = loadable)")
    p.add_argument("--demo", metavar="DIR",
                   help="demo mode (decision 0049): an isolated instance on a "
                        "fixture folder holding ashlight-demo.json and Client.txt; "
                        "never the live log, runtime or config")
    return p


def check_code(root=None, out=None):
    """HOT-RELOAD (decision 0042): the supervisor's preflight before a code
    reload. Importing this module already imported the core and the HTTP
    server; this compiles every .py under server/ too (no .pyc written).
    0 when all compile, else 1 with "<file>:<line>: <message>" printed."""
    root = Path(root) if root else paths.repo_root()
    out = out if out is not None else sys.stdout
    for f in sorted((root / "server").rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        try:
            compile(f.read_bytes(), str(f), "exec", dont_inherit=True)
        except SyntaxError as exc:
            rel = f.relative_to(root).as_posix()
            msg = " ".join(str(exc.msg or "syntax error").split())
            if out is not None:
                print(f"{rel}:{exc.lineno}: {msg}", file=out)
            return 1
        except (OSError, ValueError) as exc:
            if out is not None:
                print(f"{f.relative_to(root).as_posix()}: {type(exc).__name__}", file=out)
            return 1
    return 0


def setup_logging(quiet):
    handlers = []
    try:
        paths.ensure_dirs()
        handlers.append(logging.FileHandler(paths.all_runtime_paths()["core_log"],
                                            encoding="utf-8"))
    except OSError:
        pass
    for h in handlers:
        stream = getattr(h, "stream", None)
        if stream is not None:
            try:
                faulthandler.enable(file=stream)  # native crash -> core.log
            except (OSError, ValueError, AttributeError):
                pass
            break
    if not quiet and sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers or [logging.NullHandler()],
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")


HEARTBEAT_S = 30.0
STOP_FILE = "stop.request"  # written by scripts/stop.ps1: a user stop, not a crash


def _heartbeat_s():
    try:
        return max(0.1, float(os.environ.get("AL_HEARTBEAT_S") or HEARTBEAT_S))
    except ValueError:
        return HEARTBEAT_S


def stop_requested(path):
    """True when the user asked the core to stop (scripts/stop.ps1)."""
    return Path(path).exists()


def clear_stop_request(path):
    """A stop.request left from an earlier stop must not end this start."""
    try:
        Path(path).unlink()
    except OSError:
        pass


def install_crash_logging(log):
    """Log any unhandled exception (main or worker thread) to core.log.
    pythonw has no stderr, so without this a crash leaves no trace."""
    def _sys_hook(exc_type, exc, tb):
        log.critical("unhandled exception; core exiting", exc_info=(exc_type, exc, tb))

    def _thread_hook(hook_args):
        if hook_args.exc_type is SystemExit:
            return
        name = hook_args.thread.name if hook_args.thread is not None else "?"
        log.error("unhandled exception in thread %s", name,
                  exc_info=(hook_args.exc_type, hook_args.exc_value,
                            hook_args.exc_traceback))

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook


def write_heartbeat(path, pid, port, now=None, created=None):
    """Refresh <runtime>/core.alive so the time of a silent kill is bounded.
    created (the process creation time) lets stop.ps1 prove the pid is ours."""
    data = {"pid": int(pid), "port": int(port),
            "updated": float(time.time() if now is None else now)}
    if created:
        data["created"] = int(created)
    # RUN-DURABLE-CRLF: LF and atomic; unsynced, it is rewritten every beat
    jsonfile.write_text(path, json.dumps(data) + "\n", sync=False)


def start_token(runtime, token_file, log=None):
    """SEC-ACL-APPLY (decision 0051): make the runtime dir private before
    the token is written, then pick this start's token. HOT-RELOAD: a core
    that exited for a code reload lets this start keep its token, so the
    open dashboard and overlay reconnect on their own; a kept token is
    reused only while the runtime dir is private. Its privacy is read
    BEFORE the repair (a token that sat in a dir anyone else could read is
    not reused) and after it; unknown (None, e.g. off Windows) keeps the
    old behaviour."""
    runtime = Path(runtime)
    was_private = acl.is_private(runtime) if runtime.is_dir() else None
    try:
        runtime.mkdir(parents=True, exist_ok=True)
        now_private = acl.make_private(runtime)
    except OSError:
        now_private = None
    if now_private is False and log is not None:
        log.warning("runtime dir could not be made private (decision 0051)")
    if was_private is False or now_private is False:
        if log is not None:
            log.info("kept token not reused: the runtime dir was not private")
        try:
            (runtime / hotreload.TOKEN_REUSE_FILE).unlink()
        except OSError:
            pass
        return new_token()
    return hotreload.take_token_reuse(runtime, token_file) or new_token()


def _say(text):
    """One line on stderr when there is one (pythonw has none)."""
    if sys.stderr is not None:
        print(text, file=sys.stderr, flush=True)


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.check:
        return check_code()
    inst = None
    if args.demo is not None:
        # SEC-DEMO-ENTRY: prepared before logging, so core.log lands in the
        # scratch folder; nothing is made when the folder is unusable
        if args.log or args.replay:
            _say("AshLight demo: --log and --replay cannot be used with --demo")
            return 2
        try:
            inst = demo.prepare(args.demo)
            if args.port is None:
                args.port = demo.pick_port()
        except demo.DemoError as exc:
            _say(f"AshLight demo: {exc}")
            return 2
    setup_logging(args.quiet)
    log = logging.getLogger("al")
    install_crash_logging(log)
    if args.port is None:
        args.port = ports.resolve(os.environ, paths.load_local_config())
    if args.port and not ports.in_block(args.port):
        log.warning("port %s is outside the assigned block", args.port)

    if inst is not None:
        log.info("demo mode: fixture %s, scratch %s", inst.fixture, inst.scratch)
        core = demo.DemoCore(inst, tail=not args.no_tail, character=args.character)
    else:
        core = Core(log_path=args.log, tail=not args.no_tail, character=args.character)
    if args.replay:
        lines = Path(args.replay).read_text(encoding="utf-8", errors="replace").splitlines()
        log.info("replayed %d events from %s", core.replay(lines), Path(args.replay).name)

    token = start_token(paths.runtime_dir(), paths.token_file(), log)
    root = paths.repo_root()
    try:
        server = serve(core, token, port=args.port, web_root=root / "web",
                       tokens_css=root / "ops" / "fleet_kit" / "tokens.css")
    except OSError as exc:
        log.error("cannot bind %s:%s (%s) - is AshLight already running?",
                  ports.LOOPBACK, args.port, exc)
        return 2
    token_file = paths.token_file()
    write_private(token_file, token + "\n")
    url = f"http://{ports.LOOPBACK}:{server.port}/#token={token}"
    if not args.quiet and sys.stdout is not None:
        print(f"{NAME} {VERSION} on {url}", flush=True)
        if inst is not None:
            print(f"demo mode: fixture {inst.fixture}; scratch {inst.scratch}", flush=True)
        print(DISCLAIMER, flush=True)
    log.info("listening on %s:%s", ports.LOOPBACK, server.port)
    core.port = server.port  # DIAG-SELF: the served port

    if core.consented():
        core.start_tailing()
    elif not args.no_tail:
        log.info("Client.txt tailing waits for consent (dashboard)")

    stop = threading.Event()

    def _signal(signum, frame):
        stop.set()

    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None),
                getattr(signal, "SIGBREAK", None)):
        if sig is not None:
            try:
                signal.signal(sig, _signal)
            except (ValueError, OSError):
                pass

    clear_stop_request(paths.runtime_dir() / STOP_FILE)
    restart_file = paths.runtime_dir() / hotreload.RESTART_FILE
    clear_stop_request(restart_file)  # one left from an earlier reload
    restarting = False
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.5},
                         name="al-http", daemon=True)
    t.start()
    heartbeat = paths.runtime_dir() / "core.alive"
    stop_file = paths.runtime_dir() / STOP_FILE
    beat_s = _heartbeat_s()
    next_beat = 0.0
    from .keepalive import process_created  # pid + creation time = this process
    created = process_created(os.getpid())
    try:
        while not stop.wait(0.5):
            if stop_requested(stop_file):
                log.info("stop requested (%s); exiting cleanly", STOP_FILE)
                break
            if stop_requested(restart_file):
                # HOT-RELOAD: the supervisor saw a code change that passed
                # its preflight; exit cleanly and it starts the new code
                clear_stop_request(restart_file)
                log.info("code changed; exiting for a hot reload")
                restarting = True
                break
            core.tick_all(log)  # RUN-SEAMS: one pass of Core.ticks (decision 0056)
            if time.monotonic() >= next_beat:
                next_beat = time.monotonic() + beat_s
                try:
                    write_heartbeat(heartbeat, os.getpid(), server.port, created=created)
                except OSError:
                    pass
    except KeyboardInterrupt:
        pass
    log.info("shutting down")
    server.stop()
    core.close()
    if restarting:
        hotreload.mark_token_reuse(paths.runtime_dir())  # token file stays
    else:
        try:
            if token_file.read_text(encoding="ascii").strip() == token:
                token_file.unlink()
        except OSError:
            pass
    try:
        heartbeat.unlink()  # a leftover core.alive means the core did not exit cleanly
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
