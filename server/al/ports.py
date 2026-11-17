"""Port constants (block 8960-8979). A port literal at a bind site is a defect."""

PORT_BLOCK = (8960, 8979)
AL_PORT = 8960  # core server: API, dashboard assets, SSE
LOOPBACK = "127.0.0.1"  # the only bind address; LAN access stays off


def in_block(port):
    """True when port is inside the assigned block (0 = ephemeral, tests only)."""
    return PORT_BLOCK[0] <= int(port) <= PORT_BLOCK[1]
