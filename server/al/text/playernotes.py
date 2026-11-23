"""Player notes text (PLAY-F-186A, finding F-186, decision 0074).

Moved word for word out of server/al/playernotes.py (wave 32 fix round,
ruling A of wave 31; tests/test_structure.py rule 2): the Save refusals
(PN-2), the reasons a notes file did not load (PN-1), the Checks note name
and the fix tail of a held last good copy. server/al/playernotes.py
re-exports every name, so playernotes.<name> is the same object; the
sentences that quote a bound take it as an argument, so the bounds stay
with the store. Templates: docs/design/copy/playernotes.md. Pure
functions and constants; stdlib only.

PN-5 (PLAY-F-186B): the two route refusals server/al/http.py answered
POST /api/player-note with in its own words (ONE_ZONE, TOO_BIG) live here
too; http.py imports them. PN-6: this module and the copy sheet are edited
in both places together; tests/test_player_notes.py
(test_every_sentence_is_pinned_exactly) pins every sentence exactly.
"""

# The hot reload / Checks note name of the notes file
NAME = "Your notes"


# PN-2: refusals the Save shows, each a sentence with a next step
def text_long(max_note):
    """The Save refusal for a note over max_note characters."""
    return f"Your note is over {max_note} characters. Shorten it and save again."


TEXT_BAD = ("Your note has a character AshLight can't keep. "
            "Use plain letters, digits and punctuation.")
NO_CHARACTER = "AshLight doesn't know your character yet. Enter a zone, then save again."
NO_ZONE = "AshLight doesn't know this zone yet. Enter a zone, then save again."
# PN-5 (PLAY-F-186B): the two route refusals of POST /api/player-note that
# sat in server/al/http.py: a query naming more than one zone (400) and a
# body over the route's byte cap (413)
ONE_ZONE = "Save one zone at a time."
TOO_BIG = "Your note is too long. Shorten it and save again."
# PN5-1 (PLAY-F-186B fix round 1): a body that is not text/plain UTF-8
# (415) and a notes file that could not be written (500), both from
# server/al/http.py, which imports them
BAD_TYPE = "AshLight can't read that note. Try again."
NOTE_SAVE_FAILED = "AshLight couldn't save your note. Try again."

# PN-1: why a notes file did not load (the hot reload note's reason)
FILE_FORMAT = "the file is not in AshLight's notes format"
FILE_ROW = "a note is not in the right form"
FILE_TWO = "two notes share one zone"
FILE_BIG = "the file is too large"


def file_long(max_note):
    return f"a note is over {max_note} characters"


def file_many(max_zones):
    return f"the file holds more than {max_zones} notes"


def file_chars(max_characters):
    return f"the file holds notes of more than {max_characters} characters"


# The tail server/al/hotreload.py ends a held-copy note with (its wording,
# matched, not shown by this module) and the fix appended after it
HELD_TAIL = "The last good copy stays in use."
FIX_TAIL = "Fix the file, or save a note to replace it."
