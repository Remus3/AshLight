"""AUTO-09 (ELECTRON-WATCH, F-130; W8 of docs/plan/06; decisions 0068,
0069, 0070 item 2): the npm advisory watcher.

What it runs: `npm audit --package-lock-only --json --prefix app` against
the tracked lockfile, once per 24 h, hidden and at below-normal priority,
only while web_data is on (the frame never calls a gated source otherwise;
the check also refuses with WebDataOff itself, so a direct call while off
starts nothing). npm is the one that makes the request (the advisory bulk
endpoint listed in SOURCE['urls']); the frame's fetch is never used.

When it is idle (returns no finding, starts nothing):
- no tree: ctx["root"] absent and ctx["live"] not true;
- app/.npmrc has no user-agent line naming AshLight (unit F-037; strict
  reading of A-02: npm must name AshLight before it may ask anything);
- no app/package-lock.json;
- no runner: ctx["npm_audit"] absent and ctx["live"] not true. The real
  subprocess (run_npm_audit) starts only when ctx["live"] is true, so loop
  tests on scratch roots stay hermetic; a test injects
  ctx["npm_audit"](argv, cwd) -> (returncode, stdout text).

Finding (kind "npmaudit", row NPM-AUDIT-<PKG>-<YYYYMMDD>, lane data,
'(priority)' so the soft budget gate never holds it): one per package of
the audit's "vulnerabilities" map that carries an advisory of its own (a
"via" object, not only a chain through another package); every package in
the lockfile is pinned by it, so every such package counts. Key: the
package name plus its advisory ids, so a new advisory on the same package
files again and the same one never twice. Row text comes from
ops/loop/watch_rows/electron.json.

Python stdlib only.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import watch_gate  # noqa: E402

NAME = "npm-audit"
KIND = "npmaudit"
ADVISORY_URL = "https://registry.npmjs.org/-/npm/v1/security/advisories/bulk"
ARGV = ("audit", "--package-lock-only", "--json", "--prefix", "app")
NPMRC_REL = Path("app") / ".npmrc"
LOCK_REL = Path("app") / "package-lock.json"
DAY_S = 24 * 3600
TIMEOUT_S = 120
OUT_MAX = 4 * 1024 * 1024
KEY_MAX = 200
SEVERITIES = ("low", "moderate", "high", "critical")
# Windows: no console window, below-normal priority (decision 0069 frame).
CREATE_NO_WINDOW = 0x08000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
UA_LINE_RX = re.compile(r"^\s*user-agent\s*=\s*AshLight/", re.MULTILINE)


def _uw():
    import upstream_watch  # the frame; on sys.path whenever a source runs
    return upstream_watch


def _root(ctx):
    if ctx.get("root") is not None:
        return Path(ctx["root"])
    return ROOT if ctx.get("live") else None


def npmrc_ready(root):
    """True when app/.npmrc sends the AshLight User-Agent (F-037)."""
    try:
        text = (Path(root) / NPMRC_REL).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return UA_LINE_RX.search(text) is not None


def run_npm_audit(argv, cwd):
    """The real runner: npm audit, hidden, below-normal priority, bounded.
    (returncode, stdout text). npm exits non-zero when it finds an
    advisory, so the exit code alone is no failure."""
    npm = shutil.which("npm")
    if not npm:
        raise _uw().SourceError("workflow", "npm not found on PATH")
    flags = 0
    if os.name == "nt":
        flags = CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS
    proc = subprocess.run([npm, *argv], cwd=str(cwd), capture_output=True,
                          timeout=TIMEOUT_S, creationflags=flags,
                          stdin=subprocess.DEVNULL, check=False)
    out = (proc.stdout or b"")[:OUT_MAX]
    return proc.returncode, out.decode("utf-8", "replace")


def _runner(ctx):
    if "npm_audit" in ctx:
        return ctx["npm_audit"]
    return run_npm_audit if ctx.get("live") else None


def pkg_id(name):
    """electron -> ELECTRON, @electron/get -> ELECTRON-GET (row id part)."""
    return re.sub(r"[^A-Z0-9]+", "-", str(name).upper()).strip("-")[:40]


def pkg_word(name):
    """electron -> electron, @electron/get -> electron.get (a short word)."""
    return re.sub(r"[^A-Za-z0-9._-]+", ".", str(name).lstrip("@")).strip(".")[:64]


def _advisory_id(adv):
    for key in ("source", "url", "title"):
        val = adv.get(key)
        if isinstance(val, (int, str)) and not isinstance(val, bool) and str(val):
            return re.sub(r"[^A-Za-z0-9._:/-]+", "", str(val))[:60]
    return "unknown"


def findings(report):
    """The npmaudit findings of one parsed `npm audit --json` report."""
    uw = _uw()
    if not isinstance(report, dict):
        raise uw.SourceError("shape", "npm audit output is not an object")
    if "error" in report and "vulnerabilities" not in report:
        raise uw.SourceError("status", "npm audit reported an error")
    vulns = report.get("vulnerabilities", {})
    if not isinstance(vulns, dict):
        raise uw.SourceError("shape", "vulnerabilities is not an object")
    out = []
    for name in sorted(vulns):
        rec = vulns[name]
        if not isinstance(rec, dict) or not isinstance(rec.get("via"), list):
            continue
        own = [v for v in rec["via"] if isinstance(v, dict)]
        if not own:
            continue  # only a chain through another package
        sev = [v.get("severity") for v in own if v.get("severity") in SEVERITIES]
        if not sev and rec.get("severity") in SEVERITIES:
            sev = [rec["severity"]]
        if not sev:
            continue  # "info" only
        pid, word = pkg_id(name), pkg_word(name)
        if not pid or not word:
            continue
        ids = sorted({_advisory_id(v) for v in own})
        key = f"{name}:{','.join(ids)}"
        key = key.encode("ascii", "replace").decode("ascii")[:KEY_MAX]
        out.append({"kind": KIND, "key": key,
                    "tokens": {"PKG": pid, "package": word,
                               "severity": max(sev, key=SEVERITIES.index)}})
    return out


def check(state, now, fetch, ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    root = _root(ctx)
    if root is None:
        return []
    if not watch_gate.web_data_on(root):
        raise watch_gate.WebDataOff("web data is off (opt-in setting web_data)")
    if not npmrc_ready(root) or not (Path(root) / LOCK_REL).is_file():
        state["data"] = {"idle": "no app/.npmrc user-agent or no lockfile"}
        return []
    runner = _runner(ctx)
    if runner is None:
        return []
    _code, text = runner(list(ARGV), Path(root))
    try:
        report = json.loads(text or "")
    except (ValueError, TypeError):
        raise _uw().SourceError("shape", "npm audit output is not JSON") from None
    found = findings(report)
    state["data"] = {"advisories": len(found)}
    return found


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": DAY_S,
    "window": None,
    "needs_web_data": True,
    "hosts": [],
    "urls": [ADVISORY_URL],
    "purpose": "dev: watcher npm-audit",
    "check": check,
}
