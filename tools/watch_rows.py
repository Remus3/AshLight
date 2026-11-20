"""Watcher row templates (LOOP-WATCH-ROWS, F-030, AUTO-05). Stdlib only.

Row text for a watcher finding comes only from tracked templates: one JSON
file per source under ops/loop/watch_rows/<source>.json, loaded and checked
together as one table. No upstream sentence ever enters a row: a token value
is a short word that must full-match both its own pattern and SAFE_VALUE.

File shape:
    {"kinds": {<kind>: {"act": "note" | "row" | "gate" | "dive",
                        "id": "POB-<VTAG>", "lane": "build" | "data" | "review",
                        "priority": false, "blocked": "session" | null,
                        "text": "... SOURCE: watch ..., filed <YYYY-MM-DD>.",
                        "tokens": {<token>: <regex>},
                        "sample": {<token>: <value>}}}}

load(root) -> table ({kind: definition plus "source"}), raises WatchRowsError.
render(table, kind, tokens, today) -> (row id, row text), or (None, reason).

Placeholders are <name>; <YYYY-MM-DD> and <YYYYMMDD> are reserved and filled
from `today`. The BLOCKED tag is never written in `text`: render inserts
" BLOCKED: <blocked>." in front of the SOURCE clause (or at the end).
"""

import datetime as _dt
import json
import re
import sys
from pathlib import Path

from loop_base import BLOCKED_RX, ROW_ID, ROW_RX
from loop_roadmap import roadmap_rows

ROWS_REL = Path("ops/loop/watch_rows")
ACTS = ("note", "row", "gate", "dive")
ID_ACTS = ("row", "gate")
LANES = ("build", "data", "review")
ROW_MAX = 700
KEYS = {"act", "id", "lane", "priority", "blocked", "text", "tokens", "sample"}
RESERVED = {"YYYY-MM-DD": r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "YYYYMMDD": r"[0-9]{8}"}
# Two ids that may extend another id by a hyphen (docs/plan/06 catalogue).
ALLOWED_EXTENSIONS = {("TC-OAUTH-REG", "TC-OAUTH-REG-OPEN"), ("LIVE-1", "LIVE-1-<ITEM>")}

NAME_RX = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
TOKEN_NAME_RX = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}")
PLACEHOLDER_RX = re.compile(r"<([^<>\s]+)>")
SAFE_VALUE = re.compile(r"[A-Za-z0-9._-]{1,64}")
# A token value never carries a row tag word (it would change the row's meaning).
TAG_WORD_RX = re.compile(r"blocked|accept|depends|source|zero-click|priority", re.I)
SOURCE_CLAUSE_RX = re.compile(r"\s+SOURCE:")
# Row cost rule (docs/plan/06, research 0058 F4, F-033): a lane cannot merge
# these unattended, so a template naming one carries "BLOCKED: session".
HOTSPOT_RX = re.compile(
    r"CLAUDE\.md|ROADMAP\.md|(?<![\w./-])web/|app/overlay/|app/shared/|\bevent text\b|"
    r"\b(?:new|add an?|write an?)\s+decision\b|docs/decisions/", re.I)


class WatchRowsError(ValueError):
    """A template file or the table as a whole is refused."""


def _ascii_lf(text):
    return text.isascii() and "\r" not in text


def _placeholders(*parts):
    out = []
    for part in parts:
        out.extend(PLACEHOLDER_RX.findall(part or ""))
    return out


def cost_problem(kdef):
    """The row cost rule: None, or why the template must carry BLOCKED: session."""
    hit = HOTSPOT_RX.search(" ".join(str(kdef.get(k) or "") for k in ("id", "text")))
    if hit is None:
        return None
    blocked = kdef.get("blocked") or ""
    if re.match(r"session\b", blocked):
        return None
    return f"names {hit.group(0)!r} without 'BLOCKED: session'"


def _fill(template, values):
    return PLACEHOLDER_RX.sub(lambda m: values[m.group(1)], template)


def _id_regex(kdef):
    parts, pos, idp = [], 0, kdef["id"]
    for m in PLACEHOLDER_RX.finditer(idp):
        parts.append(re.escape(idp[pos:m.start()]))
        name = m.group(1)
        parts.append("(?:" + (RESERVED.get(name) or kdef["tokens"][name]) + ")")
        pos = m.end()
    parts.append(re.escape(idp[pos:]))
    return "".join(parts)


def _check_kind(where, kind, kdef):
    if not NAME_RX.fullmatch(kind):
        raise WatchRowsError(f"{where}: kind name {kind!r} is not [a-z0-9-]")
    if not isinstance(kdef, dict):
        raise WatchRowsError(f"{where}: kind {kind} is not an object")
    extra = set(kdef) - KEYS
    if extra:
        raise WatchRowsError(f"{where}: kind {kind} has unknown keys {sorted(extra)}")
    act = kdef.get("act")
    if act not in ACTS:
        raise WatchRowsError(f"{where}: kind {kind} act {act!r} is not one of {ACTS}")
    tokens = kdef.get("tokens") or {}
    sample = kdef.get("sample") or {}
    if not isinstance(tokens, dict) or not isinstance(sample, dict):
        raise WatchRowsError(f"{where}: kind {kind} tokens and sample are objects")
    for name, pat in tokens.items():
        if name in RESERVED or not TOKEN_NAME_RX.fullmatch(name):
            raise WatchRowsError(f"{where}: kind {kind} token name {name!r} is reserved or bad")
        if not isinstance(pat, str) or not pat or pat.startswith("^") or pat.endswith("$"):
            raise WatchRowsError(f"{where}: kind {kind} token {name} pattern is empty or anchored")
        try:
            re.compile(pat)
        except re.error as exc:
            raise WatchRowsError(f"{where}: kind {kind} token {name} pattern: {exc}") from None
    if set(sample) != set(tokens):
        raise WatchRowsError(f"{where}: kind {kind} sample must give every token, no other")
    for name, value in sample.items():
        bad = _bad_value(name, value, tokens[name])
        if bad:
            raise WatchRowsError(f"{where}: kind {kind} sample {bad}")
    if act not in ID_ACTS:
        return
    for key in ("id", "text"):
        val = kdef.get(key)
        if not isinstance(val, str) or not val.strip() or not _ascii_lf(val) or "\n" in val:
            raise WatchRowsError(f"{where}: kind {kind} {key} must be one ASCII line")
    if kdef.get("lane") not in LANES:
        raise WatchRowsError(f"{where}: kind {kind} lane must be one of {LANES}")
    if not isinstance(kdef.get("priority", False), bool):
        raise WatchRowsError(f"{where}: kind {kind} priority must be true or false")
    blocked = kdef.get("blocked")
    if blocked is not None and (not isinstance(blocked, str) or not blocked.strip()
                                or not _ascii_lf(blocked) or "\n" in blocked
                                or "<" in blocked or ">" in blocked):
        raise WatchRowsError(f"{where}: kind {kind} blocked must be null or one literal line")
    if BLOCKED_RX.search(kdef["text"]):
        raise WatchRowsError(f"{where}: kind {kind} text writes BLOCKED itself; use blocked")
    used = set(_placeholders(kdef["id"], kdef["text"]))
    unknown = used - set(tokens) - set(RESERVED)
    if unknown:
        raise WatchRowsError(f"{where}: kind {kind} uses undeclared tokens {sorted(unknown)}")
    unused = set(tokens) - used
    if unused:
        raise WatchRowsError(f"{where}: kind {kind} declares unused tokens {sorted(unused)}")
    problem = cost_problem(kdef)
    if problem:
        raise WatchRowsError(f"{where}: kind {kind} {problem}")


def _bad_value(name, value, pattern):
    if not isinstance(value, str) or not SAFE_VALUE.fullmatch(value):
        return f"token {name} value is not a short word ({SAFE_VALUE.pattern})"
    if TAG_WORD_RX.search(value):
        return f"token {name} value carries a row tag word"
    if not re.fullmatch(pattern, value):
        return f"token {name} value fails its pattern"
    return None


def _clash(a, b):
    """True when a sample id of kind b is an id of kind a, or a hyphen extension of one."""
    return re.fullmatch(a["_id_rx"] + r"(?:-.*)?", b["_sample_id"]) is not None


def load(root):
    """The one table from every <source>.json under root/ops/loop/watch_rows."""
    folder = Path(root) / ROWS_REL
    table = {}
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    for path in files:
        where = f"{ROWS_REL.as_posix()}/{path.name}"
        source = path.stem
        if not NAME_RX.fullmatch(source):
            raise WatchRowsError(f"{where}: source name is not [a-z0-9-]")
        raw = path.read_bytes()
        try:
            text = raw.decode("ascii")
        except UnicodeDecodeError:
            raise WatchRowsError(f"{where}: not ASCII") from None
        if "\r" in text:
            raise WatchRowsError(f"{where}: not LF")
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise WatchRowsError(f"{where}: bad JSON: {exc}") from None
        if not isinstance(data, dict) or set(data) != {"kinds"} or not isinstance(
                data["kinds"], dict):
            raise WatchRowsError(f"{where}: top level must be {{\"kinds\": {{...}}}}")
        for kind, kdef in data["kinds"].items():
            _check_kind(where, kind, kdef)
            if kind in table:
                raise WatchRowsError(
                    f"{where}: kind {kind} already defined by source {table[kind]['source']}")
            entry = dict(kdef)
            entry["source"] = source
            table[kind] = entry
    _check_ids(table)
    return {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
            for k, v in table.items()}


def _check_ids(table):
    today = "2026-01-01"
    with_id = []
    for kind, kdef in table.items():
        if kdef["act"] not in ID_ACTS:
            continue
        values = dict(kdef.get("sample") or {})
        values.update({"YYYY-MM-DD": today, "YYYYMMDD": today.replace("-", "")})
        kdef["_sample_id"] = _fill(kdef["id"], values)
        kdef["_id_rx"] = _id_regex(kdef)
        if not re.fullmatch(ROW_ID, kdef["_sample_id"]):
            raise WatchRowsError(f"kind {kind}: id {kdef['id']} does not render a row id")
        with_id.append((kind, kdef))
    for ka, a in with_id:
        for kb, b in with_id:
            if ka == kb or (a["id"], b["id"]) in ALLOWED_EXTENSIONS:
                continue
            if _clash(a, b):
                raise WatchRowsError(
                    f"kind {kb} id {b['id']} clashes with kind {ka} id {a['id']} "
                    "(same id or a hyphen extension of it)")


def _today_str(today):
    if isinstance(today, _dt.datetime):
        today = today.date()
    if isinstance(today, _dt.date):
        return today.isoformat()
    if isinstance(today, str) and re.fullmatch(RESERVED["YYYY-MM-DD"], today):
        return today
    return None


def check_row(text, row_id, lane):
    """None when text is exactly one ROADMAP row with that id and lane, else why."""
    if not text.isascii():
        return "row is not ASCII"
    if "\r" in text:
        return "row is not LF"
    if len(text) > ROW_MAX:
        return f"row is {len(text)} chars, over {ROW_MAX}"
    lines = text.split("\n")
    if not ROW_RX.match(lines[0]):
        return "first line is not a row"
    rows = roadmap_rows(text)
    if len(rows) != 1:
        return f"text parses as {len(rows)} rows, not one"
    row = rows[0]
    if row["id"] != row_id:
        return f"row id {row['id']} is not {row_id}"
    if row["lane"] not in LANES or row["lane"] != lane:
        return f"row lane {row['lane']} is not {lane}"
    if not row["open"]:
        return "row is not open"
    return None


def render(table, kind, tokens, today):
    """(row id, row text) for a finding, or (None, reason). The text is one
    line without a trailing newline."""
    kdef = table.get(kind)
    if kdef is None:
        return None, f"unknown kind {kind}"
    if kdef["act"] != "row":
        return None, f"kind {kind} act {kdef['act']} files no row"
    day = _today_str(today)
    if day is None:
        return None, "today is not a date"
    declared = kdef.get("tokens") or {}
    tokens = tokens or {}
    if not isinstance(tokens, dict) or set(tokens) != set(declared):
        got = sorted(tokens) if isinstance(tokens, dict) else tokens
        return None, f"tokens {got} are not {sorted(declared)}"
    for name, value in tokens.items():
        bad = _bad_value(name, value, declared[name])
        if bad:
            return None, bad
    values = dict(tokens)
    values.update({"YYYY-MM-DD": day, "YYYYMMDD": day.replace("-", "")})
    row_id = _fill(kdef["id"], values)
    body = _fill(kdef["text"], values).strip()
    blocked = kdef.get("blocked")
    if blocked:
        tag = f" BLOCKED: {blocked.strip().rstrip('.')}."
        m = SOURCE_CLAUSE_RX.search(body)
        body = body[:m.start()] + tag + body[m.start():] if m else body + tag
    head = f"- [ ] {row_id} ({kdef['lane']}) " + ("(priority) " if kdef.get("priority") else "")
    text = head + body
    why = check_row(text, row_id, kdef["lane"])
    if why:
        return None, why
    if len(BLOCKED_RX.findall(text)) != (1 if blocked else 0):
        return None, "BLOCKED tag count is wrong"
    return row_id, text


def render_samples(table, today="2026-01-01"):
    """{kind: (row id, text) or (None, reason)} for every row kind's sample."""
    return {k: render(table, k, v.get("sample") or {}, today)
            for k, v in table.items() if v["act"] == "row"}


def main(argv=None):
    root = Path(__file__).resolve().parent.parent
    try:
        table = load(root)
    except WatchRowsError as exc:
        print(f"watch_rows: refused: {exc}")
        return 1
    bad = {k: r[1] for k, r in render_samples(table).items() if r[0] is None}
    for kind, why in sorted(bad.items()):
        print(f"watch_rows: kind {kind} sample does not render: {why}")
    print(f"watch_rows: {len(table)} kinds, {len(bad)} failing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
