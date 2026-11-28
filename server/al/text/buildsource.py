"""ACTIVE-BUILD-PICK (decision 0096): the words of the build choice, the
pasted build or a Kindler plan for Play, the item check and Progression.

Copy sheet: docs/design/copy/buildsource.md. The route's refusals
(server/al/plug/buildsource.py) and the Play build line's source words and
its one switch (server/al/playview.py build_view, region B). Row 2 of
region B holds at most 36 characters (playview CAP_BUILD_ROW). Constants
only; stdlib only.
"""

# the route (POST /api/build-source): a refusal is a 400 with one of these
SAVE_FAILED = "AshLight couldn't save your build choice."
BAD = "That build choice isn't one AshLight understands."
NO_CHARACTER = "Play a character first, so AshLight knows whose build this is."
NO_RESULT = "Generate this Kindler plan first, then use it for Play."

# the Play build line (region B)
KINDLER_NAME = "Kindler: "  # row 1: "Kindler: <tab label>, level N"
SRC_KINDLER = "Kindler plan (generated)"  # row 2 while a Kindler plan is in use
SRC_PASTED = "Pasted build"  # row 2 while the pasted build is, with a plan to switch to
USE_KINDLER = "Use Kindler plan"  # the switch while the pasted build is in use
USE_PASTED = "Use pasted build"  # the switch while a Kindler plan is in use
# row 2 while no pasted build is loaded and the switch takes the paste
# button's place (design review F4: the paste route stays named)
PASTE_TOO = "Or paste a PoB code on Build."
