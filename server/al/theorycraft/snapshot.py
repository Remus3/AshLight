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
--strict). Before a changed body replaces `<name>.json` the current file is
copied to `<name>.prev.json` (`keep_previous`, DATA-TREE-HOLD): one previous
copy per source, so a reader (treedata.TreeCache) can fall back to it.
Nothing here is bundled in the repo (decision 0009 item 1).

DATA-SNAP-PROBE (F-143): every fetched body of a source in
snapprobe.PROBES is probed after the JSON check and before the write (top
level type, minimum entry count, the fields its reader uses). A failing
body is 'error: probe: ...' and the cached file and its manifest entry stay
as they were. Each probe is compared with the cached file (the copy
keep_previous keeps) and logged to <sidecar>/Logs/snapshot-drift.log; the
verdicts go to ops/runtime/snapshot/probe.json (snapprobe.report, read by
AUTO-18 and the Checks row). A caller's own sources table is not probed
unless it passes `probes`.

    python -m server.al.theorycraft.snapshot [--force] [--strict] [--dir D] [--opt-in]

Network only with consent: nothing is fetched while the web_data opt-in
(config/local.json, decision 0013) is off, unless --opt-in is passed;
AL_NO_SNAPSHOT=1 skips it always (AUDIT-SNAPSHOT-OPTIN).

ITEM-INFO-CORE (decision 0083): SOURCES holds repoe-fork's uniques.json
(same licence, opt-in and cache as base_items, decision 0009) for the item
info popover (server/al/iteminfo.py). ITEM-INFO-UNIQUES-PROBE: it joined
SOURCES (default_sources() is SOURCES, no separate item list) and has a probe
(snapprobe.PROBES "uniques": name and item_class).

DATA-GEMS-SNAP: SOURCES adds repoe-fork's gems.json (same MIT export,
GGG-owned data, opt-in, cache and attribution as base_items, decision 0009;
the export's own page lists gems) as gems.json, the file
theorycraft/archetypes.py reads (GEMS_FILE) so Kindler gem names and levels
read checked. Its probe (snapprobe.PROBES "gems") counts the entries that
yield a gem name the way archetypes.gem_index reads them.

ITEM-INFO-GEM-DETAIL (decision 0083 amendment 2026-11-28): the poe2 export
has no gems.json, so "gems" reads skill_gems.json (the same export's gem
list, still cached as gems.json); "skills" (skills.json) and "gem_tags"
(gem_tags.json) join SOURCES with the same opt-in, cache, User-Agent and
attribution. After the run, main() calls gemdetail.refresh, which turns
the three into one small file per gem under gem_details/ when their
sha256 changed, so the core reads a few KB per popover instead of the
28 MB skills file.
"""

import argparse
import calendar
import hashlib
import http.client
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .. import NAME, VERSION, jsonfile, paths, webfetch
from . import datacredit, snapprobe

ATTRIBUTION = datacredit.ATTRIBUTION  # one source: theorycraft/datacredit.py
UA_PURPOSE = "build-time game-data snapshot"
USER_AGENT = webfetch.user_agent(UA_PURPOSE)  # base form; run() adds the contact
# UA-CONTACT: GGG asks for a contact in the User-Agent (research 0011), so a
# GGG source (the skill tree export) is fetched only with a contact: the one
# in config/local.json, else the project's issues page (DATA-CONTACT-DEFAULT);
# without either it reports "off: contact not set".
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
# SEC-CEIL-SNAPSHOT (F-173): MAX_BYTES is only the ceiling every per-source
# cap stays under; a body is streamed to a temp file in the cache dir (never
# held whole in memory while it downloads), a body past its source's cap is
# refused and its temp file removed, and one fetch ends at DEADLINE_S
# (total, a dripping reply included); TIMEOUT_S bounds each socket wait.
MAX_BYTES = 256 * 1024 * 1024
MiB = 1024 * 1024
# about 4 to 8 times the sizes seen in 2026-11 (decision 0009, research
# 0037 / 0048: stat_descriptions 10.1 MB, base_items 8.2 MB, world_areas
# 1.9 MB, stats_by_file 14.4 MB, mods 12.7 MB)
SOURCE_CAPS = {
    "base_items": 64 * MiB,
    "stat_translations": 64 * MiB,
    "skilltree": 64 * MiB,
    "world_areas": 16 * MiB,
    "mods": 96 * MiB,
    "stats": 96 * MiB,
    "uniques": 16 * MiB,
    # the reader's own ceiling (archetypes.GEMS_MAX_BYTES)
    "gems": 64 * MiB,
    # 28 MB in 2026-11; read only by this tool (gemdetail.refresh)
    "skills": 128 * MiB,
    "gem_tags": 1 * MiB,
}
DEFAULT_CAP = 32 * MiB  # a caller's own source name
TIMEOUT_S = 60
DEADLINE_S = 600.0
READ_BLOCK = webfetch.READ_BLOCK
SPOOL_PREFIX = ".snap-"
SPOOL_SUFFIX = ".part"


def source_cap(name):
    """The byte cap of one source (DEFAULT_CAP for an unknown name), never
    over MAX_BYTES."""
    return min(SOURCE_CAPS.get(name, DEFAULT_CAP), MAX_BYTES)
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
    "base_items": REPOE_POE2 + "base_items.json",
    "stat_translations": REPOE_POE2 + "stat_translations/stat_descriptions.json",
    "skilltree": GGG_TREE_POE2,
    # HUD-ACT (decision 0020): act / zone levels; reader server/al/acts.py.
    "world_areas": REPOE_POE2 + "world_areas.json",
    # DATA-GEMS-SNAP (decisions 0009, 0081): gem names for Kindler; reader
    # server/al/theorycraft/archetypes.py (load_gems). The poe2 export has no
    # gems.json (HTTP 404, 2026-11-28): its gem list is skill_gems.json, cached
    # under the reader's name (decision 0083 amendment 2026-11-28).
    "gems": REPOE_POE2 + "skill_gems.json",
    # ITEM-INFO-GEM-DETAIL (decision 0083 amendment 2026-11-28): each gem
    # skill's worded stat lines per level and the gem tag words; reader
    # theorycraft/gemdetail.py, which this tool turns into small per-gem
    # files (the core never parses skills.json).
    "skills": REPOE_POE2 + "skills.json",
    "gem_tags": REPOE_POE2 + "gem_tags.json",
    # ITEM-INFO-CORE (decision 0083): unique item list for the item info
    # popover; reader server/al/iteminfo.py (uniques_from_doc).
    "uniques": REPOE_POE2 + "uniques.json",
}

# DATA-SNAP-TRIM: two files with no reader (about 27 MB) are not fetched by
# default. A dev re-check of the waystone mod pool passes
# sources=dict(SOURCES, **OPTIONAL_SOURCES) to run() explicitly. Copies
# already in a cache are left alone, never deleted by the tool.
OPTIONAL_SOURCES = {
    "mods": REPOE_POE2 + "mods.json",
    "stats": REPOE_POE2 + "stats_by_file.json",
}


def default_sources():
    """What a normal run of the tool fetches: SOURCES."""
    return dict(SOURCES)


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
    """One URL rule (SEC-CEIL-SNAPSHOT): webfetch.check_url with
    ALLOWED_HOSTS (https only, no user info, no port other than 443, no IP
    literal, exact host), then the per-host path prefix with no '..' in the
    path, decoded or not."""
    try:
        parts = webfetch.check_url(url, ALLOWED_HOSTS)
    except webfetch.UrlNotAllowed as e:
        raise FetchError(f"URL not allowed: {e}") from e
    host = (parts.hostname or "").lower()
    prefix = HOST_PATH_PREFIX.get(host)
    path = parts.path or ""
    decoded = urllib.parse.unquote(path)
    if prefix and (not path.startswith(prefix) or ".." in path or ".." in decoded):
        raise FetchError("URL not allowed: path outside the allowed repository")
    return parts


class _Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _remove(path):
    try:
        Path(path).unlink()
    except OSError:
        pass


def _spool(resp, cap, deadline_at, spool_dir):
    """Stream `resp` into a new temp file in spool_dir, at most `cap`
    bytes; FetchError past the cap or the deadline, with the file removed.
    Returns the temp file's Path."""
    spool_dir = Path(spool_dir)
    spool_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=SPOOL_PREFIX, suffix=SPOOL_SUFFIX, dir=spool_dir)
    reader = getattr(resp, "read1", None) or resp.read
    size, done = 0, False
    try:
        with os.fdopen(fd, "wb") as fh:
            while True:
                if time.monotonic() >= deadline_at:
                    raise FetchError("request passed its total deadline")
                block = reader(min(READ_BLOCK, cap + 1 - size))
                if not block:
                    break
                size += len(block)
                if size > cap:
                    raise FetchError(f"response too large (cap {cap} bytes)")
                fh.write(block)
            fh.flush()
            os.fsync(fh.fileno())
        done = True
        return Path(name)
    finally:
        if not done:
            _remove(name)


def http_fetch(url, headers, cap=None, spool_dir=None, deadline_s=DEADLINE_S):
    """(status, headers dict, body) for one GET. 304 has an empty body.

    With spool_dir the body is streamed to a temp file there and `body` is
    its Path (the caller moves or removes it); without, it is the bytes.
    cap: the byte cap (default MAX_BYTES). The whole fetch ends at
    deadline_s; no socket wait outlasts it."""
    _check_url(url)
    cap = MAX_BYTES if cap is None else min(int(cap), MAX_BYTES)
    deadline_at = time.monotonic() + deadline_s
    req = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(_Redirects())
    path = None
    try:
        timeout = max(0.001, min(TIMEOUT_S, deadline_at - time.monotonic()))
        with opener.open(req, timeout=timeout) as resp:
            if spool_dir is not None:
                path = _spool(resp, cap, deadline_at, spool_dir)
                body = path
            else:
                try:
                    body = webfetch.read_body(resp, cap, deadline_at, time.monotonic)
                except webfetch.FetchError as e:
                    raise FetchError(str(e)) from e
            result = resp.status, dict(resp.headers.items()), body
            path = None
            return result
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return 304, dict(e.headers.items()), b""
        raise FetchError(f"HTTP {e.code}") from e
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as e:
        raise FetchError(f"network: {type(e).__name__}: {e}") from e
    finally:
        if path is not None:
            _remove(path)


http_fetch.streams = True  # run() passes cap and spool_dir to this fetcher


def _header(headers, name):
    for k, v in (headers or {}).items():
        if k.lower() == name.lower():
            return v
    return None


PREV_SUFFIX = ".prev.json"


def previous_path(target):
    """`<name>.prev.json` beside `<name>.json` (DATA-TREE-HOLD)."""
    target = Path(target)
    return target.with_name(target.name[:-len(".json")] + PREV_SUFFIX
                            if target.name.endswith(".json")
                            else target.name + PREV_SUFFIX)


def keep_previous(target):
    """Copy the current `<name>.json` to `<name>.prev.json` before it is
    replaced; one previous copy, the older one is overwritten. True when a
    copy was made; a missing file is not an error (False)."""
    target = Path(target)
    try:
        body = target.read_bytes()
    except FileNotFoundError:
        return False
    jsonfile.write_bytes(previous_path(target), body)
    return True


def load_manifest(directory):
    return jsonfile.read_json(Path(directory) / MANIFEST, encoding="ascii", kind=dict,
                              default={})


LOG_MAX_BYTES = 512 * 1024  # snapshot-drift.log keeps its newest half past this


def _old_stats(target, name, probes):
    """snapprobe.stats of the cached file (None when missing or unreadable)."""
    doc = jsonfile.read_json(target, max_bytes=MAX_BYTES, kind=(dict, list))
    return None if doc is None else snapprobe.stats(name, doc, probes)


def append_log(path, lines, cap=LOG_MAX_BYTES):
    """Append ASCII lines to the drift log; past `cap` bytes only the
    newest half (from a line start) is kept."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="ascii", errors="replace", newline="\n") as fh:
        fh.write("".join(line + "\n" for line in lines))
    if path.stat().st_size > cap:
        tail = path.read_bytes()[-(cap // 2):]
        cut = tail.find(b"\n")
        jsonfile.write_bytes(path, tail[cut + 1:] if cut >= 0 else b"")


def write_probe_report(runtime, records, now=None):
    """Merge `records` into <runtime>/snapshot/probe.json (snapprobe.report)."""
    path = snapprobe.report_path(runtime)
    previous = jsonfile.read_json(path, max_bytes=snapprobe.REPORT_MAX_BYTES, kind=dict)
    doc = snapprobe.report(previous, records, now)
    jsonfile.write_bytes(path, (json.dumps(doc, indent=1, sort_keys=True) + "\n")
                         .encode("ascii"))
    return path


def _measure(body):
    """(size, sha256 hex) of a body: bytes, or a spooled temp file read in
    blocks."""
    if not isinstance(body, Path):
        body = bytes(body or b"")
        return len(body), hashlib.sha256(body).hexdigest()
    h, size = hashlib.sha256(), 0
    try:
        with open(body, "rb") as fh:
            for block in iter(lambda: fh.read(READ_BLOCK), b""):
                h.update(block)
                size += len(block)
    except OSError as e:
        raise FetchError(f"cannot read the downloaded body: {e}") from e
    return size, h.hexdigest()


def _load_json(body):
    try:
        if isinstance(body, Path):
            with open(body, "rb") as fh:
                return json.load(fh)
        return json.loads(body)
    except (ValueError, RecursionError) as e:
        raise FetchError("response is not JSON") from e
    except OSError as e:
        raise FetchError(f"cannot read the downloaded body: {e}") from e


def _install(body, target):
    """Put a checked body in place atomically: a spooled temp file (in the
    same directory) is moved over `target`, bytes are written atomically."""
    try:
        if isinstance(body, Path):
            jsonfile._replace(body, target)
        else:
            jsonfile.write_bytes(target, body)
    except OSError as e:
        raise FetchError(f"cannot write {Path(target).name}: {e}") from e


def run(directory=None, fetch=http_fetch, sources=None, force=False, now=None,
        contact=None, probes=None, runtime=None, log_dir=None):
    """Refresh every enabled source. Returns {name: outcome} where outcome is
    'fetched', 'unchanged', 'fresh' (skipped, checked < MIN_AGE_S ago),
    'disabled', 'off: contact not set' (a GGG source without a contact) or
    'error: ...' ('error: probe: ...' when a fetched body fails its probe).
    Writes the manifest when anything changed.

    probes: the probe table (None: snapprobe.PROBES for the default
    sources, nothing for a caller's own table). runtime / log_dir: where
    probe.json (runtime/snapshot/) and snapshot-drift.log go when anything
    was probed; None writes neither (main passes the real places)."""
    contact = webfetch.clean_contact(contact)
    ua = user_agent(contact)
    directory = Path(directory) if directory is not None else cache_dir()
    if probes is None:
        probes = snapprobe.PROBES if sources is None else {}
    sources = SOURCES if sources is None else sources
    now = time.time() if now is None else now
    records, lines = [], []
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
        cap = source_cap(name)
        body = None
        try:
            if getattr(fetch, "streams", False):
                status, rh, body = fetch(url, headers, cap=cap, spool_dir=directory)
            else:
                status, rh, body = fetch(url, headers)
            if status == 304 and have:
                out[name] = "unchanged"
            elif status == 200:
                size, sha = _measure(body)
                if size > cap:
                    raise FetchError(f"response too large (cap {cap} bytes)")
                doc = _load_json(body)
                same = bool(have) and sha == entry.get("sha256")
                result = snapprobe.probe(name, doc, table=probes)
                if result is not None:
                    d = None if same else snapprobe.drift(
                        _old_stats(target, name, probes), snapprobe.stats(name, doc, probes))
                    records.append(snapprobe.record(result, d, now, probes))
                    lines.append(snapprobe.drift_line(name, result, d, now))
                    if result["verdict"] != snapprobe.PASS:
                        raise FetchError("probe: " + result["reason"])
                del doc
                if same:
                    out[name] = "unchanged"
                else:
                    try:
                        keep_previous(target)
                    except OSError as e:
                        raise FetchError(f"cannot keep previous copy: {e}") from e
                    _install(body, target)
                    entry = {"url": url, "fetched_at": _utc(now), "sha256": sha,
                             "bytes": size}
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
        finally:
            if isinstance(body, Path):  # a spooled body not moved into place
                _remove(body)
    if records and runtime is not None:
        try:
            write_probe_report(runtime, records, now)
        except OSError as e:  # a report that cannot be written never fails the run
            print(f"snapshot: probe report not written: {e}", file=sys.stderr)
    if lines and log_dir is not None:
        try:
            append_log(Path(log_dir) / snapprobe.LOG_NAME, lines)
        except OSError as e:
            print(f"snapshot: drift log not written: {e}", file=sys.stderr)
    if dirty:
        doc = {"tool": f"{NAME} {VERSION} theorycraft.snapshot", "attribution": ATTRIBUTION,
               "decision": "docs/decisions/0009-data-license.md",
               "files": {k: files[k] for k in sorted(files)}}
        jsonfile.write_bytes(directory / MANIFEST,
                         (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("ascii"))
    return out


def main(argv=None, environ=None, fetch=http_fetch, contact=None, web_data=None):
    """contact: None = read "contact" from gitignored config/local.json,
    else the project's issues page from the address constant
    (DATA-CONTACT-DEFAULT, decision 0015 amendment 2026-11-23).
    web_data: None = read "web_data" from the same file (strictly True, as the
    core does); while it is off nothing is fetched unless --opt-in is passed
    (AUDIT-SNAPSHOT-OPTIN, decisions 0009 / 0013 amended 2026-11-17)."""
    env = os.environ if environ is None else environ
    cfg = None
    if contact is None or web_data is None:
        cfg = paths.load_local_config()
        cfg = cfg if isinstance(cfg, dict) else {}
    if contact is None:
        contact = webfetch.effective_contact(cfg.get(webfetch.CONTACT_KEY))
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
    result = run(directory, fetch=fetch, sources=default_sources(), force=args.force,
                 contact=contact, probes=snapprobe.PROBES,
                 runtime=paths.runtime_dir(), log_dir=paths.sidecar_dir("Logs", env))
    for name in sorted(result):
        print(f"snapshot: {name}: {result[name]}")
    from . import gemdetail  # lazy: only a full run derives the gem files
    print(f"snapshot: gem_details: {gemdetail.refresh(directory, load_manifest(directory))}")
    failed = any(v.startswith("error") for v in result.values())
    return 1 if (failed and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
