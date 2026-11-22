"""PLAY-TD-04B-THEME-CHOICE (TD-04, F-086): the Theme choice.

The page ships dark for every browser (<html data-theme="dark">) and one
Settings choice changes it: Dark (default), Follow Windows ("system") or
Light. The choice is the "theme" key of config/local.json, read and set
through the token-gated GET / POST /api/theme (the Host / Origin checks of
every route), and it travels with the settings backup (settingsio ALLOWED).

The pixel half of the proof goes only through the shared capture helper
(app/test/cdp/capture.mjs, F-147): AshLight's own page on a DEMO core, in a
headless browser, with prefers-color-scheme light emulated. With no setting
the page is dark (the body ground is rgb(15, 18, 22) and the mean relative
luminance is under 0.05); after POST /api/theme light the ground is white.
The demo core keeps its config in its own scratch folder; the live core,
config/local.json and the live Client.txt are never touched.
"""

import http.client
import json
import struct
import threading
import zlib
from pathlib import Path

import pytest

from server.al import settingsio
from server.al.core import Core, ConfigUnreadable
from server.al.http import serve

from browser_util import find_browser
from test_capture_helper import NODE, demo_core, run_helper  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "e" * 48
DARK = (15, 18, 22)  # the kit's dark --fk-surface
WHITE = (255, 255, 255)  # the kit's light --fk-surface
LUMINANCE_MAX = 0.05


# -- the setting --------------------------------------------------------------

def test_theme_is_an_allowed_setting_with_its_label():
    assert settingsio.THEMES == ("dark", "system", "light")
    assert settingsio.THEME_DEFAULT == "dark"
    assert "theme" in settingsio.ALLOWED and settingsio.LABELS["theme"] == "theme"
    assert "theme" not in settingsio.NEVER
    for good in settingsio.THEMES:
        assert settingsio.ALLOWED["theme"](good) == good
    for bad in ("Dark", "auto", "", None, 1, True, ["dark"]):
        with pytest.raises(settingsio.SettingsError):
            settingsio.ALLOWED["theme"](bad)


def test_a_bad_theme_in_a_backup_refuses_the_file_in_words():
    doc = {"kind": settingsio.KIND, "schema": 2, "settings": {"theme": "blue"}}
    with pytest.raises(settingsio.SettingsError) as e:
        settingsio.parse_import(doc, {})
    assert str(e.value) == "The theme in that file must be Dark, Follow Windows or Light."


def _core(tmp_path, cfg=None):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    path = tmp_path / "local.json"
    if cfg is not None:
        path.write_text(json.dumps(cfg), encoding="ascii")
    return Core(runtime=tmp_path / "rt", log_path=str(log), tail=False, config_path=path), path


def test_core_theme_defaults_to_dark_and_keeps_other_keys(tmp_path):
    core, path = _core(tmp_path)
    assert core.theme() == "dark"  # no config file
    path.write_text(json.dumps({"theme": "neon", "contact": "keep-me"}), encoding="ascii")
    assert core.theme() == "dark"  # an unknown stored value reads as the default
    assert core.set_theme("light") == "light"
    saved = json.loads(path.read_text(encoding="ascii"))
    assert saved == {"theme": "light", "contact": "keep-me"}
    assert core.theme() == "light"
    assert core.set_theme("system") == "system" and core.theme() == "system"
    for bad in ("Light", "", None, 3):
        with pytest.raises(ValueError):
            core.set_theme(bad)
    assert json.loads(path.read_text(encoding="ascii"))["theme"] == "system"


def test_core_never_overwrites_a_broken_config(tmp_path):
    core, path = _core(tmp_path)
    path.write_text("{not json", encoding="ascii")
    with pytest.raises(ConfigUnreadable):
        core.set_theme("light")
    assert path.read_text(encoding="ascii") == "{not json"


def test_the_theme_survives_export_and_import(tmp_path):
    (tmp_path / "a").mkdir()
    core, _path = _core(tmp_path / "a", {"theme": "light", "contact": "secret"})
    exported = json.loads(json.dumps(core.export_settings()))
    assert exported["settings"]["theme"] == "light"
    assert "secret" not in json.dumps(exported)
    (tmp_path / "b").mkdir()
    other, other_path = _core(tmp_path / "b", {"contact": "mine"})
    assert other.theme() == "dark"
    report = other.import_settings(exported)
    assert "theme" in report["applied"]
    assert other.theme() == "light"
    assert json.loads(other_path.read_text(encoding="ascii"))["contact"] == "mine"


# -- the route ----------------------------------------------------------------

@pytest.fixture
def server(tmp_path):
    core, path = _core(tmp_path)
    srv = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        yield srv, path
    finally:
        srv.shutdown()
        srv.server_close()


def _req(port, method, path, body=None, headers=None, token=TOKEN):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Host": f"127.0.0.1:{port}"}
    if token:
        h["X-AL-Token"] = token
    raw = None
    if body is not None:
        raw = body if isinstance(body, bytes) else json.dumps(body).encode("ascii")
        h["Content-Type"] = "application/json"
        h["Content-Length"] = str(len(raw))
    h.update(headers or {})
    conn.request(method, path, body=raw, headers=h)
    r = conn.getresponse()
    out = (r.status, r.read().decode("ascii"))
    conn.close()
    return out


def test_get_and_post_theme_with_the_token(server):
    srv, path = server
    status, body = _req(srv.port, "GET", "/api/theme")
    assert status == 200
    assert json.loads(body) == {"theme": "dark", "choices": ["dark", "system", "light"]}
    status, body = _req(srv.port, "POST", "/api/theme", {"theme": "system"})
    assert status == 200 and json.loads(body)["theme"] == "system"
    assert json.loads(path.read_text(encoding="ascii")) == {"theme": "system"}
    assert json.loads(_req(srv.port, "GET", "/api/theme")[1])["theme"] == "system"


def test_bad_theme_bodies_are_refused_with_nothing_written(server):
    srv, path = server
    _req(srv.port, "POST", "/api/theme", {"theme": "light"})
    before = path.read_text(encoding="ascii")
    for body in ({}, {"theme": "Light"}, {"theme": 1}, {"theme": None},
                 {"theme": "dark", "extra": 1}, [], "dark"):
        status, text = _req(srv.port, "POST", "/api/theme", body)
        assert status == 400, (body, status, text)
    assert _req(srv.port, "POST", "/api/theme", b"x" * 5000)[0] == 413
    assert path.read_text(encoding="ascii") == before


def test_the_theme_route_keeps_the_token_and_host_origin_checks(server):
    srv, path = server
    assert _req(srv.port, "GET", "/api/theme", token=None)[0] == 401
    assert _req(srv.port, "POST", "/api/theme", {"theme": "light"}, token=None)[0] == 401
    assert _req(srv.port, "GET", "/api/theme", token="x" * 48)[0] == 401
    assert _req(srv.port, "GET", "/api/theme?token=" + TOKEN, token=None)[0] == 401
    assert _req(srv.port, "POST", "/api/theme", {"theme": "light"},
                headers={"Host": "evil.example"})[0] == 400
    assert _req(srv.port, "POST", "/api/theme", {"theme": "light"},
                headers={"Origin": "http://evil.example"})[0] == 403
    assert _req(srv.port, "POST", "/api/theme", {"theme": "light"},
                headers={"Sec-Fetch-Site": "cross-site"})[0] == 403
    assert not path.exists()


def test_the_page_ships_dark_with_the_theme_row():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en" data-theme="dark">' in html
    assert '<link rel="stylesheet" href="/web/theme.css">' in html
    assert '<script src="/web/theme.js" defer></script>' in html
    assert '<select id="theme-pick" aria-describedby="theme-help theme-said">' in html
    for value, label in (("dark", "Dark"), ("system", "Follow Windows"), ("light", "Light")):
        assert f'<option value="{value}">{label}</option>' in html


# -- the pixels, through the shared capture helper ---------------------------

def read_png(data):
    """(width, height, rows of (r, g, b)) of an 8-bit RGB or RGBA PNG."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, width = 8, [], None
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            width, height, depth, ctype, _c, _f, interlace = struct.unpack(">IIBBBBB", chunk)
            assert depth == 8 and ctype in (2, 6) and interlace == 0, (depth, ctype, interlace)
            bpp = 3 if ctype == 2 else 4
        elif kind == b"IDAT":
            idat.append(chunk)
        elif kind == b"IEND":
            break
    raw = zlib.decompress(b"".join(idat))
    stride = width * bpp
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(height):
        ftype, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        if ftype == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 255
        elif ftype == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif ftype == 3:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 255
        elif ftype == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[x] = (line[x] + pred) & 255
        rows.append([tuple(line[x:x + 3]) for x in range(0, stride, bpp)])
        prev = line
    return width, height, rows


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def mean_luminance(rows):
    table = [_lin(v) for v in range(256)]
    total = count = 0
    for row in rows:
        for r, g, b in row:
            total += 0.2126 * table[r] + 0.7152 * table[g] + 0.0722 * table[b]
            count += 1
    return total / count


def _capture(browser, tmp_path, name, port, token):
    out, profile = tmp_path / f"{name}.png", tmp_path / f"profile-{name}"
    r, doc = run_helper([browser, str(profile), f"http://127.0.0.1:{port}/#token={token}",
                         str(out), "--width=800", "--height=600", "--scheme=light",
                         "--wait-ms=1500"], timeout=120)
    assert r.returncode == 0, (r.returncode, r.stdout[-2000:], r.stderr[-2000:])
    assert doc["ok"] is True
    return read_png(out.read_bytes())


def _ground(rows):
    """The page ground: the colour of the bottom-left corner pixel, which
    the footer leaves to the body background."""
    return rows[-1][0]


@pytest.mark.server
@pytest.mark.slow  # two headless captures of a demo core page (about 5 s)
@pytest.mark.skipif(not NODE, reason="node not found")
def test_capture_is_dark_under_a_light_browser_until_light_is_chosen(demo_core, tmp_path):
    browser = find_browser()
    if not browser:
        pytest.skip("headless Chrome / Edge not found")
    port, token = demo_core
    w, h, rows = _capture(browser, tmp_path, "default", port, token)
    assert (w, h) == (800, 600)
    assert _ground(rows) == DARK, _ground(rows)
    lum = mean_luminance(rows)
    assert lum < LUMINANCE_MAX, lum
    # the one Settings choice, as the select posts it
    status, body = _req(port, "POST", "/api/theme", {"theme": "light"}, token=token)
    assert status == 200, body
    _w, _h, rows = _capture(browser, tmp_path, "light", port, token)
    assert _ground(rows) == WHITE, _ground(rows)
    assert mean_luminance(rows) > 0.5
