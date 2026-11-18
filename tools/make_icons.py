"""BRAND-ICON: render AshLight's icon set and README hero from the SVG sources.

Design note: docs/design/0005-brand-mark.md. Python stdlib only.

Sources (tracked, the source of truth):
  assets/brand/ashlight-mark.svg        48 px and up
  assets/brand/ashlight-mark-small.svg  16, 24, 32 px (tray, favicon)
  assets/brand/readme-hero.svg          README hero, light and dark

Outputs (tracked, so a clone needs no Electron to show them):
  assets/brand/png/ashlight-<n>.png     n = 16 24 32 48 64 128 256
  assets/brand/readme-hero-light.png, readme-hero-dark.png  (1280 x 400)
  app/assets/icon.ico                   16 24 32 48 64 128 256 (PNG entries)
  app/assets/icon-256.png, tray-16.png, tray-32.png
  web/favicon.ico (16 32 48), web/favicon.svg (copy of the small mark)

`render` (default) runs the pinned Electron (app/node_modules, or the main
checkout's when run from a linked worktree, or --electron / AL_ELECTRON)
with scripts/brand_render.js into the sidecar Temp dir, then copies only files
whose bytes changed: a re-run with unchanged sources rewrites nothing.
`pack` rebuilds the ICO files and copies from the tracked PNGs (no
Electron). `check` verifies every output exists with the right size and the
ICOs match the PNGs; exit 0 ok, 1 mismatch.
"""

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRAND = ROOT / "assets" / "brand"
PNG_DIR = BRAND / "png"
MARK = BRAND / "ashlight-mark.svg"
SMALL = BRAND / "ashlight-mark-small.svg"
HERO = BRAND / "readme-hero.svg"
SIZES = (16, 24, 32, 48, 64, 128, 256)
SMALL_SIZES = (16, 24, 32)
FAVICON_SIZES = (16, 32, 48)
HERO_SIZE = (1280, 400)
APP_ASSETS = ROOT / "app" / "assets"
ICO = APP_ASSETS / "icon.ico"
FAVICON = ROOT / "web" / "favicon.ico"
FAVICON_SVG = ROOT / "web" / "favicon.svg"
PNG_SIG = b"\x89PNG\r\n\x1a\n"


def png_path(n):
    return PNG_DIR / ("ashlight-%d.png" % n)


def hero_path(theme):
    return BRAND / ("readme-hero-%s.png" % theme)


def copies():
    """Derived files that are byte copies: {dest: source}."""
    return {
        APP_ASSETS / "icon-256.png": png_path(256),
        APP_ASSETS / "tray-16.png": png_path(16),
        APP_ASSETS / "tray-32.png": png_path(32),
        FAVICON_SVG: SMALL,
    }


def png_size(data):
    """(width, height) from a PNG's IHDR; ValueError if it is not a PNG."""
    if data[:8] != PNG_SIG or data[12:16] != b"IHDR":
        raise ValueError("not a PNG")
    return struct.unpack(">II", data[16:24])


def png_corner_alpha(data):
    """Alpha of the top-left pixel of an 8-bit RGBA, non-interlaced PNG."""
    pos, idat, ihdr = 8, b"", None
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            ihdr = body
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    width, _h, depth, ctype = struct.unpack(">IIBB", ihdr[:10])
    if depth != 8 or ctype != 6:
        raise ValueError("not 8-bit RGBA")
    row = zlib.decompress(idat)[:1 + width * 4]
    # Row 0, pixel 0 has no left and no up neighbour, so every PNG filter
    # (none, sub, up, average, paeth) leaves its bytes raw.
    return row[4]


def ico_bytes(pngs):
    """A Windows .ico with one PNG entry per (size, png bytes), ascending."""
    pngs = sorted(pngs, key=lambda p: p[0])
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, data in pngs:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return head + entries + blobs


def ico_entries(data):
    """[(size, png bytes)] from an .ico written by ico_bytes."""
    _r, kind, count = struct.unpack("<HHH", data[:6])
    if kind != 1:
        raise ValueError("not an icon")
    out = []
    for i in range(count):
        w, _h, _c, _r2, _p, _b, size, off = struct.unpack(
            "<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
        out.append((w or 256, data[off:off + size]))
    return out


def write_if_changed(path, data):
    path = Path(path)
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def find_electron(arg=None, environ=None):
    environ = os.environ if environ is None else environ
    cands = [arg, environ.get("AL_ELECTRON")]
    rel = Path("app") / "node_modules" / "electron" / "dist" / "electron.exe"
    cands.append(ROOT / rel)
    try:
        common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        cands.append((ROOT / common).resolve().parent / rel)
    except (OSError, subprocess.CalledProcessError):
        pass
    for c in cands:
        if c and Path(c).is_file():
            return Path(c)
    return None


def jobs(outdir):
    out = []
    for n in SIZES:
        src = SMALL if n in SMALL_SIZES else MARK
        out.append({"svg": str(src), "out": str(outdir / png_path(n).name),
                    "size": [n, n], "theme": "dark", "dest": png_path(n)})
    for theme in ("light", "dark"):
        out.append({"svg": str(HERO), "out": str(outdir / hero_path(theme).name),
                    "size": list(HERO_SIZE), "theme": theme, "dest": hero_path(theme)})
    return out


def temp_dir():
    try:
        from server.al import paths
        base = paths.sidecar_dir("Temp")
    except Exception:  # noqa: BLE001 - fall back to the system temp
        base = Path(tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="al-brand-", dir=str(base)))


def render(electron):
    tmp = temp_dir()
    try:
        todo = jobs(tmp)
        spec = tmp / "jobs.json"
        spec.write_text(json.dumps({"tmp": str(tmp), "jobs": [
            {k: v for k, v in j.items() if k != "dest"} for j in todo]}), encoding="ascii")
        env = dict(os.environ)
        env.pop("ELECTRON_RUN_AS_NODE", None)
        r = subprocess.run([str(electron), str(ROOT / "scripts" / "brand_render.js"), str(spec)],
                           cwd=str(ROOT / "app"), env=env, capture_output=True, text=True,
                           timeout=300)
        if r.returncode != 0:
            sys.stderr.write(r.stdout + r.stderr)
            return None
        changed = []
        for j in todo:
            data = Path(j["out"]).read_bytes()
            if png_size(data) != tuple(j["size"]):
                sys.stderr.write("wrong size for %s\n" % j["dest"].name)
                return None
            if write_if_changed(j["dest"], data):
                changed.append(j["dest"])
        return changed
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pack():
    changed = []
    pngs = {n: png_path(n).read_bytes() for n in SIZES}
    if write_if_changed(ICO, ico_bytes(pngs.items())):
        changed.append(ICO)
    if write_if_changed(FAVICON, ico_bytes((n, pngs[n]) for n in FAVICON_SIZES)):
        changed.append(FAVICON)
    for dest, src in copies().items():
        if write_if_changed(dest, src.read_bytes()):
            changed.append(dest)
    return changed


def check():
    problems = []
    for src in (MARK, SMALL, HERO):
        if not src.is_file():
            problems.append("missing " + src.name)
    pngs = {}
    for n in SIZES:
        p = png_path(n)
        if not p.is_file():
            problems.append("missing " + p.name)
            continue
        pngs[n] = p.read_bytes()
        if png_size(pngs[n]) != (n, n):
            problems.append("wrong size " + p.name)
    for theme in ("light", "dark"):
        p = hero_path(theme)
        if not p.is_file() or png_size(p.read_bytes()) != HERO_SIZE:
            problems.append("hero " + theme)
    for ico, sizes in ((ICO, SIZES), (FAVICON, FAVICON_SIZES)):
        if not ico.is_file():
            problems.append("missing " + ico.name)
            continue
        got = ico_entries(ico.read_bytes())
        if [s for s, _ in got] != list(sizes):
            problems.append("sizes " + ico.name)
        elif any(pngs.get(s) != d for s, d in got):
            problems.append("stale " + ico.name)
    for dest, src in copies().items():
        if not dest.is_file() or not src.is_file() or dest.read_bytes() != src.read_bytes():
            problems.append("stale " + dest.name)
    return problems


def _rel(p):
    return Path(p).resolve().relative_to(ROOT).as_posix()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", nargs="?", default="render", choices=("render", "pack", "check"))
    ap.add_argument("--electron", help="path to the pinned electron.exe")
    a = ap.parse_args(argv)
    if a.mode == "check":
        problems = check()
        for p in problems:
            print("make_icons: " + p)
        print("make_icons: check " + ("ok" if not problems else "FAILED"))
        return 1 if problems else 0
    changed = []
    if a.mode == "render":
        electron = find_electron(a.electron)
        if electron is None:
            print("make_icons: Electron not found (run npm ci --prefix app, or --electron)")
            return 1
        got = render(electron)
        if got is None:
            print("make_icons: render failed")
            return 1
        changed += got
    changed += pack()
    if changed:
        for p in changed:
            print("make_icons: wrote " + _rel(p))
    else:
        print("make_icons: unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
