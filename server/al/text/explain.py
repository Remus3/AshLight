"""Checks cause row text (RUN-EXPLAIN-ROWS, finding F-129; design 0001
section 9, copy sheet docs/design/copy/explain.md).

Every player sentence of the five cause rows of server/al/plug/explain.py
lives here: row labels, details and fixes. The plug module keeps the row
logic and imports these names (plug/explain.<name> is the same object).
Pure constants and one pure helper; stdlib only; imports nothing.
"""

DAY_S = 86400.0

# -- overlay on screen
LABEL_OVERLAY = "Overlay on screen"
# app/overlay_gate.js HINTS, word for word (tests/test_diag_explain.py)
OVERLAY_WORDS = {
    "shown": ("pass", "The overlay is shown. If you can't see it over the game, "
              "set the game to Windowed Fullscreen. An exclusive fullscreen "
              "game covers every other window."),
    "hidden_user": ("off", "The overlay is hidden because you turned it off. "
                    "The show / hide key or the tray brings it back."),
    "hidden_idle": ("note", "The overlay is hidden because the game looks closed "
                    "(no new game log line for a while). It comes back on the "
                    "next one."),
    "starting": ("unknown", "The overlay is starting. This takes a few seconds."),
}
STUCK_TEXT = "The overlay has been starting for over 2 minutes."
STUCK_FIX = ("Choose Restart overlay in AshLight's tray menu. If it stays stuck, "
             "quit AshLight from the tray and start it again.")

# -- last item check
LABEL_PRESS = "Last item check"
PRESS_DETAIL = "Pressed {age}. {text}"
PRESS_WORDS = {
    "item": ("pass", "The item was checked."),
    "build": ("pass", "A build was loaded from the copied text."),
    "unscored": ("note", "AshLight couldn't score what was copied. The item "
                 "card says why."),
    "empty": ("note", "The clipboard was empty, so nothing was checked. Copy "
              "the item first, then press the key."),
    "error": ("fail", "The item check stopped with an error."),
}
PRESS_FIX = ("Press the key again. If it keeps failing, copy this report and "
             "add it to a new issue on the AshLight issues page.")
AGE_UNDER_5 = "under 5 min ago"
AGE_MIN = "{n} min ago"
AGE_HOURS = "{n} h ago"
AGE_DAYS = "{n} days ago"


def age_words(seconds):
    """A press age in steps (under 5 min, then 5 minute steps under an
    hour, then hours, then days), so the row changes rarely."""
    s = max(0.0, float(seconds))
    if s < 300:
        return AGE_UNDER_5
    if s < 3600:
        return AGE_MIN.format(n=int(s // 300) * 5)
    if s < 2 * DAY_S:
        return AGE_HOURS.format(n=int(s // 3600))
    return AGE_DAYS.format(n=int(s // DAY_S))


# -- calc in use
LABEL_CALC = "Calc in use"
FALLBACK = "Item checks use your stat weights meanwhile."
CALC_WORKING = "Working."
CALC_WORDS = {
    "ok": ("pass", "Working. The last calculation took {sec} s."),
    "timeout": ("fail", "The last calculation took too long, so AshLight "
                "stopped it. " + FALLBACK),
    "crash": ("fail", "The calc closed twice in a row during a calculation. "
              + FALLBACK),
    "unavailable": ("fail", "The calc could not start. " + FALLBACK),
    "error": ("note", "The last calculation returned an error, so that item "
              "check used your stat weights."),
}
FIX_CALC_SLOW = ("Nothing to do right now: AshLight tries the calc again on the "
                 "next item check. If it keeps happening, close other heavy "
                 "programs while you play.")
# RUN-NO-DEAD-ENDS (research 0042 R4, F20 c): the Checks row's button, never
# a script, and no "again" for a part that was never installed
FIX_CALC_SETUP = ('Press "Set up the calc" under Settings, Checks in the AshLight '
                  "window. It installs the calc and turns it on.")  # diag.FIX_CALC
CALC_FIX = {"timeout": FIX_CALC_SLOW, "crash": FIX_CALC_SETUP,
            "unavailable": FIX_CALC_SETUP}

# -- log lines understood
LABEL_LINES = "Log lines understood"
LINES_PASS = "Yes. AshLight understands the game log."
LINES_FAIL = ("AshLight read {n} game log lines in a row and understood none "
              "of them. Zone, level and death counts stop updating.")
LINES_FIX = ("Set the game's language to English: AshLight reads English game "
             "text only. If it is already English, a game update may have "
             "changed the log, and an AshLight update will follow.")

# -- restarts
LABEL_RESTARTS = "Restarts"
RESTARTS_TEXT = ("AshLight restarted itself {n} times in the last 24 hours, "
                 "last at {clock} ({why}).")
RESTARTS_FIX = ("AshLight keeps running by itself. To help find the cause, copy "
                "this report and add it to a new issue on the AshLight issues "
                "page.")
