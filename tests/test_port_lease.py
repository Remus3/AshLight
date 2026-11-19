"""TEST-PORT-LEASE (finding F-022): a test that binds a real port leases it
from ports.TEST_LEASE_PORTS (8962-8969) through tests/tc_live_util.lease_port.
A lease is an OS lock on <sidecar Temp>/port-leases/<port>.lock held for the
test's life plus a 127.0.0.1 bind probe, so two runs of this tree (two
worktrees, or xdist workers) never get the same port.
"""

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from server.al import paths, ports
from tc_live_util import (LEASE_DIR, held_leases, lease_candidates, lease_lock_dir,
                          lease_port)

ROOT = Path(__file__).resolve().parents[1]
LO, HI = ports.TEST_LEASE_PORTS
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)

CHILD = r"""
import sys, time
from pathlib import Path
root = Path(sys.argv[1])
sys.path[:0] = [str(root), str(root / "tests")]
import pytest
import tc_live_util
go = Path(sys.argv[2])
end = time.monotonic() + 30
while not go.exists() and time.monotonic() < end:
    time.sleep(0.005)
try:
    port, release = tc_live_util.lease_port(wait_s=5)
except pytest.skip.Exception:
    print("SKIP", flush=True)
    sys.exit(0)
print(port, flush=True)
sys.stdin.read()  # hold the lease until the parent closes stdin
release()
"""


def test_candidates_are_the_lease_block_only():
    cands = lease_candidates()
    assert cands == list(range(LO, HI + 1))
    assert (LO, HI) == (8962, 8969)
    never = {ports.AL_PORT, ports.AL_DEV_PORT, *ports.OAUTH_REDIRECT_PORTS,
             *range(ports.DEMO_BLOCK[0], ports.DEMO_BLOCK[1] + 1)}
    assert not never & set(cands)
    # a caller cannot widen the lease to a named port either
    with pytest.raises(pytest.skip.Exception):
        lease_port(candidates=[ports.AL_PORT, ports.AL_DEV_PORT,
                               ports.OAUTH_REDIRECT_PORTS[0]], wait_s=0)


def test_lock_folder_resolves_under_the_sidecar_temp(tmp_path):
    assert LEASE_DIR == paths.sidecar_dir("Temp") / "port-leases"
    moved = lease_lock_dir({paths.SIDECAR_ENV: str(tmp_path / "AL")})
    assert moved == (tmp_path / "AL").resolve() / "Temp" / "port-leases"


def test_a_held_lease_is_skipped_and_release_frees_it():
    port, release = lease_port()
    try:
        assert LO <= port <= HI
        assert port in held_leases()
        assert (LEASE_DIR / f"{port}.lock").is_file()
        with pytest.raises(pytest.skip.Exception):
            lease_port(candidates=[port], wait_s=0)
        other, rel2 = lease_port()
        try:
            assert other != port
        finally:
            rel2()
    finally:
        release()
    release()  # idempotent
    assert port not in held_leases()
    again, rel3 = lease_port(candidates=[port], wait_s=0)
    try:
        assert again == port
    finally:
        rel3()


def test_a_port_that_fails_to_bind_is_skipped():
    port, release = lease_port()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((ports.LOOPBACK, port))
        sock.listen(1)
        release()  # the lock is free now, but the port is bound
        with pytest.raises(pytest.skip.Exception):
            lease_port(candidates=[port], wait_s=0)
        assert port not in held_leases()
    finally:
        sock.close()
        release()


def test_all_taken_waits_until_the_deadline_then_skips():
    port, release = lease_port()
    try:
        t0 = time.monotonic()
        with pytest.raises(pytest.skip.Exception):
            lease_port(candidates=[port], wait_s=0.6)
        assert time.monotonic() - t0 >= 0.5
    finally:
        release()


def _read_line(proc, out, i):
    out[i] = proc.stdout.readline().strip()


def test_two_processes_leasing_at_once_get_different_ports(tmp_path):
    go = tmp_path / "go"
    env = {k: v for k, v in os.environ.items() if k != paths.SIDECAR_ENV}
    procs = [subprocess.Popen([sys.executable, "-c", CHILD, str(ROOT), str(go)],
                              cwd=str(ROOT), env=env, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, creationflags=FLAGS)
             for _ in range(2)]
    got = [None, None]
    try:
        time.sleep(1.0)  # both children importing, then waiting on the go file
        go.write_text("go\n", encoding="ascii")  # both lease at the same moment
        readers = [threading.Thread(target=_read_line, args=(p, got, i), daemon=True)
                   for i, p in enumerate(procs)]
        for t in readers:
            t.start()
        for t in readers:
            t.join(timeout=60)
        if "SKIP" in got:
            pytest.skip("the lease block is full (other runs hold every port)")
        a, b = (int(x) for x in got)
        assert LO <= a <= HI and LO <= b <= HI
        assert a != b
    finally:
        for p in procs:
            try:
                p.stdin.close()
            except OSError:
                pass
        for p in procs:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=10)
            p.stdout.close()
