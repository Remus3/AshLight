"""UTIL-FILTER-MERGE (decision 0033): AshLight's Show blocks prepended to a
filter the player picks in the browser; the player's bytes stay identical."""

import http.client
import threading
from pathlib import Path
from urllib.parse import quote

import pytest

from server.al.theorycraft import lootfilter
from server.al.theorycraft.model import Build, Item

ROOT = Path(__file__).resolve().parents[1]
BOM = b"\xef\xbb\xbf"

BUILD = Build(raw_xml="", class_name="Ranger", ascendancy="Deadeye", gear={
    "Weapon 1": Item(1, "", "RARE", "Grim Bite", "Expert Hunting Bow"),
    "Helmet": Item(2, "", "UNIQUE", "Odd", 'Odd "Hood"\nShow\n    SetFontSize 1')})

OWN_LF = b'# my filter\nShow\n    Rarity Unique\n    SetFontSize 45\n\nHide\n    AreaLevel > 70\n'
OWN_CRLF = OWN_LF.replace(b"\n", b"\r\n")


def split(out):
    """(section bytes, the player's bytes) at the end marker line."""
    end = lootfilter.MERGE_END.encode("ascii")
    i = out.index(end)
    j = out.index(b"\n", i) + 1
    return out[:j], out[j:]


def test_player_bytes_kept_after_marked_section():
    out = lootfilter.merge(OWN_LF, BUILD)
    section, rest = split(out)
    assert rest == OWN_LF
    assert section.startswith(lootfilter.MERGE_BEGIN.encode("ascii"))
    assert b"Hide" not in section and section.isascii()
    assert b'BaseType == "Expert Hunting Bow" "Odd Hood Show SetFontSize 1"' in section
    # the section is valid on its own: every non-comment line is a Show or indented
    for line in section.decode("ascii").split("\n"):
        assert not line or line.startswith("#") or line == "Show" or line.startswith("    ")


def test_injection_in_names_stays_inside_one_quoted_basetype():
    section, _ = split(lootfilter.merge(OWN_LF, BUILD))
    lines = section.decode("ascii").split("\n")
    assert lines.count("Show") == 1  # the newline in the name made no block
    assert not any(ln.strip() == "SetFontSize 1" for ln in lines)


def test_crlf_file_gets_a_crlf_section_and_stays_identical():
    out = lootfilter.merge(OWN_CRLF, BUILD)
    section, rest = split(out)
    assert rest == OWN_CRLF
    assert b"\n" not in section.replace(b"\r\n", b"")


def test_bom_stays_first_and_only_once():
    out = lootfilter.merge(BOM + OWN_LF, BUILD)
    assert out.startswith(BOM) and out.count(BOM) == 1
    section, rest = split(out[len(BOM):])
    assert rest == OWN_LF


def test_non_ascii_utf8_kept_byte_identical():
    own = "# Filtre de Zo\u00e9 \u2014 r\u00e9glages\nShow\n    Rarity Rare\n".encode("utf-8")
    assert split(lootfilter.merge(own, BUILD))[1] == own


def test_merging_a_merged_file_replaces_the_old_section_only():
    once = lootfilter.merge(OWN_LF, BUILD)
    twice = lootfilter.merge(once, None)
    assert twice.count(lootfilter.MERGE_BEGIN.encode("ascii")) == 1
    assert split(twice)[1] == OWN_LF
    crlf = lootfilter.merge(BOM + OWN_CRLF, BUILD)
    again = lootfilter.merge(crlf, BUILD)
    assert again == crlf


def test_no_build_section_is_comments_only():
    section, rest = split(lootfilter.merge(OWN_LF, None))
    assert rest == OWN_LF
    assert all(not ln or ln.startswith("#") for ln in section.decode("ascii").split("\n"))


def test_file_without_final_newline_is_kept_as_is():
    own = b"Show\n    Rarity Rare"
    assert split(lootfilter.merge(own, BUILD))[1] == own


def test_big_file_up_to_the_cap_is_merged():
    line = b"# " + b"x" * 97 + b"\n"
    own = line * (lootfilter.MAX_MERGE_BYTES // len(line))
    assert len(own) <= lootfilter.MAX_MERGE_BYTES
    assert split(lootfilter.merge(own, BUILD))[1] == own


@pytest.mark.parametrize("data, why", [
    (b"", "empty"),
    (BOM, "empty"),
    (b"Show\n" + b"#" * lootfilter.MAX_MERGE_BYTES, "too_big"),
    (b"Show\x00\n", "not_text"),
    (b"\xff\xfeS\x00h\x00", "not_utf8"),
    (b"Show\n# \xc3\x28\n", "not_utf8"),
    (b"\x89PNG\r\n\x1a\n", "not_utf8"),
    (b"Show\n\x1b[31m\n", "not_text"),
    (b"Show\n\x0c\n", "not_text"),
    (b"PK\x03\x04\x14\x00", "not_text"),
])
def test_refuses_what_is_not_a_text_filter(data, why):
    with pytest.raises(lootfilter.MergeRefused) as e:
        lootfilter.merge(data, BUILD)
    assert e.value.reason == why
    assert str(e.value) == lootfilter.REFUSED_TEXT[why]


def test_tabs_and_form_feed_free_text_pass():
    own = b"Show\n\tRarity Rare\n"
    assert split(lootfilter.merge(own, BUILD))[1] == own


@pytest.mark.parametrize("name, out", [
    ("NeverSink.filter", "NeverSink-ashlight.filter"),
    ("my filter.FILTER", "my filter-ashlight.filter"),
    ("top\\sub\\a.filter", "a-ashlight.filter"),
    ("../../etc/passwd", "passwd-ashlight.filter"),
    ('ev"il\r\n.filter', "evil-ashlight.filter"),
    ("Zo\u00e9.filter", "Zo-ashlight.filter"),
    ("", "filter-ashlight.filter"),
    (None, "filter-ashlight.filter"),
    ("...", "filter-ashlight.filter"),
    ("x" * 300 + ".filter", "x" * 80 + "-ashlight.filter"),
    ("NeverSink-ashlight.filter", "NeverSink-ashlight.filter"),
])
def test_out_name_is_sanitised(name, out):
    assert lootfilter.out_name(name) == out


def test_merge_code_writes_and_logs_nothing():
    src = (ROOT / "server" / "al" / "theorycraft" / "lootfilter.py").read_text(encoding="ascii")
    for bad in ("open(", "write_text", "write_bytes", ".write(", "os.replace", "shutil",
                "import os", "pathlib", "logging", "print("):
        assert bad not in src, bad
    http_src = (ROOT / "server" / "al" / "http.py").read_text(encoding="ascii")
    block = http_src.split("def _filter_merge(", 1)[1].split("\n    def ", 1)[0]
    for bad in ("open(", ".write_", "log.", "tempfile"):
        assert bad not in block, bad


@pytest.mark.server
def test_merge_endpoint(tmp_path):
    from server.al.core import Core
    from server.al.http import serve
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    token = "m" * 48
    server = serve(core, token, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    try:
        def post(body, name="My Filter.filter", tok=token, ctype="application/octet-stream"):
            conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
            h = {"Host": f"127.0.0.1:{server.port}", "Content-Type": ctype}
            if tok:
                h["X-AL-Token"] = tok
            conn.request("POST", "/api/filter-merge?name=" + quote(name), body=body, headers=h)
            r = conn.getresponse()
            out = (r.status, r.getheader("Content-Disposition"), r.read())
            conn.close()
            return out
        assert post(BOM + OWN_CRLF, tok=None)[0] == 401
        status, disp, out = post(BOM + OWN_CRLF)
        assert status == 200
        assert disp == 'attachment; filename="My Filter-ashlight.filter"'
        assert out.startswith(BOM) and split(out[3:])[1] == OWN_CRLF
        assert post(OWN_LF, ctype="application/json")[0] == 415
        status, _, out = post(b"\x00\x01binary")
        assert status == 400 and b"\x00" not in out and b"binary" not in out
        # too big: refused on the length alone (headers only, no 2 MB upload)
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        conn.putrequest("POST", "/api/filter-merge?name=a.filter")
        for k, v in (("Host", f"127.0.0.1:{server.port}"), ("X-AL-Token", token),
                     ("Content-Type", "application/octet-stream"),
                     ("Content-Length", str(lootfilter.MAX_MERGE_BYTES + 1))):
            conn.putheader(k, v)
        conn.endheaders()
        assert conn.getresponse().status == 413
        conn.close()
    finally:
        server.stop()
        core.close()
    after = sorted(str(p) for p in tmp_path.rglob("*"))
    assert not any(p.endswith(".filter") for p in after)
    assert not any("My Filter" in p for p in after)


def test_dashboard_merge_is_a_picked_file_with_no_live_region():
    html = (ROOT / "web" / "index.html").read_text(encoding="ascii")
    app = (ROOT / "web" / "app.js").read_text(encoding="ascii")
    js = (ROOT / "web" / "filtermerge.js").read_text(encoding="ascii")
    assert '<input id="filter-merge-file" type="file"' in html
    assert '<script src="/web/filtermerge.js" defer></script>' in html
    i = html.index('id="filter-merge-file"')
    near = html[i - 400:i + 300]
    assert "aria-live" not in near and 'role="status"' not in near
    assert 'addEventListener("change", mergeFilter)' in app
    assert "aria-live" not in js and "setInterval" not in js and "setTimeout" not in js
    assert "/api/filter-merge" in js and "X-AL-Token" in js
