"""Player notes text (PLAY-F-186A, finding F-186, decision 0074).

Moved word for word out of server/al/playernotes.py (wave 32 fix round,
ruling A of wave 31; tests/test_structure.py rule 2): the Save refusals
(PN-2), the reasons a notes file did not load (PN-1), the Checks note name
and the fix tail of a held last good copy. server/al/playernotes.py
re-exports every name, so playernotes.<name> is the same object; the
sentences that quote a bound take it as an argument, so the bounds stay
with the store. Templates: docs/design/copy/playernotes.md. Pure
functions and constants; stdlib only.
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
