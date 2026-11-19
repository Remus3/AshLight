# 0057 - Keep-or-vendor levelling rules: own table, hot reloaded, used only with no build

Date: 2026-11-18. Source: package TC-CAMPAIGN-KEEP (wave 5); finding F-060
(docs/plan/02-findings.md, "CAMPAIGN-KEEP: keep-or-vendor verdict with no
build loaded"); ruling 0056-Q3 (own table first; decision 0078). Inputs:
decisions 0003 (one clipboard read per manual press), 0039 (campaign
hints, boots_speed_level default 16), 0042 (hot reload), 0045 (checked
items), TC-CARD-PARTS (the card part contract). F-097 later adds its
provenance test over the table; F-070 (worn-gear baseline, decision 0052)
replaces it where worn gear is known.

## Decision

1. Table. `server/al/data/level_rules.json` is AshLight's own levelling
   rule: level bands covering levels 1 to 100 with no gap or overlap,
   each with a count-of-N rule (`need`) and checks for life, each
   resistance (fire, cold, lightning, chaos; an "all Elemental" or a
   two-element mod counts for each element it names) and, from level 16,
   boots movement speed. A check is plain JSON data (`stats`: stat keys in
   theorycraft/weights.stat_key form, `min`, optional `slots` and `must`),
   read by `server/al/theorycraft/levelrules.py` and never evaluated as
   code. Every check carries `src` and `checked`. The thresholds are
   AshLight's own levelling judgement; nothing is copied from another
   tool, guide or site.
2. Hot reload. The table is a `hotreload.Watched` in the core registry
   (one stat per core tick). A file that fails the strict check (schema,
   level coverage, a missing src or checked, a non-number min) keeps the
   last good table and shows the Checks note "Levelling rules did not load
   (<reason>). The last good copy stays in use."; a removed file means no
   table and no keep part.
3. When. The card part `server/al/theorycraft/cardparts/keep.py`
   computes only when evaluate() says "no build loaded" (no build, an
   item with a gear slot) and the slot is one the table covers (weapons,
   off-hand, armour, jewellery, belt; not flasks or charms). A loaded
   build keeps the normal comparison and the part adds nothing.
4. Verdict. In the band of the player's level (the opted-in Client.txt
   tail), an item is Keep when it meets at least `need` of the checks
   counted for its slot and misses no `must` check (boots movement speed
   from level 16, the band start equal to campaign.DEFAULT_BOOTS_LEVEL);
   otherwise Vendor. No level read yet, or an unidentified item: no
   verdict, one note naming the missing input.
5. Words (design 0001 section 9, AshLight's own). Word `Keep` with the
   upgrade edge, or `Vendor` with the note edge (never colour alone: the
   word changes with it). Overlay head `<word> - <k> of <n> met at level
   <lv>` (at most 32 characters, rule 6). Dashboard notes `Worth keeping:
   it meets <k> of <n> levelling thresholds for level <lv>.`, `Vendor: it
   meets <k> of <n> levelling thresholds for level <lv>, and <need>
   is|are needed.` or `Vendor: it lacks <label> <min>+, which this
   levelling rule needs at level <lv>.`, then `Thresholds met: <label>
   <min>+, ...` when any is met; `Keep or vendor needs your character
   level from Client.txt.` and `Keep or vendor needs the item identified
   first.` when it cannot answer. The part sets `answers`, so the overlay
   keeps the item card (merged with a same-press price line) instead of
   the price card alone.

## Choices the package text left open (ruled by the builder)

- Line 3 and the dashboard sentence. The package notes say the part sets
  line and sentence, but the card part contract (cardparts WORD_KEYS)
  lets a part change only notes, word, tone, head and answers, and the
  package edits no shared file. Ruled: the head carries the verdict and
  count, the notes carry the sentence and the thresholds met; line 3 stays
  `Paste a build on the dashboard` and the sentence stays the no-build
  next step. Alternatives: edit cardparts/__init__.py to allow line and
  sentence (outside this package's files); stop and wait (the plan says
  decide). Reverses if: a later package widens WORD_KEYS, then line 3 can
  list the thresholds met.
- Edges. Keep takes the upgrade edge, Vendor the note edge (not
  downgrade: nothing was compared). Alternatives: note for both;
  downgrade for Vendor. Reverses if: the design reviewer rules otherwise.
- Boots speed is a `must` check. Alternatives: one count among the rest.
  Why: it matches the campaign hint "Boots: no speed" from level 16, so
  the two never disagree. Reverses if: levelling play shows it too strict.
- Level bands only, no act key. F-060 mentions acts; the package goal
  names level bands only, and the level is the fact the log gives on
  every level-up. Reverses if: bands misfire for players far over or
  under the zone level.

## Alternatives

- Use the default stat weights with no build (score only): no threshold,
  no level, no keep or vendor answer.
- Import a community levelling table: licence and copy risk (0056-Q3
  rules own table first).
- Evaluate expressions in the table: barred (JSON conditions, never run
  as code).

## Why

A levelling player without a PoB build gets a one-press keep or vendor
answer from the item-check key they already use, labelled a levelling
rule and naming the thresholds met, with no new read, no new press and
nothing sent anywhere. The table is tunable live (hot reload) and a bad
edit cannot break the card.

## Reverses if

The thresholds misfire in levelling play, a licence objection to a fact
source appears, or the worn-gear baseline (F-070) makes the table unused.
