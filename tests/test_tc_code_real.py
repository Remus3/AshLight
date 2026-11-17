"""TC-CODE-REAL: the codec on a real Path of Building PoE2 export (decision 0021).

The real-code checks run once per code found in:
- tests/fixtures/pob2_real/*.txt (tracked ONLY with the build owner's
  permission, recorded in that folder's README),
- ops/runtime/tc_real/*.txt (gitignored local drop folder, never committed),
- the file named by the env var AL_TC_REAL_CODE.
With none present they skip, so the suite runs unattended either way.

The harness tests below run on synthetic codes, so the checks themselves are
proven even while no real code exists.
"""

import base64
import os
import re
import zlib
from pathlib import Path

import pytest

from server.al.theorycraft import codec, model
from tc_fixtures import FULL_XML

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "pob2_real"
LOCAL_DIR = ROOT / "ops" / "runtime" / "tc_real"
ENV = "AL_TC_REAL_CODE"
TC_JS = ROOT / "web" / "tc.js"

# Stats PoB computes for every character, whatever the build.
REQUIRED_STATS = ("Life", "Mana", "FireResist", "ColdResist", "LightningResist",
                  "ChaosResist")
# zlib header FLG byte -> the compression levels that write it (RFC 1950 FLEVEL).
_FLEVEL_LEVELS = {0x01: (0, 1), 0x5E: (2, 3, 4, 5), 0x9C: (6,), 0xDA: (7, 8, 9)}


def real_code_paths(env=None):
    """Every real-code file present, sorted and de-duplicated."""
    env = os.environ if env is None else env
    found = []
    for folder in (FIXTURE_DIR, LOCAL_DIR):
        if folder.is_dir():
            found.extend(sorted(folder.glob("*.txt")))
    named = env.get(ENV)
    if named and Path(named).is_file():
        found.append(Path(named))
    out, seen = [], set()
    for p in found:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def key_stat_names():
    """PlayerStat names the dashboard build view shows (web/tc.js KEY_STATS)."""
    text = TC_JS.read_text(encoding="utf-8")
    block = text.split("KEY_STATS = [", 1)[1].split("];", 1)[0]
    return re.findall(r'\["(\w+)",', block)


def reencode_matches(code):
    """The zlib level whose re-encoding of the decoded XML reproduces the code
    byte for byte (alphabet and padding normalised), else None."""
    compact = re.sub(r"\s+", "", code).replace("+", "-").replace("/", "_").rstrip("=")
    raw = codec._b64decode(compact)
    if codec.detect_framing(raw) != "zlib":
        return None
    xml = zlib.decompress(raw)
    for level in _FLEVEL_LEVELS.get(raw[1], range(10)):
        again = base64.urlsafe_b64encode(zlib.compress(xml, level)).decode("ascii")
        if again.rstrip("=") == compact:
            return level
    return None


def check_real_code(code):
    """Every TC-CODE-REAL acceptance check on one code; returns the parsed
    Build and the matching zlib level (None when only the XML round-trips)."""
    compact = re.sub(r"\s+", "", code)
    assert codec.classify(code) == "code"
    assert codec.looks_like_build_code(code)
    # framing: research 0010 left it UNVERIFIED; decision 0007 assumes zlib.
    raw = codec._b64decode(compact)
    assert codec.detect_framing(raw) == "zlib", "real code is not zlib-framed"
    # The "eN" (level 7-9) vs "eJ" (level 6) prefix is reported through the
    # matching level, not asserted.
    xml_bytes = codec.decode_bytes(code)
    xml = codec.decode(code)
    # root element and parse
    build = model.parse(xml)
    root = model._root(xml)
    assert root.tag == "PathOfBuilding2", f"root is {root.tag!r}"
    assert build.class_name
    assert build.level is not None and 1 <= build.level <= 100
    assert build.specs and build.active_spec is not None
    # PlayerStat names
    missing = [s for s in REQUIRED_STATS if s not in build.stats]
    assert not missing, f"PlayerStat names missing: {missing}"
    shown = [s for s in key_stat_names() if s in build.stats]
    assert len(shown) >= len(REQUIRED_STATS), f"only {shown} of tc.js KEY_STATS present"
    # byte-exact XML round trip: through our encoder and through the model
    assert codec.decode_bytes(codec.encode(xml)) == xml_bytes
    assert codec.decode_bytes(build.to_code()) == xml_bytes
    assert codec.encode(codec.decode(codec.encode(xml))) == codec.encode(xml)
    return build, reencode_matches(code)


# -- the real code(s)

_REAL = real_code_paths()


@pytest.mark.skipif(not _REAL, reason="no real PoB2 export present (decision 0021)")
@pytest.mark.parametrize("path", _REAL, ids=[p.name for p in _REAL])
def test_real_pob2_code(path):
    code = path.read_text(encoding="ascii")
    _build, level = check_real_code(code)
    if level is None:
        # The XML round trip is exact (asserted above); only PoB's compressor
        # output differs from Python's zlib, which no decoder can control.
        pytest.xfail("XML byte-exact; code bytes differ from Python zlib (decision 0021)")


# -- the harness itself, on synthetic codes

REAL_SHAPED_XML = FULL_XML.replace(
    '<PlayerStat stat="FireResist" value="75"/>',
    '<PlayerStat stat="FireResist" value="75"/>'
    '<PlayerStat stat="Mana" value="512"/>'
    '<PlayerStat stat="ColdResist" value="75"/>'
    '<PlayerStat stat="LightningResist" value="75"/>'
    '<PlayerStat stat="ChaosResist" value="-12"/>')


def test_harness_shape_fixture_is_distinct():
    assert REAL_SHAPED_XML != FULL_XML


@pytest.mark.parametrize("level", [1, 6, 9])
def test_harness_accepts_a_pob_shaped_code(level):
    code = base64.urlsafe_b64encode(
        zlib.compress(REAL_SHAPED_XML.encode("utf-8"), level)).decode("ascii")
    build, got = check_real_code(code)
    assert build.stats["Mana"] == 512
    assert got in _FLEVEL_LEVELS[base64.urlsafe_b64decode(code)[1]]
    # an equivalent code at a level in the same FLEVEL bucket reproduces it
    assert zlib.compress(REAL_SHAPED_XML.encode("utf-8"), got) == base64.urlsafe_b64decode(code)


def test_harness_accepts_std_alphabet_and_wrapped_lines():
    raw = zlib.compress(REAL_SHAPED_XML.encode("utf-8"))
    std = base64.b64encode(raw).decode("ascii")
    wrapped = "\n".join(std[i:i + 76] for i in range(0, len(std), 76)) + "\n"
    _build, level = check_real_code(wrapped)
    assert level == 6


def test_harness_rejects_raw_deflate_framing():
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = c.compress(REAL_SHAPED_XML.encode("utf-8")) + c.flush()
    with pytest.raises(AssertionError, match="not zlib-framed"):
        check_real_code(base64.urlsafe_b64encode(raw).decode("ascii"))


def test_harness_rejects_pob1_root():
    xml = REAL_SHAPED_XML.replace("PathOfBuilding2", "PathOfBuilding")
    assert "PathOfBuilding2" not in xml
    with pytest.raises(AssertionError, match="root is 'PathOfBuilding'"):
        check_real_code(codec.encode(xml))


def test_harness_reports_missing_stat_names():
    xml = REAL_SHAPED_XML.replace('stat="Mana"', 'stat="ManaMax"')
    with pytest.raises(AssertionError, match="Mana"):
        check_real_code(codec.encode(xml))


def test_reencode_none_when_compressor_differs():
    # same XML, same zlib header, different deflate stream (Huffman-only, as
    # another compressor might write): only the XML round-trips.
    data = REAL_SHAPED_XML.encode("utf-8")
    c = zlib.compressobj(9, zlib.DEFLATED, 15, 9, zlib.Z_HUFFMAN_ONLY)
    raw = c.compress(data) + c.flush()
    assert zlib.decompress(raw) == data
    assert reencode_matches(base64.urlsafe_b64encode(raw).decode("ascii")) is None
    _build, level = check_real_code(base64.urlsafe_b64encode(raw).decode("ascii"))
    assert level is None


def test_key_stat_names_read_from_dashboard():
    names = key_stat_names()
    assert "Life" in names and "TotalDPS" in names
    assert set(REQUIRED_STATS) <= set(names)


def test_discovery_finds_env_file_and_dedupes(tmp_path):
    f = tmp_path / "real.txt"
    f.write_text("x", encoding="ascii")
    got = real_code_paths({ENV: str(f)})
    assert got.count(f) == 1
    assert real_code_paths({ENV: str(tmp_path / "absent.txt")}) == real_code_paths({})
