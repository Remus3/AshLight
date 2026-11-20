"""Shared browser lookup for the headless-browser tests (not a test file).

find_browser() returns the path of an installed Chrome or Edge for the
DevTools-protocol drivers under app/test/cdp/ (dash_console.mjs, the one
capture helper capture.mjs), or None so the caller can skip. AL_CHROME
overrides the search. Moved out of tests/test_dash_console.py
(TEST-CAPTURE-HELPER) so no test file imports another (TEST-LAYOUT-GUARD).
"""

import os
import shutil
from pathlib import Path

BROWSERS = (r"Google\Chrome\Application\chrome.exe",
            r"Microsoft\Edge\Application\msedge.exe")


def find_browser():
    env = os.environ.get("AL_CHROME", "").strip().strip('"')
    if env and Path(env).is_file():
        return env
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        for rel in BROWSERS if base else ():
            p = Path(base) / rel
            if p.is_file():
                return str(p)
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        hit = shutil.which(name)
        if hit:
            return hit
    return None
