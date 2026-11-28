"""DEP-14 (F-148 text half): the player docs name the real install, update,
uninstall and verify steps and say plainly what unsigned means.

Section and wording lint over README.md and SECURITY.md:

- Install carries the one pasted line (the installer User-Agent, the
  project's release address, `| iex`) on an `al-version-stamp` line that
  holds VERSION, and the verified `-Zip` route.
- Update, Uninstall, Verify your download (SHA256SUMS, gh attestation
  verify, gh release verify-asset) and Windows may warn (each prompt named,
  never advice to switch a protection off) are present.
- The privacy text names the daily release read under web data.
- The not-affiliated line is present word for word.
- Every repository address names the project's own address from
  config/public_repo.json (ruling Q-24: the one allowed address; the
  'placeholder' of plan 05 DEP-14 is that value since GP-10).
- No GGG art and no paid or donation link.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SECURITY = ROOT / "SECURITY.md"
THIRD = ROOT / "THIRD-PARTY.md"

SECTIONS = ("Install (Windows)", "Update", "Uninstall", "Verify your download",
            "Windows may warn")
PROMPTS = ("execution policy", "SmartScreen", "Smart App Control",
           "User Account Control", "Firewall", "Antivirus")


def _text(path):
    return path.read_text(encoding="ascii")


def _flat(text):
    return " ".join(text.split())


def _section(text, heading):
    start = text.index("\n## " + heading + "\n") + 1
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else len(text)]


def _version():
    import server.al as al
    return al.VERSION


def _repo():
    doc = json.loads((ROOT / "config" / "public_repo.json").read_text(encoding="utf-8"))
    repo = doc["repo"]
    assert re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", repo), repo
    return repo


def test_sections_present_in_order():
    heads = re.findall(r"^## (.+)$", _text(README), re.M)
    idx = [heads.index(h) for h in SECTIONS]
    assert idx == sorted(idx), heads
    # README-SOURCE-FIRST (GH-1, session 44 choice a): with no release the
    # one working route comes first - Get started, then Quick start (with
    # its Stop / Update / Uninstall from source), then the release install
    qs = heads.index("Quick start (Windows)")
    assert heads.index("Get started") == qs - 1, heads
    assert qs < idx[0], heads
    subs = re.findall(r"^###? (.+)$", _text(README), re.M)
    q = subs.index("Quick start (Windows)")
    assert subs[q + 1:q + 4] == ["Stop", "Update from source",
                                 "Uninstall from source"], subs


MARKER = "al-version-stamp"


def _fenced_lines(text):
    """Every line inside a ``` fence (the fence lines themselves left out)."""
    out, inside = [], False
    for ln in text.splitlines():
        if ln.lstrip().startswith("```"):
            inside = not inside
            continue
        if inside:
            out.append(ln)
    return out


def test_install_pasted_line_is_stamped_with_version():
    sec = _section(_text(README), "Install (Windows)")
    version, repo = _version(), _repo()
    lines = sec.splitlines()
    marks = [i for i, ln in enumerate(lines) if MARKER in ln]
    assert len(marks) == 1, marks
    # README-STAMP-HIDDEN (GH-5): the marker is an HTML comment on its own
    # line above the fence, so the pasted line carries no dev comment
    mark = lines[marks[0]]
    assert re.fullmatch(r"<!--\s*" + MARKER + r"\b[^>]*-->", mark), mark
    assert lines[marks[0] + 1] == "```powershell", lines[marks[0] + 1]
    line = lines[marks[0] + 2]
    assert line.startswith("irm -UserAgent 'AshLight/%s (installer)' " % version), line
    assert "https://github.com/%s/releases/" % repo in line
    assert line.endswith("/install.ps1 | iex"), line
    assert "#" not in line and MARKER not in line, line
    # the stamp check of DEP-03 holds this line to VERSION
    assert re.search(r"(?<![\w.-])" + re.escape(version) + r"(?![\w-]|\.\d)", line)
    # every version in the line is VERSION, so release.py bump swaps them all
    found = re.findall(r"\d+\.\d+\.\d+(?:-rc\.\d+)?", line)
    assert found and set(found) == {version}, found


def test_no_fenced_readme_line_holds_the_stamp_marker():
    fenced = _fenced_lines(_text(README))
    assert fenced
    assert [ln for ln in fenced if MARKER in ln] == []


def test_release_tool_finds_the_install_line_by_the_marker_above():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "rel_version_readme", str(ROOT / "tools" / "rel_version.py"))
    rv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rv)
    hits = [(n, ln) for rel, n, ln in rv.stamp_lines(ROOT) if rel == "README.md"]
    assert len(hits) == 1, hits
    n, line = hits[0]
    assert line.startswith("irm -UserAgent 'AshLight/"), line
    assert _text(README).split("\n")[n - 1] == line


def test_install_names_the_verified_zip_route():
    sec = _section(_text(README), "Install (Windows)")
    flat = _flat(sec)
    assert re.search(r"^powershell -NoProfile -ExecutionPolicy Bypass -File "
                     r"\.\\install\.ps1 -Zip \.\\AshLight-<version>-app\.zip$", sec, re.M)
    for name in ("install.ps1", "AshLight-<version>-app.zip", "release.json",
                 "SHA256SUMS.txt", "-RuntimeDir", "-InstallDir", "-NoStart"):
        assert name in sec, name
    assert "Verify your download" in flat
    assert "never asks for admin rights" in flat
    assert "Releases: none yet, so the line below does not work today" in flat
    assert "AL_INSTALL_DIR" in sec


def test_update_section():
    flat = _flat(_section(_text(README), "Update"))
    # UX-46-P3 (P3-6): the shipped behaviour, not "not finished yet"
    assert "not finished" not in flat and "When automatic update ships" not in flat
    assert flat.startswith("## Update An installed copy updates itself while web data is on.")
    assert "once a day" in flat and "web data on" in flat
    assert "while the game looks closed" in flat
    assert "24 hours" in flat and "SHA256SUMS.txt" in flat
    assert "Update now" in flat and "About and data" in flat
    assert "Update only when I click Update now" in flat
    assert "With web data off, AshLight checks nothing" in flat
    assert "paste the install line again" in flat


def test_contact_and_uninstall_words_match_the_app():
    # UX-46-P3 (P3-6): the contact is optional (DATA-CONTACT-DEFAULT) and
    # the uninstall path names Windows Settings, not AshLight's Settings tab
    text = _flat(_text(README))
    assert "without it price fetches stay off" not in text
    assert ("`contact` (optional; how poe.ninja can reach you, sent in the "
            "User-Agent; without it AshLight sends its issues page)") in text
    assert "open Windows Settings, then Apps, then Installed apps" in text
    assert "open Settings, then Apps" not in text


def test_uninstall_section():
    sec = _section(_text(README), "Uninstall")
    flat = _flat(sec)
    assert "uninstall.ps1" in sec and "Installed apps" in flat
    assert "-Purge" in sec and "Recycle Bin" in flat and "-DryRun" in sec
    assert "data" in flat and "It asks nothing" in flat
    assert "never looks in your game folders" in flat


def test_verify_section_names_three_checks():
    sec = _section(_text(README), "Verify your download")
    repo = _repo()
    assert "SHA256SUMS.txt" in sec and "Get-FileHash" in sec
    assert re.search(r"gh attestation verify \S+ --repo " + re.escape(repo), sec)
    assert re.search(r"gh release verify-asset v<version> \S+ --repo "
                     + re.escape(repo), sec)
    assert "immutable" in sec
    assert "SECURITY.md" in sec


_OFF_ADVICE = re.compile(
    r"Set-ExecutionPolicy|Unblock-File|Run anyway|More info|Add-MpPreference|"
    r"\bexclusion\b|\b(turn|switch|shut)(ing)? (it |them )?off\b|"
    r"\bdisabl\w*|\ballow access\b|\bchoose Yes\b", re.I)


def _advice_problems(flat):
    """Sentences that tell the player to lower a protection. A sentence that
    names one only to say AshLight never needs it is allowed."""
    return [s for s in re.split(r"(?<=[.;:])\s+", flat)
            if _OFF_ADVICE.search(s)
            and not re.search(r"\bnever\b|\bno exclusion\b", s)]


def test_windows_may_warn_names_each_prompt_and_never_says_switch_off():
    sec = _section(_text(README), "Windows may warn")
    flat = _flat(sec)
    for prompt in PROMPTS:
        assert prompt in flat, prompt
    assert "not code-signed" in flat
    assert "not tested yet" in flat          # Smart App Control: unverified
    assert _advice_problems(flat) == []
    assert "AshLight needs no exclusion" in flat
    assert "Leave Smart App Control as it is" in flat


def test_off_advice_lint_catches_a_planted_line():
    bad = "If SmartScreen stops it, click More info, then Run anyway."
    assert _advice_problems(bad)
    assert _advice_problems("You can turn it off in Windows Security.")
    assert _advice_problems("Add an exclusion for the AshLight folder.")
    assert not _advice_problems("Let it finish; AshLight needs no exclusion.")


def test_privacy_names_the_daily_release_read_under_web_data():
    flat = _flat(_section(_text(README), "Privacy and consent"))
    assert re.search(r"an installed copy with web data on will read the "
                     r"project's latest release on GitHub once a day", flat)
    assert "It is not made yet." in flat
    assert "with web data off it is never made" in flat


def test_not_affiliated_line_present():
    import server.al as al
    text = _text(README)
    assert al.DISCLAIMER in text
    assert ("This product isn't affiliated with or endorsed by Grinding Gear "
            "Games in any way.") in text


def test_repository_address_is_only_the_projects_own():
    repo = _repo().lower()
    for path in (README, SECURITY, THIRD):
        text = _text(path)
        for owner_repo in re.findall(r"github\.com/([\w.-]+/[\w.-]+)", text, re.I):
            name = owner_repo.lower()
            if name.endswith(".git"):
                name = name[:-4]
            if path is THIRD:
                continue          # upstream projects of the notices
            assert name == repo, (path.name, owner_repo)
    # the third-party file names upstreams only, never another AshLight
    for owner_repo in re.findall(r"github\.com/([\w.-]+/[\w.-]+)", _text(THIRD), re.I):
        assert "ashlight" not in owner_repo.lower() or owner_repo.lower() == repo


# AshLight's own rendered pages (TEST-SHOTS-RENDER): a plain PNG name
# directly under docs/shots/, nothing nested, no '..', no query or scheme.
SHOT_SRC = re.compile(r"docs/shots/[a-z0-9][a-z0-9-]*\.png")


def _image_source_allowed(src):
    if src.startswith("assets/brand/"):
        return True
    return SHOT_SRC.fullmatch(src) is not None


def test_no_ggg_art_and_no_paid_link():
    text = _text(README)
    for src in re.findall(r"""(?:src|srcset)=["']([^"']+)["']""", text):
        assert _image_source_allowed(src), src
    for src in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
        assert _image_source_allowed(src), src
    lowered = text.lower()
    for word in ("patreon", "ko-fi", "buymeacoffee", "paypal", "sponsors",
                 "donate", "opencollective", "pathofexile.com/image",
                 "web.poecdn.com"):
        assert word not in lowered, word


def test_image_source_rule_stays_narrow():
    for ok in ("assets/brand/hero.png", "docs/shots/play-dark-1440.png"):
        assert _image_source_allowed(ok), ok
    for bad in ("docs/shots/../x.png", "docs/shots/sub/play.png",
                "docs/shots/play.jpg", "docs/shots/play.png?x=1",
                "https://web.poecdn.com/image/x.png", "docs/play.png",
                "docs/shots-x/play.png", "/docs/shots/play.png"):
        assert not _image_source_allowed(bad), bad


def test_security_states_what_the_updater_verifies():
    flat = _flat(_text(SECURITY))
    assert "## Release provenance" in _text(SECURITY)
    assert "Immutable releases" in flat and "Two hash sources" in flat
    assert "SHA256SUMS.txt" in flat and "digest" in flat
    assert "do not verify the attestation" in flat
    assert "CI verifies it" in flat and "gh attestation verify" in flat
    assert "not code-signed" in flat


def test_third_party_runtimes_fetched_at_install():
    flat = _flat(_text(THIRD))
    assert "fetched at install, not bundled" in flat
    assert "-RuntimeDir" in flat
    assert "never fetches a runtime" in flat
