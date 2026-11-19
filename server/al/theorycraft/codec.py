"""Path of Building PoE2 share-code codec (ROADMAP TC-CODE, decision 0004).

A share code is the build XML, deflated, then base64 with the URL-safe
alphabet ("+" -> "-", "/" -> "_"); research 0010 section 1 (PoB2 ImportTab,
MIT, read for the format only). Encoding writes zlib framing (shared codes
start "eN", the base64 of a 0x78 zlib header); decoding auto-detects zlib,
raw deflate and gzip so a framing difference never loses a build.

Round trip is byte-exact on the XML: decode(encode(xml)) == xml. Text that
is not valid UTF-8 rides through as surrogate escapes, so even that holds.

Safety: input length and decompressed size are capped (a deflate bomb stops
at MAX_XML_BYTES), and a share URL is recognized but never fetched here (no
network; follow-up ROADMAP row TC-URL).
"""

import base64
import binascii
import re
import zlib

MAX_CODE_CHARS = 2 * 1024 * 1024  # a pasted code; real ones are ~5-60 KB
MAX_XML_BYTES = 8 * 1024 * 1024
MIN_CODE_CHARS = 16
ENCODING = "utf-8"
ERRORS = "surrogateescape"
LEVEL = 9

_URL_RE = re.compile(r"^(https?://|www\.)\S+$", re.I)
_CODE_RE = re.compile(r"^[A-Za-z0-9+/_=-]+$")
_WS_RE = re.compile(r"\s+")


class CodeError(ValueError):
    """The text is not a decodable build code."""


class ShareUrlError(CodeError):
    """A share-site URL: recognized, but fetching it is not supported yet."""


class _FramingError(CodeError):
    """The bytes did not inflate under the guessed framing."""


def _compact(text):
    if not isinstance(text, str):
        raise CodeError("build code must be text")
    return _WS_RE.sub("", text)


def classify(text):
    """'code', 'url' or 'unknown' for pasted text (no decoding, cheap)."""
    if not isinstance(text, str):
        return "unknown"
    stripped = text.strip()
    if _URL_RE.match(stripped):
        return "url"
    compact = _compact(stripped)
    if len(compact) >= MIN_CODE_CHARS and _CODE_RE.match(compact):
        return "code"
    return "unknown"


def looks_like_build_code(text):
    """Cheap pre-check for the clipboard hotkey row: does this text look like
    a PoB build code (shape only, plus a zlib / deflate first byte)?"""
    if classify(text) != "code":
        return False
    try:
        head = _b64decode(_compact(text)[:8])
    except CodeError:
        return False
    return bool(head) and detect_framing(head + b"\x00\x00") is not None


def _b64decode(compact):
    std = compact.replace("-", "+").replace("_", "/").rstrip("=")
    std += "=" * (-len(std) % 4)
    try:
        return base64.b64decode(std, validate=True)
    except (binascii.Error, ValueError) as e:
        raise CodeError("not base64") from e


def detect_framing(raw):
    """'zlib', 'gzip' or 'raw' (deflate) from the first bytes, or None."""
    if len(raw) < 2:
        return None
    if raw[0] == 0x1F and raw[1] == 0x8B:
        return "gzip"
    if (raw[0] & 0x0F) == 8 and (raw[0] >> 4) <= 7 and ((raw[0] << 8) | raw[1]) % 31 == 0:
        return "zlib"
    if (raw[0] >> 1) & 0x03 in (0, 1, 2):  # BTYPE of a deflate block; 3 is reserved
        return "raw"
    return None


_WBITS = {"zlib": 15, "gzip": 31, "raw": -15}


def _inflate(raw, framing):
    d = zlib.decompressobj(_WBITS[framing])
    try:
        out = d.decompress(raw, MAX_XML_BYTES + 1)
        if len(out) > MAX_XML_BYTES or d.unconsumed_tail:
            raise CodeError("build XML too large")
        out += d.flush()
    except zlib.error as e:
        raise _FramingError(f"not {framing} data") from e
    if len(out) > MAX_XML_BYTES:
        raise CodeError("build XML too large")
    if not d.eof:
        raise _FramingError("truncated build code")
    return out


def decode_bytes(text):
    """The build XML bytes of a share code. Raises CodeError / ShareUrlError."""
    kind = classify(text)
    if kind == "url":
        raise ShareUrlError("share URL fetch is not supported yet; paste the code itself")
    compact = _compact(text)
    if not compact:
        raise CodeError("empty build code")
    if len(compact) > MAX_CODE_CHARS:
        raise CodeError("build code too long")
    if kind != "code":
        raise CodeError("not a build code")
    raw = _b64decode(compact)
    framing = detect_framing(raw)
    if framing is None:
        raise CodeError("unknown compression framing")
    try:
        data = _inflate(raw, framing)
    except _FramingError:
        if framing == "zlib":  # a raw stream can look like a zlib header by chance
            data = _inflate(raw, "raw")
        else:
            raise
    if b"\x00" in data:
        # UTF-16 / UTF-32 markup always holds NUL bytes; the XML parser would
        # sniff those encodings and skip the text search for DTD / ENTITY.
        raise CodeError("payload is not XML (NUL byte)")
    if not data.lstrip().startswith(b"<"):
        raise CodeError("payload is not XML")
    return data


def decode(text):
    """The build XML (str) of a share code."""
    return decode_bytes(text).decode(ENCODING, ERRORS)


def encode_bytes(xml_bytes):
    return base64.urlsafe_b64encode(zlib.compress(xml_bytes, LEVEL)).decode("ascii")


def encode(xml):
    """A share code for build XML (str), zlib framing, URL-safe base64."""
    if not isinstance(xml, str):
        raise TypeError("xml must be str")
    return encode_bytes(xml.encode(ENCODING, ERRORS))
