# 0049 - Demo mode: an isolated AshLight instance on a fixture folder

Date: 2026-11-18. Source: package SEC-DEMO-CORE (wave 2); finding F-034
(CORE-DEMO-MODE, docs/plan/02-findings.md); open items OPEN-31 and
OPEN-46; the "Port block" table of docs/plan/07-execution-plan.md;
decisions 0003, 0012, 0013 and 0042; SEC-NO-DISCOVERY (wave 1). The entry
point `python -m server.al --demo <fixture dir>` and the shipped fixture
are SEC-DEMO-ENTRY's (wave 3); this record covers the core and the port
table.

## Decision

1. Fixture folder. A demo instance runs on a folder that holds AshLight's
   demo marker `ashlight-demo.json` (a JSON object, at most 64 KB) and a
   `Client.txt` file. A missing folder, marker or log, a marker that is
   not a JSON object, or a link / junction as the folder or its log is an
   error (`demo.DemoError`) and nothing is made.
2. Never a game folder. A path with a `steamapps` or `Path of Exile 2`
   part (any case) is refused from its text alone, before any stat, as
   given, as made absolute and once more after the folder resolves.
3. Scratch. `demo.prepare` makes `<sidecar Temp>/demo-*` (the Temp dir is
   resolved before any override, decision 0012 placement) and points
   this process at it: `AL_RUNTIME_DIR` = scratch/runtime,
   `AL_SIDECAR_ROOT` = scratch/sidecar (its sidecar subfolders made),
   `AL_HOT_RELOAD=0`, and `paths.local_config_file()` = scratch/runtime/
   local.json through `paths.set_demo_config`, which only `demo.prepare`
   calls. config/local.json and the live ops/runtime are never read or
   written.
4. Consent. `prepare` writes the demo consent record into the scratch
   runtime: consented, `demo: true`, `scope: demo fixture file only`, and
   the fixture log's path. It covers that one file (decision 0003: the
   fixture is AshLight's own synthetic log, not the player's).
5. DemoCore. `demo.DemoCore(demo)` is a Core with runtime = scratch,
   log_path = the fixture Client.txt, `discover=False` (no Steam scan),
   config_path = the scratch config and a web transport
   (`demo.refuse_fetch`) that raises `WebDataOff` for every request;
   `web_data_enabled()` is always False, even if the scratch config says
   otherwise. A caller cannot pass runtime, log_path, discover,
   web_fetch or config_path. The consent API may turn reading on or off
   but a consent `path` is refused (ValueError, the API's 400).
6. Exit 97. Before a log is located or a tailer is started, the path is
   checked: lexically inside the fixture folder, and inside it again
   once resolved. Otherwise the injectable exit function runs with code
   97 (default: a message on stderr, then `os._exit(97)`), and a
   returning exit function still ends in `SystemExit(97)`, so the open
   never happens.
7. Port. `demo.pick_port(probe)` returns the first free port of
   `ports.DEMO_BLOCK` (default probe: a loopback bind, closed at once),
   never 8960; a full block is a DemoError.
8. Port table (docs/plan/07 "Port block", defined here once, pinned by
   tests/test_ports_alloc.py; other packages use the names): AL_PORT
   8960; AL_DEV_PORT 8961; TEST_LEASE_PORTS 8962-8969; DEMO_BLOCK and
   SELFTEST_PORTS 8970-8975 (one block, both probe); SPARE_PORTS
   8976-8977; OAUTH_REDIRECT_PORTS 8979 and 8978 (fixed, decision 0048,
   in no other range). `ports.block_range` turns a pair into its ports.

## Choices the package text left open (ruled by the builder)

- Marker content: any JSON object, not a fixed schema. Alternatives: a
  required key or version. Why: the file name is the marker; a schema
  would bind SEC-DEMO-ENTRY's fixture to a shape nobody reads yet.
  Reverses if: a second marker version is needed.
- Links refused: the folder and its Client.txt may not be a symlink or
  junction (lstat only). Alternatives: resolve and accept a link that
  stays inside. Why: a fixture is a copy; a link is the one way the
  lexical check could be walked out of. Reverses if: a real demo setup
  needs a linked fixture.
- Default exit is `os._exit(97)`: the guard can fire on an HTTP or core
  thread, where `sys.exit` would end only that thread. Reverses if: a
  clean-shutdown channel is added to the core.
- Scratch folders are kept after a run (what a demo wrote can be looked
  at); they live in the sidecar Temp folder, which holds only throwaway
  files. Alternatives: remove on exit. Why: an exit 97 or a crash would
  skip the removal anyway. Reverses if: demo runs pile up in Temp.

## Alternatives

- A demo flag inside Core: every Core path would carry a demo branch;
  a subclass keeps the live core unchanged. Rejected.
- Web data through a loopback mock (F-034 offered it): a mock is a server
  to keep; a refusing transport is enough for screenshots and tests.
  Rejected for now.
- Demo on port 8960 when free: a demo could then be mistaken for, or
  block, the player's core. Rejected.
- Separate port packages per user (demo, self-test, leases): the ranges
  overlapped; one table defined once (docs/plan/07 review).

## Why

Screenshots, the fit harness and the install self-test need a real core
that provably cannot reach the player's log, config, runtime or the
network. A fixture folder with a marker, a scratch runtime and an exit
before any outside open make that a property of the code, checked by
tests/test_demo_mode.py.

## Reverses if

A demo core is ever seen opening a file outside its fixture and scratch
dirs, or the operator rules a demo instance unwanted.
