"""SEC-DEMO-CORE: the one port table of the block 8960-8979 (docs/plan/07,
"Port block"), defined once in server/al/ports.py and pinned here."""

import itertools

from server.al import ports

RANGES = {
    "AL_PORT": (ports.AL_PORT, ports.AL_PORT),
    "AL_DEV_PORT": (ports.AL_DEV_PORT, ports.AL_DEV_PORT),
    "TEST_LEASE_PORTS": ports.TEST_LEASE_PORTS,
    "DEMO_BLOCK": ports.DEMO_BLOCK,
    "SELFTEST_PORTS": ports.SELFTEST_PORTS,
    "OAUTH_REDIRECT_PORTS": ports.OAUTH_REDIRECT_PORTS,
    "SPARE_PORTS": ports.SPARE_PORTS,
}
SHARED = {"DEMO_BLOCK", "SELFTEST_PORTS"}  # one block on purpose


def _set(name):
    return set(ports.block_range(RANGES[name]))


def test_the_table_values():
    assert ports.PORT_BLOCK == (8960, 8979)
    assert ports.AL_PORT == 8960
    assert ports.AL_DEV_PORT == 8961
    assert ports.TEST_LEASE_PORTS == (8962, 8969)
    assert ports.DEMO_BLOCK == (8970, 8975)
    assert ports.SELFTEST_PORTS == ports.DEMO_BLOCK
    assert ports.OAUTH_REDIRECT_PORTS == (8979, 8978)
    assert ports.SPARE_PORTS == (8976, 8977)


def test_ranges_are_pairwise_disjoint_except_demo_and_selftest():
    for a, b in itertools.combinations(sorted(RANGES), 2):
        overlap = _set(a) & _set(b)
        if {a, b} == SHARED:
            assert _set(a) == _set(b), "DEMO_BLOCK and SELFTEST_PORTS are one block"
        else:
            assert not overlap, (a, b, sorted(overlap))


def test_every_port_is_in_the_block_and_the_table_covers_it():
    covered = set()
    for name in RANGES:
        for port in _set(name):
            assert ports.in_block(port), (name, port)
        covered |= _set(name)
    lo, hi = ports.PORT_BLOCK
    assert covered == set(range(lo, hi + 1))


def test_8960_is_only_the_core_port():
    for name in RANGES:
        if name != "AL_PORT":
            assert ports.AL_PORT not in _set(name), name


def test_oauth_redirect_ports_are_in_no_other_range():
    oauth = _set("OAUTH_REDIRECT_PORTS")
    assert len(oauth) == 2
    for name in RANGES:
        if name != "OAUTH_REDIRECT_PORTS":
            assert not (oauth & _set(name)), name


def test_block_range_is_inclusive_either_order():
    assert list(ports.block_range((8979, 8978))) == [8978, 8979]
    assert list(ports.block_range((8970, 8975))) == list(range(8970, 8976))
