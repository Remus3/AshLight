"""TC-DRIFT step (decision 0025): the daily PoB-PoE2 release check in the
work phase (never HALTed, never on a dry run). The check goes through the
Deps seam drift (al_loop._drift_check -> tools/tc_drift.loop_check), so the
test kit keeps the network away. Moved here unchanged by AUTO-01."""


def work(tick):
    return tick.d.drift(tick.root, tick.d.clock())
