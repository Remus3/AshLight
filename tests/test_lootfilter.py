"""UTIL-FILTER (decision 0031): the ashlight.filter snippet."""

import http.client
import re
import threading
from pathlib import Path

import pytest

from server.al.theorycraft import lootfilter
from server.al.theorycraft.model import Build, Item

ROOT = Path(__file__).resolve().parents[1]

BUILD = Build(raw_xml="", class_name="Ranger", ascendancy="Deadeye", gear={
    "Weapon 1": Item(1, "", "RARE", "Grim Bite", "Expert Hunting Bow"),
    "Helmet": Item(2, "", "UNIQUE", "Example Hood", 'Odd "Hood"|x'),
    "Belt": Item(3, "", "MAGIC", None, "Stout Belt of the Bear"),
    "Flask 1": Item(4, "", "NORMAL", None, "Ultimate Life Flask"),
    "Gloves": Item(5, "", "RARE", "Again", "Expert Hunting Bow")})

# The documented grammar subset AshLight writes (pathofexile.com/item-filter/about)
CONDITION = re.compile(r'^(Rarity (Normal|Magic|Rare|Unique)( (Normal|Magic|Rare|Unique))*'
                       r'|BaseType == ("[A-Za-z0-9 \',-]+" ?)+)$')
ACTION = re.compile(r"^(SetFontSize ([1-9]|[1-3]\d|4[0-5])"
                    r"|Set(Border|Text|Background)Color \d{1,3} \d{1,3} \d{1,3}( \d{1,3})?"
                    r"|PlayEffect (Red|Green|Blue|Brown|White|Yellow|Cyan|Grey|Orange|Pink|Purple)"
                    r"|MinimapIcon [0-2] (Red|Green|Blue|Brown|White|Yellow|Cyan|Grey|Orange|Pink"
                    r"|Purple) (Circle|Diamond|Hexagon|Square|Star|Triangle|Cross|Moon|Raindrop"
                    r"|Kite|Pentagon|UpsideDownHouse))$")


def check_grammar(text):
    assert text.isascii() and "\r" not in text and text.endswith("\n")
    in_block = False
    for line in text.split("\n"):
        if not line or line.startswith("#"):
            in_block = in_block and bool(line)
            continue
        if line in ("Show", "Hide", "Minimal"):
            in_block = True
            continue
        assert in_block and line.startswith("    "), line
        body = line.strip()
        assert CONDITION.match(body) or ACTION.match(body), body
        if body.startswith("SetBorderColor"):
            assert all(0 <= int(x) <= 255 for x in body.split()[1:])


def test_bases_skip_magic_flasks_and_repeats_and_clean_quotes():
    assert lootfilter.bases(BUILD) == ["Expert Hunting Bow", "Odd Hood x"]


def test_generated_filter_follows_the_grammar():
    text = lootfilter.generate(BUILD)
    check_grammar(text)
    assert 'BaseType == "Expert Hunting Bow" "Odd Hood x"' in text
    assert lootfilter.IMPORT_LINE == 'Import "ashlight.filter" Optional'
    assert lootfilter.IMPORT_LINE in text and lootfilter.NOTICE in text
    assert text.count("\nShow\n") == 1


def test_no_build_is_comments_only():
    for b in (None, Build(raw_xml="")):
        text = lootfilter.generate(b)
        check_grammar(text)
        assert all(not ln or ln.startswith("#") for ln in text.split("\n"))


@pytest.mark.server
def test_filter_endpoint_is_a_token_guarded_download(tmp_path):
    from server.al.core import Core
    from server.al.http import serve
    from server.al.theorycraft import codec
    from tc_eval_fixtures import EVAL_BUILD_XML
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, "f" * 48, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    before = sorted(p.name for p in tmp_path.rglob("*"))
    try:
        def get(token):
            conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
            h = {"Host": f"127.0.0.1:{server.port}"}
            if token:
                h["X-AL-Token"] = token
            conn.request("GET", "/api/filter", headers=h)
            r = conn.getresponse()
            out = (r.status, r.getheader("Content-Disposition"), r.read().decode("ascii"))
            conn.close()
            return out
        assert get(None)[0] in (401, 403)
        core.builds.load_code(codec.encode(EVAL_BUILD_XML))
        status, disp, text = get("f" * 48)
        assert status == 200 and disp == 'attachment; filename="ashlight.filter"'
        check_grammar(text)
    finally:
        server.stop()
        core.close()
    after = sorted(p.name for p in tmp_path.rglob("*"))
    assert not any(n.endswith(".filter") for n in after) and len(after) >= len(before)


def test_no_code_path_writes_the_filter_to_disk():
    """Adjudicator ruling (research 0022 section 3): never written into the
    game's documents folder. The generator writes no file at all, and the
    endpoint only answers with the text; no source names that folder
    (tests/test_audit_buildfile.py guards the name everywhere)."""
    src = (ROOT / "server" / "al" / "theorycraft" / "lootfilter.py").read_text(encoding="ascii")
    for bad in ("open(", "write_text", "write_bytes", ".write(", "os.replace", "shutil",
                "import os", "pathlib"):
        assert bad not in src, bad
    http = (ROOT / "server" / "al" / "http.py").read_text(encoding="ascii")
    block = http.split('if path == "/api/filter":', 1)[1].split("if path ==", 1)[0]
    assert "_send(" in block and ".write" not in block and "open(" not in block
