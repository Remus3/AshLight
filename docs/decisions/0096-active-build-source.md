# 0096 - Active build source per character (ACTIVE-BUILD-PICK)

Date: 2026-11-28. Operator report: "how do i select the build to be seen
and used during the build from Play tab; it is still on a level 100
pasted build, not the progression one I generated." Adjudicator ruling
2026-11-28. Amends decisions 0045 (BUILD-LIVE), 0081 (KINDLER) and 0092
(PROGRESSION-VIEW).

## Before

Play (region B), the item check, the Build card and the stale-build
check used the character's pasted PoB build only. The Progression view
used a Kindler plan only while no pasted build was loaded, and only a
result still in memory: Kindler results were memory-only, so after a
restart no plan was used until Generate was clicked again. The Kindler
tab's "Follow Play guidance" only picks the stage shown on the plan card.
No control made a Kindler plan the build in use.

## Decision

1. One active build source per character: the pasted PoB build (the
   default) or one Kindler tab's plan. Stored in
   ops/runtime/build/source.json (theorycraft/buildsource.py), schema 1,
   only Kindler choices ({"tab", "at"}), at most 12 characters (decision
   0038's bound, the oldest choice leaves), one .bak, a Saver retry (the
   "build choice" unsaved row), not in the settings export, not cleared
   by Clear run history. A choice whose tab is gone or has no result
   reads as the pasted build and the file is left as it is.
2. Set only by the player's click through the token-gated plug route
   (server/al/plug/buildsource.py): GET /api/build-source, POST
   {"use": "pasted"} or {"use": "kindler", "id": <tab>} for the character
   being played; body capped at 4096; Host / Origin / Sec-Fetch-Site
   guard; a refusal is a 400 with a fixed sentence and no path.
3. While a Kindler plan is in use the plug tick composes the PoB XML of
   the plan's stage (kindler.compose_xml: passives up to the stage, its
   skills, the checked weapon base, no other item; model.parse) and puts
   it in the build store in place of the pasted build
   (BuildStore.use_override, source "kindler"). The stage is the one the
   Play guidance matches while the tab's follow flag is on, else the
   result's best stage; a new stage composes again. The item check (stat
   weights with the calc off, PoB stages with it on; worn gear first,
   decision 0052), the Play build line, the Build card and the stale-build
   check follow through the store's listeners. The Progression view uses
   the chosen tab's Kindler path (stage-aware next-up). The pasted build
   file is never touched; "Use pasted build" reads it again.
4. Restart: the tab's result summary gains optional "stage" and
   "variant" (genstore RESULT_FIELDS); the engine restores the result
   from the summary (kindler.from_summary, Engine.restore) with no calc
   and no Generate, marked "restored"; no score number is shown for it.
   An old summary without the fields restores the last stage, variant 0.
5. A new paste (the paste box, an item-key press holding a code) makes
   the pasted build the one in use again; a pasted file that changes on
   disk does so only when its mtime is newer than the choice's "at".
6. UI: region B row 1 reads "Kindler: <tab label>, level N" while a plan
   is in use; row 2 "Kindler plan (generated)" or "Pasted build" when
   there is a choice, else today's calc words; one button in row 1, "Use
   Kindler plan" or "Use pasted build", hidden when there is nothing to
   switch to (with no pasted build and a Kindler result it takes the
   paste button's place, and row 2 reads "Or paste a PoB code on
   Build."). A "Use this plan for Play" chip (aria-pressed) on each
   Kindler plan card (a second click goes back to the pasted build) and
   a "Use pasted build for Play" chip on the Pasted build's Build card
   (shown only while there is a choice). Design review 2026-11-28: PASS
   with fixes (F1 to F4 applied; F5, the route's refusal words on the
   region B switch, and F6, focus when the switch hides, are left: the
   switch is shown only when the route accepts it). Words in server/al/text/buildsource.py (copy sheet
   docs/design/copy/buildsource.md).

## Alternatives

- Two builds at once (pasted and Kindler side by side): breaks decision
  0045's one build per character and the one active source.
- Store the choice in the pasted build file: touches the pasted file.
- A choice that lasts only while the page is open: lost on restart.

## Why

The player generated a plan and found no way to use it. This keeps one
build per character, leaves the pasted file untouched, and makes the
plan survive a restart without a Generate.

## Reverses if

Players want both builds shown side by side; a composed no-items Kindler
build misleads the item check in play; a restored summary is shown to
differ from a fresh result; the paste-wins rule surprises players; the
12-character bound is outgrown; or the operator rules Kindler plans must
not feed the item check. Removing the override and the file returns every
character to its pasted build.
