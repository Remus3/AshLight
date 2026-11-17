# TC-BRIDGE fixtures (decision 0022)

- `fake_bridge.py`: a Python stand-in for `server/al/theorycraft/bridge.lua`
  that speaks the same stdio protocol. The protocol, timeout-kill and
  crash-restart tests in `tests/test_tc_bridge.py` run against it, so they
  need no LuaJIT.
- `minimal_build.xml`: a hand-written, empty level-1 build for the live
  smoke test (load, then read numeric outputs).

## PoB GUI reference values (the row's 0.1 percent ACCEPT)

The live comparison test reads `gui_expected.json` from this folder (tracked,
only for a build its owner allowed, see `tests/fixtures/pob2_real/README.md`)
or from the gitignored `ops/runtime/tc_bridge/gui_expected.json`, or from
the AL sidecar `Cache\tc_bridge\gui_expected.json` (paths.py key
`tc_bridge_ref`; TC-LIVE recorded one there for a public pobb.in build):

    {
      "pob": "v0.23.1",
      "build_xml": "<file name next to this json>",
      "items": ["<optional item text to equip after load>"],
      "outputs": {"Life": 1234, "TotalDPS": 5678.9}
    }

Record the numbers by opening the same build XML in the Path of Building
PoE2 GUI at the pinned version and copying the sidebar values. Each output
must match the bridge within 0.1 percent. Without the file, or without the
optional calc component (`scripts/setup.ps1 -TcCalc`), the live tests skip.
