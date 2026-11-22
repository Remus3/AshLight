"""RUN-REPORT-FIELDS (finding F-109, research 0051 R6 and F7, audit P8-7):
the Checks report made from an allow-list of structured fields
(server/al/report.py) and its whole-word redactor.

Every machine path, address and mail below is built at run time from
parts, so the leak sweep sees no literal. No socket, no process, no
network: a test core keeps its runtime in tmp_path.
"""

import collections
import json
import random
import re
import string
import threading
import types

import pytest

from server.al import VERSION, diag
from server.al import report as rep
from server.al.core import Core
from server.al.plug import report as route

NOW = 1795200000.0
SEP = "\\"
AT = "@"


def drive(*parts):
    return "Q" + ":" + SEP + SEP.join(parts)


def unc(*parts):
    return SEP + SEP + SEP.join(parts)


def mail(local, domain):
    return local + AT + domain


@pytest.fixture
def core(tmp_path, monkeypatch):
    monkeypatch.setattr(route, "_now", lambda: NOW)
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    c = Core(runtime=tmp_path / "rt", log_path=str(log), tail=False)
    yield c
    c.close()


# -- the fuzz (research 0051 F7 probe L3, 1,000 seeded variants)

L3 = ("drive path with a space", "unc path", "posix home path", "ipv4 with port",
      "host name", "48 hex run", "mail", "quoted path")
_GLUE = (" ", " (", ") ", ", ", ". ", ": ", "; ", "\t", " [", "] ")


def _seg(rnd, n=None):
    n = n or rnd.randint(4, 9)
    return "zq" + "".join(rnd.choice(string.ascii_lowercase) for _ in range(n))


def _variant(rnd):
    """(free text, [secret substrings that must not survive])."""
    user, sub = _seg(rnd), _seg(rnd)
    name = "Zq" + _seg(rnd)[2:].capitalize()
    host = _seg(rnd)
    hexrun = "".join(rnd.choice("0123456789abcdef") for _ in range(rnd.randint(32, 64)))
    ip = ".".join(str(rnd.randint(1, 254)) for _ in range(4))
    if ip.startswith("127."):
        ip = "10" + ip[3:]
    port = str(rnd.randint(1, 65535))
    pieces = {
        "drive path with a space": (drive("Users", user, "Program Files", sub, "x.txt"),
                                    [user, sub]),
        "unc path": (unc(host + "srv", "share", sub), [host + "srv", sub]),
        "posix home path": ("/home/" + user + "/" + sub + "/notes", [user, sub]),
        "ipv4 with port": (ip + ":" + port, [ip]),
        "host name": (host + ".example.com", [host]),
        "48 hex run": (hexrun, [hexrun]),
        "mail": (mail(user, host + ".org"), [user, host]),
        "quoted path": ('"' + drive("Some Dir", sub, "a b.log") + '"', [sub]),
        "character": (name, [name]),
    }
    keys = list(pieces)
    rnd.shuffle(keys)
    keep = keys[:rnd.randint(3, len(keys))]
    text = ""
    secrets = []
    for k in keep:
        frag, bad = pieces[k]
        text += rnd.choice(_GLUE) + frag
        secrets += bad
    return text + rnd.choice(("", ".", " end")), secrets, name


def test_fuzz_1000_seeded_variants_leak_no_seeded_secret():
    rnd = random.Random(20261121)
    for i in range(1000):
        text, secrets, name = _variant(rnd)
        others = ["Zq" + _seg(rnd)[2:].capitalize() for _ in range(11)]
        facts = {"_character": name if i % 2 else others[0],
                 "_characters": others + [name]}
        pairs = rep.secrets(facts, environ={})
        rows = [{"id": "x", "label": "Probe", "status": "fail", "detail": text,
                 "fix": "Try " + text}]
        out = diag.report(rows, VERSION, NOW, pairs,
                          extra={"unknown": [text], "shapes": ["plain: " + text]},
                          tails=[("core.log", [text, text.upper()])])
        low = out.lower()
        for s in secrets:
            assert s.lower() not in low, (i, s, text, out)
        out.encode("ascii")
        assert "\r" not in out


def test_each_l3_probe_is_masked():
    """research 0051 F7: each synthetic probe that passed before."""
    probes = {
        drive("Users", "zqone", "My Files", "zqtwo", "a.txt"): ("zqone", "zqtwo"),
        unc("zqhost", "share", "zqdir"): ("zqhost", "zqdir"),
        "/home/zqposix/x": ("zqposix",),
        "/" + "Us" + "ers/zqmac/x": ("zqmac",),
        "203.0.113.9:4242": ("203.0.113.9",),
        "zqbox.example.net": ("zqbox",),
        "ab" * 24: ("ab" * 24,),
        mail("zqmail", "example.org"): ("zqmail",),
        "https://zqsite.example/path?q=1": ("zqsite",),
        "2001:db8::42": ("2001:db8::42",),
    }
    for probe, bad in probes.items():
        got = rep.redact("seen " + probe + " here.", [])
        for b in bad:
            assert b not in got, (probe, got)
        assert got.startswith("seen ") and got.endswith(" here."), got


def test_redact_leaves_ordinary_words_numbers_and_loopback():
    for text in ("Updated 5 min ago.", "127.0.0.1:8961", "AshLight uses 120 MB.",
                 "at 21:14 (it had stopped answering)", "version 0.4.12",
                 "deadbeef", "/api/report", "Not registered: Alt+E."):
        assert rep.redact(text, []) == text, text


# -- P8-7: fixed report words stay

def test_redact_keeps_fixed_report_words():
    facts = {"web_data": True, "contact_set": True, "book_checked_at": NOW - 60,
             "_character": "Price", "_characters": ["Calc", "Found", "Overlay"]}
    pairs = diag.secrets(facts, environ={})
    rows = diag.checks(facts, NOW)
    text = diag.report(rows, VERSION, NOW, pairs)
    assert "[ok] Price book: Updated just now." in text
    assert "] Calc component: " in text
    assert "] Overlay: " in text
    assert "<character> book" not in text
    # free text still masks the name as a whole word, never inside a word
    got = diag.report([{"id": "x", "label": "Probe", "status": "note",
                        "detail": "Price met Pricey and price."}], VERSION, NOW, pairs)
    assert "[note] Probe: <character> met Pricey and <character>." in got


# -- every known character name

def test_every_known_character_name_is_masked(core):
    names = ["Zqcurrent"] + [f"Zqparked{chr(97 + i)}" for i in range(10)] + ["Zqother"]
    fake = types.SimpleNamespace(state=types.SimpleNamespace(
        _lock=threading.Lock(), character=names[0],
        _parked=collections.OrderedDict((n, {}) for n in names[1:11]),
        _others={names[11]}))
    assert sorted(route.known_characters(fake)) == sorted(names)
    pairs = diag.secrets(route.facts(fake, NOW), environ={})
    text = diag.report([{"id": "x", "label": "Probe", "status": "note",
                         "detail": ", ".join(names)}], VERSION, NOW, pairs,
                       extra={"unknown": [" ".join(names)]})
    for n in names:
        assert n.lower() not in text.lower(), n
    assert text.count("<character>") == 2 * len(names)
    # the live core: the facts hook names the state's characters
    with core.state._lock:
        core.state.character = "Zqlive"
        core.state._others.add("Zqguest")
    f = core.diag_facts(NOW)
    assert {"Zqlive", "Zqguest"} <= set(f["_characters"])
    assert "Zqguest" not in json.dumps(diag.view(f, VERSION, now=NOW, with_report=False))


# -- log tails only with the second choice

class _Req:
    def __init__(self, core):
        self.server = types.SimpleNamespace(core=core)
        self.sent = None

    def _json(self, status, doc, extra):
        self.sent = (status, doc)
        return status


def test_log_tails_only_with_the_second_choice(core):
    logs = core.overlay_log.parent
    logs.mkdir(parents=True, exist_ok=True)
    secret_dir = drive("Users", "zqtailuser", "x")
    (logs / "core.log").write_text(
        "2026-11-21T10:00:00.000Z INFO al.core zqtailmark opened " + secret_dir + "\n"
        "2026-11-21T10:00:01.000Z INFO al.core token " + "f" * 48 + "\n", encoding="ascii")
    (logs / "overlay.log").write_text("t overlay started; port 8961\n", encoding="ascii")
    plain = route.build(core, now=NOW)
    assert rep.FIELD_TAILS not in plain and "zqtailmark" not in plain
    req = _Req(core)
    route.get_report(req, {}, {})
    assert rep.FIELD_TAILS not in req.sent[1]["report"]
    route.get_report(req, {"tails": ["0"]}, {})
    assert rep.FIELD_TAILS not in req.sent[1]["report"]
    route.get_report(req, {"tails": ["1"]}, {})
    text = req.sent[1]["report"]
    assert req.sent[0] == 200
    assert (rep.FIELD_TAILS + ": ") in text
    assert "zqtailmark" in text and "overlay started" in text
    assert "zqtailuser" not in text and "f" * 48 not in text
    assert "<path>" in text and "<hex>" in text
    # never Client.txt: only AshLight's own two logs are named
    names = [ln.strip().split(":")[0] for ln in text.splitlines()
             if ln.startswith(rep.ITEM_INDENT) and not ln.startswith(rep.ITEM_INDENT * 2)]
    assert names == list(rep.TAIL_FILES)


def test_read_tail_keeps_the_last_lines(tmp_path):
    p = tmp_path / "core.log"
    p.write_text("".join(f"line {i}\n" for i in range(100)), encoding="ascii")
    assert rep.read_tail(p) == [f"line {i}" for i in range(80, 100)]
    assert rep.read_tail(tmp_path / "missing.log") == []
    p.write_text("x" * 40000 + "\nlast\n", encoding="ascii")
    assert rep.read_tail(p) == ["last"]


# -- the allow-list

_HEADER = re.compile(r"AshLight \S+ self-check, \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\Z")
_ROW = re.compile(r"\[(ok|FIX|\?|off|note)\] [^:]+: ")


def test_only_allow_listed_fields_appear(core):
    core.unknown_items.add(["Zqinvented grants # glimmers"])
    logs = core.overlay_log.parent
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "core.log").write_text("a line\n", encoding="ascii")
    for tails in (False, True):
        lines = route.build(core, now=NOW, tails=tails).splitlines()
        assert _HEADER.match(lines[0]), lines[0]
        assert [ln.split(":")[0] for ln in lines[1:5]] == [
            rep.FIELD_OS, rep.FIELD_PYTHON, rep.FIELD_ELECTRON, rep.FIELD_COUNTERS]
        section = None
        for ln in lines[1:]:
            if ln.startswith(rep.ITEM_INDENT):
                assert section in (rep.FIELD_UNKNOWN, rep.FIELD_SHAPES, rep.FIELD_TAILS), ln
                continue
            label = ln.split(":")[0]
            if label in rep.FIELD_LABELS:
                section = label
                continue
            assert _ROW.match(ln), ln
            section = None
        assert any(ln.startswith(rep.FIELD_UNKNOWN + ": 1 ") for ln in lines)
        assert (rep.FIELD_TAILS + ":" in "\n".join(lines)) is tails
    # the version fields are short tokens; the counters are numbers only
    f = dict(ln.split(": ", 1) for ln in lines[1:5])
    for key in (rep.FIELD_OS, rep.FIELD_PYTHON, rep.FIELD_ELECTRON):
        assert re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+_-]*", f[key]), f
    assert re.fullmatch(r"([a-z ]+ \d+)(, [a-z ]+ \d+)*", f[rep.FIELD_COUNTERS])


def test_electron_field_is_the_pinned_version(tmp_path):
    from server.al import paths
    pin = json.loads((paths.repo_root() / "config" / "electron_pin.json")
                     .read_text(encoding="utf-8"))
    assert rep.electron_version() == pin["version"]
    bad = tmp_path / "pin.json"
    bad.write_text(json.dumps({"version": "39 and a path " + drive("x")}), encoding="ascii")
    assert rep.electron_version(bad) == "unknown"
    assert rep.electron_version(tmp_path / "none.json") == "unknown"


def test_restart_and_shapes_fields():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC \(hung\)",
                        rep.restart_text({"at": NOW, "reason": "hung"}))
    assert rep.restart_text({"at": NOW, "reason": "Free text!"}) is None
    assert rep.restart_text(None) is None
    text = diag.report([], VERSION, NOW, [], extra={"restart": {"at": NOW, "reason": "crash"},
                                                    "shapes": ["system: <w> <n>"]})
    assert "\n" + rep.FIELD_RESTART + ": " in text and text.rstrip().endswith("system: <w> <n>")


def test_ledger_shapes_only_while_the_consent_is_on(core):
    wire = core.ledger_wire
    with wire.lock:
        wire.ledger.shapes[("system", "<w> zq <n>")] = [2, "h", "h", True]
        wire.ledger.shapes[("plain", "<w> unconfirmed")] = [1, "h", "h", False]
    assert route.ledger_shapes(core) == []
    core.state.tailer["ledger"] = True
    try:
        assert route.ledger_shapes(core) == ["system: <w> zq <n> (2)"]
        assert "system: <w> zq <n> (2)" in route.build(core, now=NOW)
    finally:
        core.state.tailer["ledger"] = False
