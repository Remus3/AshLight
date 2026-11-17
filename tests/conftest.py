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

os.environ["FLEET_SIDECAR_ROOT"] = ""  # empty value = off (process env wins)

fleet_test_guard.install(globals(), root=ROOT, env_roots={})


def pytest_configure(config):
    for name, doc in (("slow", "call takes over about 1.5 s"),
                      ("server", "binds a socket on 127.0.0.1"),
                      ("git", "spawns a real git process")):
        config.addinivalue_line("markers", f"{name}: {doc}")
