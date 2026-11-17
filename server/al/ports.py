"""Port constants (block 8960-8979). A port literal at a bind site is a defect."""

import logging
import os

PORT_BLOCK = (8960, 8979)
AL_PORT = 8960  # core server: API, dashboard assets, SSE
LOOPBACK = "127.0.0.1"  # the only bind address; LAN access stays off
PORT_ENV = "AL_PORT"  # per-run override (scripts\run.ps1 -Port sets it)


def in_block(port):
    """True when port is inside the assigned block (0 = ephemeral, tests only)."""
    return PORT_BLOCK[0] <= int(port) <= PORT_BLOCK[1]


def _block_port(value):
    """value as an int inside the block, else None (bool, junk, out of block)."""
    if isinstance(value, bool):
        return None
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return port if in_block(port) else None


def resolve(environ=None, config=None):
    """The core port, ONE rule for the core, run.ps1, keepalive and the
    overlay (app/main.js corePort): env AL_PORT, then config/local.json
    "port", then AL_PORT. A value outside the block is ignored with a
    logged warning, so the core never binds outside 8960-8979
    (TEST-CLEAN-CLONE: the documented "port" key was read by the overlay
    only, so a second checkout could not move off 8960)."""
    env = os.environ if environ is None else environ
    sources = ((f"env {PORT_ENV}", env.get(PORT_ENV) or ""),
               ('config "port"', (config or {}).get("port")))
    for name, value in sources:
        if value in ("", None):
            continue
        port = _block_port(value)
        if port is not None:
            return port
        logging.getLogger("al").warning(
            "%s=%r is not a port in the block %s-%s; ignored (default %s)",
            name, value, PORT_BLOCK[0], PORT_BLOCK[1], AL_PORT)
    return AL_PORT
