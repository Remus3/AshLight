# 0082 - UI: item info popover, header and version, collapsible cards

Date: 2026-11-19. Status: ruled by an adjudicator agent the same day
(operator requests 2026-11-19, items 1 (UI part), 3 and 4). Input:
research 0060. Checked against docs/design/0001-design-system.md and the
ruled target design A (docs/plan/03-target-design.md section 4). Data
side of the popover: decision 0083. Plan:
docs/plan/10-operator-requests-2026-11-19.md.

## Decision, part 1: item info popover

- Item names in price rows, movers, price watch, the item card and the
  Kindler tab (decision 0081) are link-like buttons (button
  type=button, aria-expanded, aria-controls), body size 14 px or more,
  visible focus ring.
- One shared web/iteminfo.js and one element
  `<div id="iteminfo-pop" popover="manual" role="dialog" aria-label="Item info">`,
  position fixed, width at most min(22rem, 90vw), height at most 60vh,
  scrolling inside; placed beside its button, flipped above when there
  is no room below. It overlays and never changes a card's size.
- Enter or Space opens and moves focus to its heading (tabindex -1);
  Escape closes and returns focus to the button; Tab out closes (no
  focus trap); a click anywhere outside, a tab change, a list re-render
  or a page flip closes it; one open at a time. ItemInfo.attach(root)
  uses event delegation.
- Data: token-gated GET /api/iteminfo?name=... as a plug route (decision
  0056), local caches only, no network call on open, works with web_data
  off, exact name match against cache keys, length cap, 200 with an
  empty fields object when nothing is known (the popover then shows the
  name and "No saved info for this item yet").
- Unknown fields are left out, never guessed; no "unknown" placeholders.
  The credit line names only the sources that supplied a shown field,
  with their snapshot date.
- The overlay shows plain names only (it is click-through).

## Decision, part 2: header and version

- The visible "AshLight" text left of the tabs goes. The mark img stays,
  decorative (alt="", aria-hidden). The h1 stays as a visually hidden
  "AshLight" (.sr-only), so the page keeps its heading and landmark
  order; document.title stays "AshLight" for a plain browser tab.
- The version and build show as "Version 0.1.0, build 0123456789ab"
  (buildinfo.build_id split at "+"; a ".dev" suffix reads ", dev") in the
  footer (13 px, footer sentences only) and in Settings > About and data
  (design A section 4). Not in the bar.
- This widens package RUN-BUILD-STAMP-UI (wave 13) instead of adding a
  package; its integrator records the amendment. The header change is
  its own small package (UI-HEADER-TEXT) because it touches the bar
  tests of PLAY-TD-09C-BAR.

## Decision, part 3: collapsible cards

- Cards on Build and items and on Run get a collapse button in the card
  title (aria-expanded, aria-controls, a chevron plus a visually hidden
  "Collapse" / "Expand", hit area 24 px or more). Play's fixed regions
  and Settings do not collapse.
- A collapsed card shrinks to its title row. In design A's fixed grid
  the open cards of the same column share the freed height through grid
  tracks (minmax(0, 1fr) for open, auto for collapsed) and the existing
  pager recomputes the rows that fit; no card grows past its cell and no
  tab scrolls. In today's layout (5 tabs, scrolling .col columns) the
  column simply gains the room.
- State per viewer in localStorage keyed by card id (try/catch; no
  storage means all open); default all open; not a runtime file, not in
  settings export, untouched by Clear run history.
- A card that receives an alert (trade, death, build alert) is expanded
  for that alert; nothing auto-collapses.

## Alternatives

Native popover=auto (unpredictable focus, no one-open rule); a hover
tooltip (fails keyboard and touch); a network lookup on open (breaks
0013); a client-side cache parse (duplicates the core); the version in
the bar (bar height) or as a mark tooltip (hover only); removing the h1
(breaks heading navigation); collapse on Play (fixed regions); free
drag-to-resize (against the fixed grid); a runtime file for collapse
state (a view preference, not player data).

## Why

A fixed-position popover is the only element that cannot grow a card.
One component and one cache-only route keep every surface in step and
the web-data opt-in intact. The window title and document.title already
name the app. Grid fr tracks share freed height without breaking design
A's grid, and the pager already adapts to the rows that fit.

## Reverses if

The popover covers Play regions in play or native popover misbehaves in
Electron; item names stop being unique cache keys; plain-browser users
miss a visible name or a screen-reader check fails the heading order;
the build format stops splitting at "+"; a collapsed card hides an alert
the player needs or the fr sharing makes the pager flicker; the
collapse state must follow the player across machines; decision 0075
rules otherwise for Build and items or Run; or the operator rules the
title text should stay.

## Amendment 2026-11-19 (operator follow-up: collapse, "app not browser, app only")

Ruled by an adjudicator agent the same day. Replaces the state lines of
part 3; the layout lines (title button, fr tracks, pager, alerts expand,
Play and Settings never collapse) stand.

- Reading: the state belongs to the app, and the collapse feature is an
  app feature. The collapse buttons render only inside the desktop
  client's companion window (window.alClient present, decision 0041); a
  plain browser shows every card open, with no button and no state.
- State lives in the core: ops/runtime/ui_layout.json, schema 1, a
  card-id allow-list mapped to a collapsed boolean (0036-style bounds:
  unknown ids dropped), one .bak, a jsonfile Saver retry like the other
  stores; served by a token-gated plug route GET / PUT /api/ui/layout
  (decision 0056). Every AshLight window reads the same state. No
  localStorage for this.
- Not in the settings export in slice 1; not emptied by Clear run
  history (a view preference, not run data). A missing or unreadable
  file means all open.

Alternatives: per-viewer localStorage (the browser storage the operator
rejected); buttons in every window with shared state (contradicts "app
only"); include the file in the export (deferred, cheap to add later).

Reverses if: the operator wants the browser to collapse cards or the
layout exported; or players ask for the layout to be cleared with run
history.

## Amendment 2026-11-23 (UI-CARD-COLLAPSE build: PUT plug routes, pager fit)

Ruled by an adjudicator agent the same day, while UI-CARD-COLLAPSE was
built. The state lines and layout lines above stand.

- The plug seam accepts PUT (server/al/plug ROUTE_VERBS gains "PUT").
  Handler.do_PUT falls through to the plug when PUT_ROUTES has no entry;
  the guard runs before the plug call, and a PUT path neither holds stays
  405 before the token check. GET and PUT /api/ui/layout are token-gated
  plug routes in server/al/plug/uilayout.py; the PUT body is a partial
  {"collapsed": {"<card id>": bool}} map capped at MAX_BODY (4096).
  Alternatives: POST (a wording change to this decision); a built-in
  PUT_ROUTES entry delegating to the plug (a fixed table depending on an
  optional module, against decision 0056). Why: the record and the code
  match with a minimal, tested seam change. Reverses if: a plug PUT route
  is found to bypass the handler guard, token, Host / Origin or CSP
  checks, or the operator rules PUT must stay built-in only.
- The rows that fit: web/pager.js fitRows(node, sizeClass, base, rowPx)
  gives a card marked data-fit="tall" (an open card whose column-mate is
  collapsed in the cockpit grid, set by web/collapse.js) a fixed extra
  number of rows per size class (264 px full, 236 px compact at s = 1, at
  the row height), never a measurement; refit() re-renders the pagers
  build() made, and web/search.js rowPager sizes through fitRows and
  relayout() re-renders on a fit change. Alternative: only build()
  pagers grow, rowPager deferred to a later row. Why: most cards page
  through rowPager; the figure is deterministic, so no flicker. Reverses
  if: the fixed extra shows visible slack or overflow at scale 1 with
  real strings, a re-render flickers a pager in play, or a later package
  takes web/search.js with a conflicting change.
- Cards are keyed by their section id; the Recent card on Run has none
  and is keyed eventsbox, found by its class (web/collapse.js BY_CLASS),
  so the page markup and the card-order test stay as they are. An alert
  opens its card for that alert without changing the saved state: a new
  build alert opens Build, a new death opens Deaths, a new trade request
  opens Recent. It stays open until the player's click (nothing collapses
  by itself); a reconnect does not reopen a Build card the player
  collapsed while the same alert showed.
