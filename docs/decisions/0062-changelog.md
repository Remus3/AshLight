# 0062 - Changelog: one generator, per-version notes files

Date: 2026-11-19. Source: docs/plan/05-deployment.md (goal G5, section
"Changelog generation", decision D7), finding F-101, package DEP-04;
REL-SUBJECT-CHECK (the commit-msg hook that types every subject);
DEP-03 (the `release.py` dispatcher and the notes stub of `bump`).

## Decision

1. One generator: `python tools/release.py notes` (module
   tools/rel_notes.py, loaded by the DEP-03 dispatcher). No other
   changelog tool is built.
2. Inputs are first-parent commit subjects only (`git log --first-parent
   --format=%H%x09%s`), never bodies or trailers, so no attribution line
   can reach a notes file (FLEET item 17). The range is the newest `v*`
   tag below the version reachable from the ref, to the ref; the whole
   history for the first release. Subject types come from
   tools/commit_subject.py.
3. A row id is named by `merge: <ROW-ID> ...` (the first word) or by the
   scope of `type(<ROW-ID>): ...`. The id has the loop's row id shape
   (tools/loop_base.py ROW_ID) and carries a `-` or is a known row id.
   Row titles and kinds (the lane in parentheses) come from ROADMAP.md at
   both ends of the range plus the ROADMAP.md diff of every first-parent
   commit in it, so rows pruned at /done keep their title. ROADMAP.md at
   the end wins, then the newest diff, then ROADMAP.md at the start. A
   line shows the title's first sentence with the loader's done mark
   removed.
4. One line per row id, `- <title> (<ROW-ID>)`. Groups, first match wins:
   Security (a security or deps commit of the row, or an Electron pin row:
   a title naming Electron and a pin), Changed (a (data) row), Added
   (feat), Fixed (fix), Changed (perf, refactor, data), Added (a merged
   row with nothing more). A commit without a row id makes a line only
   for feat, fix, perf and security. Every other commit (docs, test,
   chore, ops, release, plain merges, untyped history, a row with only
   such commits) is counted in one closing line, `Also: N internal
   changes.`. Security never keys on an id prefix: `DEP-` ids are
   deployment rows (0058 R9's prefix rule is not taken).
5. Per-version files: `docs/releases/<version>.md`, ASCII and LF:
   `## [<version>] - <date>`, the lead paragraph between the markers
   `<!-- lead: hand-written, kept when the notes are regenerated -->` and
   `<!-- /lead -->`, the non-empty groups, the Also line, then the
   not-affiliated sentence as the last line. `notes X.Y.Z` prints the
   draft; `notes X.Y.Z --write` writes the file (keeping an existing
   lead) and regenerates CHANGELOG.md. A file without a lead (the `bump`
   stub) gets a lead that carries the STUB mark, so `publish` refuses the
   version until a lead is written. The date defaults to the committer
   date of the ref, so two runs over one range give the same bytes.
6. CHANGELOG.md is a fixed head plus every docs/releases file, newest
   first (SemVer order, a pre-release below its release), one blank line
   between them. `notes --changelog` regenerates it; `notes --changelog
   --check` writes nothing and exits 1 when it differs.
   tests/test_release_notes.py holds the rules.
7. docs/releases/0.1.0.md is the draft of the whole history to this
   package's base with a hand-written lead. The REL-PREP lane regenerates
   it with `--write` before the 0.1.0 tag (the lead stays).

No network, no tag, no commit: the tool only writes the two files.

## Alternatives

- Hand-written notes only. Rejected: the operator asked for an
  auto-written changelog and done rows are pruned from ROADMAP.md, so
  nobody would remember them at release time.
- GitHub's generated release notes. Rejected: empty here, this repository
  merges locally and opens no pull requests.
- Grouping Security by the `DEP-` id prefix (0058 R9). Rejected: plan
  05's `DEP-` packages are deployment work, mostly features.
- Reading commit bodies for detail. Rejected: bodies may hold trailers;
  subjects are typed and checked by the hook.
- Counting git's legacy `Merge <ROW-ID> (worktree ...)` subjects as rows.
  Not taken: plan 05 names exactly two subject shapes; the early history
  is summed up by the 0.1.0 lead and counted in its Also line.

## Why

Subjects are already typed by the hook and rows already carry player
words, so a draft costs nothing and needs only a lead and a light edit.
Per-version files keep each release's curated text stable while the
changelog is always their exact concatenation, checked by a test.

## Reverses if

The drafts need a rewrite every release.
