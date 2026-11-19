"""GP-09 (decision 0080): what a test does differently on a CI runner.

AL_CI=1 is set only in .github/workflows/ci.yml. Decision 0002's timing
budgets are for the player's PC; a shared runner is slower and noisier,
so a wall-clock or CPU-share budget assert skips there with the measured
value printed, after the test's structural checks ran. Waits that only
bound how long a test may take get CI_FACTOR times longer. Locally (no
AL_CI) every budget stays hard and every wait keeps its value.
"""

import os

import pytest

CI_FACTOR = 3


def on_ci():
    return os.environ.get("AL_CI", "").strip() == "1"


def ci_scale(seconds):
    """A test wait: unchanged locally, CI_FACTOR times longer under AL_CI=1."""
    return seconds * CI_FACTOR if on_ci() else seconds


def skip_if_ci_timing(what, measured):
    """Call right before a timing-budget assert, after the structural ones.
    Under AL_CI=1 it prints why and skips; locally it does nothing."""
    if on_ci():
        reason = (f"AL_CI=1: timing budget not asserted on a shared runner "
                  f"(decision 0080): {what} measured {measured}")
        print(reason)
        pytest.skip(reason)
