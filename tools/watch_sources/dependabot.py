"""AUTO-20 (DEPBOT-WATCH, F-150; decisions 0069, 0076; FLEET item 17): the
Dependabot watcher. Dependabot alerts and open Dependabot pull requests of
the project's repository become ROADMAP rows through the loop's daily check.

A network source on api.github.com, gated on web data like every new
source (the frame never calls it while web data is off; the check also
raises WebDataOff itself, so a direct call while off starts nothing). The
alert list needs an authenticated read, which the frame's anonymous fetch
cannot give, so the two reads go through the GitHub CLI already used by
tools/dependabot_reapply.py in the main checkout (as npm-audit runs npm):
`gh api` with the AshLight User-Agent, hidden, below-normal priority,
bounded, and only for the two URLs that pass watch_gate.check_url (the
/dependabot/alerts and /pulls tails, decision 0069 amendment 2026-11-27).
The real gh starts only when ctx["live"] is true; tests inject
ctx["gh"](argv, cwd) -> (returncode, stdout text). The frame's fetch is
never used. No new workflow: the dev loop does this read.

The repository comes from the checkout's own remote (ci_issues.repository:
ctx["remote_url"] in tests, `git remote get-url origin` only while live);
no github.com remote means no request and nothing filed.

Findings (templates ops/loop/watch_rows/dependabot.json):
- depbotalert: one per open alert whose package is a name in the tracked
  app/package-lock.json and whose GHSA id, upper-cased, matches
  GHSA(-[0-9A-Z]{4}){3}. Row DEPBOT-<PACKAGE>-<GHSA>, lane data,
  '(priority)', so the soft budget gate never holds it. Key
  'alert:<package>:<GHSA>'.
- depbotpr: one per open pull request whose author is the Dependabot app
  (user login dependabot[bot], type Bot), open for at least PR_AGE_S (the
  daily re-apply worker, tools/loop_depbot.py, had its turn first), and
  whose bumped package is not named by an alert finding of this run (the
  advisory row covers it). Row DEPBOT-PR-<n>. Key 'pr:<n>'.
Nothing is merged on GitHub: a row's work is
`python tools/dependabot_reapply.py apply <n>` or a lockfile bump.

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
from watch_sources import ci_issues  # noqa: E402

NAME = "dependabot"
API = "https://api.github.com/repos/"
ALERTS_TAIL = "/dependabot/alerts?state=open&per_page=100"
PULLS_TAIL = "/pulls?state=open&per_page=100"
LOCK_REL = Path("app") / "package-lock.json"
DAY_S = 24 * 3600
PR_AGE_S = 2 * DAY_S
TIMEOUT_S = 60
OUT_MAX = 4 * 1024 * 1024
BOT_LOGIN = "dependabot[bot]"
GHSA_RX = re.compile(r"GHSA(?:-[0-9A-Z]{4}){3}")
PKG_RX = re.compile(r"[A-Za-z0-9@][A-Za-z0-9._/@-]{0,213}")
BUMP_RX = re.compile(r"^[Bb]ump (\S+) from ")
SEVERITIES = {"low": "low", "medium": "moderate", "moderate": "moderate",
              "high": "high", "critical": "critical"}
CREATE_NO_WINDOW = 0x08000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


def _uw():
    import upstream_watch
    return upstream_watch


def _root(ctx):
    if ctx.get("root") is not None:
        return Path(ctx["root"])
    return ROOT if ctx.get("live") else None


def run_gh(argv, cwd):
    """The real runner: gh api, hidden, below-normal priority, bounded."""
    gh = shutil.which("gh")
    if not gh:
        raise _uw().SourceError("workflow", "gh not found on PATH")
    flags = CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0
    proc = subprocess.run([gh, *argv], cwd=str(cwd), capture_output=True,
                          timeout=TIMEOUT_S, creationflags=flags,
                          stdin=subprocess.DEVNULL, check=False)
    return proc.returncode, (proc.stdout or b"")[:OUT_MAX].decode("utf-8", "replace")


def _runner(ctx):
    if "gh" in ctx:
        return ctx["gh"]
    return run_gh if ctx.get("live") else None


def lock_names(root):
    """The package names of the tracked lockfile (empty when unreadable)."""
    try:
        doc = json.loads((Path(root) / LOCK_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return set()
    pkgs = doc.get("packages") if isinstance(doc, dict) else None
    if not isinstance(pkgs, dict):
        return set()
    return {k.rsplit("node_modules/", 1)[1] for k in pkgs
            if isinstance(k, str) and "node_modules/" in k}


def pkg_id(name):
    """@electron/get -> ELECTRON-GET (row id part)."""
    return re.sub(r"[^A-Z0-9]+", "-", str(name).upper()).strip("-")[:40]


def pkg_word(name):
    """@electron/get -> electron.get (a short word)."""
    return re.sub(r"[^A-Za-z0-9._-]+", ".", str(name).lstrip("@")).strip(".")[:64]


def read(runner, root, repo, tail):
    """One gated gh read of API + repo + tail; the parsed JSON list."""
    uw = _uw()
    url = API + repo + tail
    watch_gate.check_url(SOURCE, url)  # UrlNotAllowed before any process
    ua = "User-Agent: " + watch_gate.webfetch.user_agent(watch_gate.purpose(SOURCE))
    argv = ["api", "--method", "GET", "-H", "Accept: application/vnd.github+json",
            "-H", ua, url[len("https://api.github.com/"):]]
    code, text = runner(argv, Path(root))
    if code != 0:
        raise uw.SourceError("status", f"gh api exited {code} for {tail.split('?')[0]}")
    try:
        doc = json.loads(text or "")
    except (ValueError, TypeError):
        raise uw.SourceError("shape", "gh api output is not JSON") from None
    if not isinstance(doc, list):
        raise uw.SourceError("shape", "gh api output is not a list")
    return [d for d in doc if isinstance(d, dict)]


def alert_findings(alerts, names):
    out = []
    for a in alerts:
        if a.get("state", "open") != "open":
            continue
        dep = a.get("dependency") if isinstance(a.get("dependency"), dict) else {}
        pkg = dep.get("package") if isinstance(dep.get("package"), dict) else {}
        name = pkg.get("name")
        adv = a.get("security_advisory") if isinstance(a.get("security_advisory"), dict) else {}
        ghsa = str(adv.get("ghsa_id") or "").upper()
        sev = SEVERITIES.get(str(adv.get("severity") or "").lower())
        if not (isinstance(name, str) and PKG_RX.fullmatch(name) and name in names):
            continue
        if not GHSA_RX.fullmatch(ghsa) or sev is None:
            continue
        pid, word = pkg_id(name), pkg_word(name)
        if not pid or not word:
            continue
        out.append({"kind": "depbotalert", "key": f"alert:{name}:{ghsa}",
                    "tokens": {"PACKAGE": pid, "GHSA": ghsa, "package": word,
                               "severity": sev}})
    return out


def pr_findings(pulls, now, covered):
    out = []
    for p in pulls:
        user = p.get("user") if isinstance(p.get("user"), dict) else {}
        if user.get("login") != BOT_LOGIN or user.get("type") != "Bot":
            continue
        n = p.get("number")
        if isinstance(n, bool) or not isinstance(n, int) or not 0 < n < 10 ** 6:
            continue
        if p.get("state", "open") != "open" or p.get("draft") is True:
            continue
        made = ci_issues._gh_time(p.get("created_at"))
        if made is None or now - made < PR_AGE_S:
            continue
        m = BUMP_RX.match(str(p.get("title") or ""))
        if m and m.group(1).lower() in covered:
            continue
        out.append({"kind": "depbotpr", "key": f"pr:{n}", "tokens": {"n": str(n)}})
    return out


def check(state, now, fetch, ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    root = _root(ctx)
    if root is None:
        return []
    if not watch_gate.web_data_on(root):
        raise watch_gate.WebDataOff("web data is off (opt-in setting web_data)")
    repo = ci_issues.repository(ctx)
    runner = _runner(ctx)
    if repo is None or runner is None:
        state["data"] = {"idle": "no github.com remote or no gh runner"}
        return []
    alerts = alert_findings(read(runner, root, repo, ALERTS_TAIL), lock_names(root))
    covered = {f["key"].split(":")[1].lower() for f in alerts}
    prs = pr_findings(read(runner, root, repo, PULLS_TAIL), now, covered)
    state["data"] = {"alerts": len(alerts), "pulls": len(prs)}
    return alerts + prs


SOURCE = {
    "name": NAME,
    "home": "loop",
    "cadence_s": DAY_S,
    "window": None,
    "needs_web_data": True,
    "hosts": ["api.github.com"],
    "urls": [],
    "purpose": "dev: watcher dependabot",
    "check": check,
}
