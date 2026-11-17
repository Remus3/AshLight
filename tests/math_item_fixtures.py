"""Synthetic item texts across many item classes for MATH-ITEM.

Hand-written by AshLight from the marker strings in research 0003 (no real
item text copied, every name and value invented). They cover the shapes the
parser and the stat-key normaliser must survive: weapons with properties,
flasks, charms, quivers / shields / foci, currency, gems, waystones,
socketables, rare / unique / magic / normal, corrupted, quality, rune
sockets, negative and decimal mods, hybrid lines and signed roll ranges in
the advanced (Ctrl+Alt+C) form. The em dash is an escape (ASCII-only file).
"""

EM = chr(0x2014)

RARE_BOW = """Item Class: Bows
Rarity: Rare
Dusk Song
Example Bow
--------
Quality: +20% (augmented)
Physical Damage: 30-55 (augmented)
Critical Hit Chance: 5.00%
Attacks per Second: 1.10
--------
Requires: Level 33, 62 Dex
--------
Sockets: S S
--------
Item Level: 50
--------
20% increased Physical Damage (rune)
--------
Adds 5 to 9 Physical Damage
+1 to Level of all Projectile Skills
14% increased Attack Speed
0.5% of Physical Attack Damage Leeched as Life
--------
Corrupted
"""

NORMAL_HELMET = """Item Class: Helmets
Rarity: Normal
Example Helm
--------
Evasion Rating: 40
--------
Requires: Level 10
--------
Item Level: 12
"""

MAGIC_RING = """Item Class: Rings
Rarity: Magic
Hale Example Ring of the Test
--------
Item Level: 20
--------
+8% to Cold Resistance (implicit)
--------
+25 to maximum Life
+11% to Lightning Resistance
"""

LIFE_FLASK = """Item Class: Life Flasks
Rarity: Magic
Example Life Flask of Testing
--------
Quality: +10% (augmented)
Recovers 300 Life over 3 Seconds
Consumes 10 of 60 Charges on use
Currently has 60 Charges
--------
Requires: Level 30
--------
Item Level: 33
--------
40% increased Amount Recovered
25% reduced Charges per use
--------
Right click to drink. Can only hold charges while in belt.
"""

CHARM = """Item Class: Charms
Rarity: Magic
Example Charm
--------
Lasts 3 Seconds
Consumes 40 of 80 Charges on use
--------
Item Level: 41
--------
Used when you become Frozen (implicit)
--------
+15 to maximum Life
"""

UNIQUE_SHIELD = """Item Class: Shields
Rarity: Unique
Example Bulwark
Example Tower Shield
--------
Block chance: 26%
Armour: 120
--------
Requires: Level 25, 44 Str
--------
Item Level: 70
--------
+(40-60) to maximum Life
-5% to maximum Block chance
10% reduced Movement Speed
+12% to Fire and Cold Resistances
--------
A flavour line about walls and the year 3 of nothing.
"""

FOCUS = """Item Class: Foci
Rarity: Rare
Mind Thread
Example Focus
--------
Energy Shield: 30
--------
Item Level: 60
--------
+40 to maximum Energy Shield
24% increased Spell Damage
Regenerate 1.5% of maximum Life per second
"""

QUIVER = """Item Class: Quivers
Rarity: Rare
Arrow Nest
Example Quiver
--------
Item Level: 55
--------
Adds 1 to 3 Physical Damage to Attacks (implicit)
--------
Adds 3 to 6 Fire Damage to Attacks
10% reduced Mana Cost of Skills and 5% increased Damage
"""

UNID_AMULET = """Item Class: Amulets
Rarity: Rare
Example Amulet
--------
Item Level: 80
--------
+10 to Strength (implicit)
--------
Unidentified
--------
Corrupted
"""

GEM = """Item Class: Skill Gems
Rarity: Gem
Example Strike
--------
Level: 5
Mana Cost: 12
--------
Requires: Level 15
--------
Strike an enemy for 100% of weapon damage.
"""

WAYSTONE = """Item Class: Waystones
Rarity: Rare
Example Waystone
--------
Waystone Tier: 5
Item Quantity: +20% (augmented)
--------
Item Level: 69
--------
Monsters deal 20% extra Damage as Fire
Area has patches of Burning Ground
"""

SOCKETABLE = """Item Class: Socketable
Rarity: Currency
Example Rune
--------
Stack Size: 1/10
--------
Martial Weapon: 15% increased Physical Damage
Armour: +12% to Fire Resistance
--------
Place into an empty Rune Socket.
"""

ADVANCED_NEGATIVE = ("Item Class: Body Armours\n"
                     "Rarity: Rare\n"
                     "Cold Shell\n"
                     "Example Vest\n"
                     "--------\n"
                     "Item Level: 75\n"
                     "--------\n"
                     "{ Prefix Modifier \"Hale\" (Tier: 2) " + EM + " Life }\n"
                     "+90(80-99) to maximum Life\n"
                     "{ Suffix Modifier \"of Frailty\" (Tier: 1) " + EM + " Resistance }\n"
                     "-15(-20--10)% to Chaos Resistance\n"
                     "{ Suffix Modifier \"of Ease\" (Tier: 4) " + EM + " Attribute }\n"
                     "10(8-12)% reduced Attribute Requirements\n"
                     "{ Prefix Modifier \"Sturdy\" (Tier: 3) " + EM + " Defences }\n"
                     "+1.5(1.2-1.8)% to maximum Life Regeneration\n")

# a Windows clipboard with CRLF, a BOM and trailing blanks
CRLF_BOM_BELT = (chr(0xFEFF) + "Item Class: Belts\r\nRarity: Rare\r\nWaist Knot\r\n"
                 "Example Belt\r\n--------\r\nItem Level: 44\r\n--------\r\n"
                 "+20 to maximum Life   \r\n+15% to Fire Resistance\r\n\r\n\r\n")

ALL = {"RARE_BOW": RARE_BOW, "NORMAL_HELMET": NORMAL_HELMET, "MAGIC_RING": MAGIC_RING,
       "LIFE_FLASK": LIFE_FLASK, "CHARM": CHARM, "UNIQUE_SHIELD": UNIQUE_SHIELD,
       "FOCUS": FOCUS, "QUIVER": QUIVER, "UNID_AMULET": UNID_AMULET, "GEM": GEM,
       "WAYSTONE": WAYSTONE, "SOCKETABLE": SOCKETABLE,
       "ADVANCED_NEGATIVE": ADVANCED_NEGATIVE, "CRLF_BOM_BELT": CRLF_BOM_BELT}
