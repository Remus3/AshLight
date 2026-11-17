"""MATH-E2E-LIVE: item texts in the PoE2 in-game copy (clipboard) format,
written by hand for the public reference build (pobb.in Nqt6FK5lIc6F, a
level 90 Gemling Legionnaire bow build; tests/fixtures/tc_bridge/README.md).

Each one is a plausible drop for one of the build's slots, made to land on
a known side of the item check: a clear upgrade, a sidegrade (near copy of
the equipped item) and a clear downgrade. `EXPECT` names the verdict the
item check must give and the sign PoB must give each delta in the best
slot ("+" > 0, "-" < 0, "~" within the sidegrade band, None = any sign).
"""

RING_UPGRADE = """Item Class: Rings
Rarity: Rare
Grim Loop
Prismatic Ring
--------
Requires: Level 60
--------
Item Level: 82
--------
+10% to all Elemental Resistances (implicit)
--------
Adds 20 to 34 Physical Damage to Attacks
+195 to maximum Life
+25 to Intelligence
+42% to Fire Resistance
+27% to Chaos Resistance
+28 to Dexterity
"""

AMULET_SIDEGRADE = """Item Class: Amulets
Rarity: Rare
Storm Locket
Solar Amulet
--------
Requires: Level 30
--------
Item Level: 79
--------
+15 to Spirit (implicit)
--------
31% increased Evasion Rating
+41 to maximum Energy Shield
+64 to maximum Life
27% increased Critical Hit Chance
"""

BOW_DOWNGRADE = """Item Class: Bows
Rarity: Rare
Dread Thread
Obliterator Bow
--------
Requires: Level 78
--------
Item Level: 79
--------
50% reduced Projectile Range (implicit)
--------
62% increased Physical Damage
Adds 4 to 9 Physical Damage
+60 to Accuracy Rating
"""

BODY_UPGRADE = """Item Class: Body Armours
Rarity: Rare
Carrion Shell
Runeforged Lizardscale Coat
--------
Quality: +20% (augmented)
--------
Requires: Level 62
--------
Item Level: 81
--------
+375 to Evasion Rating
165% increased Evasion Rating
+170 to maximum Life
+17 to Dexterity
+20% to Cold Resistance
+18% to Lightning Resistance
+271 to Stun Threshold
"""

ITEMS = {
    "ring_upgrade": RING_UPGRADE,
    "amulet_sidegrade": AMULET_SIDEGRADE,
    "bow_downgrade": BOW_DOWNGRADE,
    "body_upgrade": BODY_UPGRADE,
}

# name -> (verdict, dps sign, ehp sign) in the best (first) compared slot
EXPECT = {
    "ring_upgrade": ("upgrade", "+", "+"),
    "amulet_sidegrade": ("sidegrade", "~", "~"),
    "bow_downgrade": ("downgrade", "-", None),
    "body_upgrade": ("upgrade", None, "+"),
}
