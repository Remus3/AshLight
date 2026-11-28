"""DEP-03: one version, enforced, and the release tool dispatcher.

VERSION in server/al/__init__.py is the one source; app/package.json, both
version fields of app/package-lock.json and every stamped line must hold it.
`release.py bump` changes exactly the version-bearing paths plus the notes
stub; `bump --check` writes nothing. The scratch repos here are fresh git
repos under tmp_path holding copies of the real version files (index only,
no commit), so the bump never touches the checkout.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "tools" / "release.py"


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, str(ROOT / "tools" / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rv = _load("rel_version")
release = _load("release")

def _git(cwd, *args):
    proc = subprocess.run(["git", "-c", "core.hooksPath=", *args], cwd=str(cwd),
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _status(cwd):
    """Paths whose working copy differs from the index, plus untracked ones."""
    changed = _git(cwd, "diff", "--name-only").splitlines()
    new = _git(cwd, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(p for p in changed + new if p.strip()))


def _scratch(tmp_path, extra=None):
    """A git repo holding copies of the version files plus `extra` files."""
    repo = tmp_path / "scratch"
    for rel in (rv.INIT_REL, rv.PKG_REL, rv.LOCK_REL):
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(ROOT / rel), str(dst))
    for rel, text in (extra or {}).items():
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(text.encode("ascii"))
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    return repo


def _run(*args):
    return subprocess.run([sys.executable, str(RELEASE), *args], cwd=str(ROOT),
                          capture_output=True, text=True, check=False)


def test_version_matches_app_package_and_lock():
    version = rv.source_version(ROOT)
    rv.parse(version)
    pkg = json.loads((ROOT / rv.PKG_REL).read_text(encoding="utf-8"))
    lock = json.loads((ROOT / rv.LOCK_REL).read_text(encoding="utf-8"))
    assert pkg["version"] == version
    assert lock["version"] == version
    assert lock["packages"][""]["version"] == version
    assert rv.check(ROOT) == []


def test_source_version_matches_import():
    import server.al as al
    assert al.VERSION == rv.source_version(ROOT)


@pytest.mark.parametrize("rel,field", [
    (rv.PKG_REL, None), (rv.LOCK_REL, None), (rv.LOCK_REL, "")])
def test_planted_mismatch_fails(tmp_path, rel, field):
    repo = _scratch(tmp_path)
    doc = json.loads((repo / rel).read_text(encoding="utf-8"))
    if field is None:
        doc["version"] = "9.9.9"
    else:
        doc["packages"][field]["version"] = "9.9.9"
    (repo / rel).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    problems = rv.check(repo)
    assert len(problems) == 1 and "9.9.9" in problems[0], problems
    proc = _run("bump", "--check", "--root", str(repo))
    assert proc.returncode == 1 and "9.9.9" in proc.stdout


def test_planted_source_mismatch_fails(tmp_path):
    repo = _scratch(tmp_path)
    init = repo / rv.INIT_REL
    init.write_text(init.read_text(encoding="utf-8").replace(
        'VERSION = "%s"' % rv.source_version(ROOT), 'VERSION = "9.9.9"'),
        encoding="utf-8", newline="\n")
    assert len(rv.check(repo)) == 3


def test_every_stamped_line_holds_version():
    version = rv.source_version(ROOT)
    for rel, n, line in rv.stamp_lines(ROOT):
        assert version in line, "%s:%d stamped line lacks %s" % (rel, n, version)


def test_stamp_scan_and_prose_mentions(tmp_path):
    marker = rv.MARKER
    version = rv.source_version(ROOT)
    repo = _scratch(tmp_path, {
        "README.md": "install %s <!-- %s -->\nplain %s line\n"
                     % (version, marker, version),
        "docs/prose.md": "each line marked `%s` and '%s' and \"%s\"\n"
                         % (marker, marker, marker),
    })
    assert [(r, n) for r, n, _ in rv.stamp_lines(repo)] == [("README.md", 1)]
    assert rv.check(repo) == []
    (repo / "README.md").write_text("install 0.0.9 <!-- %s -->\n" % marker,
                                    encoding="utf-8", newline="\n")
    problems = rv.check(repo)
    assert problems and "README.md:1" in problems[0]
    # a longer version is not the version
    (repo / "README.md").write_text("install %s.1 <!-- %s -->\n"
                                    % (version, marker), encoding="utf-8", newline="\n")
    assert rv.check(repo)


def test_marker_line_above_a_fence_stamps_the_fenced_line(tmp_path):
    # README-STAMP-HIDDEN: a whole-line marker comment points at the next
    # line that is not blank or a fence, so the pasted line stays clean
    marker = rv.MARKER
    version = rv.source_version(ROOT)
    readme = ("intro\n<!-- %s: the line below -->\n```powershell\n"
              "irm -UserAgent 'X/%s (installer)' https://h/install.ps1 | iex\n"
              "```\nkeep %s here\n" % (marker, version, version))
    repo = _scratch(tmp_path, {"README.md": readme})
    hits = rv.stamp_lines(repo)
    assert [(r, n) for r, n, _ in hits] == [("README.md", 4)]
    assert marker not in hits[0][2]
    assert rv.check(repo) == []
    (repo / "README.md").write_text(readme.replace("X/%s" % version, "X/0.0.9"),
                                    encoding="utf-8", newline="\n")
    problems = rv.check(repo)
    assert problems and "README.md:4" in problems[0], problems


def test_marker_line_with_nothing_below_is_a_problem(tmp_path):
    repo = _scratch(tmp_path, {"README.md": "x\n<!-- %s -->\n\n```\n" % rv.MARKER})
    problems = rv.check(repo)
    assert problems and "README.md:2" in problems[0], problems


def test_bump_rewrites_the_line_below_the_marker(tmp_path):
    old = rv.source_version(ROOT)
    marker = rv.MARKER
    readme = ("<!-- %s -->\n```powershell\nirm 'X/%s' | iex\n```\nkeep %s\n"
              % (marker, old, old))
    repo = _scratch(tmp_path, {"README.md": readme})
    new = "0.2.0-rc.0"
    proc = _run("bump", new, "--root", str(repo))
    assert proc.returncode == 0, proc.stderr
    assert (repo / "README.md").read_text(encoding="utf-8") == (
        "<!-- %s -->\n```powershell\nirm 'X/%s' | iex\n```\nkeep %s\n"
        % (marker, new, old))
    assert rv.check(repo) == []


def test_semver_order():
    assert rv.compare("0.2.0-rc.1", "0.2.0") == -1
    assert rv.compare("0.2.0", "0.2.0-rc.1") == 1
    assert rv.compare("0.2.0-rc.1", "0.2.0-rc.2") == -1
    assert rv.compare("0.2.0-rc.10", "0.2.0-rc.2") == 1
    assert rv.compare("0.10.0", "0.9.0") == 1
    assert rv.compare("0.1.0", "0.1.0") == 0
    assert sorted(["0.2.0", "0.2.0-rc.1", "0.1.9", "0.2.0-rc.0"],
                  key=rv.sort_key) == ["0.1.9", "0.2.0-rc.0", "0.2.0-rc.1", "0.2.0"]
    for bad in ("0.1", "v0.1.0", "0.1.0-beta.1", "01.1.0", "0.1.0-rc", ""):
        with pytest.raises(rv.VersionError):
            rv.parse(bad)


def test_tag_must_equal_v_plus_version():
    version = rv.source_version(ROOT)
    assert rv.tag_ok("v" + version, version)
    assert not rv.tag_ok(version, version)
    assert not rv.tag_ok("v" + version + "-rc.1", version)
    assert rv.check(ROOT, tag="v" + version) == []
    assert rv.check(ROOT, tag="v9.9.9")
    assert _run("bump", "--check", "--tag", "v" + version).returncode == 0
    assert _run("bump", "--check", "--tag", "v9.9.9").returncode == 1


def test_bump_on_scratch_changes_exactly_the_version_paths(tmp_path):
    old = rv.source_version(ROOT)
    marker = rv.MARKER
    repo = _scratch(tmp_path, {
        "README.md": "install %s <!-- %s -->\nkeep %s here\n" % (old, marker, old),
        "notes.txt": "unrelated %s\n" % old,
    })
    lock_before = json.loads((repo / rv.LOCK_REL).read_text(encoding="utf-8"))
    new = "0.2.0-rc.0"
    proc = _run("bump", new, "--root", str(repo))
    assert proc.returncode == 0, proc.stderr
    assert _status(repo) == sorted([
        rv.INIT_REL, rv.PKG_REL, rv.LOCK_REL, "README.md", "docs/releases/%s.md" % new])
    assert rv.source_version(repo) == new
    assert rv.check(repo) == []
    assert (repo / "README.md").read_text(encoding="utf-8") == (
        "install %s <!-- %s -->\nkeep %s here\n" % (new, marker, old))
    lock_after = json.loads((repo / rv.LOCK_REL).read_text(encoding="utf-8"))
    lock_before["version"] = new
    lock_before["packages"][""]["version"] = new
    assert lock_after == lock_before
    stub = (repo / "docs" / "releases" / (new + ".md")).read_bytes()
    assert rv.STUB_MARK.encode("ascii") in stub and b"\r" not in stub
    for rel in (rv.INIT_REL, rv.PKG_REL, rv.LOCK_REL):
        assert b"\r\n" not in (repo / rel).read_bytes() or \
            b"\r\n" in (ROOT / rel).read_bytes()
    # the next bump goes on from the new version; rc -> release is upward
    assert _run("bump", "0.2.0", "--root", str(repo)).returncode == 0
    assert rv.source_version(repo) == "0.2.0"


def test_bump_refusals_write_nothing(tmp_path):
    old = rv.source_version(ROOT)
    repo = _scratch(tmp_path)
    for version in (old, "0.0.1", "not-a-version"):
        proc = _run("bump", version, "--root", str(repo))
        assert proc.returncode == 1, (version, proc.stdout)
        assert _status(repo) == []
    doc = json.loads((repo / rv.PKG_REL).read_text(encoding="utf-8"))
    doc["version"] = "9.9.9"
    (repo / rv.PKG_REL).write_text(json.dumps(doc, indent=2) + "\n",
                                   encoding="utf-8", newline="\n")
    proc = _run("bump", "0.99.0", "--root", str(repo))
    assert proc.returncode == 1 and "not consistent" in proc.stderr
    assert _status(repo) == [rv.PKG_REL]


def test_bump_check_is_a_noop_at_head():
    before = _status(ROOT)
    proc = _run("bump", "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok " + rv.source_version(ROOT) in proc.stdout
    assert _status(ROOT) == before


def test_unknown_or_unbuilt_subcommand_exits_2(monkeypatch, capsys):
    assert _run("frobnicate").returncode == 2
    assert _run().returncode == 2
    assert _run("bump").returncode == 2
    monkeypatch.setitem(release.COMMANDS, "ghost", "ghost_never_built")
    assert release.main(["ghost"]) == 2
    assert "not built yet" in capsys.readouterr().err
    assert release.main(["bump", "--check"]) == 0


def test_dispatch_table_is_fixed():
    assert release.COMMANDS == {
        "bump": "version", "notes": "notes", "build": "build", "stage": "stage",
        "publish": "publish", "prepush-check": "publish"}
