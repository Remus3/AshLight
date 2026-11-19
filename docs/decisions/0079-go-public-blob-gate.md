# 0079 - Go-public gate 6: binary blobs 500 KB, text blobs 2 MB

Date: 2026-11-18. Source: adjudicator ruling 2026-11-18 on the red gate 6
of package GP-09 (docs/plan/04-go-public.md, "Before the first push");
decision 0046 (full history is published, no rewrite); research 0057
(the 500 KB figure was a check on binaries: the hero PNGs and the other
tracked images).

## Finding

The GP-09 run of 2026-11-18 stopped at gate 6: the largest blob
reachable from main is 1294166 bytes, docs/plan/packages.json, and every
one of its 9 history versions is over 500 KB. packages.json is text (the
plan of record, decision 0077), not a binary; the 500 KB line was written
to catch an image, archive or build output committed by accident.

## Decision

1. Gate 6 applies the 500 KB limit to binary blobs only. A separate
   ceiling of 2 MB applies to text blobs. Text = valid UTF-8 with no NUL
   byte; every other blob is binary. 1 KB = 1000 bytes.
2. The check is `python tools/blob_gate.py` (stdlib): it walks
   `git rev-list --objects main`, sizes every blob with `git cat-file
   --batch-check`, reads only the blobs over 500 KB with `git cat-file
   --batch` to classify them, and exits 0, or 1 with one line per
   offender (kind, short id, size, limit, path). A git failure exits 1
   (fail closed). tests/test_blob_gate.py proves it on tmp repositories.
3. No history rewrite. History is published as it is (decision 0046).
4. Gate 6 also keeps `python -m pytest -q tests/test_brand_assets.py`
   green. The GP-09 gate list in docs/plan/packages.json calls the
   checker.

## Alternatives

- History rewrite to shrink or drop the packages.json versions. Rejected:
  a rewrite runs only on MAIN's ORDER via fleet_rewrite.py (FLEET item
  17, decision 0046) and none is ordered; it would also change every
  commit id since the plan landed.
- Defer GP-09 until the file shrinks. Rejected: the gate would stay red
  forever, since history is never rewritten; the go-public order would
  stall on a text file that leaks nothing.
- Trim packages.json at HEAD. Rejected: the 9 history versions stay over
  500 KB, so gate 6 as written stays red; it also splits the plan of
  record for no gain.

## Why

The 500 KB limit guards against binaries: images with metadata, archives,
build outputs, which can hide data and bloat every clone. A text file is
reviewed line by line by the leak sweep and the identity scan over all of
history, so its size alone is not a risk. The 2 MB ceiling still stops a
text dump or an export from slipping in.

## Reverses if

A text blob over 2 MB appears (split it), MAIN orders a rewrite (then
restore the uniform 500 KB), or a leak or accident is found hiding in a
text blob under 2 MB.
