# 0097 - A pasted build with one tree gets no order by level (PROGRESSION-NEXTUP-ORDER)

Date: 2026-11-28. Row: PROGRESSION-NEXTUP-ORDER. Amends decision 0092
(PROGRESSION-VIEW) point 2 wording only; decision 0089 (TC-SPEC-FOLLOW)
is unchanged. Adjudicator ruling 2026-11-28.

## Decision

1. A pasted Path of Building build with exactly one tree spec holds no
   order by level. AshLight orders nothing: every node of the spec stays
   "planned" (the plan's end state), as before, and no node is marked
   "take next".
2. Next up says so in fixed words instead of "Nothing new is due at this
   level.", which read as "you are done": the model's empty line is
   `Your build has one tree, with no order by level.`
   (`server/al/text/progression.py` ONE_TREE, copy sheet
   `docs/design/copy/progression.md`). The strip gets no passive step;
   gem, book and hook steps show as before.
3. The point lines stay: the passive count of the tree and the point
   budget at the level, not counting books. Point books are not counted
   in the budget (decision 0092: books are counted, never claimed taken;
   the kind of point is unsettled, DATA-GUIDE-FACTS).
4. Where an order is real it is used as before: a build with level-banded
   tree titles follows its bands (decision 0089, "Next tree: N more
   passives"), and a Kindler plan uses its own ordered passives.

## Alternatives

- A. Order the spec's nodes by graph distance (breadth first) from the
  class start over the cached tree export's links, the first
  point_budget(level) planned, the next 3 "take next". Rejected: the
  build holds no order, so which branch comes first is AshLight's guess,
  against decision 0092's "never a guess"; other wording ("Closest
  next") or a hover-only hint does not stop it reading as a plan step.
- B. Spec title bands (decision 0089) only. Already wired for builds with
  several level-titled trees; it cannot order nodes within one tree, and
  leaving "Nothing new is due at this level." misleads.

## Why

The build holds no per-level order and decisions 0092 and 0089 rule out
guessing one. The gap is a wording problem, not a missing feature: one
fixed sentence, one condition, no new data, no new calc, deterministic
and easy to reverse.

## Reverses if

Path of Building exports gain a per-node allocation order, players ask
for a nearest-first hint with distinct wording and it is shown not to
read as a plan, or the operator rules an AshLight-authored order
acceptable.
