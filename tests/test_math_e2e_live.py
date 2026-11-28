"""MATH-E2E-LIVE: the whole theorycraft path on real data (decision 0028).

A test core on a leased test port (8962-8969), a temp runtime whose own
local.json turns "tc_calc" on (the operator's config/local.json is never
read or written: a test core reads only its runtime's config), the real
reference build posted as a PoB code to POST /api/build-code, then real
item texts (tests/math_live_items.py, PoE2 copy format) posted to
POST /api/eval. The card's DPS / EHP deltas must come from PoB through
TC-DELTA (calc.source "pob", base outputs equal to the PoB GUI reference),
point the right way, arrive within the decision 0028 budgets, and fall back
gracefully when the calc process is killed mid-request.

Skips unless the optional calc component (setup.ps1 -TcCalc) and the PoB
GUI reference (sidecar Cache\\tc_bridge, decision 0027) both exist.
"""

import http.client
import json
import threading
import time
from pathlib import Path

import pytest

import math_live_items as items
from tc_live_util import (BUDGET, CALC_GROUP_B, LIVE_CALC, LIVE_REF, keep_warm, lease_port,
                          reference)

from server.al.core import Core
from server.al.http import serve
from server.al.theorycraft import augment, bridge, codec, delta

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "m" * 48
SIDE_BAND = delta.SIDEGRADE_PCT

# TEST-CALC-GROUP-SPLIT: the calc mark for the whole module, the xdist
# group per test (one group each): test_repeat_press_uses_cached_probes is
# self-contained (TEST-E2E-REPEAT-SELF), so it runs in calc-b beside
# test_fullstack_calc_on_leg while the rest of the file stays in calc-a.
# Wave 30 ruling (decision 0060): a test that asserts a wall-clock press
# budget runs in the serial timing phase. Wave 31 GATE-HOLD ruling (option
# A): one proof per budget stays timed and serial (ring: first_press_s,
# body: press_s, repeat: repeat_press_s, killed: fallback_press_s); the
# amulet and bow correctness checks run untimed in the parallel phase.
pytestmark = [pytest.mark.server, pytest.mark.slow, LIVE_REF, pytest.mark.calc]


def _req(port, method, path, body=None, timeout=120):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    h = {"Host": f"127.0.0.1:{port}", "X-AL-Token": TOKEN}
    data = None
    if body is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(body).encode("ascii")
    conn.request(method, path, body=data, headers=h)
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    return r.status, json.loads(raw)


@pytest.fixture(scope="module")
def live(tmp_path_factory, warm_bridge):
    ref, xml = reference()
    tmp = tmp_path_factory.mktemp("e2e_live")
    rt = tmp / "rt"
    rt.mkdir()
    cfg = rt / "local.json"
    cfg.write_text(json.dumps({"tc_calc": True}), encoding="ascii")
    log = tmp / "Client.txt"
    log.write_bytes(b"")
    # TEST-FULLSTACK-CALC-WARM: the session's warm shared bridge (the cold
    # start is measured in test_math_perf); the first press still pays the
    # build's first probes, under the first-press budget. GATE-HOLD:
    # keep_warm shares one PoB weight cache per test process, so in a whole
    # run test_fullstack_calc_on_leg (first by file order) pays the ring's
    # cold probes under the same budget and the ring press here is cached.
    core = Core(runtime=rt, log_path=str(log), poll_s=0.05, config_path=cfg)
    stops = keep_warm(core)
    assert core.config_path == cfg  # never the operator's config/local.json
    port, release = lease_port()
    server = serve(core, TOKEN, port=port, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    status, snap = _req(port, "POST", "/api/build-code", {"code": codec.encode(xml)})
    assert status == 200, snap
    ctx = {"port": port, "core": core, "ref": ref, "times": {}}
    try:
        yield ctx
    finally:
        server.stop()
        release()
        core.close()  # asks to stop the shared bridge (AUDIT-TC-WIRE) ...
        assert stops == [True]  # ... kept warm for the session here
        print("\nMATH-E2E-LIVE press times (s):",
              {k: round(v, 2) for k, v in ctx["times"].items()})


def _press(ctx, text, label):
    """One press; TC-PRESS-STAGED-LIVE: the reply is the first stage (the
    stat-weight card), so this waits for the last stage the core publishes
    and returns its result; `took` runs to that last stage."""
    t0 = time.perf_counter()
    status, first = _req(ctx["port"], "POST", "/api/eval", {"item": text})
    assert status == 200, first
    ctx["times"][label + "_reply"] = time.perf_counter() - t0
    last = ctx["core"].last_eval
    assert last.wait(BUDGET["first_press_s"] + 60), "the last stage never came"
    took = time.perf_counter() - t0
    ctx["times"][label] = took
    result = last.last_result
    assert result is not None and result["item"]["name"] == first["item"]["name"], result
    return result, took


def _best(result):
    comps = [c for c in result.get("comparisons") or [] if c.get("slot") == result.get("slot")]
    assert comps, f"no comparison for the best slot {result.get('slot')}: {result}"
    return comps[0]


def _sign_ok(change, want):
    p = change["pct"]
    if want == "+":
        return p > 0
    if want == "-":
        return p < 0
    if want == "~":
        return abs(p) <= 2 * SIDE_BAND
    return True


ORDER = ["ring_upgrade", "amulet_sidegrade", "bow_downgrade", "body_upgrade"]
# GATE-HOLD option A: the timed proofs (the first press of the module, then
# a warm press) and the untimed correctness checks
TIMED = ["ring_upgrade", "body_upgrade"]
UNTIMED = [n for n in ORDER if n not in TIMED]


@LIVE_CALC
@pytest.mark.timing
@pytest.mark.parametrize("name", TIMED)
def test_item_check_deltas_come_from_pob(live, name):
    """Waits for the last stage (TC-PRESS-STAGED-LIVE): PoB's numbers reach
    the card after the press reply, within the decision 0028 budget."""
    first = not live["times"]
    took = _check_deltas(live, name)
    assert took <= BUDGET["first_press_s" if first else "press_s"], took


@LIVE_CALC
@pytest.mark.parametrize("name", UNTIMED)
def test_item_check_deltas_come_from_pob_untimed(live, name):
    """The same PoB delta checks for the other items, with no time assert
    (the parallel phase; the budgets are proved by the timed tests)."""
    _check_deltas(live, name)


def _check_deltas(live, name):
    """One press of items.ITEMS[name] and every delta check; returns the
    press time (to the last stage)."""
    result, took = _press(live, items.ITEMS[name], name)
    assert result["ok"], result
    assert result["calc"] == {"source": "pob", "notice": None}, result["calc"]
    verdict, dps_sign, ehp_sign = items.EXPECT[name]
    best = _best(result)
    # the base figures are PoB's own: equal to the PoB GUI sidebar
    out = live["ref"]["outputs"]
    assert best["dps"]["old"] == pytest.approx(out["FullDPS"], rel=1e-3)
    assert best["ehp"]["old"] == pytest.approx(out["TotalEHP"], rel=1e-3)
    assert result["verdict"] == verdict, (name, best)
    assert _sign_ok(best["dps"], dps_sign), (name, best["dps"])
    assert _sign_ok(best["ehp"], ehp_sign), (name, best["ehp"])
    # magnitude: a single item never moves DPS by more than 3x or EHP by 2x
    assert -100 < best["dps"]["pct"] < 200 and -100 < best["ehp"]["pct"] < 100, best
    # MATH-WEIGHTS: the stat weights on the card are PoB-measured too
    assert result.get("mod_weights"), "no PoB per-mod weights"
    # the published card carries the same PoB deltas (dashboard + overlay)
    _, snap = _req(live["port"], "GET", "/api/state")
    card = snap["eval"]
    assert card["calc"]["source"] == "pob" and card["verdict"] == verdict
    cbest = [c for c in card["comparisons"] if c["slot"] == result["slot"]][0]
    assert cbest["dps"] == best["dps"] and cbest["ehp"] == best["ehp"]
    return took


@LIVE_CALC(group=CALC_GROUP_B)
@pytest.mark.timing
def test_repeat_press_uses_cached_probes(live):
    """TEST-E2E-REPEAT-SELF: self-contained in any order. The ring is pressed
    twice here: the first press fills the probe cache (a cold one may pay
    the build's first probes, under the first-press budget), and only the
    second press is held to the repeat budget."""
    warm, took = _press(live, items.RING_UPGRADE, "ring_repeat_warm")
    assert took <= BUDGET["first_press_s"], took
    assert warm["calc"]["source"] == "pob", warm["calc"]
    again, took = _press(live, items.RING_UPGRADE, "ring_repeat")
    assert took <= BUDGET["repeat_press_s"], took
    assert again["calc"]["source"] == "pob", again["calc"]
    assert _best(again)["dps"]["pct"] > 0


def _socketed_bow(inc):
    """TC-AUGMENT-WHATIF-LIVE: the bow of items.BOW_DOWNGRADE with two free
    rune sockets (a Sockets line, no rune line) and its own physical damage
    number, so no earlier press of this module has its probes cached."""
    text = items.BOW_DOWNGRADE.replace("62% increased", f"{inc}% increased")
    text = text.replace("Item Level: 79", "Sockets: S S\n--------\nItem Level: 79")
    assert text.count("Sockets: S S") == 1 and f"{inc}% increased" in text
    return text


def _check_augment(live, result):
    """The press reached the "augment" stage and it is Path of Building's."""
    assert result["ok"] and result["calc"]["source"] == "pob", result["calc"]
    aug = result.get("augment")
    assert isinstance(aug, dict), "no augment stage on a free-socket bow"
    assert aug["state"] == augment.STATE_READY, aug
    assert aug["slot"] == result["slot"] and aug["source"] == augment.SOURCE_ID, aug
    assert 1 <= aug["calls"] <= delta.MAX_PROBES and aug["tried"] <= aug["calls"], aug
    assert len(aug["top"]) <= augment.TOP_MAX, aug
    _, snap = _req(live["port"], "GET", "/api/state")
    assert snap["eval"]["calc"]["source"] == "pob"


@LIVE_CALC
@pytest.mark.timing
def test_augment_stage_within_press_budget(live):
    """TC-AUGMENT-WHATIF-LIVE (decision 0093 and its 2026-11-28 amendment):
    a bow with a free socket gets the augment stage after the pob and mods
    stages; the first press of the item stays within the first-press budget
    and a warm press of a fresh variant (bridge warm, its probes not cached)
    within the 12 s warm budget, every stage included (manual 2026-11-28:
    11.21 s first, 5.97 / 6.35 s warm)."""
    assert live["core"].augments.get(), "no pinned augment rows (decision 0091)"
    first, took = _press(live, _socketed_bow(66), "augment_first")
    _check_augment(live, first)
    assert took <= BUDGET["first_press_s"], took
    warm, took = _press(live, _socketed_bow(67), "augment_warm")
    _check_augment(live, warm)
    assert took <= BUDGET["press_s"], took


@LIVE_CALC
@pytest.mark.timing
def test_killed_calc_falls_back_then_recovers(live):
    """The calc process is killed again and again while a press runs: the
    press still answers 200 within budget with the weights fallback and the
    "failed" notice; once the killing stops the next press is PoB again."""
    stop = threading.Event()
    kills = []

    def killer():
        while not stop.is_set():
            b = bridge._SHARED
            proc = b._proc if b is not None else None
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                    kills.append(time.monotonic())
                except OSError:
                    pass
            time.sleep(0.02)

    # a slot whose probes are not cached, so the press needs the calc
    text = items.BOW_DOWNGRADE.replace("62% increased", "71% increased")
    box = {}

    def press():
        try:
            box["r"] = _press(live, text, "killed")
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            box["e"] = exc

    p = threading.Thread(target=press, daemon=True)
    p.start()
    time.sleep(0.5)  # the press is now mid-request (a fresh slot takes ~5 s)
    assert p.is_alive(), "the press ended before the kill"
    t = threading.Thread(target=killer, daemon=True)
    t.start()
    try:
        p.join(BUDGET["fallback_press_s"] + 30)
    finally:
        stop.set()
        t.join(5)
    if "e" in box:
        raise box["e"]
    result, took = box["r"]
    assert kills, "the killer never saw a running calc process"
    assert result["ok"], result
    assert result["calc"]["notice"] == delta.NOTICE_FAILED, result["calc"]
    assert result["calc"]["source"] in ("weights", "pob_cached"), result["calc"]
    assert took <= BUDGET["fallback_press_s"], took
    _, snap = _req(live["port"], "GET", "/api/state")
    assert snap["eval"]["calc"]["notice"] == delta.NOTICE_FAILED
    again, _ = _press(live, items.AMULET_SIDEGRADE, "recovered")
    assert again["calc"] == {"source": "pob", "notice": None}, again["calc"]
