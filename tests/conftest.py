"""Kit v12 race guard (FLEET-COMMON 16 d): a suite that changes live state
(ops/loop/control, moon_sync_inbox, moon_sync_outbox) fails. AshLight code
resolves its runtime roots from the repo path, so env_roots is empty.

Kit v14 3.4: FLEET_SIDECAR_ROOT is pinned to "" (off) for the whole suite, so
fleet_lanes.worktree_path() never reads the machine variable."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops" / "fleet_kit"))
sys.path.insert(0, str(ROOT))
import fleet_test_guard  # noqa: E402
import pytest  # noqa: E402

os.environ["FLEET_SIDECAR_ROOT"] = ""  # empty value = off (process env wins)
# HOT-RELOAD (decision 0042): a real core or supervisor a test starts from
# this source checkout never restarts on a .py edit made during the suite;
# the hot reload tests pass their own environ.
os.environ["AL_HOT_RELOAD"] = "0"

# TEST-FLAKE: the armed lane loop (tools/al_loop.py tick, every 15 min) and
# its lanes rewrite these control files while a suite may be running, so the
# guard reported a false "created/changed" at a random teardown. They are the
# tick's own state (tools/loop_base.py *_REL), never written by a test against
# the live root; the kit's documented mechanism is extra_ignore. HALT and
# SESSION_HALT stay watched (stop sentinels).
LOOP_TICK_STATE = (
    "ops/loop/control/loop_items/*",
    "ops/loop/control/loop_inbox_watch.json",
    "ops/loop/control/loop_orders.json",
    "ops/loop/control/backoff.json",
    "ops/loop/control/gate_verdicts.json",
    "ops/loop/control/push_worker.json",
    "ops/loop/control/push_last.json",
    "ops/loop/control/ledger_rotate.json",
)

fleet_test_guard.install(globals(), root=ROOT, env_roots={},
                         extra_ignore=LOOP_TICK_STATE)


@pytest.fixture(scope="session")
def warm_bridge():
    """TEST-FULLSTACK-CALC-WARM: one live calc process (the core's shared
    bridge, bridge.shared()) for the whole test session, for the live calc
    tests that do not measure a cold start or need a fresh process
    (test_math_perf measures the cold start and test_tc_bridge's reload /
    leak test keeps its own process). A test core using it must not stop it
    on close: tests/tc_live_util.keep_warm(core). Skips when the
    optional calc component is absent."""
    from server.al.theorycraft import bridge
    if not bridge.available():
        pytest.skip("optional calc component absent (setup.ps1 -TcCalc)")
    b = bridge.shared()
    b.ping()
    yield b
    bridge.shutdown_shared()


@pytest.fixture(autouse=True)
def _no_real_steam_scan(request, monkeypatch):
    """SEC-NO-DISCOVERY: no test may look for the live Client.txt. Reading
    Steam's registry key or the Program Files roots fails the test; a test
    that passes steam_roots itself never reaches them. Opt out with
    @pytest.mark.discovery (a test that stubs the lookup on purpose).
    A lookup from a core thread, where the raise cannot reach the test,
    fails the test at teardown. Yields the list of refused lookups."""
    if request.node.get_closest_marker("discovery") is not None:
        yield []
        return
    from server.al import logfile
    hits = []

    def guard(name):
        def refuse(*_a, **_k):
            hits.append(name)
            pytest.fail(f"a test reached the real Steam library lookup ({name}); "
                        "SEC-NO-DISCOVERY: pass steam_roots or a log path")
        return refuse

    monkeypatch.setattr(logfile, "_steam_roots_from_registry",
                        guard("_steam_roots_from_registry"))
    monkeypatch.setattr(logfile, "_steam_roots_from_env", guard("_steam_roots_from_env"))
    yield hits
    if hits:
        pytest.fail(f"real Steam library lookup reached: {sorted(set(hits))} "
                    "(SEC-NO-DISCOVERY)")


def pytest_configure(config):
    for name, doc in (("slow", "call takes over about 1.5 s"),
                      ("server", "binds a socket on 127.0.0.1"),
                      ("git", "spawns a real git process"),
                      ("discovery", "may reach the real Steam library lookup "
                                    "(SEC-NO-DISCOVERY guard off)")):
        config.addinivalue_line("markers", f"{name}: {doc}")


# TEST-SLOW-BUDGET (F-168): per-test call ceilings, the full-run suite
# ceiling and the five worst call times (tests/slow_budget.py).
import slow_budget  # noqa: E402
slow_budget.install(globals())
