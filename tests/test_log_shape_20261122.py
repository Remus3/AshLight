"""LOG-SHAPE-20261122: the eighteen masked shapes the watch ledger confirmed
on 2026-11-22 (ops/runtime/watch/live1_report.json, new_shapes).

Six of them were already worked by LOG-SHAPE-20261121 (fixture
tests/fixtures/client_log_shape_20261121.txt, notes in
tests/test_log_shape_20261121.py); REPEATS below checks they are still
covered there. The twelve new ones get a stand-in fixture line each in
tests/fixtures/client_log_shape_20261122.txt that masks to exactly the
reported shape (the ledger stores only masked shapes, never the raw line).
Every shape stays unparsed: none carries a fact an AshLight surface shows,
and the mask hides the content words, so there is no verified wording to
anchor a pattern on. The one-line note per shape is NOTES below.
"""

from pathlib import Path

from server.al import logshapes, parser

FIXTURE = Path(__file__).parent / "fixtures" / "client_log_shape_20261122.txt"
PREV_FIXTURE = Path(__file__).parent / "fixtures" / "client_log_shape_20261121.txt"

# Shapes of this report already worked (with a fixture and a note) by
# LOG-SHAPE-20261121.
REPEATS = (
    "[<w> <w>] (<w> <w>) <w> <n> <w>",
    "<w> instance <w> from <w> server",
    "<w> to instance server was <w>",
    "<w> instance <w> <n>",
    "<w> <n>",
    "<w>",
)

_ENGINE = "start-up device / engine report with a spaced tag; no play fact, stays unparsed"
_ITEM = ("inventory action refusal shown to the player in game; "
         "no AshLight surface, stays unparsed")

# (kind, reported shape) -> one-line note on why it stays unparsed.
NOTES = {
    ("plain", "[<w> <w>] (the <w> <w>) <w> <n> <w>"): _ENGINE,
    ("plain", "[<w> <w>] (<w> of the <w>) <w> <n> <w>"): _ENGINE,
    ("plain", "[<w> <w>] (the <w>) <w> <n> <w>"): _ENGINE,
    ("plain", "[<w> <w>] (<w>) <w> <n> <w>"): _ENGINE,
    ("plain", "[<w> request] <w> to request <w>"):
        "client resource request housekeeping; no play fact, stays unparsed",
    ("plain", "connected to <host> in <w>."):
        "login / patch server connect latency; no surface shows it, stays unparsed",
    ("plain", "<w> to <w> a <w> with <n> <w>!"):
        "masked banner line, every content word hidden; nothing to anchor on, stays unparsed",
    ("sys", "error: failed to <w> instance <w>: the <w> of the <w> <w>."):
        "instance join error; area entry comes from the generation and scene lines, "
        "stays unparsed",
    ("sys", "failed to <w> item: item cannot be <w>."): _ITEM,
    ("sys", "failed to <w> item: <w> is not <w>."): _ITEM,
    ("sys", "failed to <w> item: item has no <w> for more <w>."): _ITEM,
    ("sys", "<w> the <w>?"):
        "a two-word question with both words masked; nothing to anchor on, stays unparsed",
}

KIND_OF = {"plain": logshapes.KIND_PLAIN, "system": logshapes.KIND_SYSTEM}


def _lines():
    return [ln for ln in FIXTURE.read_text(encoding="ascii").splitlines() if ln]


def _shapes():
    out = []
    for line in _lines():
        ev = parser.parse_line(line)
        cls, detail = logshapes.classify(line, ev)
        assert cls in KIND_OF, (cls, line)
        out.append((KIND_OF[cls], logshapes.mask(detail)))
    return out


def test_every_new_shape_has_a_fixture_line():
    assert sorted(_shapes()) == sorted(NOTES)


def test_repeats_are_covered_by_the_previous_row():
    seen = set()
    for line in PREV_FIXTURE.read_text(encoding="ascii").splitlines():
        if line:
            cls, detail = logshapes.classify(line, parser.parse_line(line))
            if cls == "plain":
                seen.add(logshapes.mask(detail))
    for shape in REPEATS:
        assert shape in seen
    assert not set(REPEATS) & {s for _, s in NOTES}


def test_every_note_is_one_short_ascii_line():
    for (_, shape), note in NOTES.items():
        assert logshapes.is_safe_shape(shape)
        assert note.isascii() and "\n" not in note and 0 < len(note) <= 120


def test_shapes_stay_unparsed():
    for line in _lines():
        ev = parser.parse_line(line)
        if ev is not None:
            assert ev["type"] == "unknown_system_line", line


def test_no_shape_trips_the_drift_counter():
    drift = logshapes.Drift()
    for line in _lines():
        assert not drift.observe(line, parser.parse_line(line)), line


def test_ledger_confirms_each_shape():
    led = logshapes.Ledger()
    for now in (0, logshapes.CONFIRM_S):
        for line in _lines():
            led.observe(line, parser.parse_line(line), now=now)
    assert set(led.confirmed()) == set(NOTES)
