"""TEST-FUZZ: seeded property / fuzz tests for the untrusted-text parsers and
the snapshot builders.

Stdlib only (random with a fixed seed, so a failure reproduces). Each target
runs for a bounded time (AL_FUZZ_S seconds, default 0.6; AL_FUZZ_SEED picks
another seed for a longer local hunt). A failure message names the seed and
the input. Properties checked:

- the Client.txt line parser, the item-text parser, the trade link builder
  and the snapshot builders never raise on any input (random bytes in mixed
  encodings, truncations, mutations, extreme numbers, wrong-typed fields);
- the share-code codec and the build / character JSON / poe.ninja parsers
  raise only their documented ValueError family;
- the codec round trip is exact for any text, lone surrogates included;
- every output is JSON-serializable and every call returns quickly (a
  regex with catastrophic backtracking fails the per-call time bound).

Regression tests for each defect the fuzzing found are at the bottom.
"""

import gzip
import json
import math
import os
import random
import time
from pathlib import Path

import fleet_test_guard  # tests/conftest.py puts ops/fleet_kit on sys.path
import pytest

from server.al import ninja, parser, price, state, webfetch
from server.al.theorycraft import charjson, codec, item, model

ROOT = Path(__file__).resolve().parents[1]
FUZZ_S = float(os.environ.get("AL_FUZZ_S", "0.6"))
SEED = int(os.environ.get("AL_FUZZ_SEED", "20261117"))
CALL_S = 1.0  # per-call bound; real inputs parse in well under 10 ms
# TEST-MARKS: a test that runs _run (per-call bound) or _timed carries it.
TIMING = pytest.mark.timing

LOG_SEEDS = [ln for ln in (ROOT / "tests" / "fixtures" / "client_sample.txt")
             .read_text(encoding="utf-8").splitlines() if ln.strip()]
LOG_SEEDS += [
    "2026/11/16 21:00:01 1000 1f2e3d4c [INFO Client 5150] @From <GUILD> Tradewind: Hi, "
    "I would like to buy your Grim Bane Ruby Ring listed for 5 exalted in Standard "
    "(stash tab \"Sale\"; position: left 3, top 7) thanks",
    "2026/11/16 21:00:02 1000 1f2e3d4c [INFO Client 5150] @From X: Hi, I'd like to buy "
    "your 10 Chaos Orb for my 1 Divine Orb in Standard.",
    "2026/11/16 21:00:03 1000 1f2e3d4c [INFO Client 5150] : Cinderwisp (Sorceress) is "
    "now level 12",
    "2026/11/16 21:00:04 1000 1f2e3d4c [DEBUG Client 5150] Generating level 3 area "
    "\"G1_3\" with seed 99",
    "2026/11/16 21:00:05 1000 1f2e3d4c [INFO Client 5150] [SCENE] Set Source [Act 1]",
]
ITEM_SEED = """Item Class: Rings
Rarity: Rare
Grim Bane
Ruby Ring
--------
Requirements:
Level: 32
--------
Sockets: S S
--------
Item Level: 40
--------
{ Prefix Modifier "Healthy" (Tier: 3) - Life }
+52(40-60) to maximum Life
--------
+12% to Fire Resistance (implicit)
--------
Adds 3 to 7 Fire Damage to Attacks
+20% to Cold Resistance (10-20)
--------
Corrupted
"""
POB_XML = ('<PathOfBuilding2><Build level="90" className="Sorceress" '
           'mainSocketGroup="1"/><Tree activeSpec="1"><Spec nodes="1,2,3"/></Tree>'
           '<Items><Item id="1">Rarity: RARE\nX\nRuby Ring\n+5 to Strength</Item>'
           '</Items><Notes>hi</Notes></PathOfBuilding2>')
CHAR_JSON = ('{"character":{"name":"A","class":"Sorceress","level":5,"equipment":'
             '[{"name":"X","typeLine":"Ruby Ring","frameType":2,"explicitMods":'
             '["+5 to Strength"],"inventoryId":"Ring"}],"passives":{"hashes":[1,2]}}}')
NINJA_OVERVIEW = ('{"lines":[{"id":"divine","primaryValue":12.5,"volumePrimaryValue":3}],'
                  '"items":[{"id":"divine","name":"Divine Orb"}],"core":{"primary":"exalted",'
                  '"items":[]}}')
NINJA_LEAGUES = '[{"id":"Standard","name":"Standard"}]'

ALPHABET = ("abcXYZ:;()[]{}<>@#$%&\"' 0123456789.-+_/=\\\t\r\n\x00\x7f"
            "\u00e9\u00eb\u30b5\u2014\ufeff\ud800\udfff")
TOKENS = ["9" * 400, "-1", "1e308", "-1e308", "nan", "inf", "-0", ": ", "@From ",
          "--------", "(implicit)", "{ ", " }", "(10-20)", "Rarity: ", "Item Class: ",
          " listed for ", " in ", "(stash tab \"", "\"; position: left ", ", top ",
          "[SCENE] Set Source [", "<", "> "]


def _mutate(rng, text):
    s = list(text)
    for _ in range(rng.randint(1, 8)):
        op = rng.random()
        i = rng.randint(0, len(s))
        if op < 0.25 and s:
            del s[min(i, len(s) - 1)]
        elif op < 0.5:
            s.insert(i, rng.choice(ALPHABET))
        elif op < 0.75:
            s.insert(i, rng.choice(TOKENS))
        elif op < 0.9:
            s = s[:i]  # truncation
        elif s:
            j = rng.randint(0, len(s) - 1)
            s[i:i] = s[j:j + rng.randint(1, 40)]  # duplication
    return "".join(s)


def _random_text(rng):
    raw = bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 300)))
    how = rng.random()
    if how < 0.3:
        return raw.decode("utf-8", "replace")
    if how < 0.5:
        return raw.decode("utf-8", "surrogateescape")
    if how < 0.7:
        return raw.decode("latin-1")
    if how < 0.85:
        return raw.decode("utf-16-le", "replace")
    return raw.decode("cp1252", "replace")


def _input(rng, seed_text):
    return _mutate(rng, seed_text) if rng.random() < 0.8 else _random_text(rng)


EXTREMES = [0, -1, 1, 2.5, -0.0, 1e308, -1e308, float("inf"), float("-inf"),
            float("nan"), 10 ** 40, 10 ** 400, -(10 ** 400), True, False]
KEYS = ["status", "url", "item", "league", "count", "listings", "error", "wait_s",
        "at", "updated_at", "id", "name", "base", "rarity", "amount", "currency",
        "price_amount", "price_currency", "verdict", "slot", "stats", "score_delta",
        "key", "delta", "weighted", "calc", "source", "notice", "comparisons",
        "equipped", "empty", "pct", "old", "new", "dps", "ehp", "ok", "unidentified",
        "from", "left", "top", "stash_tab", "note", "kind", "want_amount", "type",
        "character", "level", "scene", "is_hideout", "trade", "text", "to", "on",
        "reason", "suicide", "class", "seq", "recv_ts"]


def _value(rng, depth=0):
    r = rng.random()
    if r < 0.12:
        return None
    if r < 0.32:
        return rng.choice(EXTREMES)
    if r < 0.5:
        return rng.choice(["", " ", "x", "link", "done", "waiting", "off", "error",
                           "upgrade", "downgrade", "sidegrade", "pob", "no build loaded",
                           "not an item", "+# to maximum Life", "Adds # to # Fire",
                           "#% increased Speed", "\u30b5" * 3, "a" * 3000,
                           "https://www.pathofexile.com/trade2/search/poe2/Standard?q=%7B%7D"])
    if r < 0.62 and depth < 3:
        return [_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    if r < 0.8 and depth < 3:
        return _rdict(rng, depth + 1)
    return rng.randint(-10 ** 6, 10 ** 6)


def _rdict(rng, depth=0):
    return {rng.choice(KEYS): _value(rng, depth) for _ in range(rng.randint(0, 12))}


def _run(name, target, gen, allowed=()):
    """Call target(gen(rng)) for FUZZ_S seconds; fail with the seed and the
    input on an unexpected exception or a slow call. Returns the count."""
    rng = random.Random(f"{SEED}:{name}")
    end = time.monotonic() + FUZZ_S
    n = 0
    while n < 50 or time.monotonic() < end:
        n += 1
        arg = gen(rng)
        t0 = time.perf_counter()
        try:
            target(arg)
        except allowed:
            pass
        except Exception as e:  # noqa: BLE001 - any other exception is the finding
            pytest.fail(f"{name} raised {type(e).__name__}: {e} (seed {SEED}, call {n}); "
                        f"input: {arg!r:.500}")
        took = time.perf_counter() - t0
        assert took < fleet_test_guard.budget(CALL_S), (f"{name} took {took:.2f} s (seed {SEED}, call {n}); "
                               f"input: {arg!r:.300}")
    return n


def _json(obj):
    return json.dumps(obj, allow_nan=True)


# ------------------------------------------------------------------ parsers

@TIMING
def test_fuzz_client_line_parser_state_and_summary():
    st = state.SessionState()
    seq = [0]

    def target(line):
        ev = parser.parse_line(line, keep_raw=True)
        if ev is None:
            return
        assert isinstance(ev["type"], str) and ev["source"] == "client_log"
        seq[0] += 1
        ev["seq"] = seq[0]
        st.apply(ev)
        assert isinstance(state.summarize(ev), str)
        _json(ev)
        if seq[0] % 25 == 0:
            _json(st.snapshot())

    _run("parse_line", target, lambda r: _input(r, r.choice(LOG_SEEDS)))
    snap = st.snapshot()
    assert len(snap["recent_events"]) <= state.RECENT_EVENTS
    assert "recent_whispers" not in snap
    assert len(snap["trade_requests"]) <= state.TRADE_REQUESTS


@TIMING
def test_fuzz_parse_lines_bytes_in_any_encoding():
    def target(raw):
        for enc in ("utf-8", "latin-1", "utf-16-le"):
            text = raw.decode(enc, "replace")
            parser.parse_lines(text.splitlines())

    _run("parse_lines", target,
         lambda r: _input(r, "\r\n".join(r.sample(LOG_SEEDS, 3))).encode("utf-8",
                                                                          "surrogatepass"))


@TIMING
def test_fuzz_item_text_parser_and_trade_link():
    pc = price.PriceChecker(league=lambda: "Standard")

    def target(text):
        parsed = item.parse(text)
        _json(parsed.to_dict())
        assert isinstance(parsed.is_item, bool)
        doc = pc.request(text, at=1.0)
        assert doc["status"] in ("link", "skipped")
        card = price.card_of(doc)
        assert card["status"] in ("link", "error")
        _json(card)

    _run("item.parse", target, lambda r: _input(r, ITEM_SEED))


@TIMING
def test_fuzz_share_code_codec_raises_only_code_error():
    good = codec.encode(POB_XML)

    def target(text):
        try:
            xml = codec.decode(text)
        except codec.CodeError:
            return
        assert isinstance(xml, str)

    _run("codec.decode", target, lambda r: _input(r, good))


@TIMING
def test_fuzz_share_code_round_trip_is_exact():
    # the codec's claim: any UTF-8 text plus surrogate escapes (bytes that
    # are not UTF-8, U+DC80-U+DCFF) round-trips exactly
    # NUL is left out on purpose: SEC-XML-NUL refuses it (asserted below)
    alphabet = (ALPHABET.replace(chr(0xD800), chr(0xDC80)).replace(chr(0xDFFF), chr(0xDCFF))
                .replace("\x00", ""))

    def gen(rng):
        body = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 200)))
        return "<PathOfBuilding2>" + body

    def target(xml):
        assert codec.decode(codec.encode(xml)) == xml

    _run("codec.roundtrip", target, gen)


def test_codec_refuses_a_nul_byte_in_the_inflated_payload():
    with pytest.raises(codec.CodeError):
        codec.decode(codec.encode("<PathOfBuilding2>a\x00b"))


@TIMING
def test_fuzz_build_xml_and_code_raise_only_value_errors():
    good = codec.encode(POB_XML)
    # documented contract: codec.CodeError or BuildError, nothing else
    _run("model.parse", model.parse, lambda r: _input(r, POB_XML),
         allowed=(model.BuildError,))
    _run("model.from_code", model.from_code, lambda r: _input(r, good),
         allowed=(codec.CodeError, model.BuildError))


@TIMING
def test_fuzz_character_json_raises_only_value_errors():
    _run("charjson", charjson.from_json, lambda r: _input(r, CHAR_JSON),
         allowed=(model.BuildError,))


@TIMING
def test_fuzz_ninja_parsers_yield_finite_rates():
    def overview(body):
        doc = ninja.parse_overview(body)
        for lid, entry in doc["rates"].items():
            assert isinstance(lid, str) and math.isfinite(entry["value"])
        _json(doc)

    def enc(r, seed):
        return _input(r, seed).encode("utf-8", "surrogatepass")

    _run("ninja.overview", overview, lambda r: enc(r, NINJA_OVERVIEW), allowed=(ValueError,))
    _run("ninja.leagues", ninja.parse_leagues, lambda r: enc(r, NINJA_LEAGUES),
         allowed=(ValueError,))


@TIMING
def test_fuzz_webfetch_inflate_raises_only_fetch_error():
    # DATA-WEBFETCH-GZIP: random bytes, mutated and truncated gzip streams
    # either inflate within the cap or raise FetchError, nothing else
    good = gzip.compress(NINJA_OVERVIEW.encode("utf-8"))
    cap = 4096

    def gen(rng):
        r = rng.random()
        if r < 0.4:
            return bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 300)))
        b = bytearray(good)
        for _ in range(rng.randint(0, 6)):
            if b:
                b[rng.randrange(len(b))] = rng.getrandbits(8)
        return bytes(b[:rng.randint(0, len(b))]) if r < 0.7 else bytes(b)

    def target(data):
        rh, out = webfetch.inflate({"Content-Encoding": "gzip"}, data, cap)
        assert isinstance(out, bytes) and len(out) <= cap
        assert webfetch.header(rh, "Content-Encoding") is None

    _run("webfetch.inflate", target, gen, allowed=(webfetch.FetchError,))


# ------------------------------------------------------- snapshot builders

@TIMING
def test_fuzz_card_text_builders_never_raise():
    def target(d):
        for fn in (price.card_of, state.price_card_text, state.eval_card_text,
                   state.trade_card_text, state.summarize):
            _json(fn(d))
        state.overlay_card(d, d, 1.0)
        state.overlay_card(dict(d, at=1.0), dict(d, at=1.0), 2.0)

    _run("card_text", target, _rdict)


@TIMING
def test_fuzz_published_cards_never_break_the_snapshot():
    st = state.SessionState(clock=lambda: 1000.0)

    def target(d):
        st.set_eval(d)
        st.set_price(d)
        snap = st.snapshot()
        _json(snap)
        assert snap["eval"] is not None and snap["price"] is not None

    _run("snapshot", target, _rdict)


# --------------------------------------------- regressions (fuzz findings)

# TEST-FLAKE-SSE: wall-clock bounds scale with the suite gate's load factor;
# the regressions they guard took 4-7 s, so 0.5 s still catches them.
FAST_S = fleet_test_guard.budget(0.5)


def _timed(fn, *args):
    t0 = time.perf_counter()
    fn(*args)
    return time.perf_counter() - t0


PREFIX = "2026/11/16 21:00:00 1000 1f2e3d4c [INFO Client 5150] "


@TIMING
@pytest.mark.parametrize("body", [
    "@From X: Hi, I would like to buy your " + "listed for 1 in " * 600,
    "@From X: Hi, I would like to buy your " + "a listed for 1 b in c " * 400,
    "@From X: Hi, I'd like to buy your 1 a for my 1 b in " + "1 x for my 1 y in " * 500,
    "@From " + "<a> " * 15000,
    "#" + "<a> " * 15000,
    ": " + "a (b) " * 10000,
], ids=["priced", "priced2", "exchange", "guild", "chat", "levelup"])
def test_crafted_long_line_parses_fast(body):
    # FUZZ-1: the trade-whisper regexes backtracked cubically (a 10 KB
    # whisper took 4 s, a 64 KB line - the tailer's cap - hours) and the
    # guild / chat / level-up ones quadratically, all on the tailer thread.
    assert _timed(parser.parse_line, PREFIX + body) < FAST_S
    longest = (PREFIX + body)[:parser.MAX_LINE_CHARS]  # just under the cap
    assert _timed(parser.parse_line, longest) < FAST_S


def test_real_trade_whisper_still_parses():
    ev = parser.parse_line(LOG_SEEDS[-5])
    assert ev["trade"]["item"] == "Grim Bane Ruby Ring"
    assert ev["trade"]["price_amount"] == 5 and ev["trade"]["top"] == 7


def test_overlong_line_is_ignored_and_long_trade_text_is_plain_whisper():
    assert parser.parse_line(PREFIX + ": " + "a" * (parser.MAX_LINE_CHARS + 1)) is None
    note = "x" * parser.MAX_TRADE_TEXT
    ev = parser.parse_line(LOG_SEEDS[-5] + " " + note)
    assert ev is not None and ev["type"] == "whisper_in" and "trade" not in ev


@TIMING
def test_item_mod_tag_after_long_whitespace_is_fast():
    # FUZZ-2: _TAG_RE's leading \s* made re.search quadratic on a run of
    # spaces (60 000 spaces took 7 s on the press handler).
    text = "Item Class: Rings\nRarity: Rare\nA\nB\n--------\nx" + " " * 60000 + "y (implicit)\n"
    assert _timed(item.parse, text) < FAST_S
    mods = item.parse("Item Class: Rings\nRarity: Rare\nA\nB\n--------\n"
                      "+12% to Fire Resistance   (implicit)\n").mods
    assert mods[0].text == "+12% to Fire Resistance" and mods[0].section == "implicit"


@pytest.mark.parametrize("card", [
    {"ok": True, "item": 2.5, "comparisons": 7},
    {"ok": True, "comparisons": [1, "x", None], "verdict": {"a": 1}},
    {"ok": True, "comparisons": [{"stats": [1, {"key": [], "delta": 10 ** 400,
                                                "weighted": True}],
                                  "equipped": "x", "verdict": ["upgrade"]}],
     "calc": "pob", "score_delta": 10 ** 400},
    {"ok": True, "calc": {"source": "pob", "notice": {}},
     "comparisons": [{"dps": {"pct": 10 ** 400}, "ehp": "x"}]},
    {"ok": False, "error": {"a": 1}, "item": "ring"},
    {"error": ["x"], "status": ["done"], "listings": 10 ** 40, "item": [1]},
    {"status": "done", "listings": [{"amount": 10 ** 400, "currency": {}}], "count": 2},
    {"status": "waiting", "wait_s": 10 ** 400},
], ids=range(8))
def test_malformed_card_fields_read_honestly(card):
    # FUZZ-3: wrong-typed card fields (a number for `item`, a dict for
    # `error`, a non-list `listings`, a huge int) raised AttributeError /
    # TypeError / OverflowError in the text builders, and set_price raised
    # on a non-iterable listings; one bad card broke every /api/state.
    for fn in (state.eval_card_text, state.price_card_text, state.trade_card_text):
        _json(fn(card))
    st = state.SessionState(clock=lambda: 10.0)
    st.set_eval(card)
    st.set_price(card)
    snap = st.snapshot()
    assert snap["card"] is not None
    _json(snap)


def test_non_dict_trade_row_reads_honestly():
    assert state.trade_card_text(None)["text"].endswith("wants an item - no price set")


def test_lone_surrogate_in_character_json_is_a_build_error():
    # FUZZ-5: a "\udfff" JSON escape in a pasted character object raised
    # UnicodeEncodeError past the BuildError contract (/api/build-code 400).
    text = CHAR_JSON.replace('"Sorceress"', '"Sorc' + chr(92) + 'udfffress"')
    with pytest.raises(model.BuildError):
        charjson.from_json(text)
    with pytest.raises(model.BuildError):
        model.parse("<PathOfBuilding2>" + chr(0xD800) + "</PathOfBuilding2>")


def test_absurd_level_up_does_not_break_the_snapshot():
    # FUZZ-6 (found after merging UTIL-PACE): a level-up line with a huge
    # number overflowed pace maths (int too large to convert to float).
    st = state.SessionState()
    for i, lvl in enumerate((5, 6, 10 ** 400, 7)):
        ev = parser.parse_line(PREFIX + f": Cinderwisp (Sorceress) is now level {lvl}")
        ev["recv_ts"] = 1000.0 + 60 * i
        st.apply(ev)
    _json(st.snapshot())
