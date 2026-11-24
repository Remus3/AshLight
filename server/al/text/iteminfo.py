"""Item info text (ITEM-INFO-CORE, decision 0083, decision 0082 part 1).

The player-facing words of the item info lookup (server/al/iteminfo.py)
and its route GET /api/iteminfo (server/al/plug/iteminfo.py): the name
refusals the route answers with status 400, the poe.ninja credit of the
market block, the one rarity word the lookup gives, and the hot reload
names of its two tables. Both modules import these names; the bounds stay
with the lookup and are passed in. Templates:
docs/design/copy/iteminfo.md; tests/test_iteminfo.py
(test_every_sentence_is_pinned_exactly) pins every sentence. Pure
functions and constants; stdlib only.
"""

# Name refusals (status 400), each with a next step
NO_NAME = "AshLight needs one item name. Open the item again."
MANY_NAMES = "Look up one item at a time."
ONE_LINE = ("An item name is one line of text. "
            "Use the name as the game shows it.")


def name_long(name_max):
    """The refusal for a name over name_max characters."""
    return (f"An item name is at most {name_max} characters. "
            "Use the name as the game shows it.")


# The market block's credit (decision 0083 point 1; = ninja.SHORT_CREDIT)
CREDIT = "Prices: poe.ninja"
# The only rarity the lookup gives (uniques; currency has none)
UNIQUE = "Unique"
# Hot reload names of the two cached tables (decision 0042)
BASES_NAME = "Item base list"
UNIQUES_NAME = "Unique item list"
