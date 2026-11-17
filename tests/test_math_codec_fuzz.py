"""MATH-CODEC-FUZZ: property / fuzz tests for the PoB2 share-code codec.

Stdlib only, fixed seeds (deterministic). The contract under test
(server/al/theorycraft/codec.py): decode(encode(xml)) == xml byte-exact;
zlib, raw deflate and gzip framings all decode; URL-safe or standard
alphabet, padded or not, whitespace-wrapped all decode; anything else
raises CodeError (or its ShareUrlError subclass) and never another
exception; the deflate-bomb cap holds.
"""

import base64
import gzip
import random
import zlib

import pytest

from server.al.theorycraft import codec

SEED = 20261117


def _rand_xml(rng):
    tags = ["PathOfBuilding2", "Build", "Items", "Item", "Skill", "Tree", "Spec", "PlayerStat"]
    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<PathOfBuilding2>']
    for _ in range(rng.randint(0, 30)):
        tag = rng.choice(tags)
        attr = "".join(rng.choice("abcXYZ019 _-.") for _ in range(rng.randint(0, 12)))
        body = "".join(chr(rng.choice([rng.randint(32, 126), rng.randint(160, 0x2FFF)]))
                       for _ in range(rng.randint(0, 40)))
        body = body.replace("<", "&lt;").replace("&", "&amp;")
        parts.append(f'<{tag} v="{attr}">{body}</{tag}>')
    parts.append("</PathOfBuilding2>")
    return "\n".join(parts)


def _frame(data, framing, level=6):
    if framing == "zlib":
        return zlib.compress(data, level)
    if framing == "gzip":
        return gzip.compress(data, compresslevel=level, mtime=0)
    c = zlib.compressobj(level, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def _b64(raw, urlsafe=True, pad=True):
    s = (base64.urlsafe_b64encode(raw) if urlsafe else base64.b64encode(raw)).decode("ascii")
    return s if pad else s.rstrip("=")


def test_round_trip_is_byte_exact_on_random_xml():
    rng = random.Random(SEED)
    for _ in range(300):
        xml = _rand_xml(rng)
        code = codec.encode(xml)
        assert codec.decode(code) == xml
        assert codec.classify(code) == "code"
        assert set(code) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=")


def test_round_trip_keeps_invalid_utf8_through_surrogate_escapes():
    rng = random.Random(SEED + 1)
    for _ in range(100):
        junk = bytes(rng.randint(0x80, 0xFF) for _ in range(rng.randint(1, 20)))
        data = b"<Build>" + junk + b"</Build>"
        xml = data.decode("utf-8", "surrogateescape")
        assert codec.decode_bytes(codec.encode(xml)) == data


@pytest.mark.parametrize("framing", ["zlib", "gzip", "raw"])
def test_every_framing_alphabet_and_padding_decodes(framing):
    rng = random.Random(SEED + 2)
    for _ in range(60):
        data = _rand_xml(rng).encode("utf-8")
        raw = _frame(data, framing, rng.randint(1, 9))
        code = _b64(raw, urlsafe=rng.random() < 0.5, pad=rng.random() < 0.5)
        assert codec.decode_bytes(code) == data


def test_whitespace_wrapped_codes_decode():
    rng = random.Random(SEED + 3)
    for _ in range(60):
        data = _rand_xml(rng).encode("utf-8")
        code = codec.encode_bytes(data)
        wrapped = ""
        i = 0
        while i < len(code):
            n = rng.randint(1, 80)
            wrapped += code[i:i + n] + rng.choice(["\n", "\r\n", " ", "\t", ""])
            i += n
        assert codec.decode_bytes("  " + wrapped + "\n") == data


def _decode_or_codeerror(text):
    try:
        out = codec.decode_bytes(text)
    except codec.CodeError:
        return None
    assert isinstance(out, bytes) and out.lstrip().startswith(b"<")
    return out


def test_truncated_codes_raise_codeerror_only():
    rng = random.Random(SEED + 4)
    for _ in range(80):
        data = _rand_xml(rng).encode("utf-8")
        code = codec.encode_bytes(data)
        for cut in sorted({rng.randint(0, len(code) - 1) for _ in range(6)}):
            out = _decode_or_codeerror(code[:cut])
            assert out is None or data.startswith(out) or out == data


def test_bit_flips_and_char_swaps_raise_codeerror_only():
    rng = random.Random(SEED + 5)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_+/=!*. "
    for _ in range(150):
        data = _rand_xml(rng).encode("utf-8")
        framing = rng.choice(["zlib", "gzip", "raw"])
        raw = bytearray(_frame(data, framing))
        for _ in range(rng.randint(1, 4)):
            i = rng.randrange(len(raw))
            raw[i] ^= 1 << rng.randrange(8)
        _decode_or_codeerror(_b64(bytes(raw)))
        code = list(codec.encode_bytes(data))
        for _ in range(rng.randint(1, 4)):
            code[rng.randrange(len(code))] = rng.choice(alphabet)
        _decode_or_codeerror("".join(code))


def test_random_text_never_raises_anything_but_codeerror():
    rng = random.Random(SEED + 6)
    pool = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_+/= \n"
            "https://www.:.?" + chr(0xE9) + chr(0x2014))
    for _ in range(1500):
        text = "".join(rng.choice(pool) for _ in range(rng.randint(0, 120)))
        if rng.random() < 0.3:
            text = "eN" + text  # a zlib-looking head
        _decode_or_codeerror(text)
        codec.classify(text)
        codec.looks_like_build_code(text)


@pytest.mark.parametrize("value", [None, 5, b"eNo=", ["eN"], 3.5])
def test_non_text_input_raises_codeerror(value):
    with pytest.raises(codec.CodeError):
        codec.decode_bytes(value)
    assert codec.classify(value) == "unknown"
    assert codec.looks_like_build_code(value) is False


def test_share_url_is_recognised_never_fetched():
    with pytest.raises(codec.ShareUrlError):
        codec.decode_bytes("https://pobb.in/abcdefgh")


def test_non_xml_payload_is_refused():
    with pytest.raises(codec.CodeError):
        codec.decode_bytes(codec.encode_bytes(b"not xml at all, plain text payload"))


def test_deflate_bomb_stops_at_the_cap(monkeypatch):
    monkeypatch.setattr(codec, "MAX_XML_BYTES", 64 * 1024)
    bomb = b"<" + b"A" * (codec.MAX_XML_BYTES * 4)
    for framing in ("zlib", "gzip", "raw"):
        with pytest.raises(codec.CodeError, match="too large"):
            codec.decode_bytes(_b64(_frame(bomb, framing, 9)))
    exact = b"<" + b"A" * (codec.MAX_XML_BYTES - 1)
    assert codec.decode_bytes(_b64(_frame(exact, "zlib", 9))) == exact


def test_overlong_code_is_refused_before_decoding(monkeypatch):
    monkeypatch.setattr(codec, "MAX_CODE_CHARS", 100)
    with pytest.raises(codec.CodeError, match="too long"):
        codec.decode_bytes("A" * 101)


def test_encode_is_deterministic_and_zlib_framed():
    rng = random.Random(SEED + 7)
    for _ in range(30):
        xml = _rand_xml(rng)
        a, b = codec.encode(xml), codec.encode(xml)
        assert a == b and a.startswith("eN")
        assert codec.detect_framing(base64.urlsafe_b64decode(a)) == "zlib"
