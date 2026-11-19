"""TC-CODE: PoB2 build-code codec, build model, store (decision 0004).

Synthetic fixtures only (tests/tc_fixtures.py); no network, no real build.
"""

import base64
import gzip
import zlib

import pytest

from server.al.theorycraft import codec, model, store
from tc_fixtures import FLAT_XML, FULL_XML, MINIMAL_XML


def _b64(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii")


# -- codec

@pytest.mark.parametrize("xml", [MINIMAL_XML, FULL_XML, FLAT_XML])
def test_round_trip_is_byte_exact(xml):
    code = codec.encode(xml)
    assert codec.decode(code) == xml
    # and a second pass is stable
    assert codec.encode(codec.decode(code)) == code


def test_encode_is_urlsafe_zlib():
    code = codec.encode(FULL_XML)
    assert set(code) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=")
    raw = base64.urlsafe_b64decode(code)
    assert raw[0] == 0x78  # zlib header, as seen at the start of shared codes ("eN")
    assert code.startswith("eN")
    assert zlib.decompress(raw).decode("utf-8") == FULL_XML


@pytest.mark.parametrize("frame", ["zlib", "raw", "gzip"])
def test_decode_detects_framing(frame):
    data = FULL_XML.encode("utf-8")
    if frame == "zlib":
        raw = zlib.compress(data, 9)
    elif frame == "raw":
        c = zlib.compressobj(9, zlib.DEFLATED, -15)
        raw = c.compress(data) + c.flush()
    else:
        raw = gzip.compress(data)
    assert codec.decode(_b64(raw)) == FULL_XML
    assert codec.detect_framing(raw) == frame


def test_decode_tolerates_whitespace_padding_and_std_alphabet():
    raw = zlib.compress(FULL_XML.encode("utf-8"), 9)
    std = base64.b64encode(raw).decode("ascii")
    assert codec.decode(std) == FULL_XML
    url = _b64(raw).rstrip("=")
    wrapped = "  " + "\n".join(url[i:i + 60] for i in range(0, len(url), 60)) + "\r\n"
    assert codec.decode(wrapped) == FULL_XML


def test_non_utf8_payload_survives_round_trip():
    raw_xml = b"<PathOfBuilding2><Notes>\xff\xfe</Notes></PathOfBuilding2>"
    code = _b64(zlib.compress(raw_xml))
    text = codec.decode(code)
    assert zlib.decompress(base64.urlsafe_b64decode(codec.encode(text))) == raw_xml


@pytest.mark.parametrize("bad", ["", "   ", "not base64 !!!", _b64(b"plain bytes, not deflate"),
                                 "a" * 5])
def test_decode_rejects_garbage(bad):
    with pytest.raises(codec.CodeError):
        codec.decode(bad)


@pytest.mark.parametrize("enc", ["utf-16-le", "utf-16-be", "utf-16", "utf-32-le", "utf-32"])
def test_decode_refuses_a_payload_with_a_nul_byte(enc):
    xml = '<!DOCTYPE x [<!ENTITY a "aaaa">]><PathOfBuilding2/>'
    with pytest.raises(codec.CodeError, match="NUL"):
        codec.decode(_b64(zlib.compress(xml.encode(enc))))


def test_decode_caps_decompressed_size():
    bomb = zlib.compress(b"<" + b"A" * (codec.MAX_XML_BYTES + 10), 9)
    with pytest.raises(codec.CodeError, match="too large"):
        codec.decode(_b64(bomb))


def test_decode_caps_code_length():
    with pytest.raises(codec.CodeError, match="too long"):
        codec.decode("A" * (codec.MAX_CODE_CHARS + 4))


def test_share_url_is_recognized_not_fetched():
    for text in ("https://pobb.in/AbCdEf123", "https://pastebin.com/abcd1234",
                 "http://example.org/some/build"):
        with pytest.raises(codec.ShareUrlError, match="not supported yet"):
            codec.decode(text)
        assert codec.classify(text) == "url"


def test_classify_and_looks_like_build_code():
    code = codec.encode(MINIMAL_XML)
    assert codec.classify(code) == "code"
    assert codec.looks_like_build_code(code)
    assert codec.looks_like_build_code("\n" + code + "\n")
    for text in ("", "Rarity: RARE\nDoom Grip", "hello world", "eN", "https://pobb.in/x"):
        assert not codec.looks_like_build_code(text), text
    assert codec.classify("Rarity: RARE\nItem") == "unknown"


# -- model

def test_parse_full_build():
    b = model.parse(FULL_XML)
    assert b.class_name == "Monk"
    assert b.ascendancy == "Invoker"
    assert b.level == 87
    assert b.target_version == "0_3"
    assert b.raw_xml == FULL_XML
    # PoB's saved stats, numeric where numeric, text kept otherwise
    assert b.stats["Life"] == 2410
    assert b.stats["EnergyShield"] == 1830.5
    assert b.stats["TotalDPS"] == 123456.78
    assert b.stats["Spirit"] == "not-a-number"
    # tree: all specs, the active one picked by activeSpec (1-based)
    assert [s.title for s in b.specs] == ["Leveling", "Endgame"]
    tree = b.active_spec
    assert tree.title == "Endgame"
    assert tree.nodes == (10, 20, 30, 40, 50, 60)
    assert tree.tree_version == "0_3"
    assert tree.url == "https://example.org/tree/endgame"
    assert tree.jewels == {40: 3}
    # items: by id, slotted per the active item set; empty slot skipped
    assert set(b.items) == {1, 2, 3}
    gloves = b.gear["Gloves"]
    assert (gloves.rarity, gloves.name, gloves.base) == ("RARE", "Doom Grip", "Example Gloves")
    assert "+40 to maximum Life" in gloves.text
    assert b.gear["Weapon 1"].name == "Example Unique"
    assert b.gear["Weapon 1"].base == "Example Quarterstaff"
    assert "Ring 1" not in b.gear
    assert b.items[3].rarity == "MAGIC" and b.items[3].base == "Example Jewel of the Test"
    # skills
    assert len(b.skills) == 2
    main = b.skills[0]
    assert main.enabled and main.slot == "Weapon 1" and main.label == "Main"
    assert [g.name for g in main.gems] == ["Example Strike", "Example Support"]
    assert main.gems[0].level == 19 and main.gems[0].quality == 20
    assert main.gems[0].skill_id == "ExampleStrike"
    assert main.gems[1].enabled is False
    assert b.skills[1].enabled is False
    assert b.main_skill_index == 2
    assert b.notes.startswith("Synthetic notes & a second line")


def test_parse_flat_older_layout():
    b = model.parse(FLAT_XML)
    assert (b.class_name, b.ascendancy, b.level) == ("Ranger", None, 12)
    assert b.active_spec.nodes == (5,)
    assert b.skills[0].gems[0].name == "Example Arrow"
    assert b.gear["Weapon 1"].base == "Example Bow"
    assert b.gear["Weapon 1"].name is None


def test_parse_minimal_has_safe_defaults():
    b = model.parse(MINIMAL_XML)
    assert b.class_name == "Warrior" and b.ascendancy is None and b.level == 1
    assert b.specs == () and b.active_spec is None
    assert b.items == {} and b.gear == {} and b.skills == () and b.stats == {}
    assert b.notes == ""


def test_model_to_code_is_lossless():
    code = codec.encode(FULL_XML)
    b = model.from_code(code)
    assert codec.decode(b.to_code()) == FULL_XML
    assert model.from_code(b.to_code()).to_dict() == b.to_dict()


def test_to_dict_is_json_ready():
    import json
    d = model.parse(FULL_XML).to_dict()
    text = json.dumps(d)
    assert "raw_xml" not in d
    assert d["class_name"] == "Monk" and d["tree"]["node_count"] == 6
    assert d["gear"]["Gloves"]["name"] == "Doom Grip"
    assert d["skills"][0]["gems"][0]["name"] == "Example Strike"
    assert text.isascii()


@pytest.mark.parametrize("xml", [
    "<notxml",
    "<Other/>",
    '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><PathOfBuilding2/>',
    "<PathOfBuilding2><Build level='x'/></PathOfBuilding2>",
    "<PathOfBuilding2><Notes>a\x00b</Notes></PathOfBuilding2>",
])
def test_parse_rejects_bad_xml(xml):
    with pytest.raises(model.BuildError):
        model.parse(xml)


def test_bad_numbers_are_tolerated_where_optional():
    xml = ("<PathOfBuilding2><Build level='5' className='Witch'/>"
           "<Tree activeSpec='9'><Spec nodes='1,x,,3'/></Tree>"
           "<Skills><Skill><Gem nameSpec='G' level='q'/></Skill></Skills></PathOfBuilding2>")
    b = model.parse(xml)
    assert b.active_spec.nodes == (1, 3)  # falls back to the last spec
    assert b.skills[0].gems[0].level is None


# -- store

def test_store_persists_and_reloads(tmp_path):
    path = tmp_path / "build" / "last-code.txt"
    s = store.BuildStore(path)
    assert s.build is None
    code = codec.encode(FULL_XML)
    b = s.load_code(code)
    assert b.class_name == "Monk"
    assert path.read_text(encoding="ascii").strip() == code
    s2 = store.BuildStore(path)
    assert s2.build is not None and s2.build.raw_xml == FULL_XML


def test_store_bad_code_keeps_previous(tmp_path):
    path = tmp_path / "last-code.txt"
    s = store.BuildStore(path)
    s.load_code(codec.encode(MINIMAL_XML))
    with pytest.raises(codec.CodeError):
        s.load_code("garbage !!")
    assert s.build.class_name == "Warrior"
    assert store.BuildStore(path).build.class_name == "Warrior"


def test_store_ignores_corrupt_file_on_start(tmp_path):
    path = tmp_path / "last-code.txt"
    path.write_text("corrupt\n", encoding="ascii")
    s = store.BuildStore(path)
    assert s.build is None and s.load_error


def test_store_listener_fires(tmp_path):
    s = store.BuildStore(tmp_path / "c.txt")
    seen = []
    s.add_listener(seen.append)
    s.load_code(codec.encode(MINIMAL_XML))
    assert len(seen) == 1 and seen[0].class_name == "Warrior"
