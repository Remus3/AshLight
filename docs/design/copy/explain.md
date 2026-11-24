# Copy sheet: explain

Templates for the five Checks cause rows (RUN-EXPLAIN-ROWS, F-129):
`server/al/text/explain.py`, used by the row logic in
`server/al/plug/explain.py`. The rules that bind every template (one
event, one sentence; missing fields read honestly; plurals; time words;
an exact-output test per template) stay in design 0001 section 9
([0001-design-system.md](../0001-design-system.md)). This sheet holds the
templates only, word for word as the text module holds them; a new or
changed template is edited in both places together.

## Templates

- overlay on screen (`LABEL_OVERLAY` `Overlay on screen`; the four
  `OVERLAY_WORDS` are app/overlay_gate.js HINTS word for word):
  - shown (pass): `The overlay is shown. If you can't see it over the
    game, set the game to Windowed Fullscreen. An exclusive fullscreen
    game covers every other window.`
  - hidden_user (off): `The overlay is hidden because you turned it
    off. The show / hide key or the tray brings it back.`
  - hidden_idle (note): `The overlay is hidden because the game looks
    closed (no new game log line for a while). It comes back on the
    next one.`
  - starting (unknown): `The overlay is starting. This takes a few
    seconds.`
  - stuck start (fail, `STUCK_TEXT`): `The overlay has been starting for
    over 2 minutes.`; fix (`STUCK_FIX`): `Choose Restart overlay in
    AshLight's tray menu. If it stays stuck, quit AshLight from the tray
    and start it again.`
- last item check (`LABEL_PRESS` `Last item check`; detail
  `PRESS_DETAIL` `Pressed <age>. <outcome text>`; age `under 5 min ago`,
  `<n> min ago` in 5 minute steps, `<n> h ago`, `<n> days ago`):
  - item (pass): `The item was checked.`
  - build (pass): `A build was loaded from the copied text.`
  - unscored (note): `AshLight couldn't score what was copied. The item
    card says why.`
  - empty (note): `The clipboard was empty, so nothing was checked. Copy
    the item first, then press the key.`
  - error (fail): `The item check stopped with an error.`; fix
    (`PRESS_FIX`): `Press the key again. If it keeps failing, copy this
    report and send it to the project.`
- calc in use (`LABEL_CALC` `Calc in use`; `FALLBACK` `Item checks use
  your stat weights meanwhile.`):
  - ok (pass): `Working. The last calculation took <sec> s.` (no time
    known: `Working.`)
  - timeout (fail): `The last calculation took too long, so AshLight
    stopped it. <FALLBACK>`; fix (`FIX_CALC_SLOW`): `Nothing to do right
    now: AshLight tries the calc again on the next item check. If it
    keeps happening, close other heavy programs while you play.`
  - crash (fail): `The calc closed twice in a row during a calculation.
    <FALLBACK>`; fix (`FIX_CALC_SETUP`, the same words as diag.FIX_CALC):
    `Press "Set up the calc" under Settings, Checks in the AshLight
    window. It installs the calc and turns it on.` (RUN-NO-DEAD-ENDS: the
    Checks row's button, never a script)
  - unavailable (fail): `The calc could not start. <FALLBACK>`; fix
    `FIX_CALC_SETUP`
  - error (note): `The last calculation returned an error, so that item
    check used your stat weights.`
- log lines understood (`LABEL_LINES` `Log lines understood`):
  - pass (`LINES_PASS`): `Yes. AshLight understands the game log.`
  - fail (`LINES_FAIL`): `AshLight read <n> game log lines in a row and
    understood none of them. Zone, level and death counts stop
    updating.`; fix (`LINES_FIX`): `Set the game's language to English:
    AshLight reads English game text only. If it is already English, a
    game update may have changed the log, and an AshLight update will
    follow.`
- restarts (`LABEL_RESTARTS` `Restarts`; shown only from 3 restarts in
  24 hours):
  - fail (`RESTARTS_TEXT`): `AshLight restarted its core <n> times in
    the last 24 hours, last at <HH:MM> (<reason words>).`; fix
    (`RESTARTS_FIX`): `AshLight keeps running by itself. To help find
    the cause, copy this report and send it to the project.`

- setup card facts line (`SETUP_PROMISE`, web/setupcard.js the same): `Read only. Play in Windowed Fullscreen.` One row, at most 52 characters; it drops with the promise line where the setup budget is tight. Replaces "Read only. AshLight never touches the game."; the no-touch promise lives in the ask line (SETUP_ASK), the README and About.
