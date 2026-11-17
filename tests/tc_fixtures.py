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
