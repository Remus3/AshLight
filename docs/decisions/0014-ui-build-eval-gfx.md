# 0014 - Build view, item check UI and graphics advisor (TC-VIEW, TC-EVAL-UI, GFX-ADVISOR)

Date: 2026-11-17. Trigger: ROADMAP rows TC-VIEW, TC-EVAL-UI, GFX-ADVISOR.
Forks F1-F4 ruled by an adjudicator agent the same day (headless, operator
away); rulings recorded below.

## Decision

- TC-VIEW: a Build card on the dashboard (`web/tc.js` buildView,
  `web/app.js`): class / ascendancy, planned level next to the live level
  and zone from Client.txt, PoB's saved key stats, gear by slot with the
  item text, skill groups and gems, tree summary with an https-only tree
  link, notes, "Copy code for Path of Building" plus a selectable code box.
  Gems and uniques link out to poe2db and the PoE2 wiki by name (decision
  0009: link-out only, no copied text, no GGG art). A paste box loads a
  code or character JSON on paste (no import button). The state snapshot
  carries `build` {loaded, rev, class, ascendancy, level}; a new rev makes
  the dashboard fetch GET /api/build, so the view follows the core with no
  refresh button.
- TC-EVAL-UI: `server/al/theorycraft/live.py` keeps the last item check,
  publishes a trimmed card in the state snapshot (`eval`, with `at` and
  `expires_at`) and re-scores the last item when the weights (PUT
  /api/weights) or the build change. The words come from one template in
  `server/al/state.py` (`eval_card_text`, `stat_delta_text`, exact-output
  tests in `tests/test_eval_text.py`). Dashboard: an Item check card with
  every compared slot (both rings) and a Stat weights editor that saves on
  change. Overlay: a 3-line card (verdict and score delta, item, top
  counted stat), 20 s (`EVAL_CARD_S`), then gone by itself. POST /api/eval
  now accepts a blank string (an empty clipboard reads "Not an item").
- GFX-ADVISOR: `server/al/gfx.py`, GET /api/gfx (token-gated). One hidden
  `powershell.exe` CIM query (Win32_Processor, Win32_ComputerSystem,
  Win32_VideoController) plus the display-adapter class registry key for
  VRAM; pure `parse` and `recommend` on fixture profiles
  (`tests/test_gfx.py`). Setting names and specs: research 0012. RECOMMEND
  ONLY: the module opens no file at all (a test walks its AST), and the
  panel says to apply the settings in game.

## Rulings

- F1 TC-EVAL-UI has its own hotkey (Alt+Shift+E, config `eval_hotkey`) in
  the Electron main process (`app/eval_hotkey.js`): one
  `clipboard.readText()` per press, posted to /api/eval; no timer, no
  watcher, no input to the game. Alternatives: (b) wait for PRICE-1; (c)
  route through the /api/clipboard-read stub. Why: within the 0003 floor
  (one read per manual press); unblocks the row; PRICE-1 can later share
  the same press. Reverses if: PRICE-1 lands with a different hotkey
  contract, or GGG's overlay rules change.
- F2 The item check card takes the one overlay card slot for 20 s, then
  expires by itself; the trade card returns after it (design 0001 section
  10 amended). Alternatives: (b) stack both cards; (c) dashboard only. Why:
  keeps the 2 lines + one card cap and the fixed window size (FPS / RAM
  budget). Reverses if: section 10 is amended to allow two cards.
- F3 The hardware read runs on the first GET /api/gfx, sent when the
  player opens the collapsed panel (a click on the dashboard, so the game
  is not focused then), cached in memory for the core's life.
  Alternatives: (b) read at core start in a thread; (c) read at start and
  poll for change. Why: OS hardware info only, never the game process or
  files; runs on a dashboard click; no polling. Deviation from the row's
  ZERO-CLICK "read on first start": recorded here. Reverses if: the panel
  must be ready with no click (then (b), skipped while the game is
  focused), or hardware-change detection is required. The registry read
  stays on the display-adapter key only, never a game or Steam path.
- F4 "Copy code for Path of Building" writes the code with
  `navigator.clipboard.writeText` on a dashboard click, with a selectable
  text box shown as well. Alternative: a text box only. Why: the floor
  restricts clipboard reads and input to the game; a write from the
  dashboard on the player's own click does neither. Reverses if: CLAUDE.md
  or decision 0003 is amended to restrict clipboard writes.

## Amendment 2026-11-22 (PLAY-TD-23-RECORDS; plan units TD-17, TD-18, OVL-LINE2-GUIDE; decision 0075)

Ruling F2 is widened, not reversed: the overlay still holds 2 HUD lines
and one card, never two cards, so its own Reverses-if is not met.

- Card slot holders (TD-17, OVL-CARD-SLOT, `server/al/overlayview.py`
  CARD_HOLDERS): the one card slot is held, first match, by the press
  card (item check, price or the merged card of one press; "Copy the
  item first" for an empty clipboard), the Settings sample card (10 s,
  only on its button), the newest open trade card ("+N more" for the
  rest), a zone or act card (12 s, only into a free slot, never queued),
  then the key hint line ("<key>: check an item", until the first press
  or 3 game sessions). When a holder leaves, the next one due shows by
  itself; the trade card coming back after the press card is one case of
  this.
- Card time (TD-18, OVL-TD18-CARD-TIME): the press card shows for 20 s by
  default (`EVAL_CARD_S`); the setting "Keep a card for" picks 20, 60 or
  200 s (layout `card_s`, `server/al/layout.py` CARD_S). The dashboard
  twins (region I on Play, the Item check card on Build and items) stay
  with no timer.
- The guide line on HUD line 2 (OVL-LINE2-GUIDE): an opt-in. The setting
  "Zone guide on the overlay" is On entry (default; the zone card only),
  Always or Never. Only under Always, in a guided campaign zone, the
  guide entry's `short` (at most 34 characters) replaces the level and
  deaths text while no connection, log state, trade count, under-level
  or AFK / DND word is due; a death or a level-up brings them back for
  20 s. It is a line-2 state, not a third line.

Alternatives: (b) a third HUD line for the guide (plan option O-5, not
adopted: 0040-X5 and the placement ruling); (c) a queue of cards (design
C, not adopted: a second card by another name); (d) a fixed 20 s with no
setting (rejected: a slower reader loses the card before reading it,
while the twin stays). Why: every new holder fits the existing 2 lines +
one card cap and the fixed window size, so the decision 0002 budgets are
unchanged. Reverses if: unchanged (section 10 of design 0001 is amended
to allow two cards).
