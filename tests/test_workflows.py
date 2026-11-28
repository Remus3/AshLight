"""DEP-15 (F-076, F-148): the tag-triggered release workflow, linted.

Text parse only (stdlib, no YAML library) of .github/workflows/release.yml:
every action pinned by a 40-hex commit with a version comment (the same pin
as ci.yml for a shared action); the only trigger is a pushed v* tag; the
token holds exactly contents write, id-token write and attestations write;
the steps run in the order checkout (full history), pytest, node tests,
release.py build --tag, the sums-sha256 comparison with the tag message,
tools/sbom.py, the attestation, a draft release with the notes file as
body, the asset upload and the publish (--prerelease for an -rc. tag); no
step merges, commits, pushes or turns web data on; Python is one exact
version. The live half (a real -rc. tag) is REL-RC-LIVE.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF_DIR = ROOT / ".github" / "workflows"
RELEASE = WF_DIR / "release.yml"
CI = WF_DIR / "ci.yml"

USES_RX = re.compile(r"(?m)^\s*(?:-\s+)?uses:\s*(\S+)(.*)$")
PINNED_RX = re.compile(r"^([\w.-]+/[\w./-]+)@([0-9a-f]{40})$")
COMMENT_RX = re.compile(r"^\s*# v\d+(?:\.\d+)*\s*$")


def _text(path=RELEASE):
    return path.read_bytes().decode("ascii")


def _top_block(text, key):
    """The lines under a top-level `key:` (indented lines up to the next
    top-level key), comments and blank lines dropped."""
    lines = text.split("\n")
    start = lines.index(key + ":")
    out = []
    for line in lines[start + 1:]:
        if line and not line.startswith((" ", "#")):
            break
        if line.strip() and not line.lstrip().startswith("#"):
            out.append(line.rstrip())
    return out


def _steps(text):
    """The step blocks of the one job, in order (each starts at '      - ')."""
    lines = text.split("\n")
    start = next(i for i, l in enumerate(lines) if l == "    steps:")
    steps, cur = [], None
    for line in lines[start + 1:]:
        if line.startswith("      - "):
            cur = [line]
            steps.append(cur)
        elif cur is not None and (not line.strip() or line.startswith("        ")):
            cur.append(line)
        elif line.strip():
            break
    return ["\n".join(s) for s in steps]


def _pins(text):
    pins = {}
    for ref, _rest in USES_RX.findall(text):
        m = PINNED_RX.match(ref)
        if m:
            pins[m.group(1)] = m.group(2)
    return pins


def test_ascii_lf():
    raw = RELEASE.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")


def test_every_uses_is_pinned_by_commit():
    uses = USES_RX.findall(_text())
    assert uses, "no uses: lines found"
    for ref, rest in uses:
        assert PINNED_RX.match(ref), ref
        assert COMMENT_RX.match(rest), (ref, rest)


def test_shared_actions_carry_the_ci_pin():
    ours, ci = _pins(_text()), _pins(_text(CI))
    for action, sha in ours.items():
        if action in ci:
            assert ci[action] == sha, action


def test_only_trigger_is_v_tags():
    assert _top_block(_text(), "on") == [
        "  push:",
        "    tags:",
        '      - "v*"',
    ]
    text = _text()
    for word in ("pull_request", "workflow_dispatch", "schedule:",
                 "workflow_run", "branches:", "repository_dispatch"):
        assert word not in text, word


def test_permissions_exactly_three_writes():
    text = _text()
    assert _top_block(text, "permissions") == [
        "  contents: write",
        "  id-token: write",
        "  attestations: write",
    ]
    assert len(re.findall(r"(?m)^\s*permissions:", text)) == 1


def test_steps_in_order():
    steps = _steps(_text())
    markers = [
        ("checkout", lambda s: "actions/checkout@" in s
         and re.search(r"(?m)^\s*fetch-depth:\s*0\s*$", s)),
        ("pytest", lambda s: "python -m pytest -q" in s),
        ("node tests", lambda s: "npm test --prefix app" in s),
        ("build", lambda s: "tools/release.py build --tag" in s),
        ("sums", lambda s: "sums-sha256" in s and "SHA256SUMS.txt" in s
         and "git tag -l --format='%(contents)'" in s),
        ("sbom", lambda s: "python tools/sbom.py --commit" in s),
        ("attest", lambda s: "actions/attest-build-provenance@" in s),
        ("draft", lambda s: "gh release create" in s and "--draft" in s
         and "--notes-file" in s and "-notes.md" in s),
        ("upload", lambda s: "gh release upload" in s),
        ("publish", lambda s: "gh release edit" in s and "--draft=false" in s),
    ]
    at = []
    for name, hit in markers:
        idx = [i for i, s in enumerate(steps) if hit(s)]
        assert len(idx) == 1, (name, idx)
        at.append(idx[0])
    assert at == sorted(at), dict(zip([m[0] for m in markers], at))


def test_the_release_body_carries_the_sums_file_sha256():
    # REL-INSTALL-SUMS-PRINT (research 0066 F6): the same value install.ps1
    # prints, kept out of the uploaded folder (the body is not an asset)
    draft = [s for s in _steps(_text()) if "gh release create" in s]
    assert len(draft) == 1
    step = draft[0]
    assert "Get-FileHash -Algorithm SHA256" in step and "'SHA256SUMS.txt'" in step
    assert "SHA-256 of SHA256SUMS.txt: $sumsHash" in step
    assert "Join-Path $env:RUNNER_TEMP 'release-body.md'" in step
    assert "--notes-file $body" in step


def test_publish_marks_rc_tags_prerelease():
    pub = [s for s in _steps(_text()) if "gh release edit" in s]
    assert len(pub) == 1
    assert "-match '-rc\\.'" in pub[0]
    assert "--prerelease" in pub[0]
    rc_branch = pub[0].split("} else {")[0]
    assert "--prerelease" in rc_branch


def test_checkout_keeps_no_credentials():
    co = [s for s in _steps(_text()) if "actions/checkout@" in s]
    assert len(co) == 1
    assert re.search(r"(?m)^\s*persist-credentials:\s*false\s*$", co[0])


def test_no_merge_commit_push_or_web_data():
    text = "\n".join(l for l in _text().split("\n")
                     if not l.lstrip().startswith("#"))
    low = text.lower()
    for bad in ("git push", "git commit", "git merge", "gh pr", "pull-requests",
                "web_data", "web-data", "secrets.", "--force"):
        assert bad not in low, bad
    assert "merge" not in low, "no step may merge"


def test_python_is_one_exact_version():
    vals = re.findall(r"(?m)^\s*python-version:\s*(.*?)\s*$", _text())
    assert len(vals) == 1, vals
    assert re.fullmatch(r'"\d+\.\d+\.\d+"', vals[0]), vals[0]


def test_tag_shape_matches_rel_version():
    """The workflow's tag pattern accepts X.Y.Z and X.Y.Z-rc.N only, like
    tools/rel_version.py."""
    m = re.search(r"-notmatch '([^']+)'", _text())
    assert m
    rx = re.compile(m.group(1))
    for ok in ("v0.1.0", "v1.20.3", "v0.2.0-rc.1"):
        assert rx.match(ok), ok
    for bad in ("v01.0.0", "v1.0", "v1.0.0-beta", "1.0.0", "v1.0.0-rc.01"):
        assert not rx.match(bad), bad
