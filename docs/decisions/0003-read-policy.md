# 0003 - What AshLight reads, and when

Date: 2026-11-16. Input: `docs/research/0001-ggg-tool-policy.md` (verified
quotes of https://www.pathofexile.com/developer/docs, accessed 2026-11-16).

## Decision

- Client.txt: tailed continuously, read only, ONLY after the user's opt-in
  (first-run consent naming the file and what is derived from it), with a
  visible "reading Client.txt" indicator on the dashboard. GGG: "You may only
  read this information as long as the user is aware of what you are doing
  with that data."
- Clipboard and screen: read ONLY once per manual key press of an AshLight
  hotkey. No clipboard watcher, no timer, no continuous screen capture. GGG:
  "Reading from the screen or clipboard may only be performed once per manual
  key press."
- AshLight never sends any key, mouse or chat input to the game - not even
  the Ctrl+C that other tools synthesize. The user copies the item; the
  AshLight hotkey then reads the clipboard once.

## Alternatives

- Clipboard-change watcher (reads whenever the clipboard changes): ruled out,
  it reacts to events instead of a key press.
- Send Ctrl+C on the user's hotkey (Awakened PoE Trade / Exiled Exchange 2
  style): one action per key press is arguably allowed, but the floor here is
  stricter - no input to the game at all.

## Reverses if

GGG's developer docs change the overlay rules (re-read on every research
refresh; ROADMAP row RES-POLICY).

## Amendment 2026-11-18 (SEC-NO-DISCOVERY, plan units F-001, OPEN-30, OPEN-45)

Ruled under ruling 0050-Q6 ("only offer, never switch"), the stricter
reading while operator question A-03 (is the Steam library scan on the read
list) is open.
- Decision: only the real entry point with no configured log path runs the
  Steam library scan (registry key and libraryfolders.vdf, read only). A
  core given a runtime dir (a test or demo core) or a log path never scans
  (`Core(discover=None)` resolves to False then; a test may pass
  `discover=True` on purpose). A configured Client.txt path is used as is,
  existing or not, and never falls through to the scan; while it is
  missing the Checks row reads "The Client.txt path in your settings is
  missing." with a fix line, and the player decides (the offer is that row
  plus the typed path field of SEC-LOG-PATH-FIELD). Only a file named
  Client.txt (any case) is ever opened: a configured value with another
  last part is a folder (`<path>/logs/Client.txt` or `<path>/Client.txt`),
  and a consent path that is an existing file of another name is refused
  (400) with the tailer path unchanged. The test suite fails any test that
  reaches the real registry or Program Files lookup (tests/conftest.py,
  opt-out marker `discovery`).
- Alternatives: (b) keep the fall-through from a missing configured path
  to the scan - rejected: a test, demo or pointed core could read the
  player's live Client.txt without the indicator that instance shows, and
  0050-Q6 rules "never switch"; (c) remove the scan now - rejected: that
  is A-03's strict branch, carried by the parked package
  SEC-STEAM-SCAN-A03 once the typed path field lands; (d) open a
  configured file of any name - rejected: a mistyped or hostile path
  could make the tailer read an unrelated file.
- Why: Client.txt is read only by the instance whose indicator the player
  sees; reads nothing new; zero-click (the Checks row shows by itself).
- Reverses if: the operator rules on A-03 that the Steam scan must go (the
  typed path is then the only route), or stale configured paths strand
  players in normal use.
- Tests: tests/test_no_discovery.py, tests/test_audit_http_harden.py,
  tests/test_diag_self.py, tests/test_e2e_replay.py.
