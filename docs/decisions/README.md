# Decisions

One file per decision: `NNNN-<topic>.md` (decision, alternatives, why,
reverses if). Numbers 0047 to 0076 are reserved for the packages of
docs/plan/packages.json (docs/plan/07, Reserved decision numbers); a
package uses the number in its new_files entry. 0077 and 0078 are
taken. A decision written outside a package takes the next free
number: 0079 (read back 2026-11-18), then the next after the highest
file here.
Numbers are reserved per package in docs/plan/packages.json before a
wave starts; the wave integrator adds the index line. 0035 stays unused.

- 0078: ultraplan rulings ledger: Q-01 to Q-28, A-01 to A-03, the
  close-out LE rulings and R1 to R6 of the close-out 2, each with its
  default in force (ULTRAPLAN).
- 0077: ultraplan execution model: waves in sessions, per-wave
  integrator, loop tail, HALT removal point; 0047 to 0076 are reserved
  for packages in docs/plan/packages.json (ULTRAPLAN).
- 0054: core hello handshake: clients prove the core before they send
  the token (SEC-HELLO-CORE).
- 0053: main-process parts seam (app/parts/) (OVL-MAIN-PARTS).
- 0052: worn-gear baseline: parsed mod lines in a bounded per-character
  file (TC-WORN-STORE).
- 0051: private runtime files: an explicit ACL on the runtime dir and
  local config (SEC-ACL-APPLY).
- 0050: research dive sources - no free web tools, one host allow-list,
  GGG only at the API Reference and Data Exports pages (DIVE-FLOOR).
- 0049: Demo mode: an isolated AshLight instance on a fixture folder
  (SEC-DEMO-CORE).
- 0048: AshLight's own GGG OAuth public client: scope, ports, token
  handling (TC-OAUTH-REG).
- 0047: licence and NOTICE: Apache-2.0, holder The AshLight authors
  (GP-03).
- 0046: go public: guarded push, private first, public on gates
  (GP-02).
- 0045: per-character build, stale-build alert and upgrade notices
  (BUILD-LIVE).
- 0044: daily GGG developer docs watch, registration reopen alert
  (GGG-DOCS-WATCH).
- 0043: live zone guide and quest tracker (ZONE-GUIDE).
- 0042: hot reload of data files, web assets, overlay page and core
  code (HOT-RELOAD).
- 0041: desktop client (companion window, tray, overlay only inside the
  client) (DESKTOP-CLIENT).
- 0040: self checks and the non-English client notice
  (DIAG-SELF, LANG-GUARD).
- 0039: waystone reward totals and campaign checks
  (UTIL-WAYSTONE-REWARD, UTIL-CAMPAIGN-CHECKS).
- 0038: per-character run history, pace, act splits and deaths
  (UTIL-MULTICHAR).
- 0035: intentionally unused. It was reserved by a lane draft that never
  merged; do not reuse it (AREA-AUDIT P5-7, 2026-11-17).
