"""AUTO-03 ROW-FILES: `tools/roadmap.py lint` fails on a row-like bullet the
loop's parser cannot read (a dotted id), a repeated id and an unknown lane
hint, and on a malformed row file; the tree's open ROADMAP bullets lint
clean."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import roadmap  # noqa: E402

CLEAN = """# ROADMAP

- [ ] ALPHA (build) Open. ACCEPT: a.
  continuation line.
- [ ] BETA (priority) Open, no lane, priority.
- [ ] GAMMA (build) (priority) Open, lane then priority.
- [ ] DELTA (data) (AREA-MATH b2) prose in brackets is not a hint.
- [x] EPSILON (review) Done. -- done 2026-11-17 (session)
- FOLDED 2026-11-18: a pointer line is not a row-like bullet.
"""

BAD_DONE = """- [x] UTIL-1.0-READY (build) A done dotted id.
- [x] AUDIT-TC-WIRE (build) First.
- [x] AUDIT-TC-WIRE (build) Repeated done id.
- [x] DOC-X (docs) A done row with an unknown lane hint.
"""

BAD_OPEN = """- [ ] UTIL-1.0-POST (build) An open dotted id.
- [ ] ALPHA (data) Repeats an open id.
- [ ] RUNBOOK (docs) An open row with an unknown lane hint.
- [ ]NOSPACE (build) No space after the mark.
"""


def _root(tmp_path, text):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ROADMAP.md").write_text(text, encoding="ascii", newline="\n")
    return root


def _write(root, rel, data):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def _has(probs, *words):
    return any(all(w in p for w in words) for p in probs)


def test_lint_fails_on_dotted_id_repeated_id_and_bad_lane(tmp_path):
    root = _root(tmp_path, CLEAN)
    assert roadmap.lint(root) == []
    assert roadmap.lint(root, open_only=True) == []
    (root / "ROADMAP.md").write_text(CLEAN + BAD_DONE + BAD_OPEN, encoding="ascii",
                                     newline="\n")

    probs = roadmap.lint(root)
    assert _has(probs, "ROADMAP.md:10:", "does not parse", "UTIL-1.0-READY")
    assert _has(probs, "repeated row id AUDIT-TC-WIRE", "ROADMAP.md:11", "ROADMAP.md:12")
    assert _has(probs, "ROADMAP.md:13:", "unknown lane hint (docs)", "DOC-X")
    assert _has(probs, "ROADMAP.md:14:", "does not parse", "UTIL-1.0-POST")
    assert _has(probs, "repeated row id ALPHA", "ROADMAP.md:3", "ROADMAP.md:15")
    assert _has(probs, "ROADMAP.md:16:", "unknown lane hint (docs)", "RUNBOOK")
    assert _has(probs, "ROADMAP.md:17:", "does not parse", "NOSPACE")
    assert len(probs) == 7, probs

    # open_only (the tree test's mode): the done bullets are history
    probs = roadmap.lint(root, open_only=True)
    assert not _has(probs, "UTIL-1.0-READY") and not _has(probs, "AUDIT-TC-WIRE")
    assert not _has(probs, "DOC-X")
    assert _has(probs, "UTIL-1.0-POST") and _has(probs, "repeated row id ALPHA")
    assert _has(probs, "RUNBOOK") and _has(probs, "NOSPACE")
    assert len(probs) == 4, probs

    # the CLI is strict on every bullet and exits 1
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "roadmap.py"), "--root",
                        str(root), "lint"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and len(r.stdout.strip().splitlines()) == 7


def test_lint_checks_row_files(tmp_path):
    root = _root(tmp_path, CLEAN)
    _write(root, "docs/roadmap/new/ZETA.md", b"- [ ] ZETA (build) Fine.\n  more.\n")
    _write(root, "docs/roadmap/done/ZETA.md", b" -- done 2026-11-18 (session)\n")
    _write(root, "docs/roadmap/archive/2026-11.md", b"- [x] OLD.1 (docs) history\n")
    assert roadmap.lint(root) == []
    _write(root, "docs/roadmap/new/ETA.md", b"- [ ] THETA (build) Wrong file name.\n")
    _write(root, "docs/roadmap/new/IOTA.md", b"- [ ] IOTA (build) CRLF.\r\n")
    _write(root, "docs/roadmap/new/ALPHA.md", b"- [ ] ALPHA (build) Repeats ROADMAP.\n")
    _write(root, "docs/roadmap/new/lower.md", b"- [ ] LOWER (build) Bad name.\n")
    _write(root, "docs/roadmap/new/KAPPA.md", b"- [ ] KAPPA (wiki) Bad lane.\n")
    _write(root, "docs/roadmap/done/NOROW.md", b" -- done 2026-11-18 (session)\n")
    _write(root, "docs/roadmap/done/ALPHA.md", b"done\n")
    _write(root, "docs/roadmap/done/BETA.md",
           b" -- done 2026-11-18 (a)\n -- done 2026-11-18 (b)\n")
    probs = roadmap.lint(root)
    assert _has(probs, "new/ETA.md", "does not match the file name")
    assert _has(probs, "new/IOTA.md", "not LF")
    assert _has(probs, "repeated row id ALPHA", "docs/roadmap/new/ALPHA.md")
    assert _has(probs, "new/lower.md", "not a row file name")
    assert _has(probs, "new/KAPPA.md", "unknown lane hint (wiki)")
    assert _has(probs, "done/NOROW.md", "done file without a row")
    assert _has(probs, "done/ALPHA.md", "not exactly one line")
    assert _has(probs, "done/BETA.md", "not exactly one line")
    assert not _has(probs, "archive")
    # row-file problems count in open_only mode too
    assert len(roadmap.lint(root, open_only=True)) == len(probs)


def test_tree_roadmap_lints_clean():
    probs = roadmap.lint(ROOT, open_only=True)
    assert probs == [], "\n".join(probs)
