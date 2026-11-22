"""Publish read-back (REL-PUBLISH-READBACK): tools/rel_readback.py and its
one call from tools/rel_publish.py.

gh, the clock and sleep are injected: FakeGh answers the release, tag and
attestation reads from a state dict, FakeClock moves only when sleep is
called, so no test touches GitHub or waits. The stage folder is a scratch
folder under tmp_path holding stage.json, SHA256SUMS.txt and the app zip.
"""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(
        "readback_test_" + name, str(ROOT / "tools" / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rr = _load("rel_readback")
rp = _load("rel_publish")
VERSION = "0.4.2"
TAG = "v" + VERSION
HEAD = "a" * 40
OTHER = "b" * 40
TAGOBJ = "d" * 40
REPO = "Example/AshLight"
ZIP = "AshLight-%s-app.zip" % VERSION
NOW = datetime.datetime(2026, 11, 21, 12, 0, 0,
                        tzinfo=datetime.timezone.utc).timestamp()


def _stage(out):
    out.mkdir(parents=True, exist_ok=True)
    assets = {ZIP: b"zip bytes", "install.ps1": b"script",
              "release.json": b"{}"}
    for name, data in assets.items():
        (out / name).write_bytes(data)
    digests = {n: hashlib.sha256(d).hexdigest() for n, d in assets.items()}
    sums = "".join("%s  %s\n" % (digests[n], n) for n in sorted(digests))
    (out / "SHA256SUMS.txt").write_bytes(sums.encode("ascii"))
    sums_sha = hashlib.sha256(sums.encode("ascii")).hexdigest()
    digests["SHA256SUMS.txt"] = sums_sha
    (out / "stage.json").write_text(json.dumps({
        "version": VERSION, "commit": HEAD, "verdict": "PASS",
        "sums_sha256": sums_sha, "created": "2026-11-21T10:00:00Z"}),
        encoding="ascii")
    return digests


class FakeGh:
    def __init__(self, digests, **over):
        self.state = {
            "release": True, "draft": False, "immutable": True,
            "assets": {n: "sha256:" + d for n, d in digests.items()},
            "tag_commit": HEAD, "annotated": True, "attest_rc": 0,
            "installed": True, "publish_after": 0,
        }
        self.state.update(over)
        self.calls = []

    def __call__(self, *args):
        self.calls.append(list(args))
        s = self.state
        a = list(args)
        if not s["installed"]:
            return 127, "", "gh not installed"
        if a[:1] == ["attestation"]:
            assert a[1] == "verify" and a[3:] == ["--repo", REPO]
            assert Path(a[2]).name == ZIP
            return s["attest_rc"], "", ("" if s["attest_rc"] == 0
                                        else "no matching attestation\n")
        assert a[0] == "api"
        path = a[1]
        if path == "repos/%s/releases/tags/%s" % (REPO, TAG):
            reads = sum(1 for c in self.calls if c[1] == path)
            if not s["release"] or reads <= s["publish_after"]:
                return 1, "", "gh: Not Found (HTTP 404)"
            return 0, json.dumps({
                "tag_name": TAG, "draft": s["draft"],
                "immutable": s["immutable"],
                "assets": [{"name": n, "digest": d}
                           for n, d in sorted(s["assets"].items())]}), ""
        if path == "repos/%s/git/ref/tags/%s" % (REPO, TAG):
            obj = ({"type": "tag", "sha": TAGOBJ} if s["annotated"]
                   else {"type": "commit", "sha": s["tag_commit"]})
            return 0, json.dumps({"ref": "refs/tags/" + TAG,
                                  "object": obj}), ""
        if path == "repos/%s/git/tags/%s" % (REPO, TAGOBJ):
            return 0, json.dumps({"object": {"type": "commit",
                                             "sha": s["tag_commit"]}}), ""
        raise AssertionError("unexpected gh call %r" % (a,))

    def attested(self):
        return [c for c in self.calls if c[:1] == ["attestation"]]


class FakeClock:
    def __init__(self, start=NOW):
        self.t = start
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        assert seconds > 0
        self.sleeps.append(seconds)
        self.t += seconds


def _run(tmp_path, deadline_s=300, slice_s=30, **over):
    out = tmp_path / "out"
    digests = _stage(out)
    gh = FakeGh(digests, **over)
    clock = FakeClock()
    res = rr.read_back(VERSION, gh=gh, now=clock.now, sleep=clock.sleep,
                       out=out, repo=REPO, deadline_s=deadline_s,
                       slice_s=slice_s)
    return res, gh, clock, out


# --- the pass and the record ------------------------------------------------

def test_a_matching_release_reads_back_pass_and_is_recorded(tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "publish.json").write_text(
        json.dumps({"tag": TAG, "pushed": True}), encoding="ascii")
    res, gh, clock, out = _run(tmp_path)
    assert res["verdict"] == "PASS", res["reason"]
    assert res["polls"] == 1 and clock.sleeps == []
    assert len(gh.attested()) == 1
    doc = json.loads((out / "publish.json").read_text(encoding="ascii"))
    assert doc["tag"] == TAG and doc["pushed"] is True  # kept
    assert doc["read_back"]["verdict"] == "PASS"
    # the record names what was read back, never a command
    text = " ".join(doc["read_back"]["read"]) + doc["read_back"]["hand_off"]
    assert "immutable" in text and HEAD[:12] in text
    assert "4 asset digests" in text and ZIP in text
    for word in ("gh ", "api", "--repo", "git "):
        assert word not in text


def test_a_lightweight_tag_on_the_stage_commit_passes(tmp_path):
    res, _gh, _c, _o = _run(tmp_path, annotated=False)
    assert res["verdict"] == "PASS", res["reason"]


# --- bounded polling --------------------------------------------------------

def test_polling_waits_in_slices_until_the_release_appears(tmp_path):
    res, _gh, clock, _o = _run(tmp_path, publish_after=3)
    assert res["verdict"] == "PASS"
    assert res["polls"] == 4 and clock.sleeps == [30, 30, 30]


def test_polling_stops_at_the_deadline_with_a_clear_verdict(tmp_path):
    res, _gh, clock, out = _run(tmp_path, release=False, deadline_s=100,
                                slice_s=30)
    assert res["verdict"] == "FAIL"
    assert "timed out after 100 s" in res["reason"]
    assert "not found" in res["reason"]
    assert sum(clock.sleeps) == 100 and max(clock.sleeps) <= 30
    assert clock.t == NOW + 100
    doc = json.loads((out / "publish.json").read_text(encoding="ascii"))
    assert doc["read_back"]["verdict"] == "FAIL"
    assert doc["read_back"]["hand_off"].startswith(TAG + " read-back FAILED")


def test_a_frozen_clock_still_ends(tmp_path):
    out = tmp_path / "out"
    gh = FakeGh(_stage(out), release=False)
    sleeps = []
    res = rr.read_back(VERSION, gh=gh, now=lambda: NOW, sleep=sleeps.append,
                       out=out, repo=REPO, deadline_s=120, slice_s=30)
    assert res["verdict"] == "FAIL" and "timed out" in res["reason"]
    assert res["polls"] == 5 and len(sleeps) == 4


def test_a_draft_release_fails_at_the_deadline(tmp_path):
    res, _gh, _c, _o = _run(tmp_path, draft=True, deadline_s=60)
    assert res["verdict"] == "FAIL"
    assert "draft" in res["reason"] and "timed out" in res["reason"]


def test_gh_missing_ends_at_once(tmp_path):
    res, _gh, clock, _o = _run(tmp_path, installed=False)
    assert res["verdict"] == "FAIL" and "gh is not available" in res["reason"]
    assert clock.sleeps == []


# --- each check fails the read-back ----------------------------------------

def test_a_release_that_is_not_immutable_fails(tmp_path):
    res, gh, clock, _o = _run(tmp_path, immutable=False)
    assert res["verdict"] == "FAIL" and "not immutable" in res["reason"]
    assert clock.sleeps == [] and gh.attested() == []


def test_a_digest_mismatch_fails(tmp_path):
    out = tmp_path / "out"
    digests = _stage(out)
    bad = dict(digests)
    bad["install.ps1"] = "f" * 64
    gh = FakeGh(digests, assets={n: "sha256:" + d for n, d in bad.items()})
    clock = FakeClock()
    res = rr.read_back(VERSION, gh=gh, now=clock.now, sleep=clock.sleep,
                       out=out, repo=REPO)
    assert res["verdict"] == "FAIL"
    assert "install.ps1" in res["reason"] and "digest" in res["reason"]
    assert clock.sleeps == []


def test_an_unstaged_extra_asset_fails(tmp_path):
    out = tmp_path / "out"
    digests = _stage(out)
    more = {n: "sha256:" + d for n, d in digests.items()}
    more["extra.bin"] = "sha256:" + "e" * 64
    gh = FakeGh(digests, assets=more)
    res = rr.read_back(VERSION, gh=gh, now=FakeClock().now,
                       sleep=FakeClock().sleep, out=out, repo=REPO)
    assert res["verdict"] == "FAIL" and "extra.bin" in res["reason"]


def test_a_missing_asset_polls_then_fails(tmp_path):
    out = tmp_path / "out"
    digests = _stage(out)
    fewer = {n: "sha256:" + d for n, d in digests.items() if n != ZIP}
    gh = FakeGh(digests, assets=fewer)
    clock = FakeClock()
    res = rr.read_back(VERSION, gh=gh, now=clock.now, sleep=clock.sleep,
                       out=out, repo=REPO, deadline_s=60, slice_s=30)
    assert res["verdict"] == "FAIL" and "lacks 1 asset" in res["reason"]
    assert clock.sleeps == [30, 30]


def test_a_tag_on_another_commit_fails(tmp_path):
    res, gh, _c, _o = _run(tmp_path, tag_commit=OTHER)
    assert res["verdict"] == "FAIL"
    assert "not the stage commit" in res["reason"]
    assert OTHER[:12] in res["reason"] and gh.attested() == []


def test_a_failed_attestation_verify_fails(tmp_path):
    res, gh, _c, _o = _run(tmp_path, attest_rc=1)
    assert len(gh.attested()) == 1
    assert res["verdict"] == "FAIL"
    assert "attestation of %s did not verify" % ZIP in res["reason"]


def test_a_staged_sums_file_changed_after_stage_fails(tmp_path):
    out = tmp_path / "out"
    digests = _stage(out)
    (out / "SHA256SUMS.txt").write_bytes(b"changed\n")
    gh = FakeGh(digests)
    res = rr.read_back(VERSION, gh=gh, now=FakeClock().now,
                       sleep=FakeClock().sleep, out=out, repo=REPO)
    assert res["verdict"] == "FAIL" and "differs" in res["reason"]
    assert gh.calls == []


# --- the one call from rel_publish -----------------------------------------

class _Git:
    """The git reads the publish gates make, all passing."""

    def __init__(self):
        self.calls = []

    def __call__(self, *a):
        a = list(a)
        self.calls.append(a)
        if a[:3] == ["remote", "get-url", "origin"]:
            return 0, "https://github.com/%s.git\n" % REPO, ""
        if a[:1] == ["rev-parse"] and "--git-common-dir" in a:
            return 0, "", ""
        if a[:3] == ["rev-parse", "-q", "--verify"]:
            return (0, HEAD + "\n", "") if a[3] == "HEAD^{commit}" \
                else (1, "", "")
        if a[:1] == ["status"]:
            return 0, "", ""
        if a[:1] == ["ls-remote"]:
            return 0, "%s\trefs/heads/main\n" % HEAD, ""
        if a[:1] == ["log"]:
            return 0, "Op Erator\x00op@example.com\n", ""
        if a[:2] == ["config", "--local"]:
            return 0, "Op Erator <op@example.com>\n", ""
        if a[:1] == ["tag"]:
            return 0, "", ""
        raise AssertionError("unexpected git call %r" % (a,))


def _publish_ctx(tmp_path, read_back, push_rc=0):
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "docs" / "releases").mkdir(parents=True)
    (root / "config" / "public_repo.json").write_text(
        json.dumps({"repo": REPO}), encoding="ascii")
    (root / "config" / "release.json").write_text(
        json.dumps({"immutable_confirmed": "2026-11-20"}), encoding="ascii")
    (root / "docs" / "releases" / ("%s.md" % VERSION)).write_text(
        "## [%s]\n\nNotes.\n" % VERSION, encoding="ascii")
    out = tmp_path / "out"
    _stage(out)
    clock = FakeClock()
    return rp.make_ctx(
        VERSION, "release " + VERSION, root=root, out=out, git=_Git(),
        gh=lambda *a: (127, "", "gh not installed"),
        push=lambda argv: push_rc, now=clock.now, env={},
        lane_locks=lambda ctx: [], owner="sess.agent",
        changelog_current=lambda r: True, read_back=read_back,
        sleep=clock.sleep)


class _Recorder:
    def __init__(self, verdict="PASS"):
        self.calls = []
        self.verdict = verdict

    def __call__(self, version, **kw):
        self.calls.append((version, kw))
        return {"verdict": self.verdict, "hand_off": "x"}


def test_publish_calls_the_read_back_once_after_the_push(tmp_path):
    rec = _Recorder()
    ctx = _publish_ctx(tmp_path, rec)
    res = rp.run(ctx)
    assert res["refusals"] == [] and res["pushed"] is True
    assert len(rec.calls) == 1
    version, kw = rec.calls[0]
    assert version == VERSION and kw["repo"] == REPO
    assert kw["out"] == ctx["out"] and kw["sleep"] is ctx["sleep"]
    assert res["read_back"]["verdict"] == "PASS"


def test_rehearse_skips_the_read_back(tmp_path):
    rec = _Recorder()
    res = rp.run(_publish_ctx(tmp_path, rec), rehearse=True)
    assert res["refusals"] == [] and res["pushed"] is False
    assert rec.calls == [] and res["read_back"] is None


def test_a_failed_push_skips_the_read_back(tmp_path):
    rec = _Recorder()
    res = rp.run(_publish_ctx(tmp_path, rec, push_rc=1))
    assert res["pushed"] is False and rec.calls == []


def test_publish_with_the_real_read_back_records_the_verdict(tmp_path):
    ctx = _publish_ctx(tmp_path, None)
    res = rp.run(ctx)
    assert res["pushed"] is True
    assert res["read_back"]["verdict"] == "FAIL"
    assert "gh is not available" in res["read_back"]["reason"]
    doc = json.loads((ctx["out"] / "publish.json").read_text(encoding="ascii"))
    assert doc["tag"] == TAG and doc["read_back"]["verdict"] == "FAIL"


def test_default_deadline_is_bounded():
    assert 0 < rr.SLICE_S <= rr.DEADLINE_S <= 3600


@pytest.mark.parametrize("name", ["rel_readback"])
def test_the_tool_is_ascii_and_stdlib_only(name):
    text = (ROOT / "tools" / (name + ".py")).read_bytes()
    text.decode("ascii")
    assert b"\r" not in text
    for bad in (b"import requests", b"import urllib", b"socket"):
        assert bad not in text
