"""PUB-GUIDE-DOWNLOAD-PLACE (F-126): one download place.

README.md, docs/guide/download.md, docs/guide/faq.md and the overlay About
(app/about.js downloadLine, fed by app/main.js from config/public_repo.json)
name the same single place: the releases page of the address in
config/public_repo.json (the one address the leak sweep allows). No scheme
in the line, so the guide's no-address rule (tests/test_player_guide.py)
still holds; the app only shows the text and fetches nothing.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("README.md", "docs/guide/download.md", "docs/guide/faq.md")
REPO_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$")


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _flat(text):
    return " ".join(text.split())


def js_const(src, name):
    """The double-quoted string value of `const <name> = "...";` in src."""
    m = re.search(r'^const %s = "([^"\\]*)";$' % re.escape(name), src, re.M)
    assert m, f"const {name} in app/about.js"
    return m.group(1)


def place_line(repo, src=None):
    """The line app/about.js downloadLine builds for repo, from its own
    prefix and suffix constants."""
    src = _read("app/about.js") if src is None else src
    return js_const(src, "DOWNLOAD_PREFIX") + repo + js_const(src, "DOWNLOAD_SUFFIX")


def _repo():
    doc = json.loads(_read("config/public_repo.json"))
    repo = doc.get("repo")
    assert isinstance(repo, str) and REPO_RX.match(repo), repo
    return repo


def test_the_place_is_the_releases_page_of_the_public_repo():
    repo = _repo()
    line = place_line(repo)
    assert ("github.com/" + repo + "/releases") in line
    assert "://" not in line
    assert line.isascii()


def test_readme_and_guide_pages_carry_the_same_line():
    line = place_line(_repo())
    for rel in PAGES:
        assert line in _flat(_read(rel)), f"{rel}: download place line"


def test_no_other_releases_place_is_named_in_the_guide():
    repo = _repo()
    for rel in ("docs/guide/download.md", "docs/guide/faq.md"):
        others = [m for m in re.findall(r"[\w.-]+/[\w.-]+/releases", _read(rel))
                  if m != repo + "/releases"]
        assert not others, f"{rel}: {others}"


def test_readme_line_sits_beside_the_guide_link_outside_quick_start():
    text = _read("README.md")
    flat = _flat(text)
    line = place_line(_repo())
    at = flat.index(line)
    assert at < flat.index("## Quick start (Windows)")
    assert at < flat.index("## How this repository is run")
    para = next(p for p in text.split("\n\n") if line in _flat(p))
    assert "docs/guide/" in para


def test_about_is_given_the_line_built_from_public_repo_json():
    code = re.sub(r"/\*.*?\*/", "", _read("app/main.js"), flags=re.S)
    code = re.sub(r"(^|[^:])//[^\n]*", r"\1", code)
    assert re.search(r'^const DOWNLOAD_LINE = About\.downloadLine\(readJson\('
                     r'path\.join\(REPO, "config", "public_repo\.json"\)\)\);$',
                     code, re.M)
    calls = re.findall(r"About\.aboutText\(([^)]*)\)", code)
    assert len(calls) == 1
    assert [a.strip() for a in calls[0].split(",")][-1] == "DOWNLOAD_LINE"
    about = _read("app/about.js")
    assert "function downloadLine(doc)" in about
    assert "return DOWNLOAD_PREFIX + repo + DOWNLOAD_SUFFIX;" in about


def test_place_line_helper_reads_the_constants():
    src = 'const DOWNLOAD_PREFIX = "at x/";\nconst DOWNLOAD_SUFFIX = "/r.";\n'
    assert place_line("a/b", src) == "at x/a/b/r."
