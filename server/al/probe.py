"""RUN-METRICS-PROBE (finding F-032, decision 0067): the probe command.

    python -m server.al.probe [--port N] [--timeout S]

Reads GET /api/health and the token-gated GET /api/debug of the local
core and prints one line per item ("key: value"): core, build, version,
mode, uptime, reader, feed, events, sse, http, loop, process, calc, fetch.
Exit 0 while the core is live, 1 when it is stopped (no token file, no
answer, or a listener that fails the hello proof).

Talks only to 127.0.0.1 on the core port (ports.resolve: env AL_PORT,
then config/local.json "port", then 8960), with no proxy. The per-start
token comes from paths.token_file(); the listener must prove the token
first (hello.verify, decision 0054) before the token is sent, and the
token is never printed. Every printed value is a number, a bool or a
short code word that passed a strict pattern; anything else prints "?",
so no path, name, pid or token can reach the output.

ZERO-CLICK: a session or a lane runs the one command; nothing for the
player. Standard library only.
"""

import argparse
import json
import re
import sys
import urllib.request

from . import hello, paths, ports

MAX_BODY = 16384  # bytes read of one answer (the debug body is under 4 KB)
TIMEOUT_S = 3.0
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}\Z")
_NAME_RE = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,63}\Z")  # no / | * in a shown name
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
CALC_PREFIX = "calc"
FETCH_PREFIX = "fetch"
TOP = 8  # counters shown on the calc and fetch lines


def _num(v):
    """A number or bool as text, else "?" (None reads "-")."""
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:g}"
    return "?"


def _word(v):
    return v if isinstance(v, str) and _WORD_RE.match(v) else "?"


def _get(doc, *keys):
    for k in keys:
        if not isinstance(doc, dict):
            return None
        doc = doc.get(k)
    return doc


def _pairs(d, keys):
    if not isinstance(d, dict):
        return "-"
    return " ".join(f"{k}={_num(d.get(k))}" for k in keys)


def _family(doc, prefix):
    """name=value pairs of the counters and timing rings under prefix."""
    out = []
    for name, v in sorted((_get(doc, "counters") or {}).items()):
        if (isinstance(name, str) and _NAME_RE.match(name)
                and name.startswith(prefix + ".")):
            out.append(f"{name[len(prefix) + 1:]}={_num(v)}")
    for name, ring in sorted((_get(doc, "timings") or {}).items()):
        if (isinstance(name, str) and _NAME_RE.match(name)
                and name.startswith(prefix + ".") and isinstance(ring, dict)):
            out.append(f"{name[len(prefix) + 1:]}_p50={_num(ring.get('p50'))}ms")
    return " ".join(out[:TOP]) if out else "none counted"


def render(health, debug, out):
    """Write the live lines for a /api/health and a /api/debug document."""
    tail = _get(debug, "tailer")
    if isinstance(tail, dict):
        reader = ("running" if tail.get("running") is True else "stopped") + " " + \
            _pairs(tail, ("lines", "bytes", "resets", "dropped_lines"))
    else:
        reader = "none"
    events = _get(debug, "events") or {}
    total = sum(v for k, v in events.items()
                if k != "log" and isinstance(v, int) and not isinstance(v, bool)) \
        if isinstance(events, dict) else None
    loop = _get(debug, "loop") or {}
    ring = _get(debug, "timings", "loop_ms")
    lines = [
        ("core", "live"),
        ("build", _word(_get(health, "build"))),
        ("version", _word(_get(health, "version"))),
        ("mode", _word(_get(health, "mode"))),
        ("uptime", _num(_get(debug, "uptime_s")) + "s"),
        ("reader", reader),
        ("feed", _pairs(_get(debug, "lines"), ("fed", "ignored", "failed"))),
        ("events", f"total={_num(total)} log={_num(_get(events, 'log'))}"),
        ("sse", _pairs(_get(debug, "sse"), ("subscribers", "frames", "bytes"))),
        ("http", f"unauthorized={_num(_get(debug, 'http', 'unauthorized'))}"),
        ("loop", f"age={_num(_get(loop, 'age_s'))}s"
                 f" p50={_num(_get(ring, 'p50'))}ms max={_num(_get(ring, 'max'))}ms"),
        ("process", _pairs(_get(debug, "process"),
                           ("working_set_mb", "cpu_s", "threads"))),
        ("calc", _family(debug, CALC_PREFIX)),
        ("fetch", _family(debug, FETCH_PREFIX)),
    ]
    trimmed = _get(debug, "trimmed")
    if isinstance(trimmed, list) and trimmed:
        lines.append(("trimmed", " ".join(_word(t) for t in trimmed)))
    for key, value in lines:
        out.write(f"{key}: {value}\n")


def stopped(out, reason):
    out.write("core: stopped\n")
    out.write(f"reason: {reason}\n")
    return 1


def _fetch(port, path, token, timeout):
    req = urllib.request.Request(f"http://{ports.LOOPBACK}:{int(port)}{path}",
                                 headers={"X-AL-Token": token})
    with _NO_PROXY.open(req, timeout=timeout) as r:
        if r.status != 200:
            raise ValueError("status")
        data = r.read(MAX_BODY + 1)
    if len(data) > MAX_BODY:
        raise ValueError("too big")
    doc = json.loads(data)
    if not isinstance(doc, dict):
        raise ValueError("shape")
    return doc


def _token():
    try:
        return paths.token_file().read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        return ""


def probe(port, out, timeout=TIMEOUT_S):
    """Print the items of the core on 127.0.0.1:port; 0 live, 1 stopped."""
    token = _token()
    if not token:
        return stopped(out, "no token file")
    if not hello.verify(port, token, opener=_NO_PROXY, timeout=timeout):
        return stopped(out, f"no core answers on port {int(port)}")
    try:
        health = _fetch(port, "/api/health", token, timeout)
        debug = _fetch(port, "/api/debug", token, timeout)
    except (OSError, ValueError):
        hello.forget(port)
        return stopped(out, f"no core answers on port {int(port)}")
    render(health, debug, out)
    return 0


def main(argv=None, out=None):
    out = sys.stdout if out is None else out
    ap = argparse.ArgumentParser(prog="python -m server.al.probe",
                                 description="One line per item of the local core.")
    ap.add_argument("--port", type=int, default=None,
                    help="core port (default: AL_PORT, config port, then 8960)")
    ap.add_argument("--timeout", type=float, default=TIMEOUT_S)
    args = ap.parse_args(argv)
    port = args.port
    if port is None:
        port = ports.resolve(None, paths.load_local_config())
    if not ports.in_block(port):
        out.write("core: stopped\nreason: port outside the AshLight block\n")
        return 1
    return probe(port, out, timeout=max(0.1, args.timeout))


if __name__ == "__main__":
    sys.exit(main())
