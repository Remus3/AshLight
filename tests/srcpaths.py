"""TEST-WEB-SRCPATHS-PY (F-135): where the dashboard sources live.

The pytest files that read the dashboard page, its scripts or its sheets by
name go through this one helper, so a later move of web/ or an assembled
page (web/panels/) changes this file only. A helper module, not a test
(tests/test_test_layout.py rule 2). The server's own web_root argument in
serve(...) calls is a directory the core serves and stays where it is.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PANELS = WEB / "panels"
PAGE = "index.html"


def path(name):
    """The path of a dashboard source file named relative to web/."""
    return WEB / name


def read(name, encoding="ascii"):
    """The text of a dashboard source file named relative to web/."""
    return path(name).read_text(encoding=encoding)


def read_bytes(name):
    """The bytes of a dashboard file named relative to web/ (icons)."""
    return path(name).read_bytes()


def index_html(encoding="ascii"):
    """The dashboard page text."""
    return read(PAGE, encoding=encoding)


def _listed(pattern):
    found = sorted(WEB.glob(pattern))
    if PANELS.is_dir():
        found += sorted(PANELS.glob(pattern))
    return found


def web_js():
    """Every dashboard script: web/*.js, then web/panels/*.js when present."""
    return _listed("*.js")


def web_css():
    """Every dashboard sheet: web/*.css, then web/panels/*.css when present."""
    return _listed("*.css")
