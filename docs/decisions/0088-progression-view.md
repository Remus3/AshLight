# 0088 - Progression view: own-drawn passive tree, gems and next-up strip

Status: accepted 2026-11-27 (operator order 2026-11-27, widened the same
day: the whole character progression, not only the passive tree).
Design: [docs/design/tree-view.md](../design/tree-view.md). Copy sheet:
[docs/design/copy/progression.md](../design/copy/progression.md).

## Decision

1. One "Progression" view, built from shared parts, shows the character's
   progression: (a) the passive tree, (b) the ascendancy tree with its
   points, (c) the skill gems with their support links and gem timing,
   (d) Spirit and weapon-set passive points when the PoB build states
   them, (e) the guide's point books, counted, and (f) a next-up strip of
   at most 3 steps due at the current level.
2. Sources, only those already permitted, never a guess: the pasted Path
   of Building build (spec node ids, skill groups, gem levels, PoB's own
   Spirit and SpiritUnreserved stats, WeaponSet node lists), a Kindler
   tab's plan (decision 0081: ordered passives, ascendancy nodes by
   trial, gem steps, KINDLER-SUPPORT-FIT applies flags), the cached GGG
   tree export (decision 0034: ids are the export's skill ids; positions
   x / y, out / in links, kind flags), the cached gems snapshot
   (DATA-GEMS-SNAP: the level a gem can be used at; a gem it does not
   name reads "unchecked"), the zone guide's 'A book of 2 points' entries
   (DATA-GUIDE-FACTS) and the snapshot's published level, area id and
   zone. A support is a gem whose PoB skillId starts with "Support" (PoB's
   own naming), never a name rule.
3. The tree is drawn by AshLight's own SVG renderer
   (web/panels/tree.js) from the export's positions: own shapes (small
   dot, notable dot, keystone diamond, jewel diamond, class and
   ascendancy start ring), straight lines for the export's links, no GGG
   image, sprite or icon. Colours only from the kit tokens, dark and
   light. Node state by shape and line style, colour only reinforcing
   (design 0001 C4): planned by this level filled, due next a dashed
   ring, planned later a thin ring, not in the plan a dim dot, due since
   the last change a steady outer ring.
4. States. Kindler: the first point_budget(level) planned passives are
   "planned by this level", the next 3 "take next", the rest "later";
   ascendancy nodes of stages before the followed stage are planned, of
   the followed stage due ("after trial N"), later ones later. PoB: the
   shown spec's nodes are planned; the next spec's new nodes are due.
   Nothing ever says a passive was taken, a gem slotted, a trial done or
   a book picked up.
5. TC-SPEC-FOLLOW: progression.pick_specs(build, level, picker) reads the
   chosen spec through one picker(build, level) -> spec index or None,
   falling back to the active spec; the next spec is the picker's first
   other answer within 25 levels. server/al/plug/progression.py
   spec_picker(core) is the one integration point (None until
   TC-SPEC-FOLLOW wires its chooser there). This package does not touch
   the spec-selection code.
6. Next-up hook: progression.add_next_source(name, fn, order) adds steps
   ({kind, text}, ASCII, at most 120 characters) from a later package
   (TC-UNCUT-GEM, TC-GEM-UNLOCK); built-in kinds use orders 10 to 40,
   hooks default to 100; the strip is cut to 3 steps of at most 60
   characters. A failing source is skipped.
7. Delivery (decision 0056): the plug server/al/plug/progression.py adds
   one core tick that rebuilds the model only when the build object, the
   level, area id or zone changes (checked every pass), or the tree
   export, Kindler tab result, gems snapshot or guide changes (checked at
   most every 2 s), and publishes a small summary as the snapshot's
   "progression" view (key, source line, level, next steps, counts); with
   nothing loaded no key is published. The whole model (at most 700 main
   tree nodes, 1,400 links, 48 ascendancy nodes, 260 named nodes, 160 KB)
   comes from the token-gated GET /api/progression, which the page reads
   only when the published key changes. The Kindler planner is read with
   busy=True, so a read never starts a PoB run (decision 0081 point 4).
8. Placement. Play: region I (the item check region) shows a compact
   "Next up" view (the strip over a mini-tree framed on the due nodes)
   by itself when the progression moves on (a level, build, tree or plan
   change) and no newer item check came in; a new item check gives the
   region back to the item card, and while the view shows with an item
   check present one "Item check" button does the same. The view sits
   inside region I's fixed track (absolute in the cockpit classes, 1.25rem
   foot slack), so the 7 regions, their tracks and the no-scroll rule
   are unchanged. Build and items: a "Progression" button at the end of
   the Builds row opens the full card, which spans the card grid as the
   Kindler card does; "Back to build" or a build sub-tab closes it. Gem
   names open the shared item info popover; a tree node is read on one
   hover line under the tree. The overlay is not changed (2 HUD lines
   plus one card).
9. No motion. The brief asked for newly due nodes to animate and for a
   smooth fit to bounds; design 0001 principle 3 and audit item N7 rule
   out motion on the dashboard, so a newly due node gets a steady outer
   ring and the fit is immediate. Each svg is redrawn at its new size by
   one ResizeObserver (event-driven, no timer); a hidden page paints
   nothing (RUN-FEED-TRUTH).
10. Budget (decision 0002): a whole tree is one svg of 10 paths (4 link
   states, 1 ring, 4 node states, 1 new) whatever its size, so the page
   stays under the 1,500 element cap; the model is built in a few ms and
   only on a change.

## Alternatives

- A seventh Play region or a wider region B: rejected, it breaks the
  fixed 7-region tracks (decision 0075) and every fit figure.
- A toggle button in region I while the item card shows: rejected, the
  item card already holds the G6 maximum of 4 controls; the swap follows
  the feed instead (zero clicks).
- One SVG element per node with a title: rejected, a 700-node tree is
  1,400+ elements, near the whole dashboard budget.
- GGG's tree art (frames, orbits, icons): rejected, the ToS floor bars
  GGG art in the app.
- Publishing the whole model in the snapshot: rejected, it would ride
  every state push (about 35 KB); the key-then-read keeps pushes small.
- Animated transitions: rejected (design 0001 principle 3).

## Why

The player sees what to take, slot and do next at a glance, moving on by
itself as they level, without a second tool and without a guess: every
fact comes from the build, the plan, the tree export, the gems snapshot
or the guide, and the view never claims progress it cannot see.

## Reverses if

The tree export drops x / y or the out / in links (then no tree, the rest
stays); PoB's support skillIds stop starting with "Support"; region I
players miss the item card after a level-up in play, or the swap
misfires; the element or push budgets of decision 0002 are breached;
TC-SPEC-FOLLOW needs a different adapter shape; design 0001 allows
motion; or the operator rules the view unwanted.
