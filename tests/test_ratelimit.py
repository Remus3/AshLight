"""TC-GGG-RATELIMIT: the header-driven rate limiter (server/al/ratelimit.py).

Synthetic headers only; no request is made and no socket is opened.
"""
import ast
from pathlib import Path

from server.al import ratelimit
from server.al.ratelimit import RateLimiter

SRC = Path(ratelimit.__file__)


class Clock:
    def __init__(self, t=1000.0, wall=1_800_000_000.0):
        self.t = t
        self.w = wall

    def mono(self):
        return self.t

    def wall(self):
        return self.w

    def tick(self, s):
        self.t += s
        self.w += s


def make():
    c = Clock()
    return c, RateLimiter(clock=c.mono, wall=c.wall)


def hdrs(rules, state=None, policy="test-policy", extra=None):
    """rules: {name: 'h:p:r,...'}, state: {name: 'c:p:a,...'}"""
    h = {"X-Rate-Limit-Policy": policy,
         "X-Rate-Limit-Rules": ",".join(rules)}
    for name, val in rules.items():
        h["X-Rate-Limit-" + name] = val
    for name, val in (state or {}).items():
        h["X-Rate-Limit-" + name + "-State"] = val
    h.update(extra or {})
    return h


def test_fresh_key_waits_nothing():
    _, rl = make()
    assert rl.wait_s("k") == 0.0


def test_parse_rules_and_windows():
    _, rl = make()
    rl.observe("k", 200, hdrs({"Ip": "5:10:60,30:300:600", "Account": "2:5:10"},
                              {"Ip": "1:10:0,1:300:0", "Account": "1:5:0"}))
    assert rl.policy("k") == "test-policy"
    assert rl.rules("k") == {"Ip": [(5, 10, 60), (30, 300, 600)],
                             "Account": [(2, 5, 10)]}


def test_several_rules_and_windows_tightest_wins():
    c, rl = make()
    h = hdrs({"Ip": "3:10:60,100:300:600", "Account": "2:4:30"})
    rl.observe("k", 200, h)
    rl.note_request("k")
    c.tick(1)
    assert rl.wait_s("k") == 0.0
    rl.note_request("k")
    # Account 2 hits in 4 s is full: first hit (t=1000) ages out at 1004
    assert abs(rl.wait_s("k") - 3.0) < 1e-9
    c.tick(3)
    assert rl.wait_s("k") == 0.0
    rl.note_request("k")
    # Ip 3 in 10 s is full now: wait until the first hit (t=1000) + 10
    assert abs(rl.wait_s("k") - 6.0) < 1e-9


def test_server_state_count_is_followed():
    c, rl = make()
    # server says the 10 s window already holds 5 of 5 hits
    rl.observe("k", 200, hdrs({"Ip": "5:10:60"}, {"Ip": "5:10:0"}))
    assert abs(rl.wait_s("k") - 10.0) < 1e-9
    c.tick(10)
    assert rl.wait_s("k") == 0.0


def test_server_count_plus_own_hits_since():
    c, rl = make()
    rl.observe("k", 200, hdrs({"Ip": "3:10:60"}, {"Ip": "2:10:0"}))
    assert rl.wait_s("k") == 0.0
    c.tick(1)
    rl.note_request("k")
    assert abs(rl.wait_s("k") - 9.0) < 1e-9


def test_active_restriction_in_state_blocks():
    c, rl = make()
    rl.observe("k", 200, hdrs({"Ip": "5:10:60"}, {"Ip": "6:10:60"}))
    assert abs(rl.wait_s("k") - 60.0) < 1e-9
    c.tick(59)
    assert abs(rl.wait_s("k") - 1.0) < 1e-9
    c.tick(1)
    assert rl.wait_s("k") == 0.0


def test_retry_after_wins():
    c, rl = make()
    h = hdrs({"Ip": "5:10:60"}, {"Ip": "6:10:60"}, extra={"Retry-After": "120"})
    rl.observe("k", 429, h)
    assert abs(rl.wait_s("k") - 120.0) < 1e-9
    # a shorter Retry-After also wins over the 60 s restriction (the window
    # count itself is under its limit here, so only the block decides)
    _, rl2 = make()
    rl2.observe("k", 429, hdrs({"Ip": "5:10:60"}, {"Ip": "4:10:60"},
                               extra={"Retry-After": "7"}))
    assert abs(rl2.wait_s("k") - 7.0) < 1e-9


def test_retry_after_http_date():
    c, rl = make()
    import email.utils
    when = email.utils.formatdate(c.w + 30, usegmt=True)
    rl.observe("k", 429, {"Retry-After": when})
    assert abs(rl.wait_s("k") - 30.0) < 1.0


def test_bare_429_backs_off_by_floor_and_doubles():
    c, rl = make()
    rl.observe("k", 429, {})
    assert rl.wait_s("k") == ratelimit.FLOOR_429_S
    c.tick(ratelimit.FLOOR_429_S)
    assert rl.wait_s("k") == 0.0
    rl.observe("k", 429, {})
    assert rl.wait_s("k") == 2 * ratelimit.FLOOR_429_S
    for _ in range(20):
        rl.observe("k", 429, None)
    assert rl.wait_s("k") <= ratelimit.FLOOR_429_MAX_S
    c.tick(ratelimit.FLOOR_429_MAX_S)
    rl.observe("k", 200, {})
    rl.observe("k", 429, {})
    assert rl.wait_s("k") == ratelimit.FLOOR_429_S


def test_429_with_rule_headers_but_no_restriction_still_floors():
    _, rl = make()
    rl.observe("k", 429, hdrs({"Ip": "5:10:60"}, {"Ip": "1:10:0"}))
    assert rl.wait_s("k") >= ratelimit.FLOOR_429_S


def test_wait_never_negative():
    c, rl = make()
    rl.observe("k", 200, hdrs({"Ip": "1:5:10"}, {"Ip": "1:5:0"}))
    rl.note_request("k")
    rl.observe("k", 429, {"Retry-After": "3"})
    for _ in range(50):
        c.tick(1.7)
        assert rl.wait_s("k") >= 0.0
    rl.observe("k", 429, {"Retry-After": "Thu, 01 Jan 1970 00:00:00 GMT"})
    assert rl.wait_s("k") >= 0.0
    rl.observe("k", 200, {"Retry-After": "-5"})
    assert rl.wait_s("k") >= 0.0


def test_wait_is_capped():
    _, rl = make()
    rl.observe("k", 429, {"Retry-After": "99999999"})
    assert rl.wait_s("k") == ratelimit.MAX_WAIT_S


def test_unknown_rule_names_are_obeyed():
    c, rl = make()
    rl.observe("k", 200, hdrs({"Nebula": "1:20:60"}, {"Nebula": "1:20:0"}))
    assert abs(rl.wait_s("k") - 20.0) < 1e-9
    rl.observe("k", 200, hdrs({"Zeta-2": "9:9:9"}, {"Zeta-2": "0:9:45"}))
    assert abs(rl.wait_s("k") - 45.0) < 1e-9


def test_rules_change_dynamically():
    c, rl = make()
    rl.observe("k", 200, hdrs({"Ip": "1:10:60"}))
    rl.note_request("k")
    assert rl.wait_s("k") > 0
    rl.observe("k", 200, hdrs({"Ip": "100:10:60"}, {"Ip": "1:10:0"}))
    assert rl.wait_s("k") == 0.0


def test_case_insensitive_and_pair_lists():
    _, rl = make()
    rl.observe("k", 200, [("x-rate-limit-rules", "ip"), ("x-rate-limit-ip", "1:30:60"),
                          ("x-rate-limit-ip-state", "1:30:0")])
    assert abs(rl.wait_s("k") - 30.0) < 1e-9


def test_malformed_headers_ignored():
    _, rl = make()
    rl.observe("k", 200, {"X-Rate-Limit-Rules": "Ip,../x, ,A B",
                          "X-Rate-Limit-Ip": "a:b:c,5:0:1,5:10",
                          "X-Rate-Limit-Ip-State": "x" * 2000,
                          "Retry-After": "soon"})
    assert rl.wait_s("k") == 0.0
    assert rl.rules("k") == {}


def test_keys_are_independent():
    _, rl = make()
    rl.observe("a", 429, {"Retry-After": "50"})
    assert rl.wait_s("a") == 50.0
    assert rl.wait_s("b") == 0.0


def test_state_survives_only_in_memory():
    _, rl = make()
    rl.observe("k", 429, {"Retry-After": "50"})
    _, fresh = make()
    assert fresh.wait_s("k") == 0.0
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0] or ".")
        elif isinstance(node, ast.Name) and node.id == "open":
            raise AssertionError("ratelimit.py must not open a file")
    assert names <= {"email", "time"}, names


def test_own_hits_list_is_bounded():
    c, rl = make()
    rl.observe("k", 200, hdrs({"Ip": "100000:86400:60"}))
    for _ in range(ratelimit.MAX_HITS_KEPT + 50):
        rl.note_request("k")
        c.tick(0.001)
    assert len(rl._keys["k"].sent) <= ratelimit.MAX_HITS_KEPT
