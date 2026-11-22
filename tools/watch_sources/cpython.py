"""DEP-19 (CPython pin watch; decisions 0063, 0069): the private CPython
runtime watcher.

What it reads: www.python.org's public downloads API, at most 2 requests a
run, once per 24 h, purpose 'cpython watch' (truthful AshLight User-Agent,
no cookie), only while web_data is on (the frame never calls a gated source
otherwise):
- RELEASES_URL, the release list: [{"name": "Python 3.14.11",
  "is_published": true, "pre_release": false, ...}, ...];
- FILES_URL, only when the list names a newer patch of the pinned line: the
  release files named "Windows embeddable package (64-bit)", each with a
  "url" .../ftp/python/<X.Y.Z>/python-<X.Y.Z>-embed-amd64.zip. The version
  is read from that url only, so an ignored name filter changes nothing.
From the tree (ctx["root"], or this checkout only when ctx["live"] is true;
with neither the source reads nothing and makes no request): the python pin
of config/runtime_pins.json (read, never written). The pinned line is the
pin's major.minor (3.14 today).

HALT: unlike GGG-DOCS-WATCH this source respects HALT. While ctx["halted"]
is true or ops/loop/control/HALT exists under the root it makes no request
and returns nothing; the check runs on the first tick after HALT is gone.

Findings (row text from ops/loop/watch_rows/cpython.json):
- kind "cpythonbump" (row CPYTHON-<MAJ>-<MIN>-<PAT>), key the version: the
  newest published final patch of the pinned line that is newer than the
  pin and ships an embeddable amd64 zip. Once per version for all time (the
  frame's seen list).
- kind "cpythonnozip" (act note, one tick line), key "nozip-<version>": the
  newest published patch of the line is newer than the pin but ships no
  embeddable amd64 zip (yet); no row is filed for it.
A non-200 answer or an unknown shape fails the run with one tick line
naming the URL read; a moved endpoint is never guessed.

Python stdlib only; no subprocess, no runtime file.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

NAME = "cpython"
KIND_BUMP = "cpythonbump"
KIND_NOZIP = "cpythonnozip"
RELEASES_URL = "https://www.python.org/api/v2/downloads/release/"
FILES_URL = ("https://www.python.org/api/v2/downloads/release_file/"
             "?name=Windows%20embeddable%20package%20(64-bit)")
PINS_REL = Path("config") / "runtime_pins.json"
HALT_REL = Path("ops") / "loop" / "control" / "HALT"
ARCH = "amd64"

DAY_S = 24 * 3600

VERSION_RX = re.compile(r"([0-9]{1,2})\.([0-9]{1,3})\.([0-9]{1,3})")
NAME_RX = re.compile(r"Python ([0-9]{1,2}\.[0-9]{1,3}\.[0-9]{1,3})")
ZIP_RX = re.compile(r"https://www\.python\.org/ftp/python/([0-9]{1,2}\.[0-9]{1,3}\.[0-9]{1,3})/"
                    r"python-([0-9]{1,2}\.[0-9]{1,3}\.[0-9]{1,3})-embed-amd64\.zip")


def _uw():
    import upstream_watch  # the frame; on sys.path whenever a source runs
    return upstream_watch


def vtuple(text):
    """(major, minor, patch) of an exact X.Y.Z string, else None."""
    m = VERSION_RX.fullmatch(text) if isinstance(text, str) else None
    return tuple(int(p) for p in m.groups()) if m else None


def _root(ctx):
    if ctx.get("root") is not None:
        return Path(ctx["root"])
    return ROOT if ctx.get("live") else None


def halted_now(root, ctx):
    if ctx.get("halted"):
        return True
    return root is not None and (Path(root) / HALT_REL).exists()


def pin_of(root):
    """The exact python version config/runtime_pins.json pins for amd64, or
    None (no file). A pin that is not an exact X.Y.Z is a shape failure."""
    try:
        doc = json.loads((Path(root) / PINS_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    py = doc.get("runtimes", {}).get("python") if isinstance(doc, dict) else None
    if not isinstance(py, dict) or py.get("arch") != ARCH:
        return None
    ver = py.get("version")
    if vtuple(ver) is None:
        raise _uw().SourceError("shape", "the python pin in config/runtime_pins.json "
                                "is not an exact X.Y.Z")
    return ver


def _get(fetch, url):
    uw = _uw()
    status, _headers, body = fetch(url)
    if status != 200:
        raise uw.SourceError("status", f"HTTP {status} from {url} (endpoint moved?)")
    try:
        doc = json.loads((body or b"").decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise uw.SourceError("shape", f"{url} answered no JSON") from None
    if isinstance(doc, dict) and isinstance(doc.get("results"), list):
        doc = doc["results"]  # a paginated answer
    if not isinstance(doc, list):
        raise uw.SourceError("shape", f"{url} answered no list")
    return doc


def line_releases(items, pin):
    """The published final versions of the pin's major.minor newer than the
    pin, oldest first."""
    pt = vtuple(pin)
    out = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("is_published") is not True or item.get("pre_release") is not False:
            continue
        m = NAME_RX.fullmatch(item.get("name") or "") if isinstance(item.get("name"), str) \
            else None
        vt = vtuple(m.group(1)) if m else None
        if vt and vt[:2] == pt[:2] and vt > pt:
            out.add(m.group(1))
    return sorted(out, key=vtuple)


def zip_versions(items):
    """The versions with an embeddable amd64 zip in the release files."""
    out = set()
    for item in items:
        url = item.get("url") if isinstance(item, dict) else None
        m = ZIP_RX.fullmatch(url) if isinstance(url, str) else None
        if m and m.group(1) == m.group(2):
            out.add(m.group(1))
    return out


def check(state, now, fetch, ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    root = _root(ctx)
    if root is None or halted_now(root, ctx):
        return []
    pin = pin_of(root)
    if pin is None:
        return []
    data = dict(state.get("data")) if isinstance(state.get("data"), dict) else {}
    newer = line_releases(_get(fetch, RELEASES_URL), pin)
    found = []
    zipped = []
    if newer:
        have = zip_versions(_get(fetch, FILES_URL))
        zipped = [v for v in newer if v in have]
        if zipped:
            ver = zipped[-1]
            maj, mnr, pat = vtuple(ver)
            found.append({"kind": KIND_BUMP, "key": ver,
                          "tokens": {"MAJ": str(maj), "MIN": str(mnr), "PAT": str(pat),
                                     "version": ver, "pin": pin}})
        if newer[-1] not in have:
            found.append({"kind": KIND_NOZIP, "key": f"nozip-{newer[-1]}",
                          "tokens": {"version": newer[-1], "pin": pin}})
    data.update(pin=pin, newest=newer[-1] if newer else pin,
                zip=zipped[-1] if zipped else None)
    state["data"] = data
    return found


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": DAY_S,
    "window": None,
    "needs_web_data": True,
    "hosts": [],
    "urls": [RELEASES_URL, FILES_URL],
    "purpose": "cpython watch",
    "check": check,
}
