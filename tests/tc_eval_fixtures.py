"""Synthetic item texts and a build for the TC-EVAL tests.

Hand-written by AshLight from the marker strings in research 0003 (no real
item, no copied parser data). Every name and value is invented. The
em dash of the advanced header is written as an escape (ASCII-only files).
"""

EM = chr(0x2014)

RARE_GLOVES = """Item Class: Gloves
Rarity: Rare
Grim Clutch
Example Gloves
--------
Quality: +12% (augmented)
Armour: 88 (augmented)
--------
Requirements:
Level: 45
Str: 30 (unmet)
--------
Sockets: S S
--------
Item Level: 81
--------
+15% to Fire Resistance (rune)
--------
+70 to maximum Life
+30% to Cold Resistance
-10% to Lightning Resistance
12% reduced Attack Speed
Cannot be Example Frozen
--------
Corrupted
--------
Note: ~price 5 exalted
"""

ADVANCED_RING = ("Item Class: Rings\r\n"
                 "Rarity: Rare\r\n"
                 "Storm Loop\r\n"
                 "Example Ring\r\n"
                 "--------\r\n"
                 "Requires: Level 40, 20 Dex\r\n"
                 "--------\r\n"
                 "Item Level: 77\r\n"
                 "--------\r\n"
                 "{ Implicit Modifier " + EM + " Resistance }\r\n"
                 "+8(6-10)% to Cold Resistance (implicit)\r\n"
                 "--------\r\n"
                 "{ Prefix Modifier \"Hale\" (Tier: 3) " + EM + " Life }\r\n"
                 "+55(50-59) to maximum Life\r\n"
                 "{ Suffix Modifier \"of Sparks\" (Tier: 2) " + EM + " Elemental, Lightning }\r\n"
                 "+31(31-35)% to Lightning Resistance\r\n"
                 "(Reminder text about resistances)\r\n"
                 "{ Prefix Modifier \"Charged\" (Tier: 5) " + EM + " Damage, Lightning }\r\n"
                 "Adds 2(1-3) to 40(35-44) Lightning Damage to Attacks\r\n")

MAGIC_BOOTS = """Item Class: Boots
Rarity: Magic
Swift Example Boots of Warmth
--------
Item Level: 30
--------
25% increased Movement Speed
+20% to Fire Resistance
"""

UNIQUE_STAFF = """Item Class: Quarterstaves
Rarity: Unique
Example Unique
Example Quarterstaff
--------
Physical Damage: 20-40
--------
Item Level: 60
--------
+1 to Level of all Melee Skills (implicit)
--------
80% increased Physical Damage
--------
A quiet line of flavour text.
--------
A second flavour section with no numbers
"""

CURRENCY = """Item Class: Stackable Currency
Rarity: Currency
Orb of Example
--------
Stack Size: 12/20
--------
Right click this item then left click a target to apply it.
"""

JEWEL = """Item Class: Jewels
Rarity: Magic
Example Jewel of Testing
--------
Item Level: 70
--------
+10 to maximum Life
"""

GERMAN = """Gegenstandsklasse: Handschuhe
Seltenheit: Selten
Beispiel
--------
+70 zu maximalem Leben
"""

# A build with gloves, two rings and no boots; PoB item text with the
# `Implicits: N` line and `{tag}` prefixes.
EVAL_BUILD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding2>
\t<Build level="80" className="Ranger" ascendClassName="None"/>
\t<Items activeItemSet="1">
\t\t<Item id="1">
Rarity: RARE
Old Grip
Example Gloves
Item Level: 70
Implicits: 0
+40 to maximum Life
+20% to Cold Resistance
</Item>
\t\t<Item id="2">
Rarity: RARE
Weak Loop
Example Ring
Item Level: 50
LevelReq: 30
Implicits: 1
{tags:resistance}+7% to Cold Resistance
+20 to maximum Life
</Item>
\t\t<Item id="3">
Rarity: RARE
Strong Loop
Example Ring
Item Level: 82
Implicits: 1
+9% to Cold Resistance
{crafted}+80 to maximum Life
+40% to Lightning Resistance
+40% to Fire Resistance
</Item>
\t\t<ItemSet id="1">
\t\t\t<Slot name="Gloves" itemId="1"/>
\t\t\t<Slot name="Ring 1" itemId="2"/>
\t\t\t<Slot name="Ring 2" itemId="3"/>
\t\t</ItemSet>
\t</Items>
</PathOfBuilding2>
"""
