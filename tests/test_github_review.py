"""REVIEW-GH (decision 0090): every weekly GitHub page review record names
the six lenses and marks each finding fixed, filed or no change; the facts
fixed by the 2026-11-28 review stay fixed."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEWS = ROOT / "docs" / "reviews" / "github"
LENSES = ("UI/UX", "Visual", "Readability", "Comprehension", "Ease of use",
          "Ease of setup")
OUTCOME = re.compile(r"^- (GH-\d+) \[S[1-4]\] .*?-> (fixed|filed [A-Z0-9-]+|"
                     r"no change: .+)$")


def _records():
    return sorted(REVIEWS.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md"))


def _text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_first_record_exists():
    assert (REVIEWS / "2026-11-28.md").is_file()


def test_every_record_has_six_lenses_and_outcomes():
    for path in _records():
        text = path.read_text(encoding="utf-8")
        heads = re.findall(r"^## (.+)$", text, re.M)
        for lens in LENSES:
            assert lens in heads, (path.name, lens)
        items = _items(text)
        assert items, path.name
        for item in items:
            assert OUTCOME.match(item), (path.name, item)


def _items(text):
    """Each '- GH-<n>' bullet joined with its indented continuation lines."""
    items, open_item = [], False
    for ln in text.splitlines():
        if ln.startswith("- GH-"):
            items.append(ln.strip())
            open_item = True
        elif open_item and ln.startswith("  ") and ln.strip():
            items[-1] += " " + ln.strip()
        else:
            open_item = False
    return items


def test_filed_rows_exist():
    for path in _records():
        for item in _items(path.read_text(encoding="utf-8")):
            m = re.search(r"-> filed ([A-Z0-9-]+)$", item)
            if not m:
                continue
            row = m.group(1)
            # a done row is pruned to docs/roadmap/archive/ by roadmap_fold
            archived = any(row in a.read_text(encoding="utf-8") for a in
                           (ROOT / "docs" / "roadmap" / "archive").glob("*.md"))
            assert (ROOT / "docs" / "roadmap" / "new" / (row + ".md")).is_file() \
                or row in _text("ROADMAP.md") or archived, row


def test_port_advice_avoids_reserved_ports():
    # 8962-8969 are the test lease ports (server/al/ports.py); a player
    # picks a spare port
    from server.al import ports
    lo, hi = ports.SPARE_PORTS
    for rel in ("README.md", "docs/guide/common-issues.md"):
        text = _text(rel)
        assert "8962" not in text and "8969" not in text, rel
        assert str(lo) in text, rel
    assert ports.TEST_LEASE_PORTS == (8962, 8969)


def test_python_floor_said_one_way():
    text = _text("README.md")
    assert "Python 3.13 or newer and" not in text
    assert "Python 3.13 or newer. Add" not in text


def test_security_names_no_token_route_for_version():
    assert "GET /api/version" not in _text("SECURITY.md")


def test_guide_quick_start_tells_setup_time_and_stop():
    text = _text("docs/guide/quick-start.md")
    assert "allow a few minutes" in text
    assert text.count("Next: [Common issues]") == 0
    assert "README.md#uninstall-from-source" in text


def test_faq_names_setup_downloads():
    text = _text("docs/guide/faq.md")
    assert "Setup downloads its packages once" in text
