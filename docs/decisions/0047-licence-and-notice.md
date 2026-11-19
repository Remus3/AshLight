# 0047 - Licence and NOTICE: Apache-2.0, holder The AshLight authors

Date: 2026-11-18. Source: package GP-03 (docs/plan/04-go-public.md,
section "GP-03 NOTICE and the licence record", and its "Decisions to
record" item 2); finding F-009; research 0057 (R5, public files and the
peer comparison); operator item OA-5 (docs/plan/09-operator-acts.md),
default in force.

## Decision

1. AshLight's own code is licensed under Apache-2.0 (the LICENSE file at
   the repository root, unchanged).
2. The NOTICE copyright holder is "The AshLight authors". No person,
   handle or account is named as holder.
3. NOTICE describes ops/fleet_kit/ as a vendored development kit
   (Apache-2.0), unmodified, under its own LICENSE and NOTICE in that
   directory, and ops/loop/slots.py as a shared concurrency helper from
   the same development kit family, Apache-2.0. ops/loop/slots.py itself
   is byte-pinned and is not edited.
4. Nothing third-party is bundled. Game data is used only as attributed
   build-time snapshots in the sidecar cache (decision 0009); the
   optional calc tools are fetched at setup on opt-in and listed in
   THIRD-PARTY.md (decision 0018).
5. The trademark and non-affiliation text of NOTICE stays as it is.

## Alternatives

- A named person or handle as copyright holder. Rejected: it would put a
  personal identifier in a public tracked file (CLAUDE.md, Public-repo
  hygiene) and is not needed for the licence to apply.
- MIT. Rejected: it has no express patent grant; Apache-2.0 keeps one and
  is already the LICENSE at HEAD and the kit's own licence.

## Why

- "The AshLight authors" names no person and passes the leak sweep.
- Apache-2.0 matches 5 of the 7 public peers compared in research 0057
  and keeps the patent grant.
- Describing the kit in public words removes the internal fleet wording
  ("the operator", "MAIN") from a file every visitor reads.

If the code-of-conduct fallback of GP-06 (Contributor Covenant 2.1,
CC BY 4.0) is ever used, its licence check is added to this record.

## Reverses if

The operator wants a named holder (OA-5), or a bundled dependency forces
another licence.
