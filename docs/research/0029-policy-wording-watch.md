# 0029 - Policy wording watch (overlay / macro rules)

ROADMAP row POLICY-WORDING-WATCH. Not legal advice. This file is the
standing log for one recurring check: after GGG's 1.0 notes (2026-12-11)
and after each new entry in the developer-docs changelog, re-read the
Policy section of the developer docs (overlay rules, macro rules, app
classes) and diff it against the verified quotes in research 0001. Each
re-read adds one log line and, when the wording moved, a `### Diff <date>`
section. `tests/test_policy_wording_watch.py` checks the shape of this
record and that the baseline below still carries every 0001 verified quote.

Floor rule: any change to the CLAUDE.md "Game ToS floor" that a re-read
suggests is written here as a proposal and sent to MAIN as a note; the
floor is never self-edited by a lane or session of this tree.

## How to run a re-read

1. Fetch https://www.pathofexile.com/developer/docs/changelog anonymously
   (truthful AshLight User-Agent). Note the newest entry's date (DD/MM/YYYY
   on the page) and version label.
2. If that entry is newer than the last UNCHANGED / CHANGED log line below,
   or the trigger is the 1.0 notes, fetch
   https://www.pathofexile.com/developer/docs and compare every baseline
   quote below word for word.
3. Append one log line. Verdict UNCHANGED if every baseline quote is still
   on the page verbatim and no new Policy sentence touches screen,
   clipboard, log, overlay, macro, input or automation; else CHANGED, with
   a `### Diff <date>` section listing old text, new text and the effect on
   the floor, plus a floor proposal for MAIN when the floor is affected.

## Baseline (the 0001 verified quotes, carried verbatim)

Source: https://www.pathofexile.com/developer/docs, verified 2026-11-16,
re-read word for word 2026-11-17 (research 0001, section "Re-read
2026-11-17 (ROADMAP RES-POLICY)").

- O1 overlay scope: "Apps that use information sourced from the screen, the clipboard, or the game's logs must follow our overlay rules:"
- O2 awareness: "You may only read this information as long as the user is aware of what you are doing with that data."
- O3 one read per press: "Reading from the screen or clipboard may only be performed once per manual key press."
- M1 manual macros: "Macros must be invoked manually by the user"
- M2 no automated invocation: "such as but not limited to: timers, reacting to file changes, ... or from reading the screen are not allowed." (the full page text reads "timers, reacting to file changes, or from reading the screen", per the 0001 re-read)
- M3 one set function: "Each macro invocation must have one set function (it cannot cycle between actions)."
- M4 one game action: "The resulting function may only perform one action that interacts with the game (sending a single chat message or command counts as one action)."
- A1 standalone apps: "While not encouraged, these are permitted."
- A2 OAuth: "must use a public OAuth client if interacting with our APIs."
- A3 game interaction: "is strictly against our Terms of Use (sections 7b, 7c, 7i)"
- A4 penalty: "Creation or use of these type of applications will result in immediate account termination."
- A5 statement: "This product isn't affiliated with or endorsed by Grinding Gear Games in any way."

What binds AshLight from these lines: O1-O3 (Client.txt tail only with
opt-in and a visible indicator; clipboard / screen once per manual press);
M1-M4 bind input automation only, and AshLight sends no input at all; A1
places AshLight in the permitted standalone class; A5 is shown in the
README, the dashboard footer and the overlay About.

## Watch log

- 2026-11-17 | trigger=baseline, changelog newest entry 3.30.0 (Covens of Umbra) dated 12/11/2026 | verdict=UNCHANGED | source=https://www.pathofexile.com/developer/docs (and /developer/docs/changelog), accessed 2026-11-17
- 2026-12-11 | trigger=1.0 notes (also UTIL-1.0-POST step 1) | verdict=PENDING | source=https://www.pathofexile.com/developer/docs/changelog

Notes on the 2026-11-17 line: the page reads behind it are the two
same-day anonymous re-reads already on file, research 0001 (RES-POLICY
section) and research 0024, both accessed 2026-11-17. Both found every
baseline quote above on the page word for word. The newest changelog
entry, 3.30.0 dated 12/11/2026 (12 November 2026), is the one that
"Clarified Policy wording on macros and overlays"; it predates the
2026-11-16 verification, so the baseline already reflects it. No
changelog entry is newer. The lane that wrote this file had no web access
in its run (fetch tool not granted), so it did not fetch the pages a third
time on 2026-11-17; the next log line must come from a fresh fetch.

Known downstream effect of the 3.30.0 wording (research 0026): another
community tool disabled its screen-read automation after it. AshLight is
not affected: it has no screen watcher and reads the screen or clipboard
only once per manual hotkey press (decision 0003).

## Floor proposals for MAIN

None from this watch. The three wording proposals from the 2026-11-17
RES-POLICY re-read (research 0001: commercial revenue, presentation as
GGG-authorised, trade2 wording) are already in the CLAUDE.md floor.

## Sources

- https://www.pathofexile.com/developer/docs (accessed 2026-11-17, via research 0001 and 0024)
- https://www.pathofexile.com/developer/docs/changelog (accessed 2026-11-17, via research 0001 and 0024)
