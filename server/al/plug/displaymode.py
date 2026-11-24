"""RUN-LEFTOVERS-CORE (finding F-188): the Windowed Fullscreen advice as a
Checks note, through the plug seam (decision 0056).

The overlay is a separate always-on-top window, and it shows over the game
only in Windowed Fullscreen, the one supported display mode (CLAUDE.md,
decision 0002). An exclusive fullscreen game covers every other window.
This row is advice only: it reads no game file and nothing detects the
display mode, so it is the same note on every pass. No request, no
process, nothing sent.
"""

ORDER = 170  # beside explain (160) and its "Overlay on screen" row
ROW_ID = "display_mode"
LABEL = "Display mode"
# the same words as the "Overlay on screen" hint (server/al/text/explain.py)
TEXT = ("Play in Windowed Fullscreen. An exclusive fullscreen game covers "
        "every other window.")


def rows(f, now):
    return {"id": ROW_ID, "label": LABEL, "status": "note", "detail": TEXT}
