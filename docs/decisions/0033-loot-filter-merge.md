# 0033 - Loot filter merge into the player's own filter (UTIL-FILTER-MERGE)

Date: 2026-11-17. Lane AREA-UTIL batch 7. Row UTIL-FILTER-2 (merge part).
Inputs: CLAUDE.md "Game ToS floor", decision 0003 (per-press reads), 0014
(player-click delivery), 0031 (filter download), 0032 (tiers), research
0022 section 3.

## Adjudicator ruling (2026-11-17)

Within the floor. The player explicitly picks the file in the browser; the
browser reads it and sends the bytes; the core never opens a file or learns
a path, which is no more than the clipboard text it already takes per press
(decision 0003): a user-initiated, one-shot read of the player's own data,
not GGG content. Delivery is a download the player places (0031, 0014). No
game file, process, packet or input is touched. Constraints: no watcher,
polling or auto-reload (one merge per pick); 2 MB cap and UTF-8 / no-NUL
checks, refusals in plain words that never echo the content; token, Host
and Origin checks kept; the body, file name and any path are never logged
or stored (memory only, no cache, no temp file); the output name comes from
the posted name, sanitised, plus `-ashlight.filter`; the player's bytes are
otherwise identical (CRLF kept, BOM kept first) after a marked section.

## Decision

- `lootfilter.merge(data, build, base_names, prices)`: bytes in, bytes out.
  It prepends the same Show blocks as `ashlight.filter` (build bases and
  value tiers, `_body_lines`) between `# ===== AshLight section start =====`
  and `# ===== AshLight section end =====`, with a comment saying nothing is
  hidden and how to undo it. A leading UTF-8 BOM stays first; the section
  uses CRLF when the file has CRLF; everything after the end line is the
  player's bytes unchanged. The only part of the player's file read past
  the text checks: an AshLight section from an earlier merge at the very
  start is replaced, so merging again does not stack sections.
- `check_text` refuses (`MergeRefused`, REFUSED_TEXT): empty, over
  MAX_MERGE_BYTES (2 MiB), a NUL byte (UTF-16 reads as "not UTF-8"),
  invalid UTF-8, C0 controls other than tab / LF / CR, and DEL.
- `POST /api/filter-merge?name=<picked name>` (token header, Host / Origin
  as every API call): raw `application/octet-stream` body, 415 otherwise,
  413 on the length alone; 400 with the plain reason; 200 is the merged
  bytes as an attachment named `lootfilter.out_name(name)` (no folders;
  ASCII letters, digits, space . _ ( ) - only; at most 80 characters). The
  request log drops the query string, so the name is not logged.
- Dashboard: a labelled file input under "Loot filter add-on"; picking a
  file is the only act (the browser refuses over 2 MB before sending);
  web/filtermerge.js posts it and saves the answer as a download. The
  answer text shows next to the input and rides on the focused input's
  name (as for the Download button), no new live region (design-reviewer
  pass; texts reworded per its findings).
- AshLight's blocks come first and carry no `Continue`, so they win for
  the items they match and never hide anything; every other item gets the
  player's own rules.

## Alternatives

- Keep the download-only snippet and the Import line (0031): stays as the
  fallback next to the merge.
- Read or write the filter in the game folder by path, or accept a path
  from the player: rejected, game-file access and a path in the core.
- Parse the player's filter to insert blocks in a "better" place or drop
  conflicting rules: rejected, AshLight never rewrites the player's rules.
- `Continue` on AshLight's blocks: rejected, the player's later block would
  override the highlight (and a later Hide would hide it).

## Why

One pick and one save gives the player a combined filter with no Import
line to edit by hand (ZERO-CLICK as far as the floor allows), while the
core stays read-nothing / write-nothing on disk.

## Reverses if

GGG states in writing that filter tools may not read or rewrite user
filters, or that a merged filter counts as game-file modification; the
operator rules otherwise; the core ever needs a file path or a persisted
copy; the game stops loading UTF-8 filters (then revisit the text checks).
