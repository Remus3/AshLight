# Copy sheet: mapstats

Templates for the per-map stats family (UTIL-MAP-STATS, research 0064
G5): `server/al/text/mapstats.py` (`head_text`, `row_text`, `here_text`
and the constants beside them), used by server/al/mapstats.py. The rules
that bind every template (one event, one sentence; missing fields read
honestly; line limits; plurals; time words; passive notifications; an
exact-output test per template) stay in design 0001 section 9
([0001-design-system.md](../0001-design-system.md)). This sheet and
server/al/text/mapstats.py are edited in both places together, in one
change: tests/test_map_stats.py pins every sentence below word for word.

## Templates

- Page sentence of the Maps card's "By map" page (Run tab; one line,
  whole text in `title`): `<title>: <n> map(s). Median time counts
  finished runs.` (`head_text`; title is the ladder's own, `This session`
  or `All saved sessions`). Empty page: `No maps yet. Each map shows here
  by itself as you play it.` (EMPTY_TEXT).
- Table row (`row_text`): `<map>: <n> run(s), <n> death(s), median
  <m:ss>`, or `..., no finished run yet` while every run of that map is
  still open. The map name is data from the area id.
- Map context card row (Play tab region C, inside a map that was run
  before, this run counted; at most 52 characters): `<n> runs here,
  median <m:ss>, <n> death(s)` (`here_text`; the median part is left out
  while no run of the map has finished).
- Dashboard string composed in web/runs.js (not in this module): each
  table row ends with `, last run <time>`, the local clock time of the
  map's last opened run, dated (`2026-11-16 14:05`) when it is not today
  (design 0001 rule 8, web/fmt.js clockDated). The foot button reads
  `By map` (aria-label `Maps by name`); the page label is `By map name`.
