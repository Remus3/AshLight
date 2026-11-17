"""TC-DRIFT: watch Path of Building PoE2 releases against the pin.

Decision 0004 item 3, decision 0018, decision 0025. Python stdlib only.

- `check`: one read-only GET of the GitHub releases API (api.github.com only,
  truthful User-Agent, no cookie, no token) compares the newest PoB-PoE2
  release with config/tc_pins.json. At most one check per CHECK_EVERY_S;
  X-RateLimit-Reset / Retry-After push the next check out. State lives in the
  gitignored ops/runtime/tc_drift.json.
- `loop_check`: the al_loop tick hook. Silent until a check is due; on a new
  tag it launches ONE detached `trial` for that tag and reports one line.
- `trial --tag vX.Y.Z`: resolves the tag's commit, downloads the commit
  archive twice (both SHA-256 and sizes must agree, as decision 0018 requires
  for a pin), writes a candidate pin file in the sidecar, runs the opt-in
  setup step on it (tools/tc_pin.py) and the bridge tests against it
  (AL_TC_PINS_FILE). Verdict: green (every test passed and live tests ran),
  red, untested (the live tests skipped: no luajit.exe on this host) or error.
- `apply`: writes the green candidate into config/tc_pins.json (the pin moves
  in one commit by whoever commits it); refuses without a green trial.
- `note`: the dated HOLD line for decision 0004 when the pin stays.

Nothing from an archive is imported here; the bridge tests run in a
subprocess. Exit codes: 0 ok, 1 failure, 2 refused.
"""

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tc_pin  # noqa: E402
from server.al import paths, webfetch  # noqa: E402

API_HOSTS = ("api.github.com",)
API = "https://api.github.com/repos/{repo}"
UA_PURPOSE = "dev: Path of Building PoE2 release drift check"
PINS_ENV = paths.TC_PINS_ENV
CHECK_EVERY_S = 24 * 3600
RETRY_S = 3 * 3600
RATE_DEFAULT_S = 3600
TRIAL_STALE_S = 6 * 3600
TRIAL_MAX_LAUNCHES = 3
TRIAL_TESTS = ("tests/test_tc_bridge.py", "tests/test_tc_delta.py")
TRIAL_TIMEOUT_S = 3600
MAX_ARCHIVE = 2 * 1024 ** 3
API_MAX_BYTES = 256 * 1024
STATE_REL = Path("ops") / "runtime" / "tc_drift.json"

_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")

RC_OK, RC_FAIL, RC_REFUSED = 0, 1, 2


class DriftError(Exception):
    """A drift step refused (no green trial, bad candidate)."""


class RateLimited(webfetch.FetchError):
    """GitHub asked us to wait; `until` is the epoch of the next allowed call."""

    def __init__(self, until):
        super().__init__(f"rate limited until {int(until)}")
        self.until = until


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))


# --- tags ---------------------------------------------------------------

def parse_tag(tag):
    m = _TAG.match(tag) if isinstance(tag, str) else None
    return tuple(int(x) for x in m.groups()) if m else None


def compare(pinned, latest):
    """current / new / behind / unknown (latest vs the pinned tag)."""
    a, b = parse_tag(pinned), parse_tag(latest)
    if a is None or b is None:
        return "unknown"
    if b == a:
        return "current"
    return "new" if b > a else "behind"


# --- GitHub reads (read-only GETs) --------------------------------------

def _headers(accept):
    return {"User-Agent": webfetch.user_agent(UA_PURPOSE), "Accept": accept}


def _get(url, accept, fetch, now):
    status, hdrs, body = webfetch.request("GET", url, _headers(accept), API_HOSTS,
                                          fetch=fetch, max_bytes=API_MAX_BYTES)
    if status in (403, 429):
        until = None
        reset = webfetch.header(hdrs, "X-RateLimit-Reset")
        after = webfetch.header(hdrs, "Retry-After")
        if after and after.strip().isdigit():
            until = now + int(after.strip())
        if reset and reset.strip().isdigit() and webfetch.header(
                hdrs, "X-RateLimit-Remaining") == "0":
            until = max(until or 0, float(reset.strip()))
        if until is None and status == 429:
            until = now + RATE_DEFAULT_S
        if until is not None:
            raise RateLimited(until)
    if status != 200:
        raise webfetch.FetchError(f"HTTP {status} from {url}")
    return body or b""


def latest_release(repo, fetch=None, now=None):
    """{"tag", "published", "draft", "prerelease"} of the newest release."""
    now = time.time() if now is None else now
    body = _get(API.format(repo=repo) + "/releases/latest",
                "application/vnd.github+json", fetch, now)
    try:
        doc = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise webfetch.FetchError(f"releases reply unreadable: {e}") from e
    tag = doc.get("tag_name") if isinstance(doc, dict) else None
    if not isinstance(tag, str):
        raise webfetch.FetchError("releases reply has no tag_name")
    return {"tag": tag, "published": doc.get("published_at"),
            "draft": bool(doc.get("draft")), "prerelease": bool(doc.get("prerelease"))}


def resolve_commit(repo, tag, fetch=None, now=None):
    """The full commit sha the release tag points at."""
    if parse_tag(tag) is None:
        raise ValueError(f"not a release tag: {tag!r}")
    now = time.time() if now is None else now
    body = _get(API.format(repo=repo) + f"/commits/{tag}",
                "application/vnd.github.sha", fetch, now)
    sha = body.decode("ascii", "replace").strip()
    if not _HEX40.match(sha):
        raise webfetch.FetchError(f"tag {tag} did not resolve to a commit sha")
    return sha


# --- state --------------------------------------------------------------

def state_file(root):
    return Path(root) / STATE_REL


def load_state(root):
    try:
        doc = json.loads(state_file(root).read_text(encoding="ascii"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(root, st):
    p = state_file(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(st, indent=1, sort_keys=True) + "\n", encoding="ascii")
    os.replace(tmp, p)


def _pins(root):
    return tc_pin.load_pins(Path(root) / "config" / "tc_pins.json")


# --- check --------------------------------------------------------------

def check(root, now, fetch=None):
    """One release check; returns and saves the state."""
    doc = _pins(root)
    pob = doc["pob2"]
    st = load_state(root)
    st.update({"checked": iso(now), "pinned": pob["tag"], "repo": pob["repo"]})
    try:
        rel = latest_release(pob["repo"], fetch=fetch, now=now)
    except RateLimited as e:
        st.update({"status": "rate-limited", "next_check": e.until, "error": str(e)})
        save_state(root, st)
        return st
    except webfetch.FetchError as e:
        st.update({"status": "error", "next_check": now + RETRY_S, "error": str(e)})
        save_state(root, st)
        return st
    st.pop("error", None)
    st.update({"latest": rel["tag"], "published": rel["published"],
               "status": compare(pob["tag"], rel["tag"]),
               "next_check": now + CHECK_EVERY_S})
    save_state(root, st)
    return st


def _trial_due(st, now):
    tr = st.get("trial") or {}
    if tr.get("tag") != st.get("latest"):
        return True
    if tr.get("state") != "launched":
        return False
    stale = now - float(tr.get("at_epoch") or 0) > TRIAL_STALE_S
    return stale and int(tr.get("launches") or 0) < TRIAL_MAX_LAUNCHES


def summary(st):
    status, pinned, latest = st.get("status"), st.get("pinned"), st.get("latest")
    if status == "current":
        return f"tc drift: PoB-PoE2 {pinned} current"
    if status == "rate-limited":
        return f"tc drift: rate limited, next check {iso(st['next_check'])}"
    if status == "error":
        return f"tc drift: check failed: {st.get('error')}"
    if status == "new":
        tr = st.get("trial") or {}
        if tr.get("state") == "launched":
            return f"tc drift: PoB-PoE2 {latest} released (pin {pinned}), trial launched"
        if tr.get("verdict") == "green":
            return (f"tc drift: PoB-PoE2 {latest} trial green, pin move ready "
                    "(tools/tc_drift.py apply)")
        return f"tc drift: PoB-PoE2 {latest} trial {tr.get('verdict') or tr.get('state')}, hold"
    return f"tc drift: latest {latest} vs pin {pinned}: {status}, hold"


def loop_check(root, now, fetch=None, launch=None):
    """The al_loop tick hook: None when no check is due (or no pin file);
    else one summary line. A new tag launches one detached trial."""
    if not (Path(root) / "config" / "tc_pins.json").is_file():
        return None
    st = load_state(root)
    if now < float(st.get("next_check") or 0):
        return None
    try:
        st = check(root, now, fetch=fetch)
    except tc_pin.PinError as e:
        return f"tc drift: pin file refused: {e}"
    if st.get("status") == "new" and _trial_due(st, now):
        prev = st.get("trial") or {}
        n = int(prev.get("launches") or 0) + 1 if prev.get("tag") == st["latest"] else 1
        launch = launch or launch_trial
        try:
            pid = launch(root, st["latest"])
        except OSError as e:
            return f"tc drift: {st['latest']} released, trial launch failed: {e}"
        st["trial"] = {"tag": st["latest"], "state": "launched", "at": iso(now),
                       "at_epoch": now, "launches": n, "pid": pid}
        save_state(root, st)
    return summary(st)


def launch_trial(root, tag):
    """A detached, windowless `tc_drift.py trial --tag <tag>`; returns its pid."""
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    exe = pyw if pyw.is_file() else exe
    logs = paths.all_runtime_paths()["logs"]
    logs.mkdir(parents=True, exist_ok=True)
    flags = 0
    if os.name == "nt":
        flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                 | subprocess.CREATE_NO_WINDOW)
    with open(logs / "tc-drift.log", "ab") as out:
        proc = subprocess.Popen([str(exe), str(Path(root) / "tools" / "tc_drift.py"),
                                 "trial", "--tag", tag], cwd=str(root),
                                stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                                creationflags=flags, close_fds=True)
    return proc.pid


# --- trial --------------------------------------------------------------

def candidate(doc, tag, commit, sha256, size, today):
    """The pin document with PoB-PoE2 moved to tag / commit (LuaJIT kept)."""
    out = copy.deepcopy(doc)
    pob = out["pob2"]
    name = pob["repo"].split("/")[1]
    pob.update({"tag": tag, "commit": commit,
                "archive_url": f"https://github.com/{pob['repo']}/archive/{commit}.zip",
                "archive_sha256": sha256, "archive_size": size,
                "top_dir": f"{name}-{commit}", "verified": today})
    return out


def parse_junit(text):
    """{"tests", "failures", "errors", "skipped", "live_ran"} of a junit xml."""
    root = ET.fromstring(text)
    out = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "live_ran": 0}
    for case in root.iter("testcase"):
        out["tests"] += 1
        kinds = {child.tag for child in case}
        if "skipped" in kinds:
            out["skipped"] += 1
            continue
        if "failure" in kinds:
            out["failures"] += 1
        if "error" in kinds:
            out["errors"] += 1
        if case.get("name", "").startswith("test_live"):
            out["live_ran"] += 1
    return out


def download_measure(url, dest):
    """Stream url into dest; (sha256, size)."""
    h, size = hashlib.sha256(), 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with open(part, "wb") as f:
        for block in tc_pin.http_stream(url, MAX_ARCHIVE):
            h.update(block)
            size += len(block)
            f.write(block)
    os.replace(part, dest)
    return h.hexdigest(), size


def run_bridge_tests(cand_path, junit_path, environ):
    """The bridge tests against the candidate pins, in a subprocess."""
    env = dict(os.environ)
    env.update(environ or {})
    env[PINS_ENV] = str(cand_path)
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            *TRIAL_TESTS, f"--junitxml={junit_path}"]
    subprocess.run(argv, cwd=str(ROOT), env=env, timeout=TRIAL_TIMEOUT_S,
                   stdin=subprocess.DEVNULL, capture_output=True)
    return parse_junit(Path(junit_path).read_text(encoding="utf-8"))


def _verdict(res):
    if res["failures"] or res["errors"]:
        return "red", f"{res['failures']} failed, {res['errors']} errors of {res['tests']}"
    if not res["live_ran"]:
        return "untested", (f"live bridge tests skipped ({res['skipped']} skipped): "
                            "no luajit.exe on this host")
    return "green", f"{res['tests']} tests, {res['live_ran']} live, all passed"


def trial(root, tag, environ=None, fetch=None, download=None, setup=None,
          run_tests=None, today=None):
    """Trial the bridge tests on `tag`; records and returns the result."""
    download = download or download_measure
    setup = setup or (lambda doc, env: tc_pin.run_setup(doc, environ=env))
    run_tests = run_tests or run_bridge_tests
    today = today or time.strftime("%Y-%m-%d")
    doc = _pins(root)
    work = paths.all_runtime_paths(environ)["build"] / "tc-drift"
    res = {"tag": tag, "state": "done", "at": iso(time.time())}
    try:
        commit = resolve_commit(doc["pob2"]["repo"], tag, fetch=fetch)
        name = doc["pob2"]["repo"].split("/")[1]
        url = f"https://github.com/{doc['pob2']['repo']}/archive/{commit}.zip"
        archive = paths.all_runtime_paths(environ)["pob2_cache"] / f"{name}-{commit}.zip"
        first = download(url, archive)
        check_copy = work / f"{name}-{commit}.check.zip"
        second = download(url, check_copy)
        try:
            check_copy.unlink()  # a re-downloadable copy, only for the hash check
        except OSError:
            pass
        if first != second:
            raise DriftError(f"two downloads of {tag} differ: {first} vs {second}")
        cand = candidate(doc, tag, commit, first[0], first[1], today)
        problems = tc_pin.validate_pins(cand)
        if problems:
            raise DriftError("candidate pins invalid: " + "; ".join(problems))
        work.mkdir(parents=True, exist_ok=True)
        cand_path = work / f"{tag}-pins.json"
        cand_path.write_text(json.dumps(cand, indent=2) + "\n", encoding="ascii")
        res["candidate"] = str(cand_path)
        setup(cand, environ)
        tests = run_tests(cand_path, work / f"{tag}-junit.xml", environ)
        res["tests"] = tests
        res["verdict"], res["detail"] = _verdict(tests)
    except (DriftError, webfetch.FetchError, tc_pin.HashMismatch, tc_pin.UnsafeArchive,
            OSError, RuntimeError, ValueError, ET.ParseError,
            subprocess.SubprocessError) as e:
        res["verdict"], res["detail"] = "error", f"{type(e).__name__}: {e}"
    st = load_state(root)
    prev = st.get("trial") or {}
    if prev.get("tag") == tag:
        res["launches"] = prev.get("launches", 1)
    st["trial"] = res
    save_state(root, st)
    return res


# --- apply / note -------------------------------------------------------

def apply(root):
    """Move config/tc_pins.json to the green trial's candidate; the tag."""
    st = load_state(root)
    tr = st.get("trial") or {}
    if tr.get("verdict") != "green" or not tr.get("candidate"):
        raise DriftError(f"no green trial to apply (trial: {tr.get('verdict') or 'none'})")
    cand = json.loads(Path(tr["candidate"]).read_text(encoding="ascii"))
    problems = tc_pin.validate_pins(cand)
    if problems or cand["pob2"]["tag"] != tr["tag"]:
        raise DriftError("candidate pins invalid: " + "; ".join(problems or ["tag mismatch"]))
    pins = Path(root) / "config" / "tc_pins.json"
    text = json.dumps(cand, indent=2) + "\n"
    tmp = pins.with_name(pins.name + ".tmp")
    with open(tmp, "w", encoding="ascii", newline="\n") as f:
        f.write(text)
    os.replace(tmp, pins)
    tr["state"] = "applied"
    st["trial"] = tr
    save_state(root, st)
    return tr["tag"]


def hold_note(st):
    """The dated HOLD line for decision 0004 when the pin stays."""
    tr = st.get("trial") or {}
    date = (tr.get("at") or st.get("checked") or iso(time.time()))[:10]
    if st.get("trial") and tr.get("tag") == st.get("latest"):
        date = (st.get("checked") or tr.get("at") or "")[:10] or date
        return (f"{date} HOLD: PoB-PoE2 {tr['tag']} trial {tr.get('verdict')} "
                f"({tr.get('detail')}); pin stays {st.get('pinned')}.")
    return (f"{date} HOLD: no PoB-PoE2 release after {st.get('pinned')} "
            f"(latest {st.get('latest')}); pin stays.")


# --- CLI ----------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="tc_drift", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="one release check now (ignores the daily throttle)")
    t = sub.add_parser("trial", help="trial the bridge tests on a release tag")
    t.add_argument("--tag", required=True)
    sub.add_parser("apply", help="move the pin to the green trial's candidate")
    sub.add_parser("note", help="print the dated HOLD line for decision 0004")
    sub.add_parser("status", help="print the drift state")
    args = ap.parse_args(argv)
    root = ROOT
    try:
        if args.cmd == "check":
            st = check(root, time.time())
            print(summary(st))
            return RC_FAIL if st.get("status") in ("error", "rate-limited") else RC_OK
        if args.cmd == "trial":
            res = trial(root, args.tag)
            print(f"trial {args.tag}: {res['verdict']}: {res['detail']}")
            return RC_OK if res["verdict"] == "green" else RC_FAIL
        if args.cmd == "apply":
            print(f"pin moved to PoB-PoE2 {apply(root)}; commit config/tc_pins.json")
            return RC_OK
        if args.cmd == "note":
            print(hold_note(load_state(root)))
            return RC_OK
        print(json.dumps(load_state(root), indent=1, sort_keys=True))
        return RC_OK
    except (DriftError, tc_pin.PinError) as e:
        print(f"refused: {e}")
        return RC_REFUSED


if __name__ == "__main__":
    sys.exit(main())
