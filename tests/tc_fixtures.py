"""Synthetic Path of Building PoE2 build XML for the TC-* tests.

Hand-written by AshLight from the publicly observed element / attribute
names of a PoB2 build export (research 0010 section 1). No PoB2 source code
or real user build is copied; every name and value below is invented.
"""

MINIMAL_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<PathOfBuilding2>\n'
    '\t<Build level="1" className="Warrior" ascendClassName="None"/>\n'
    '</PathOfBuilding2>\n'
)

FULL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding2>
\t<Build level="87" targetVersion="0_3" className="Monk" ascendClassName="Invoker" mainSocketGroup="2" viewMode="ITEMS">
\t\t<PlayerStat stat="Life" value="2410"/>
\t\t<PlayerStat stat="EnergyShield" value="1830.5"/>
\t\t<PlayerStat stat="TotalDPS" value="123456.78"/>
\t\t<PlayerStat stat="FireResist" value="75"/>
\t\t<PlayerStat stat="Spirit" value="not-a-number"/>
\t</Build>
\t<Tree activeSpec="2">
\t\t<Spec title="Leveling" treeVersion="0_3" classId="1" ascendClassId="0" nodes="10,20,30">
\t\t\t<URL>https://example.org/tree/leveling</URL>
\t\t</Spec>
\t\t<Spec title="Endgame" treeVersion="0_3" classId="1" ascendClassId="2" nodes="10,20,30,40,50,60">
\t\t\t<URL>https://example.org/tree/endgame</URL>
\t\t\t<Sockets>
\t\t\t\t<Socket nodeId="40" itemId="3"/>
\t\t\t</Sockets>
\t\t</Spec>
\t</Tree>
\t<Skills activeSkillSet="1">
\t\t<SkillSet id="1">
\t\t\t<Skill enabled="true" slot="Weapon 1" label="Main" mainActiveSkill="1">
\t\t\t\t<Gem nameSpec="Example Strike" skillId="ExampleStrike" level="19" quality="20" enabled="true"/>
\t\t\t\t<Gem nameSpec="Example Support" skillId="SupportExample" level="1" quality="0" enabled="false"/>
\t\t\t</Skill>
\t\t\t<Skill enabled="false" label="Aura">
\t\t\t\t<Gem nameSpec="Example Aura" skillId="ExampleAura" level="15" quality="0" enabled="true"/>
\t\t\t</Skill>
\t\t</SkillSet>
\t</Skills>
\t<Items activeItemSet="1">
\t\t<Item id="1">
Rarity: RARE
Doom Grip
Example Gloves
Item Level: 80
+40 to maximum Life
</Item>
\t\t<Item id="2">
Rarity: UNIQUE
Example Unique
Example Quarterstaff
</Item>
\t\t<Item id="3">
Rarity: MAGIC
Example Jewel of the Test
</Item>
\t\t<ItemSet id="1" title="Default">
\t\t\t<Slot name="Gloves" itemId="1"/>
\t\t\t<Slot name="Weapon 1" itemId="2"/>
\t\t\t<Slot name="Ring 1" itemId="0"/>
\t\t</ItemSet>
\t</Items>
\t<Notes>Synthetic notes &amp; a second line
with an ampersand.</Notes>
\t<Config/>
</PathOfBuilding2>
"""

# Older single-set layout: Skill directly under Skills, Slot under Items.
FLAT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding>
\t<Build level="12" className="Ranger" ascendClassName="None"/>
\t<Tree activeSpec="1">
\t\t<Spec treeVersion="0_1" nodes="5"/>
\t</Tree>
\t<Skills>
\t\t<Skill enabled="true">
\t\t\t<Gem nameSpec="Example Arrow" level="3" quality="0"/>
\t\t</Skill>
\t</Skills>
\t<Items>
\t\t<Item id="7">
Rarity: NORMAL
Example Bow
</Item>
\t\t<Slot name="Weapon 1" itemId="7"/>
\t</Items>
</PathOfBuilding>
"""

# TC-JSON: a synthetic character in the shape of GGG's reference Character /
# Item types (PoE2 fields skills, passives.specialisations, runeMods), plus
# the PoB build XML it must read as (JSON_TWIN_XML). Every value is invented;
# unknown and wrongly typed fields are included on purpose.
CHAR_JSON = {
    "character": {
        "id": "0123abcd",
        "name": "ExampleHero",
        "realm": "poe2",
        "class": "Invoker",
        "league": "Example League",
        "level": 87,
        "experience": 123456789,
        "futureField": {"nested": [1, 2, 3]},
        "passives": {
            "hashes": [10, 20, 30, 40],
            "hashes_ex": [],
            "specialisations": {"set1": [50], "set2": [60, 20], "set3": "bad"},
            "jewel_data": {},
            "quest_stats": ["ignored"],
        },
        "equipment": [
            {"id": "i1", "w": 2, "h": 2, "icon": "https://example.org/i.png",
             "rarity": "Rare", "name": "Doom Grip", "typeLine": "Example Gloves",
             "baseType": "Example Gloves", "ilvl": 80, "identified": True,
             "inventoryId": "Gloves",
             "runeMods": ["+10% to Fire Resistance"],
             "explicitMods": ["+40 to maximum Life"]},
            {"id": "i2", "frameType": 3, "name": "Example Unique",
             "typeLine": "Example Quarterstaff", "inventoryId": "Weapon",
             "gemSockets": ["S"], "desecrated": False},
            {"id": "i3", "frameType": 0, "typeLine": "Example Potion",
             "inventoryId": "MainInventory"},
            "not-an-item",
        ],
        "jewels": [
            {"id": "j1", "rarity": "Magic", "typeLine": "Example Jewel of the Test",
             "x": 0},
        ],
        "skills": [
            {"typeLine": "Example Strike", "support": False,
             "properties": [{"name": "Level", "values": [["19", 0]]},
                            {"name": "Quality", "values": [["+20%", 1]]}],
             "socketedItems": [
                 {"typeLine": "Example Support", "support": True,
                  "properties": [{"name": "Level", "values": [["1", 0]]}]}]},
            {"typeLine": "Example Aura",
             "properties": [{"name": "Level", "values": [["15", 0]]}]},
        ],
        "metadata": {"version": "0.0.0"},
    }
}

JSON_TWIN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding2>
\t<Build level="87" className="Monk" ascendClassName="Invoker"/>
\t<Tree activeSpec="1">
\t\t<Spec title="Imported" nodes="10,20,30,40,50,60">
\t\t\t<WeaponSet1 nodes="50"/>
\t\t\t<WeaponSet2 nodes="60,20"/>
\t\t</Spec>
\t</Tree>
\t<Skills>
\t\t<Skill enabled="true">
\t\t\t<Gem nameSpec="Example Strike" level="19" quality="20" enabled="true"/>
\t\t\t<Gem nameSpec="Example Support" level="1" enabled="true"/>
\t\t</Skill>
\t\t<Skill enabled="true">
\t\t\t<Gem nameSpec="Example Aura" level="15" enabled="true"/>
\t\t</Skill>
\t</Skills>
\t<Items>
\t\t<Item id="1">
Rarity: RARE
Doom Grip
Example Gloves
Item Level: 80
+10% to Fire Resistance
+40 to maximum Life
</Item>
\t\t<Item id="2">
Rarity: UNIQUE
Example Unique
Example Quarterstaff
</Item>
\t\t<Item id="3">
Rarity: NORMAL
Example Potion
</Item>
\t\t<Item id="4">
Rarity: MAGIC
Example Jewel of the Test
</Item>
\t\t<Slot name="Gloves" itemId="1"/>
\t\t<Slot name="Weapon 1" itemId="2"/>
\t</Items>
</PathOfBuilding2>
"""

# TC-CHARJSON-SHAPES (research 0035 F7 / F9): one synthetic character in
# both item shapes. CURRENT_SHAPE_JSON uses the shape of API entry 3.29.0
# (implicitMods / explicitMods as ItemMod objects, fractured and crafted
# mods inside explicitMods, PoE2 bondedMods); OLD_SHAPE_JSON is the same
# character with string mods and the since-removed fracturedMods /
# craftedMods / desecratedMods lists. Both must read as the same build.
# Every value is invented; the ItemMod flag spellings are placeholders
# (the reader needs only `description`).
_SHAPES_COMMON = {
    "id": "0456cdef",
    "name": "ShapeHero",
    "realm": "pc",
    "class": "Acolyte of Chayula",
    "league": "Example League",
    "level": 90,
    "passives": {
        "hashes": [101, 102, 103],
        "specialisations": {"set1": [201, 202], "set2": [301], "set3": []},
        "skill_overrides": {"101": {"name": "ignored"}},
        "quest_stats": ["ignored"],
    },
    "skills": [
        {"typeLine": "Example Palm", "support": False,
         "properties": [{"name": "Level", "values": [["20", 0]]}]},
    ],
}

_FLASKS = [
    {"id": "f0", "rarity": "Magic", "typeLine": "Example Life Flask",
     "inventoryId": "Flask", "x": 0, "y": 0},
    {"id": "f1", "rarity": "Normal", "typeLine": "Example Mana Flask",
     "inventoryId": "Flask", "x": 1, "y": 0},
    {"id": "c1", "rarity": "Magic", "typeLine": "Example Thawing Charm",
     "inventoryId": "Flask", "x": 2, "y": 0},
    {"id": "c2", "rarity": "Normal", "typeLine": "Example Staunching Charm",
     "inventoryId": "Flask", "x": 3, "y": 0},
]

CURRENT_SHAPE_JSON = {"character": dict(_SHAPES_COMMON, equipment=[
    {"id": "w1", "rarity": "Rare", "name": "Storm Branch",
     "typeLine": "Example Quarterstaff", "baseType": "Example Quarterstaff",
     "ilvl": 81, "inventoryId": "Weapon", "x": 0, "y": 0,
     "enchantMods": ["+1 to Level of all Example Skills"],
     "runeMods": ["+8% to Lightning Resistance"],
     "bondedMods": [{"description": "+6 to Dexterity", "flags": {}}],
     "implicitMods": [{"description": "+12% to Critical Hit Chance",
                       "flags": {}}],
     "explicitMods": [
         {"description": "+20 to Strength", "flags": {"fractured": True},
          "fractured": True},
         {"description": "Adds 5 to 10 Physical Damage", "flags": {},
          "rareonly": False},
         {"description": "+30 to maximum Mana\n+5% to Chaos Resistance",
          "flags": {}},
         {"description": "+15% to Cold Resistance", "flags": {"crafted": True},
          "crafted": True},
         {"description": "+9% increased Attack Speed",
          "flags": {"desecrated": True}},
         {"flags": {}}, {"description": 7}, "  ",
     ]},
    {"id": "w2", "rarity": "Magic", "typeLine": "Example Spear of Haste",
     "inventoryId": "Weapon2", "x": 0, "y": 0,
     "explicitMods": [{"description": "10% increased Attack Speed"}]},
] + _FLASKS)}

OLD_SHAPE_JSON = {"character": dict(_SHAPES_COMMON, equipment=[
    {"id": "w1", "rarity": "Rare", "name": "Storm Branch",
     "typeLine": "Example Quarterstaff", "baseType": "Example Quarterstaff",
     "ilvl": 81, "inventoryId": "Weapon", "x": 0, "y": 0,
     "enchantMods": ["+1 to Level of all Example Skills"],
     "runeMods": ["+8% to Lightning Resistance"],
     "bondedMods": ["+6 to Dexterity"],
     "implicitMods": ["+12% to Critical Hit Chance"],
     "fracturedMods": ["+20 to Strength"],
     "explicitMods": ["Adds 5 to 10 Physical Damage",
                      "+30 to maximum Mana\n+5% to Chaos Resistance"],
     "craftedMods": ["+15% to Cold Resistance"],
     "desecratedMods": ["+9% increased Attack Speed"]},
    {"id": "w2", "rarity": "Magic", "typeLine": "Example Spear of Haste",
     "inventoryId": "Weapon2", "x": 0, "y": 0,
     "explicitMods": ["10% increased Attack Speed"]},
] + _FLASKS)}

# The item text both shapes must give for the weapon (MOD_FIELDS order).
SHAPES_WEAPON_TEXT = """Rarity: RARE
Storm Branch
Example Quarterstaff
Item Level: 81
+1 to Level of all Example Skills
+8% to Lightning Resistance
+6 to Dexterity
+12% to Critical Hit Chance
+20 to Strength
Adds 5 to 10 Physical Damage
+30 to maximum Mana
+5% to Chaos Resistance
+15% to Cold Resistance
+9% increased Attack Speed"""
