"""DATA-CONTACT-DEFAULT (F-018, decision 0015 amendment 2026-11-23): once
the repository address is in the tree (config/public_repo.json, the one
address source) and no contact is typed, the User-Agent carries the
project's issues page and prices are not blocked; a typed contact still
overrides it. A test core is handed its address (update_repo) and never
reads the tracked file; a core with no address has no default.

Mocked fetch only; no request reaches the network. Tmp runtime and config.
"""

import json

from server.al import ninja, updates, webfetch
from server.al.core import Core

# A made-up address, never the project's own (leak sweep)
REPO = "example-owner/AshLight"
ISSUES = "https://github.com/" + REPO + "/issues"
TYPED = "zq-contact-4417"
LEAGUES = json.dumps([{"id": "Standard", "name": "Standard"}]).encode()
OVERVIEW = json.dumps({
    "core": {"items": [{"id": "divine", "name": "Divine Orb"}],
             "rates": {"exalted": 500.0}, "primary": "divine"},
    "lines": [{"id": "exalted", "primaryValue": 0.002}],
    "items": [{"id": "exalted", "name": "Exalted Orb"}]}).encode()


class FakeNet:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        if url.endswith(ninja.LEAGUES_PATH):
            return 200, {}, LEAGUES
        return 200, {}, OVERVIEW


def _core(tmp_path, cfg, repo):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    rt = tmp_path / "rt"
    rt.mkdir()
    net = FakeNet()
    core = Core(runtime=rt, log_path=str(log), tail=False, web_fetch=net, update_repo=repo)
    core.config_path.write_text(json.dumps(cfg), encoding="ascii")
    return core, net


def test_no_typed_contact_uses_the_issues_page_and_is_not_blocked(tmp_path):
    # the default comes from the address constant only, never a literal
    own = updates.load_repo()
    assert webfetch.default_contact() == (
        "https://github.com/" + own + "/issues" if own else "")
    assert webfetch.default_contact(REPO) == ISSUES
    assert webfetch.effective_contact(None, ISSUES) == ISSUES
    core, net = _core(tmp_path, {"web_data": True, "league": "Standard"}, REPO)
    try:
        assert core.contact() is None            # nothing typed: the field stays optional
        assert core.effective_contact() == ISSUES
        assert core.web_blocked_reason() is None
        assert core.rates.blocked_reason() is None
        assert core.rates.refresh(force=True) not in ("off", "off: contact not set")
        assert net.calls
        assert all(c[2]["User-Agent"].endswith("(contact: " + ISSUES + ")") for c in net.calls)
        facts = core.diag_facts()
        assert facts["contact_set"] is True       # Checks: prices are not blocked
    finally:
        core.close()


def test_typed_contact_overrides_the_default(tmp_path):
    assert webfetch.effective_contact(TYPED, ISSUES) == TYPED
    assert webfetch.effective_contact("a(b)", ISSUES) == ISSUES  # unusable typed value
    core, net = _core(tmp_path, {"web_data": True, "league": "Standard",
                                 "contact": TYPED}, REPO)
    try:
        assert core.contact() == TYPED
        assert core.effective_contact() == TYPED
        assert core.web_blocked_reason() is None
        core.rates.refresh(force=True)
        assert net.calls
        for c in net.calls:
            ua = c[2]["User-Agent"]
            assert ua.endswith("(contact: " + TYPED + ")") and ISSUES not in ua
        # clearing the typed contact falls back to the issues page
        assert core.set_contact("") is False
        assert core.effective_contact() == ISSUES and core.web_blocked_reason() is None
    finally:
        core.close()


def test_default_is_empty_while_the_address_constant_is_unset(tmp_path):
    assert updates.load_repo(tmp_path / "missing.json") == ""
    for repo in ("", None, "not a repo", "a/b/c", 7):
        assert webfetch.default_contact(repo if repo is not None else "") == ""
    assert webfetch.effective_contact(None, "") is None
    core, net = _core(tmp_path, {"web_data": True, "league": "Standard"}, "")
    try:
        assert core.contact() is None and core.effective_contact() is None
        assert core.web_blocked_reason() == webfetch.REASON_CONTACT
        assert core.rates.refresh(force=True) == "off: " + webfetch.REASON_CONTACT
        assert net.calls == []
        assert core.diag_facts()["contact_set"] is False
    finally:
        core.close()
