"""LOG-SHAPE-20261123: the twenty-three masked shapes the watch ledger
confirmed on 2026-11-23 (ops/runtime/watch/live1_report.json, new_shapes).

Eighteen of them were already worked by LOG-SHAPE-20261121 and
LOG-SHAPE-20261122 (fixtures tests/fixtures/client_log_shape_20261121.txt
and _20261122.txt, notes in their test files); REPEATS below checks they are
still covered there. The five new ones get a stand-in fixture line each in
tests/fixtures/client_log_shape_20261123.txt that masks to exactly the
reported shape (the ledger stores only masked shapes, never the raw line).
Every shape stays unparsed: none carries a fact an AshLight surface shows,
and the mask hides the content words, so there is no verified wording to
anchor a pattern on. The one-line note per shape is NOTES below.
"""

from pathlib import Path

from server.al import logshapes, parser

HERE = Path(__file__).parent / "fixtures"
FIXTURE = HERE / "client_log_shape_20261123.txt"
PREV_FIXTURES = (HERE / "client_log_shape_20261121.txt",
                 HERE / "client_log_shape_20261122.txt")

# Shapes of this report already worked (with a fixture and a note) by
# LOG-SHAPE-20261121 or LOG-SHAPE-20261122.
REPEATS = (
    ("sys", "error: failed to <w> instance <w>: the <w> of the <w> <w>."),
    ("sys", "failed to <w> item: item cannot be <w>."),
    ("plain", "[<w> <w>] (the <w>) <w> <n> <w>"),
    ("plain", "[<w> <w>] (<w> of the <w>) <w> <n> <w>"),
    ("sys", "failed to <w> item: <w> is not <w>."),
    ("plain", "[<w> <w>] (<w>) <w> <n> <w>"),
    ("plain", "<w> to <w> a <w> with <n> <w>!"),
    ("sys", "<w> the <w>?"),
    ("sys", "failed to <w> item: item has no <w> for more <w>."),
    ("plain", "[<w> request] <w> to request <w>"),
    ("plain", "connected to <host> in <w>."),
    ("plain", "<w>"),
    ("plain", "[<w> <w>] (<w> <w>) <w> <n> <w>"),
    ("plain", "<w> instance <w> from <w> server"),
    ("plain", "<w> to instance server was <w>"),
    ("plain", "<w> instance <w> <n>"),
    ("plain", "<w> <n>"),
    ("plain", "[<w> <w>] (the <w> <w>) <w> <n> <w>"),
)

_FILTER = ("item filter load / fetch housekeeping with a spaced tag; "
           "no play fact, stays unparsed")

# (kind, reported shape) -> one-line note on why it stays unparsed.
NOTES = {
    ("plain", "<w> to <w>() after level generation was <w>"):
        "engine call-order diagnostic after a level build; area entry comes "
        "from the generation line, stays unparsed",
    ("sys", "failed to <w> item: item cannot <w> to the <w> item."):
        "inventory action refusal shown to the player in game; "
        "no AshLight surface, stays unparsed",
    ("plain", "[item <w>] <w> to <w> online <w>"): _FILTER,
    ("plain", "[item <w>] <w> online <w>"): _FILTER,
    ("sys", "<n> items <w>"):
        "item count notice with its verb masked; no verified wording "
        "or surface, stays unparsed",
}

KIND_OF = {"plain": logshapes.KIND_PLAIN, "system": logshapes.KIND_SYSTEM}


def _lines(path=FIXTURE):
    return [ln for ln in path.read_text(encoding="ascii").splitlines() if ln]


def _shapes(path=FIXTURE, strict=True):
    out = []
    for line in _lines(path):
        ev = parser.parse_line(line)
        cls, detail = logshapes.classify(line, ev)
        if not strict and cls not in KIND_OF:
            continue  # the earlier fixtures also hold parsed event lines
        assert cls in KIND_OF, (cls, line)
        out.append((KIND_OF[cls], logshapes.mask(detail)))
    return out


def test_every_new_shape_has_a_fixture_line():
    assert sorted(_shapes()) == sorted(NOTES)


def test_repeats_are_covered_by_the_previous_rows():
    seen = set()
    for path in PREV_FIXTURES:
        seen.update(_shapes(path, strict=False))
    for shape in REPEATS:
        assert shape in seen, shape
    assert not set(REPEATS) & set(NOTES)
    assert len(REPEATS) + len(NOTES) == 23


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
