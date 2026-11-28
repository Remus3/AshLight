"""PROGRESSION-VIEW (decision 0092): invented demo data for the
Progression tests, the fit harness and the screenshot.

A helper module, not a test (tests/test_test_layout.py rule 2). Nothing
here comes from GGG, Path of Building or any community source: the tree
is a made-up ring layout in the GGG export's shape (nodes with skill, name,
stats, x / y, out / in, the kind flags, classes with ascendancies), the
names are "Demo ..." words, and the build and plan are invented.
"""

import math

from server.al.theorycraft import model, treedata

CLASSES = ("Warrior", "Ranger", "Witch", "Mercenary", "Monk", "Sorceress")
ASC = "Demo Ascendant"
ASC_ID = "Warrior9"
START_ID = 100
LONG = "Demo notable with a deliberately long passive name for the fit"


def tree_doc(rings=9, long_names=False):
    """A synthetic tree export document: 6 class starts on an inner ring,
    `rings` rings of nodes around them, every node linked to its ring
    neighbours and to the nearest node of the ring inside, plus one small
    ascendancy tree far to the left."""
    nodes = {}
    classes = [{"name": c, "ascendancies": ([{"id": ASC_ID, "name": ASC}] if c == "Warrior"
                                            else [])} for c in CLASSES]
    prev = []
    for i, cls in enumerate(CLASSES):
        a = 2 * math.pi * i / 6
        nid = START_ID + i
        nodes[str(nid)] = {"skill": nid, "id": f"start{i}", "name": cls.upper(),
                           "stats": [], "classStartIndex": [i],
                           "x": round(1300 * math.cos(a), 2), "y": round(1300 * math.sin(a), 2),
                           "out": [], "in": ["root"]}
        prev.append(nid)
    nid = 1000
    for k in range(1, rings + 1):
        count = 12 * k
        radius = 1300 + 650 * k
        ring = []
        for j in range(count):
            a = 2 * math.pi * j / count
            nid += 1
            notable = j % 5 == 2
            keystone = k == rings and j % 9 == 4
            jewel = j % 13 == 7 and not notable
            name = (LONG if long_names and notable else
                    "Demo keystone" if keystone else
                    "Demo notable %d" % nid if notable else "Demo passive")
            nodes[str(nid)] = {
                "skill": nid, "id": f"demo{nid}", "name": name,
                "stats": (["+10% to demo damage", "+5 to demo armour"] if notable or keystone
                          else ["+1 to demo strength"]),
                "isNotable": notable, "isKeystone": keystone, "isJewelSocket": jewel,
                "x": round(radius * math.cos(a), 2), "y": round(radius * math.sin(a), 2),
                "out": [], "in": []}
            ring.append(nid)
        for j, a_id in enumerate(ring):
            b_id = ring[(j + 1) % len(ring)]
            nodes[str(a_id)]["out"].append(str(b_id))
            nodes[str(b_id)]["in"].append(str(a_id))
            near = prev[int(j * len(prev) / len(ring))]
            nodes[str(a_id)]["in"].append(str(near))
            nodes[str(near)]["out"].append(str(a_id))
        prev = ring
    # one mastery node: drawn by nobody
    nodes["9999"] = {"skill": 9999, "name": "Demo mastery", "isMastery": True,
                     "x": 0, "y": 0, "out": [], "in": []}
    # the ascendancy: a start and 11 nodes in a small fan far to the left
    asc_ids = []
    for j in range(12):
        aid = 5000 + j
        asc_ids.append(aid)
        nodes[str(aid)] = {
            "skill": aid, "id": f"asc{j}", "name": "Demo ascendancy start" if j == 0
            else ("Demo ascendancy notable %d" % j if j % 3 == 0 else "Demo ascendancy passive"),
            "stats": [] if j == 0 else ["+1 to demo ascendancy power"],
            "ascendancyId": ASC_ID, "isAscendancyStart": j == 0, "isNotable": bool(j and j % 3 == 0),
            "x": -20000 + (0 if j == 0 else 220 * ((j - 1) % 4 + 1)),
            "y": (0 if j == 0 else 260 * ((j - 1) // 4) - 260),
            "out": [str(5000 + j + 1)] if 0 < j < 11 and j % 4 else [],
            "in": ["5000"] if j in (1, 5, 9) else []}
    for j in (1, 5, 9):
        nodes["5000"]["out"].append(str(5000 + j))
    return {"tree": "Default", "classes": classes, "nodes": nodes}


def tree(rings=9, long_names=False):
    return treedata.parse(tree_doc(rings, long_names))


def path_from_start(t, count, start=START_ID):
    """`count` node ids reached outward from a class start, breadth first
    over the links (the made-up 'planned' order)."""
    order, seen, queue = [], {start}, [start]
    while queue and len(order) < count:
        cur = queue.pop(0)
        for nid in sorted(t.nodes[cur].links):
            n = t.nodes.get(nid)
            if nid in seen or n is None or n.ascendancy or n.class_start or n.mastery:
                continue
            seen.add(nid)
            order.append(nid)
            queue.append(nid)
            if len(order) >= count:
                break
    return order


def plan(t, long_names=False, skills=2, supports=3):
    """An invented Kindler-like plan document (build_plan's shape)."""
    order = path_from_start(t, 60)
    gem = "Demo strike with a long gem name" if long_names else "Demo Strike"
    sup = ["Demo support %d with a long name" % i if long_names else "Demo Support %d" % i
           for i in range(supports)]
    stages = []
    cuts = [(0, 10, 1, None), (10, 30, 12, None), (30, 50, 30, 1), (50, 60, 50, 2)]
    for i, (a, b, lvl, trial) in enumerate(cuts):
        asc = None
        if trial:
            asc = {"trial": trial, "nodes": [{"id": 5000 + n, "name": None}
                                             for n in ((1, 2) if trial == 1 else (3, 4))]}
        stages.append({
            "id": f"s{i}", "label": f"Stage {i}", "trigger": {"kind": "level", "min": lvl,
                                                              "max": lvl + 15},
            "level": lvl,
            "skills": [{"name": gem if k == 0 else f"Demo Skill {k}", "level": lvl,
                        "checked": k % 2 == 0, "sockets": supports,
                        "supports": [{"name": s, "level": lvl + 2 * j, "checked": j != 1,
                                      "applies": [True, False, None][j % 3]}
                                     for j, s in enumerate(sup)]}
                       for k in range(skills)],
            "gems": [{"name": sup[0], "action": "pick", "for": None, "level": lvl + 1,
                      "checked": True, "trigger": {}},
                     {"name": "Demo Skill 9", "action": "pick", "for": None, "level": lvl + 9,
                      "checked": False, "trigger": {}}],
            "passives": [{"id": n, "name": None} for n in order[a:b]],
            "points": b, "budget": max(0, lvl - 1), "ascendancy": asc, "focus": {}})
    return {"template": "demo", "label": "Demo template", "class": "Warrior",
            "ascendancy": ASC, "focus": "authored", "focus_note": "", "stages": stages}


GUIDE = {"version": 1, "acts": {"G1": {"zones": {
    "Demo Woods": {"objective": "Demo goal.", "optional": [
        {"kind": "other", "text": "A book of 2 points - beat the demo boss in the woods."}]},
    "Demo Farm": {"objective": "Demo goal.", "optional": [
        {"kind": "other", "text": "A book of 2 points - bring the demo lute back."},
        {"kind": "gem", "text": "Uncut skill gem - in a demo chest."}]},
    "Demo Town": {"objective": "Town."}}}}}


def build_xml(t, nodes, specs=None, skills=None, stats=None, weapon_sets=None):
    """A PoB-style build XML with the given spec node lists."""
    specs = specs or [("Demo tree", nodes)]
    spec_xml = ""
    for title, ids in specs:
        ws = ""
        if weapon_sets:
            ws = "".join(f'<WeaponSet{k} nodes="{",".join(map(str, v))}"/>'
                         for k, v in weapon_sets.items())
        spec_xml += (f'<Spec title="{title}" treeVersion="0_4" '
                     f'nodes="{",".join(str(n) for n in ids)}">{ws}</Spec>')
    stats_xml = "".join(f'<PlayerStat stat="{k}" value="{v}"/>' for k, v in (stats or {}).items())
    groups = skills or [[("Demo Strike", "DemoStrikePlayer", 20),
                         ("Demo Support 0", "SupportDemoZeroPlayer", 18),
                         ("Demo Support 1", "SupportDemoOnePlayer", 15)]]
    skills_xml = ""
    for g in groups:
        gems = "".join(f'<Gem nameSpec="{n}" skillId="{sid}" level="{lv}" enabled="true"/>'
                       for n, sid, lv in g)
        skills_xml += f'<Skill enabled="true">{gems}</Skill>'
    return ('<PathOfBuilding2><Build level="30" className="Warrior" '
            f'ascendClassName="{ASC}" mainSocketGroup="1">{stats_xml}</Build>'
            f'<Tree activeSpec="1">{spec_xml}</Tree>'
            f'<Skills>{skills_xml}</Skills><Items/></PathOfBuilding2>')


def build(t, count=30, **kw):
    nodes = path_from_start(t, count) + [5000, 5001]
    return model.parse(build_xml(t, nodes, **kw))
