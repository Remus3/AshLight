# 0088 - Weekly GitHub page review row (REVIEW-GH)

Status: accepted 2026-11-27 (operator order 2026-11-27).

## Decision

The operator ordered that the public GitHub repository is monitored and
maintained periodically and goes through review agents for UI/UX, visual,
readability, comprehension, ease of use and ease of setup. It is done as one
more upstream watcher source, with no new tick step and no new workflow:

1. `tools/watch_sources/github_page.py` (source `github-page`, home loop,
   cadence 7 days, network group, `needs_web_data` true). It reads through
   the same `gh api` path and web-data gate as the Dependabot watch
   (AUTO-20): only while web data is on, only in the main checkout's tick
   (ctx live; never a lane), every URL through `watch_gate.check_url` before
   any process, the AshLight User-Agent, hidden and below-normal.
2. Four metadata reads, no file content: `repos/<R>` (description, topics,
   homepage, has_discussions), `repos/<R>/releases?per_page=10` (newest
   non-draft tag), `repos/<R>/commits?path=README.md&per_page=1` (the last
   README commit stands for the README version) and
   `repos/<R>/community/profile` (health percentage, missing community
   files). METADATA_TAILS gains exactly `/community/profile` (decision 0069
   amendment 2026-11-27); every sub-path stays refused.
3. Each run yields one finding keyed `review:<YYYYMMDD>`, filed by
   tools/watch_file.py from the tracked template
   `ops/loop/watch_rows/github-page.json` as `REVIEW-GH-<YYYYMMDD>`, a
   review-lane row that is not BLOCKED (HALT, 3 a local day, the soft budget
   gate and the add-only commit rules of decisions 0025 / 0028 apply
   unchanged). The row names the six lenses, the files (README.md,
   docs/guide/, the .github templates, SECURITY.md, CONTRIBUTING.md), the
   design-reviewer agent and its standard, the README test facts as the
   limit of a fix, and docs/reviews/github/<date>.md as the record. Lanes
   have no gh, so the page snapshot rides in the row as short-word tokens:
   README commit (12 hex), release tag, homepage set / empty, description
   set / empty, topic count, missing community files.
4. Drift words in the row: readme or release moved since the last filed
   row, homepage empty, a community file missing; `first` with no earlier
   row, else `weekly`. A quiet week (nothing moved since the last filed row)
   files nothing while an earlier REVIEW-GH row is still open, so rows do
   not pile up when the lane falls behind; a persistent gap (an empty
   homepage) is named once and not re-filed weekly on top of an open row.

## Alternatives

- The `/readme` endpoint for the README sha: rejected, it serves file
  content, and the gate refuses the `readme` path word on GitHub hosts on
  purpose; the README commit list gives the same change signal from
  metadata.
- A tracked snapshot file written by the tick: rejected, a tick commit may
  touch only add-only row files (decision 0025 amendment, Q-12).
- A CI workflow doing the read: rejected, the dev loop already has gh and
  CI must not write rows or contents (decision 0069).
- A separate loop step in tools/loop_steps/: rejected, a watcher source gets
  cadence, state, the web-data gate, dedupe and filing from the frame.
- File on drift only: rejected, the order asks for a periodic review.

## Why

The public repository page is the first thing a player sees; the smallest
fit is a weekly watcher row that the review lane works unattended
(ZERO-CLICK), with drift named so the review knows what moved.

## Reverses if

GitHub treats the community profile as non-metadata or drops it, gh leaves
the dev host, the weekly rows crowd out row work or are mostly empty
reviews (then drift only), the operator changes the cadence or the lenses,
or a lane needs a read the row snapshot cannot carry (then a session row).
