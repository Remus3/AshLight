"""PUB-GUIDE-PAGES (F-126): the four-page player guide under docs/guide/.

Download, Quick start, Common issues and FAQ exist; each carries the
non-affiliation sentence word for word; none claims GGG approval outside
that sentence (Game ToS floor in CLAUDE.md, research 0001); the FAQ's first
question is the allowed / banned one.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "guide"
PAGES = ("download.md", "quick-start.md", "common-issues.md", "faq.md")
SENTENCE = ("This product isn't affiliated with or endorsed by Grinding Gear "
            "Games in any way.")
BANNED = ("approved by", "authorised by", "authorized by",
          "endorsed by grinding")


def _text(name):
    return (GUIDE / name).read_text(encoding="utf-8")


def claims(text):
    """Approval phrases in text once the non-affiliation sentence is cut."""
    rest = " ".join(text.replace(SENTENCE, " ").split()).lower()
    return [p for p in BANNED if p in rest]


def first_question(text):
    """The first level-2 heading of a page, or None."""
    m = re.search(r"^## (.+)$", text, re.M)
    return m.group(1).strip() if m else None


def test_the_four_pages_exist():
    missing = [n for n in PAGES if not (GUIDE / n).is_file()]
    assert not missing, f"player guide pages missing: {missing}"


def test_every_page_carries_the_sentence():
    for name in PAGES:
        assert SENTENCE in _text(name), f"{name}: non-affiliation sentence"


def test_no_page_claims_approval():
    for name in PAGES:
        assert not claims(_text(name)), f"{name}: {claims(_text(name))}"


def test_faq_opens_with_the_allowed_and_banned_question():
    q = first_question(_text("faq.md"))
    assert q is not None
    low = q.lower()
    assert "allowed" in low and "banned" in low, q


def test_faq_says_no_tool_is_approved():
    text = " ".join(_text("faq.md").split()).lower()
    assert "no third-party tool is approved" in text


def test_download_has_no_release_and_no_address():
    text = _text("download.md")
    assert "No release yet" in text
    assert "http://" not in text and "https://" not in text


def test_checker_catches_a_claim_and_spares_the_sentence():
    assert claims(SENTENCE) == []
    assert claims("Fully approved by\nthe studio.") == ["approved by"]
    assert claims("Endorsed by Grinding Gear Games.") == ["endorsed by grinding"]
    assert first_question("# T\n\n## Is it allowed? Can I be banned?\n") == \
        "Is it allowed? Can I be banned?"
