# Copy sheet: events

Templates for the event family: `server/al/text/events.py` (`summarize`,
`trade_card_text`) and the dashboard run views built from log events
(Acts, Maps, level pace, Deaths, last session). The rules that bind every
template (one event, one sentence; player text quoted; missing fields read
honestly; overlay register; line limits; plurals; time words; passive
notifications; an exact-output test per template) stay in design 0001
section 9 ([0001-design-system.md](../0001-design-system.md)). This sheet
holds the templates only, moved word for word out of design 0001
(TEST-COPY-SHEETS); a new or changed events template is edited here, not
in design 0001.

## Templates

- level up: `<character> reached level <n>`
- death: `<character> died` (suicide: `<character> died (self-inflicted)`)
- zone: `Entered <zone>` (hideout: `Entered <zone> (hideout)`)
- trade: `<from> wants <item> - <price>` (no price: `- no price set`)
- whisper in / out: `<from>: "<text>"` / `To <to>: "<text>"`
- AFK / DND: `You're AFK` / `You're back`, `Do not disturb on` / `off`
- party: `<character> joined the area` / `<character> left the area`
- log state: `Reading Client.txt`, `Client.txt was reset (<reason>)`;
  the game's server connect line is not listed (it came before every
  zone, UX-COPY); overlay status slot before the opt-in `not reading -
  see dashboard` (UX-FIRSTRUN), opted in `waiting for log` when
  the file is known but quiet (15 characters at most next to the
  numbers), `no Client.txt` when it is not found
  (UX-COPY); dashboard bar while the log is quiet for 20 min `log
  quiet, still reading - game closed or AFK?` (overlay `log quiet`;
  AshLight still reads the file, so the bar says so, FIX-IDLE-WORD);
  dashboard deaths tile before the opt-in `-` over `Counts
  once reading starts` (UX-FIRSTRUN)
- new trade request (UX-REVIEW F6, `web/trades.js`): dashboard polite
  live region `New trade request from <from>.` (no name: `New trade
  request.`; several at once: `<n> new trade requests.`), only when the
  set of open trade ids grows
- Acts card (HUD-ACT, `server/al/acts.py`, `web/acts.js`; titled
  `Acts` since PLAY-TD-20A-RUN-GRID): dashboard only; one line per act,
  key facts first, `<act> (<notes>): <t>, total <t>, best <t>` (act
  `Act <n>` / `Cruel Act <n>` / `Interlude <n>`; time in the act, run
  total and your best, m:ss or h:mm:ss; `best` only when a saved run
  has one); the notes `now`, `partial` in one pair of parentheses,
  joined with ", ", the parentheses left out with no note; for a
  partial row the whole text adds `Partial: counted from the first
  zone AshLight saw.` (UX-NEW-CARDS); zone heading `Zone levels in
  <act>`, zone notes `(you are here)` / `(town)`; empty `No act times yet. They start by
  themselves when you enter a campaign zone.`, `Zone levels show here
  while you are in a campaign act.`, `Zone levels aren't downloaded yet.
  AshLight fetches them by itself while "Use web data" is ticked under
  Settings, Reading and web data.`, and in an act the downloaded table
  lacks (UTIL-1.0-FIXTURES) `Zone levels for <act> aren't downloaded
  yet. They show here once the game data has them. AshLight fetches
  newer game data by itself, at most once a day, while web data is on.`
  (RUN-NO-DEAD-ENDS: never a script); source
  line `Zone levels: RePoE fork export, downloaded when AshLight was
  built. Game data (c) Grinding Gear Games.` (decision 0020)
- Maps card (UTIL-MAPS, `server/al/runs.py`, `web/runs.js`): dashboard
  only; one line per map, `<map> (<note>): level <n>, <t>, <n>
  death(s)` (level missing: `unknown`; time in the map m:ss or
  h:mm:ss; `1 death`, `2 deaths`); the open row's note `now` or
  `paused`, the parentheses left out on a finished map; the By level
  pages (UTIL-MAP-LADDER) one line per map level, `Level <n>: <n>
  maps, <n> deaths, median <t>, <n> level-ups` (each count singular
  at 1); summary `Average map: <m:ss> over <n> finished map(s).`
  then `<n> death(s) in maps.` or `No deaths in maps.`; empty `No maps
  yet. Map times start by themselves when you open a map.`
- level pace (UTIL-PACE, `server/al/pace.py`): dashboard only, one
  line under the Level tile, hidden while empty, key word first:
  `Pace: about <m:ss> a level over the last <n>, <x.x> levels an
  hour.` (one level: `about <m:ss> for the last level`; `1.0 level an
  hour`; the hourly part needs 2+ level-ups seen live and 10 minutes
  since AshLight started; m:ss matches the dashboard timers; shortened
  for 320 px, UX-NEW-CARDS)
- Deaths card (UTIL-DEATHS, same files; titled `Deaths` since
  PLAY-TD-20A-RUN-GRID, the death recap): dashboard only; one line per
  death, newest first, `HH:MM` local time then `Died in <zone> (area
  level <n>) at level <n>, <m:ss> into the zone.` (parts without data
  are left out; no zone: `Died at level <n>.`); `Most deaths: <zone>
  (<n>).` from 2 deaths in one zone; empty `No deaths this session.
  Each one shows here with its zone and level.`; deaths counted
  before AshLight started reading (LIVE-RESUME restores the count,
  not the details): empty `<n> death(s) came before AshLight started
  reading, so their zones aren't known. New deaths show here with
  their zone and level.`, else `<n> death(s) came before AshLight
  started reading.` after the worst-zone line (UX-NEW-CARDS)
- last session (UTIL-SESSION-SUMMARY, `server/al/summary.py`,
  `web/summary.js`): dashboard only, hidden until the first card; lines
  `Played <m:ss|h:mm:ss> and reached level <n>.` (no levels gained: `at
  level <n>`; no level known: `Played <t>.`), `Levels: <a> to <b>, at
  <x.x> an hour.` (pace from 10 minutes of play), `Maps: <n>.`,
  `Deaths: <n>.`, `Price movers: <name> up|down <n>%, ...` (top 3 by
  size); then `Session ended at <HH:MM> after 20 minutes with no game
  activity.` / `... when the game closed.` (date added for an older
  card); not a live region (not urgent, never announced; reachable via
  its labelled `Last session` heading; keeps the 12-region cap)
