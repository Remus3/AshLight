#!/usr/bin/env python3
"""Publish read-back (REL-PUBLISH-READBACK, F-074, DEP-12, decision 0073).

After tools/rel_publish.py pushed the release tag, CI builds and publishes
the GitHub release on that tag. read_back() then reads back, through gh
only, that what went out is what was staged:

    release      releases/tags/vX.Y.Z exists, is not a draft and reads
                 "immutable": true
    tag          the remote tag (dereferenced when annotated) targets the
                 stage commit of <out>/stage.json
    digests      the release's asset set equals the staged one: every name
                 of the staged SHA256SUMS.txt plus SHA256SUMS.txt itself,
                 each asset digest equal to the staged sha256 (SHA256SUMS.txt
                 against the stage's sums_sha256), no extra asset
    attestation  `gh attestation verify <staged app zip> --repo <repo>`
                 exits 0 (the staged zip has the released digest)

Polling is bounded slices to a deadline (FLEET item 12): while the release
is missing, a draft or still short of assets, one gh read per slice until
the deadline, then a clear FAIL verdict naming the last state; never one
open-ended wait. A frozen clock cannot loop forever: the number of reads is
capped at ceil(deadline / slice) + 1. gh missing (exit 127) ends at once.

The result is written into <out>/publish.json under "read_back" (other keys
kept). It names what was READ BACK (FLEET item 5), never the commands run;
"hand_off" is the one line for the hand-off.

gh, the clock and sleep are injected (tests). Floor: no game access, no
upload, no write to GitHub; gh reads only. Stdlib only.
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path

STAGE_NAME = "stage.json"
PUBLISH_NAME = "publish.json"
SUMS_NAME = "SHA256SUMS.txt"
DEADLINE_S = 30 * 60
SLICE_S = 30
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SUMS_LINE = re.compile(r"^([0-9a-f]{64})  (\S.*)$")


class Fail(Exception):
    """A read-back check failed; the text names what was read."""


class NotYet(Exception):
    """The release is not there yet; polling goes on to the deadline."""


def _gh3(gh, *args):
    got = gh(*args)
    if len(got) == 2:
        return got[0], got[1], ""
    return got


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def parse_sums(text):
    """{name: sha256} of SHA256SUMS.txt text; a bad line raises Fail."""
    found = {}
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        m = _SUMS_LINE.match(line)
        if not m:
            raise Fail("the staged %s has a bad line" % SUMS_NAME)
        found[m.group(2)] = m.group(1)
    return found


def staged(version, out):
    """{commit, sums_sha256, digests: {name: sha256}, zip} from the stage
    folder; raises Fail when it does not hold a usable stage."""
    out = Path(out)
    rep = _read_json(out / STAGE_NAME)
    if not isinstance(rep, dict) or rep.get("version") != version:
        raise Fail("no stage report of %s to compare with" % version)
    commit = str(rep.get("commit") or "")
    sums = str(rep.get("sums_sha256") or "")
    if not re.match(r"^[0-9a-f]{40}$", commit) or not _HEX64.match(sums):
        raise Fail("the stage report has no commit or sums_sha256")
    try:
        data = (out / SUMS_NAME).read_bytes()
    except OSError:
        raise Fail("no staged %s" % SUMS_NAME)
    if hashlib.sha256(data).hexdigest() != sums:
        raise Fail("the staged %s differs from the stage report" % SUMS_NAME)
    digests = parse_sums(data.decode("ascii", "replace"))
    digests[SUMS_NAME] = sums
    zips = sorted(n for n in digests if n.endswith("-app.zip"))
    if len(zips) != 1:
        raise Fail("the staged %s names no single app zip" % SUMS_NAME)
    return {"commit": commit, "sums_sha256": sums, "digests": digests,
            "zip": out / zips[0], "zip_name": zips[0]}


def _api(gh, path):
    """The JSON of one gh api read; NotYet on 404 or a passing error,
    Fail when gh is not installed."""
    rc, out, err = _gh3(gh, "api", path)
    if rc == 127:
        raise Fail("gh is not available, nothing could be read back")
    if rc != 0:
        if "404" in (err or "") or "Not Found" in (err or ""):
            raise NotYet("%s not found yet" % path.split("/", 3)[-1])
        raise NotYet("gh could not read %s (exit %s)"
                     % (path.split("/", 3)[-1], rc))
    try:
        doc = json.loads(out)
    except ValueError:
        raise NotYet("gh returned unreadable JSON")
    if not isinstance(doc, dict):
        raise NotYet("gh returned an unexpected shape")
    return doc


def read_release(gh, repo, tag):
    """The release object once it is published; NotYet while it is missing
    or a draft."""
    doc = _api(gh, "repos/%s/releases/tags/%s" % (repo, tag))
    if doc.get("draft") is not False:
        raise NotYet("release %s is a draft" % tag)
    return doc


def tag_commit(gh, repo, tag):
    """The commit the remote tag targets (an annotated tag dereferenced,
    at most 4 levels)."""
    ref = _api(gh, "repos/%s/git/ref/tags/%s" % (repo, tag))
    obj = ref.get("object") or {}
    for _ in range(4):
        kind, sha = obj.get("type"), str(obj.get("sha") or "")
        if kind == "commit":
            return sha
        if kind != "tag" or not sha:
            raise Fail("the tag %s points at a %s" % (tag, kind))
        obj = (_api(gh, "repos/%s/git/tags/%s" % (repo, sha))
               .get("object") or {})
    raise Fail("the tag %s is nested too deep" % tag)


def check_assets(release, want):
    """Fail unless the release's assets equal want {name: sha256} by name
    and digest; NotYet while names are still missing."""
    have = {}
    for asset in release.get("assets") or []:
        if isinstance(asset, dict) and asset.get("name"):
            have[str(asset["name"])] = str(asset.get("digest") or "")
    extra = sorted(set(have) - set(want))
    if extra:
        raise Fail("the release holds an asset that was not staged: %s"
                   % extra[0])
    missing = sorted(set(want) - set(have))
    if missing:
        raise NotYet("the release lacks %d asset(s), first: %s"
                     % (len(missing), missing[0]))
    for name in sorted(want):
        digest = have[name]
        if digest.lower().startswith("sha256:"):
            digest = digest[7:]
        if digest.lower() != want[name]:
            raise Fail("asset %s: the release digest differs from the "
                       "staged sha256" % name)
    return len(want)


def verify_attestation(gh, zip_path, repo):
    rc, _out, err = _gh3(gh, "attestation", "verify", str(zip_path),
                         "--repo", repo)
    if rc != 0:
        first = (err or "").strip().splitlines()[:1]
        raise Fail("the attestation of %s did not verify%s"
                   % (Path(zip_path).name,
                      (": " + first[0][:120]) if first else ""))


def _once(gh, repo, tag, stage):
    """One full read; returns the list of read-back lines or raises."""
    release = read_release(gh, repo, tag)
    count = check_assets(release, stage["digests"])
    if release.get("immutable") is not True:
        raise Fail("release %s is published but not immutable" % tag)
    commit = tag_commit(gh, repo, tag)
    if commit != stage["commit"]:
        raise Fail("the tag %s targets %s, not the stage commit %s"
                   % (tag, commit[:12], stage["commit"][:12]))
    verify_attestation(gh, stage["zip"], repo)
    return ["release %s published and immutable" % tag,
            "tag %s targets the stage commit %s" % (tag, commit[:12]),
            "%d asset digests equal the staged ones" % count,
            "attestation verified for %s" % stage["zip_name"]]


def _write(out, record):
    path = Path(out) / PUBLISH_NAME
    doc = _read_json(path)
    doc = doc if isinstance(doc, dict) else {}
    doc["read_back"] = record
    tmp = path.with_name(path.name + ".partial")
    try:
        tmp.write_bytes((json.dumps(doc, indent=1, sort_keys=True) + "\n")
                        .encode("ascii"))
        os.replace(str(tmp), str(path))
    except OSError:
        return False
    return True


def _stamp(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(seconds)))


def read_back(version, gh, now=time.time, sleep=time.sleep, out=None,
              repo=None, deadline_s=DEADLINE_S, slice_s=SLICE_S, write=True):
    """Poll in bounded slices until the release reads back or the deadline
    passes. Returns {verdict PASS|FAIL, read: [lines], reason, polls,
    started, ended, hand_off}; written into <out>/publish.json."""
    tag = "v" + version
    start = now()
    record = {"verdict": "FAIL", "read": [], "reason": "", "polls": 0,
              "started": _stamp(start), "deadline_s": deadline_s}
    max_polls = int(-(-deadline_s // max(slice_s, 1))) + 1
    try:
        if not repo:
            raise Fail("no repository address to read back from")
        if out is None:
            raise Fail("no stage folder to compare with")
        stage = staged(version, out)
        last = ""
        while True:
            record["polls"] += 1
            try:
                record["read"] = _once(gh, repo, tag, stage)
                record["verdict"] = "PASS"
                break
            except NotYet as exc:
                last = str(exc)
            left = start + deadline_s - now()
            if left <= 0 or record["polls"] >= max_polls:
                raise Fail("timed out after %d s (%d reads): %s"
                           % (deadline_s, record["polls"], last))
            sleep(min(slice_s, left))
    except Fail as exc:
        record["reason"] = str(exc)
    record["ended"] = _stamp(now())
    if record["verdict"] == "PASS":
        record["hand_off"] = "%s read back: %s" % (tag, "; ".join(
            record["read"]))
    else:
        record["hand_off"] = "%s read-back FAILED: %s" % (tag,
                                                          record["reason"])
    if write and out is not None:
        record["written"] = _write(out, record)
    return record
