"""AshLight core entry point.

    python -m server.al [--log PATH] [--port N] [--no-tail] [--replay FILE]

Prints the dashboard URL with the per-start token in the fragment
(#token=...), so it never reaches the server log or a Referer.
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

from . import DISCLAIMER, NAME, VERSION, paths, ports
from .core import Core, write_private
from .http import new_token, serve


def build_parser():
    p = argparse.ArgumentParser(prog="python -m server.al",
                                description=f"{NAME} {VERSION} core server")
    p.add_argument("--log", help="path to Client.txt (default: config, then Steam scan)")
    p.add_argument("--port", type=int, default=ports.AL_PORT,
                   help=f"port (default {ports.AL_PORT}; block "
                        f"{ports.PORT_BLOCK[0]}-{ports.PORT_BLOCK[1]})")
    p.add_argument("--no-tail", action="store_true", help="never tail Client.txt")
    p.add_argument("--replay", metavar="FILE",
                   help="feed a fixture file through the parser at start")
    p.add_argument("--character", help="character name to track")
    p.add_argument("--quiet", action="store_true", help="no console output")
    return p


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
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data) + "\n", encoding="ascii")
    os.replace(tmp, path)


def main(argv=None):
    args = build_parser().parse_args(argv)
    setup_logging(args.quiet)
    log = logging.getLogger("al")
    install_crash_logging(log)
    if args.port and not ports.in_block(args.port):
        log.warning("port %s is outside the assigned block", args.port)

    core = Core(log_path=args.log, tail=not args.no_tail, character=args.character)
    if args.replay:
        lines = Path(args.replay).read_text(encoding="utf-8", errors="replace").splitlines()
        log.info("replayed %d events from %s", core.replay(lines), Path(args.replay).name)

    token = new_token()
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
        print(DISCLAIMER, flush=True)
    log.info("listening on %s:%s", ports.LOOPBACK, server.port)

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
            try:
                core.ensure_tailing()  # TEST-E2E: log found later / moved
            except Exception:  # noqa: BLE001 - never stops the core loop
                log.exception("ensure_tailing failed")
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
