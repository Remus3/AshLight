"""LOG-SHAPE-20261121: the six masked shapes the watch ledger confirmed on
2026-11-21 (ops/runtime/watch/live1_report.json, new_shapes).

The ledger stores only masked shapes, never the raw line, so each fixture
line in tests/fixtures/client_log_shape_20261121.txt is a stand-in that
masks to exactly the reported shape. Every shape stays unparsed: none
carries a fact any AshLight surface shows (the session connect is already
the INSTANCE pattern, session_connect), and for the generic ones the mask
hides every word, so there is no wording to anchor a pattern on. The
one-line note per shape is NOTES below.
"""

from pathlib import Path

from server.al import logshapes, parser

FIXTURE = Path(__file__).parent / "fixtures" / "client_log_shape_20261121.txt"

# Reported shape -> one-line note on why it stays unparsed.
NOTES = {
    "[<w> <w>] (<w> <w>) <w> <n> <w>":
        "start-up device / engine report with a spaced tag; no play fact, stays unparsed",
    "<w> instance <w> from <w> server":
        "'Got Instance Details from login server' precedes the INSTANCE line; "
        "session_connect already marks it, stays unparsed",
    "<w> to instance server was <w>":
        "'Connect time to instance server was <n>ms' is network latency; "
        "no surface shows it, stays unparsed",
    "<w> instance <w> <n>":
        "'Client-Safe Instance ID = <n>' is an opaque server id; "
        "nothing keys on it, stays unparsed",
    "<w> <n>":
        "one word and a number: the mask hides the word, nothing to anchor on, stays unparsed",
    "<w>":
        "a single masked word: nothing to anchor on, stays unparsed",
}


def _lines():
    return [ln for ln in FIXTURE.read_text(encoding="ascii").splitlines() if ln]


def _plain_shapes():
    out = []
    for line in _lines():
        ev = parser.parse_line(line)
        cls, detail = logshapes.classify(line, ev)
        if cls == "plain":
            out.append(logshapes.mask(detail))
    return out


def test_every_reported_shape_has_a_fixture_line():
    assert sorted(_plain_shapes()) == sorted(NOTES)


def test_every_note_is_one_short_ascii_line():
    for shape, note in NOTES.items():
        assert logshapes.is_safe_shape(shape)
        assert note.isascii() and "\n" not in note and 0 < len(note) <= 120


def test_shapes_stay_unparsed():
    for line in _lines():
        ev = parser.parse_line(line)
        if "Connecting to instance server" in line:
            assert ev is not None and ev["type"] == "session_connect"
        else:
            assert ev is None, line


def test_ledger_confirms_each_shape_as_plain():
    led = logshapes.Ledger()
    for now in (0, logshapes.CONFIRM_S):
        for line in _lines():
            led.observe(line, parser.parse_line(line), now=now)
    got = {s for k, s in led.confirmed() if k == logshapes.KIND_PLAIN}
    assert got == set(NOTES)
    assert led.hits.get("session_connect", [0])[0] == 2
