"""Kindler server text (KINDLER-WEAPON-BASE, decision 0081).

The server-side words of the Kindler build generator: the hot reload
names of the template table and the three sidecar caches that the
template loader (server/al/theorycraft/archetypes.py) and the engine
(server/al/theorycraft/kindler.py) watch, the weapon kinds an attack
template's base may be (the item class names of the repoe-fork base_items
snapshot, word for word, so a base matches its snapshot entry), and the
note resolve() gives for a weapon base the snapshot does not name. The
card and plan words stay in web/kindler.js. Both modules import these
names. Templates: docs/design/copy/kindler.md (Server words);
tests/test_kindler_data.py (test_server_words_are_pinned_exactly) pins
every one. Pure functions and constants; stdlib only.
"""

# Hot reload names (decision 0042): the template loader's; only TABLE_NAME
# is in the core's Checks registry, every other watch is registry=False
TABLE_NAME = "Kindler templates"
TREE_NAME = "Passive tree (Kindler)"
GEMS_NAME = "Gems snapshot"
BASES_NAME = "Weapon bases (Kindler)"
# ... and the engine's own copies (registry=False: never shown to a player)
ENGINE_TABLE_NAME = "Kindler templates (engine)"
ENGINE_TREE_NAME = "Passive tree (Kindler engine)"
ENGINE_GEMS_NAME = "Gems snapshot (Kindler engine)"
ENGINE_BASES_NAME = "Weapon bases (Kindler engine)"

# Weapon kinds for an attack template's base: the base_items item class
# names (melee toggle, then the ranged kinds; the bow toggle takes Bow)
MELEE_CLASSES = ("One Hand Mace", "Two Hand Mace", "One Hand Sword",
                 "Two Hand Sword", "One Hand Axe", "Two Hand Axe", "Dagger",
                 "Claw", "Spear", "Flail", "Warstaff")
RANGED_CLASSES = ("Bow", "Crossbow")
BOW_CLASS = "Bow"


def weapon_unknown(where, name):
    """resolve()'s note for an authored weapon base the base_items
    snapshot does not name as a weapon base; nothing is composed. Author
    and test output only: it never reaches a card, Checks or an API
    answer."""
    return (f"{where}: weapon {name} is not a weapon base in the "
            f"base_items snapshot; not composed")
