"""AshLight core entry point.

    python -m server.al [--log PATH] [--port N] [--no-tail] [--replay FILE]

Prints the dashboard URL with the per-start token in the fragment
(#token=...), so it never reaches the server log or a Referer.
"""

import argparse
import logging
import signal
import sys
import threading
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
    if not quiet and sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers or [logging.NullHandler()],
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")


def main(argv=None):
    args = build_parser().parse_args(argv)
    setup_logging(args.quiet)
    log = logging.getLogger("al")
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

    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.5},
                         name="al-http", daemon=True)
    t.start()
    try:
        while not stop.wait(0.5):
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
