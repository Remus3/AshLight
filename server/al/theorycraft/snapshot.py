"""Game-data snapshot (ROADMAP TC-SNAP, decision 0009).

Fetches the permitted public game-data files into the AL sidecar cache
(`<sidecar>\\Cache\\gamedata\\`, resolved by server/al/paths.py) and writes
`manifest.json` (URL, fetch date, SHA-256, size, ETag / Last-Modified per
file). Run at build time by scripts/build.ps1, or at start time by the
keepalive supervisor (server/al/snapstart.py, DATA-SNAP-AT-START), always
as this tool's own process; the core never imports this module, so the
core itself never fetches game data.

Idempotent: a file checked within MIN_AGE_S is skipped with no request;
otherwise a conditional request (If-None-Match / If-Modified-Since) is sent
and a 304 or an unchanged SHA-256 leaves the file and its entry untouched.
Offline or failing sources are reported, never fatal (exit 0 unless
--strict). Nothing here is bundled in the repo (decision 0009 item 1).

    python -m server.al.theorycraft.snapshot [--force] [--strict] [--dir D] [--opt-in]

Network only with consent: nothing is fetched while the web_data opt-in
(config/local.json, decision 0013) is off, unless --opt-in is passed;
AL_NO_SNAPSHOT=1 skips it always (AUDIT-SNAPSHOT-OPTIN).
"""

import argparse
import calendar
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .. import NAME, VERSION, jsonfile, paths, webfetch
from . import datacredit

ATTRIBUTION = datacredit.ATTRIBUTION  # one source: theorycraft/datacredit.py
UA_PURPOSE = "build-time game-data snapshot"
USER_AGENT = webfetch.user_agent(UA_PURPOSE)  # base form; run() adds the contact
# UA-CONTACT: GGG asks for a contact in the User-Agent (research 0011), so a
# GGG source (the skill tree export) is fetched only with a contact set in
# config/local.json; without one it reports "off: contact not set".
CONTACT_SOURCES = ("skilltree",)
CONTACT_HOSTS = ("www.pathofexile.com", "pathofexile.com")


def user_agent(contact=None):
    """The snapshot User-Agent, "(contact: <value>)" appended when set."""
    return webfetch.user_agent(UA_PURPOSE, contact)


def needs_contact(name, url):
    parts = urllib.parse.urlsplit(url or "")
    return (name in CONTACT_SOURCES or (parts.hostname or "").lower() in CONTACT_HOSTS
            or "/grindinggear/" in parts.path.lower())
OPT_OUT_ENV = "AL_NO_SNAPSHOT"
MIN_AGE_S = 24 * 3600
MAX_BYTES = 256 * 1024 * 1024
TIMEOUT_S = 60
ALLOWED_HOSTS = ("repoe-fork.github.io", "raw.githubusercontent.com")
# raw.githubusercontent.com serves every public repo: only GGG's own export
# repository is allowed there (decision 0009 item 3 as amended).
HOST_PATH_PREFIX = {"raw.githubusercontent.com": "/grindinggear/poe2-skilltree-export/"}
MANIFEST = datacredit.MANIFEST
REPOE_POE2 = "https://repoe-fork.github.io/poe2/"
GGG_TREE_POE2 = ("https://raw.githubusercontent.com/grindinggear/"
                 "poe2-skilltree-export/main/data.json")

# name -> url; cached as <name>.json; url None = disabled. File names per
# decision 0009 "What changes" and research 0011 (ROADMAP DATA-SRC-URLS).
# The GGG tree export is fetch-only, never bundled (DATA-TREE-SRC; reader:
# theorycraft/treedata.py).
SOURCES = {
    "mods": REPOE_POE2 + "mods.json",
    "base_items": REPOE_POE2 + "base_items.json",
    "stats": REPOE_POE2 + "stats_by_file.json",
    "stat_translations": REPOE_POE2 + "stat_translations/stat_descriptions.json",
    "skilltree": GGG_TREE_POE2,
    # HUD-ACT (decision 0020): act / zone levels; reader server/al/acts.py.
    "world_areas": REPOE_POE2 + "world_areas.json",
}


class FetchError(Exception):
    pass


def cache_dir(environ=None):
    return datacredit.cache_dir(environ)


def _utc(ts=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _parse_utc(text):
    try:
        return calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


def _check_url(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise FetchError(f"URL not allowed: {url}")
    prefix = HOST_PATH_PREFIX.get(parts.hostname)
    if prefix and (not parts.path.startswith(prefix) or ".." in parts.path):
        raise FetchError(f"URL not allowed: {url}")


class _Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_fetch(url, headers):
    """(status, headers dict, body bytes) for one GET. 304 has an empty body."""
    _check_url(url)
    req = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(_Redirects())
    try:
        with opener.open(req, timeout=TIMEOUT_S) as resp:
            body = resp.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise FetchError("response too large")
            return resp.status, dict(resp.headers.items()), body
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return 304, dict(e.headers.items()), b""
        raise FetchError(f"HTTP {e.code}") from e
    except (urllib.error.URLError, OSError) as e:
        raise FetchError(f"network: {e}") from e


def _header(headers, name):
    for k, v in (headers or {}).items():
        if k.lower() == name.lower():
            return v
    return None


def load_manifest(directory):
    return jsonfile.read_json(Path(directory) / MANIFEST, encoding="ascii", kind=dict,
                              default={})


def run(directory=None, fetch=http_fetch, sources=None, force=False, now=None,
        contact=None):
    """Refresh every enabled source. Returns {name: outcome} where outcome is
    'fetched', 'unchanged', 'fresh' (skipped, checked < MIN_AGE_S ago),
    'disabled', 'off: contact not set' (a GGG source without a contact) or
    'error: ...'. Writes the manifest when anything changed."""
    contact = webfetch.clean_contact(contact)
    ua = user_agent(contact)
    directory = Path(directory) if directory is not None else cache_dir()
    sources = SOURCES if sources is None else sources
    now = time.time() if now is None else now
    manifest = load_manifest(directory)
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    out, dirty = {}, False
    for name, url in sources.items():
        if not url:
            out[name] = "disabled"
            continue
        if contact is None and needs_contact(name, url):
            out[name] = "off: " + webfetch.REASON_CONTACT
            continue
        entry = files.get(name) if isinstance(files.get(name), dict) else {}
        target = directory / f"{name}.json"
        have = target.is_file() and entry.get("url") == url and entry.get("sha256")
        if have and not force:
            checked = _parse_utc(entry.get("checked_at"))
            if checked is not None and 0 <= now - checked < MIN_AGE_S:
                out[name] = "fresh"
                continue
        headers = {"User-Agent": ua, "Accept": "application/json"}
        if have and not force:
            if entry.get("etag"):
                headers["If-None-Match"] = entry["etag"]
            if entry.get("last_modified"):
                headers["If-Modified-Since"] = entry["last_modified"]
        try:
            status, rh, body = fetch(url, headers)
            if status == 304 and have:
                out[name] = "unchanged"
            elif status == 200:
                try:
                    json.loads(body)
                except ValueError as e:
                    raise FetchError("response is not JSON") from e
                sha = hashlib.sha256(body).hexdigest()
                if have and sha == entry.get("sha256"):
                    out[name] = "unchanged"
                else:
                    jsonfile.write_bytes(target, body)
                    entry = {"url": url, "fetched_at": _utc(now), "sha256": sha,
                             "bytes": len(body)}
                    out[name] = "fetched"
                entry["etag"] = _header(rh, "ETag") or entry.get("etag")
                entry["last_modified"] = (_header(rh, "Last-Modified")
                                          or entry.get("last_modified"))
            else:
                raise FetchError(f"HTTP {status}")
            entry["checked_at"] = _utc(now)
            files[name] = entry
            dirty = True
        except FetchError as e:
            out[name] = f"error: {e}"
    if dirty:
        doc = {"tool": f"{NAME} {VERSION} theorycraft.snapshot", "attribution": ATTRIBUTION,
               "decision": "docs/decisions/0009-data-license.md",
               "files": {k: files[k] for k in sorted(files)}}
        jsonfile.write_bytes(directory / MANIFEST,
                         (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("ascii"))
    return out


def main(argv=None, environ=None, fetch=http_fetch, contact=None, web_data=None):
    """contact: None = read "contact" from gitignored config/local.json.
    web_data: None = read "web_data" from the same file (strictly True, as the
    core does); while it is off nothing is fetched unless --opt-in is passed
    (AUDIT-SNAPSHOT-OPTIN, decisions 0009 / 0013 amended 2026-11-17)."""
    env = os.environ if environ is None else environ
    cfg = None
    if contact is None or web_data is None:
        cfg = paths.load_local_config()
        cfg = cfg if isinstance(cfg, dict) else {}
    if contact is None:
        contact = cfg.get(webfetch.CONTACT_KEY)
    if web_data is None:
        web_data = cfg.get("web_data") is True
    ap = argparse.ArgumentParser(prog="snapshot", description=f"{NAME} game-data snapshot")
    ap.add_argument("--force", action="store_true", help="re-download every file")
    ap.add_argument("--strict", action="store_true", help="exit 1 when a source fails")
    ap.add_argument("--dir", help="cache directory (default: sidecar Cache\\gamedata)")
    ap.add_argument("--opt-in", action="store_true",
                    help="run even while web_data is off (build -Snapshot / AL_SNAPSHOT=1)")
    args = ap.parse_args(argv)
    if (env.get(OPT_OUT_ENV) or "").strip() not in ("", "0"):
        print(f"snapshot: skipped ({OPT_OUT_ENV} set)")
        return 0
    if not (web_data is True or args.opt_in):
        print("snapshot: skipped (web_data off; turn web data on or pass --opt-in)")
        return 0
    directory = Path(args.dir) if args.dir else cache_dir(env)
    result = run(directory, fetch=fetch, force=args.force, contact=contact)
    for name in sorted(result):
        print(f"snapshot: {name}: {result[name]}")
    failed = any(v.startswith("error") for v in result.values())
    return 1 if (failed and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
