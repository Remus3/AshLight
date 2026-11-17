# Client.txt log format and events (PoE2)

Research date: 2026-11-16. Everything here is from public pages; claims that no
source confirmed are marked UNVERIFIED. No code was copied; formats are described
and sample lines are short.

Source keys used below (full URLs in "## Sources"): [EE2-CS], [EE2-REPO], [EXILEXP],
[POESEED], [FORUM-CRASH], [FORUM-SKIP], [PASTE], [PLM], [PLM-AREA], [GROKHUB],
[POE2UTILS], [POEFIRE], [GGG-DEV], [SEARCH-PATHS].

## 1. File location, growth, encoding

- Steam default (PoE2): `<Steam library>/steamapps/common/Path of Exile 2/logs/Client.txt`.
  Forum posts show the install dir as `C:/Program Files (x86)/Steam/steamapps/common/Path of Exile 2`
  and a second library on another drive (e.g. `<other drive>/SteamLibrary/steamapps/common/Path of Exile 2`).
  Some forum posts give the same path with folder `Path of Exile` (PoE1); treat PoE2 vs PoE1
  folder name as the key difference. (accessed 2026-11-16) [SEARCH-PATHS]
- ExileXP (MIT) tails `<PoE2 install>/logs/Client.txt`; on first launch it checks default Steam and
  standalone install locations on drives C through H and lets the user browse to the install
  folder (the one containing `logs/`). (accessed 2026-11-16) [EXILEXP]
- poefire (MIT) finds Client.txt automatically for standard and Steam installs and has a manual
  "Game log" folder setting for others. (accessed 2026-11-16) [POEFIRE]
- poe2-utils (no license stated) finds the install folder from the running game process, then
  `logs/Client.txt`. (accessed 2026-11-16) [POE2UTILS]
- GrokHub PR notes the watcher follows Steam installs of PoE and PoE2 only; standalone installs
  were not followed by that PR. (accessed 2026-11-16) [GROKHUB]
- Standalone (non-Steam) PoE2 path: UNVERIFIED. PoE1 standalone default reported as
  `C:/Program Files (x86)/Grinding Gear Games/Path of Exile/logs/Client.txt`
  (accessed 2026-11-16) [SEARCH-PATHS-PLM]. A PoE2 equivalent folder name is UNVERIFIED; the app
  should offer a folder picker plus a Steam library scan (read `libraryfolders.vdf`, UNVERIFIED
  as to exact file, standard Steam behaviour).
- LatestClient.txt: forum posts mention the name, but no source confirms it for PoE2. UNVERIFIED.
  Do not depend on it. (accessed 2026-11-16) [SEARCH-PATHS]
- Growth and rotation: no source documents rotation or truncation. Reports of multi-GB files
  and of rotation: UNVERIFIED. Design for: file shrinking (size < saved offset) means reset to 0;
  file replaced (new inode / creation time) means reopen.
- Encoding: UNVERIFIED by any source. Sample lines in forum threads show non-Latin character names
  (Korean) intact, which implies UTF-8 (or UTF-16 is not used). Handle an optional UTF-8 BOM and
  decode with replacement on invalid bytes. (accessed 2026-11-16) [FORUM-SKIP]
- Line endings: UNVERIFIED. PowerShell `Get-Content -Tail 0 -Wait` works on it (accessed
  2026-11-16) [PASTE]; accept both LF and CRLF and hold back a trailing partial line until its
  terminator arrives.
- Share mode: the game keeps writing while tools read, so tools open it read-only with share
  read/write. Not documented by a source; UNVERIFIED. Open with FILE_SHARE_READ | FILE_SHARE_WRITE |
  FILE_SHARE_DELETE.

## 2. How existing tools tail it

- Polling at an interval: poe-log-monitor (MIT) has an `interval` option, default 1000 ms
  (its area doc uses 500 ms). (accessed 2026-11-16) [PLM] [PLM-AREA]
- PowerShell script: `Get-Content <path> -tail 0 -wait`, i.e. start at end of file, then stream new
  lines. (accessed 2026-11-16) [PASTE]
- GrokHub watcher: begins at end of file on start so old sessions are not replayed. (accessed
  2026-11-16) [GROKHUB]
- poe2-utils: on startup scans the END of the file backwards to learn the current scene, then tails.
  (accessed 2026-11-16) [POE2UTILS]
- poeseed (MIT): a command-line parser with a setting for how many trailing lines to parse (default
  1000). (accessed 2026-11-16) [POESEED]
- Recommendation: poll (200-500 ms) on file size + read from saved offset; fs-watch on Windows is
  unreliable for a file the game appends to (UNVERIFIED claim, design opinion). On startup, read the
  last N KB (e.g. 256 KB) to recover current zone and character, then follow from end.

## 3. Line prefix format

Real PoE2 lines (June 2026 forum post, ASCII) (accessed 2026-11-16) [FORUM-CRASH]:

- `2026/06/11 06:36:24 9557000 7fbd1225 [INFO Client 15736] [SCENE] Set Source [Atlas]`
- `2026/06/11 06:37:08 9601390 78f667ee [WARN Client 15736] Atlas input suspension DISABLED`
- `2026/06/10 00:43:59 34739218 337881d4 [CRIT Client 25344] [RENDER] Shader uses incorrect vertex layout`

A December 2024 PoE2 chat/system sample (accessed 2026-11-16) [FORUM-SKIP]:

- `2024/12/25 12:22:56 5694281 3ef2336f [INFO Client 12584] : AFK mode is now ON.`
- `2024/12/25 12:24:35 5792718 3ef2336f [INFO Client 12584] #Name: text`
- `2024/12/25 12:25:34 5852546 3ef2336f [INFO Client 12584] : Trade accepted.`
- `2024/12/25 12:25:42 5859703 3ef2336f [INFO Client 12584] @To Name: text`

Regex-ready description of the prefix (derived from the samples; the field meanings are inferred):

- Date: `YYYY/MM/DD` (4-2-2 digits, slash separated). Local time (UNVERIFIED, see pitfalls).
- Space, time `HH:MM:SS`.
- Space, millisecond-ish counter: decimal integer, grows with uptime of the client (appears to be
  milliseconds since process start; UNVERIFIED). Not wall clock.
- Space, 8 lowercase hex chars (a per-session or per-thread id; varies between lines in the same
  second: `7fbd1225` vs `78f667ee`; meaning UNVERIFIED).
- Space, `[LEVEL Client PID]` where LEVEL is INFO, WARN or CRIT seen; PID is the process id (decimal).
- Then either a body starting with `[TAG]` (e.g. `[SCENE]`, `[RENDER]`), or a space-prefixed
  `: ` for system messages, or a chat prefix character (`#`, `$`, `%`, `&`, `@From`, `@To`) directly
  after the `]` and one space.
- Suggested regex shape (ASCII, PCRE style):
  `^(\d{4}/\d{2}/\d{2}) (\d{2}:\d{2}:\d{2}) (\d+) ([0-9a-f]{8}) \[(\w+) Client (\d+)\] (.*)$`
  then match the captured body (group 7) against the event patterns below.
- Exiled Exchange 2 (MIT) matches on the body only, with these patterns after the prefix is
  stripped: system `^: (.+)$`, trade `$`, global `#`, party `%`, guild `&`, whisper `@To`/`@From`.
  (accessed 2026-11-16) [EE2-CS]
- GrokHub (parses only system lines) uses the fragments `] : ` and `[SCENE] Set Source [...]` and
  says only system lines count as game events so typed chat cannot fake a death or level-up.
  (accessed 2026-11-16) [GROKHUB]

## 4. Events and exact line patterns

### Zone / area change

- PoE2 confirmed: `[SCENE] Set Source [<scene name>]`. Seen names: `Atlas`, `Caer Tarth`, `(null)`.
  A `(null)` source appears between scenes. A WARN line often precedes the change. (accessed
  2026-11-16) [FORUM-CRASH]
- poe2-utils (no license) watches `[SCENE] Set Source ...`; entering a hideout disables its hotkey
  and leaving re-enables after a delay of 3 seconds. (accessed 2026-11-16) [POE2UTILS]
- A PoE2 parsing write-up (could not be fetched; known only from a search snippet) says the parser
  keys on `[SCENE] Set Source [` or `[SCENE] Load Source [` and extracts the bracketed name.
  UNVERIFIED (snippet only). (accessed 2026-11-16) [SEARCH-PARSE-BLOG]
- Area generation line, from EE2's client strings (MIT):
  `Generating level <N> area "<zone id>" with seed <digits>`.
  Body regex shape: `^Generating level (\d+) area "(.*)" with seed (\d+)$`. The quoted value is an
  internal area id (not necessarily the display name). ExileXP also keys on this and on
  `You have entered <zone>`. (accessed 2026-11-16) [EE2-CS] [EXILEXP]
- `: You have entered <Zone>.` is confirmed for PoE1 (poe.trade-era script matches
  `] : You have entered`). No PoE2 example was found. UNVERIFIED for PoE2. Treat the English text as
  language dependent. (accessed 2026-11-16) [PASTE] [EXILEXP]
- Example PoE1 line: `... [INFO Client 1372] : You have entered Coral Ruins.` (accessed 2026-11-16)
  [SEARCH-EVENTS-SNIPPET]

### Character level up

- Body: `: <Character> (<Class>) is now level <N>`. Regex shape from EE2 (MIT): name, class in
  parentheses, `is now level`, digits. (accessed 2026-11-16) [EE2-CS]
- Name/class are free text; use the greedy name group then a final `\((.*)\)` group.

### Death

- `: <Character> has been slain.` and variant `: <Character> has committed suicide.` (reported
  from a PoE1 tool event table seen as a search snippet; neither verified for PoE2). UNVERIFIED.
  (accessed 2026-11-16) [SEARCH-EVENTS-SNIPPET]
- poe-log-monitor lists a `death` event, GrokHub tracks deaths from system lines. (accessed
  2026-11-16) [PLM] [GROKHUB]
- Other players' deaths in the area use the same text; filter by the tracked character name.

### Whispers and trade

- Incoming: `@From [<GuildTag> ]<Character>: <text>`; outgoing: `@To <Character>: <text>`.
  Regexes from EE2: `^@To (.+?): (.+)$`, `^@From (?:<(.+?)> )?(.+?): (.+)$`. (accessed 2026-11-16)
  [EE2-CS]
- Trade-site templates (PoE1 forum thread shows the poe.trade whisper style; exact PoE2 wording
  UNVERIFIED):
  - Priced item: `Hi, I would like to buy your <Item> listed for <price> <currency> in <League> (stash tab "<Tab>"; position: left <X>, top <Y>)`
  - Unpriced: `Hi, I would like to buy your <Item> in <League> (stash tab "<Tab>"; position: left <X>, top <Y>)`
  - Currency exchange: `Hi, I'd like to buy your <N> <Currency> for my <M> <Currency> in <League>.`
  (templates quoted from memory of the live game; no fetched source gave the full text; UNVERIFIED.
  The poe.trade thread confirms only that the format differs per client language.)
  (accessed 2026-11-16) [SEARCH-WHISPER]
- `: Trade accepted.` is a system line (seen in PoE2 Dec 2024 sample). (accessed 2026-11-16)
  [FORUM-SKIP]
- EE2 also has a "webtrade gem" line pattern `level <N> <Q>% <gem name>` used inside whispers for
  gems. (accessed 2026-11-16) [EE2-CS]

### Chat channel prefixes (after the `] `)

- `#` global, `$` trade, `%` party, `&` guild, `@To` / `@From` whispers, `: ` system. Optional
  guild tag in angle brackets before the name, then `: ` and the body. (accessed 2026-11-16)
  [EE2-CS]
- The 2015-era trade-alert script suppresses alerts when the line contains `#`, `@`, `%` or `&`
  (to avoid chat spoofing). Same lesson: only trust system lines (`: ` prefix). (accessed
  2026-11-16) [PASTE]

### AFK / DND

- `: AFK mode is now ON. <autoreply>` and `: AFK mode is now OFF.` (PoE2 sample seen). DND uses
  analogous `: DND mode is now ON/OFF` lines (UNVERIFIED wording). poe-log-monitor emits `afk` and
  `dnd` events. (accessed 2026-11-16) [FORUM-SKIP] [PLM]

### Player joined / left area; party

- poe-log-monitor emits `areaJoin` and `areaLeave` (line text for PoE1: `: <Name> has joined the area.`
  / `has left the area.`, UNVERIFIED for PoE2). GrokHub treats a name joining the player's area as
  a party member, never as the player. (accessed 2026-11-16) [PLM] [GROKHUB]

### Login / instance server

- A PoE2 log shows `Connecting to instance server at <ip>:<port>` (from a search snippet; exact
  prefix not fetched). UNVERIFIED. poe-log-monitor emits `instanceServer` and `login` events.
  (accessed 2026-11-16) [SEARCH-EVENTS-SNIPPET] [PLM]
- Character select vs in-game: no verified line. UNVERIFIED. Treat the first `[SCENE] Set Source`
  after a `Connecting to instance server` as a new session start.

### Other commands and misc

- poe-log-monitor lists events for `/deaths`, `/remaining`, `/age`, `/played` outputs and for NPC
  encounters; line texts not shown by the sources. UNVERIFIED. (accessed 2026-11-16) [PLM]
- Passive/ascendancy messages, item filter load lines, map or waystone completion, boss kills:
  no source found. UNVERIFIED. A tailer should log unknown bodies to a debug sink to discover them.
- Level-up and zone tracking is enough for a levelling overlay; poefire (MIT) uses zone and act splits
  plus loading-screen exclusion for campaign timing. (accessed 2026-11-16) [POEFIRE]

## 5. Localization: language-dependent lines

- Structural parts are language independent: prefix, `[SCENE] Set Source [..]` (internal scene id,
  UNVERIFIED if translated), `Generating level N area "id" with seed N`, chat prefix characters.
- Language dependent: `You have entered`, `is now level`, `has been slain`, AFK/DND text, whisper
  trade templates, party join/leave text, `Connecting to instance server` (likely, UNVERIFIED).
- poefire requires the game language set to English because it reads English log messages. (accessed
  2026-11-16) [POEFIRE]
- A poe.trade helper thread says whisper parsing failed for Russian clients because the
  whisper labels differ per language. (accessed 2026-11-16) [SEARCH-WHISPER]
- Policy: prefer language-independent signals (`Generating level`, `[SCENE]`) for zone, and the
  `X (Class) is now level N` shape only for English; ship per-locale pattern sets and a
  "wrong language" diagnostic.

## 6. Pitfalls

- Missing messages: a forum bug thread reports some chat lines missing from the log (non-Latin names;
  a supporter said Korean-client messages are not logged by design; unconfirmed by staff). Never
  rely on the log as a complete chat record. (accessed 2026-11-16) [FORUM-SKIP]
- Duplicate lines: `[SCENE] Set Source` appears with `(null)` in between and repeated entries for the
  same zone; debounce and collapse duplicates by (counter, text). (accessed 2026-11-16) [FORUM-CRASH]
- Same-zone ambiguity: poe-log-monitor notes story areas share names and the log does not say which
  variant; return all possibilities. (accessed 2026-11-16) [PLM-AREA]
- Very large files: never read whole file; seek from end, read backwards for recent state.
  Multi-GB size claims are UNVERIFIED.
- Timestamps: local time of the machine (UNVERIFIED; no timezone/offset in the line). DST changes
  produce non-monotonic times; use the counter field or your own receipt time for ordering.
- Chat spoofing: only trust lines whose body starts with `: ` (system). Player chat can contain
  fake `X is now level 99` text only after a channel prefix. (accessed 2026-11-16) [GROKHUB]
- Hideout detection: poe2-utils uses the scene name; the exact hideout scene names (e.g. containing
  the word Hideout) are UNVERIFIED. Matching `Hideout` as a substring is the common approach.
  (accessed 2026-11-16) [POE2UTILS]
- Policy (GGG developer docs): reading logs is allowed only while the user is aware of what the app
  does with the data; reacting to file changes to trigger game actions (macros) is forbidden;
  macros must be manually invoked and do one game-affecting action. A passive tailer that never
  sends input to the game is the safe design. Apps that interact with the game or its files are
  prohibited per the page (account termination); read-only log tailing is what existing tools do.
  (accessed 2026-11-16) [GGG-DEV]

## Event schema proposal

All events carry `ts_local` (ISO 8601 without zone, from the line), `counter` (int), `raw` (original
line, optional), `source` ("client_log"), `seq` (monotonic per process).

- `tailer_started`: `{ path, offset, file_size, resumed: bool }`
- `tailer_reset`: `{ reason: "truncated" | "replaced" | "missing" }`
- `session_connect`: `{ host, port }` (from `Connecting to instance server at`; UNVERIFIED line)
- `scene_changed`: `{ scene: string, is_null: bool, is_hideout: bool }`
- `area_generated`: `{ area_level: int, area_id: string, seed: string }`
- `area_entered`: `{ name: string }` (language dependent; PoE1-confirmed)
- `level_up`: `{ character: string, class: string, level: int }`
- `death`: `{ character: string, suicide: bool }`
- `whisper_in`: `{ from: string, guild_tag?: string, text: string, trade?: { item, price_amount, price_currency, league, stash_tab, left, top } }`
- `whisper_out`: `{ to: string, text: string }`
- `chat`: `{ channel: "global" | "trade" | "party" | "guild", character: string, guild_tag?: string, text: string }`
- `afk_changed`: `{ on: bool, autoreply?: string }`
- `dnd_changed`: `{ on: bool }`
- `player_joined_area` / `player_left_area`: `{ character: string }`
- `trade_accepted`: `{}`
- `unknown_system_line`: `{ body: string }` (debug sink for discovery)
- `parse_warning`: `{ code: string, detail: string }` (e.g. wrong_language)

Derived state the tailer should keep: current character, class, level, current scene, in_hideout,
session start counter, language guess.

## Sources

- [EE2-CS] Exiled Exchange 2 client strings (English), license MIT (accessed 2026-11-16):
  https://raw.githubusercontent.com/Kvan7/Exiled-Exchange-2/dev/renderer/public/data/en/client_strings.js
- [EE2-REPO] Exiled Exchange 2 repo, license MIT (LICENSE first line "MIT License") (accessed
  2026-11-16): https://github.com/Kvan7/Exiled-Exchange-2 and
  https://raw.githubusercontent.com/Kvan7/Exiled-Exchange-2/master/LICENSE
- [EXILEXP] ExileXP, MIT (accessed 2026-11-16): https://github.com/andreins/ExileXP
- [POESEED] poeseed, MIT (accessed 2026-11-16): https://github.com/TwentyFiveEx/poeseed
- [FORUM-CRASH] PoE2 crash thread with raw Client.txt lines (accessed 2026-11-16):
  https://www.pathofexile.com/forum/view-thread/3957386
- [FORUM-SKIP] Game logs skipping some ingame messages, PoE2 sample lines (accessed 2026-11-16):
  https://www.pathofexile.com/forum/view-thread/3664076
- [PASTE] PoE client log monitoring script (accessed 2026-11-16): https://pastebin.com/5Nki7Das
  (license not stated)
- [PLM] poe-log-monitor, MIT (accessed 2026-11-16): https://github.com/klayveR/poe-log-monitor
- [PLM-AREA] poe-log-monitor AREA.md (accessed 2026-11-16):
  https://raw.githubusercontent.com/klayveR/poe-log-monitor/master/AREA.md
- [GROKHUB] GrokHub PR 1251 (accessed 2026-11-16):
  https://github.com/blackviperxiii-ui/GrokHub/pull/1251 (license not checked)
- [POE2UTILS] poe2-utils, no license stated (accessed 2026-11-16):
  https://github.com/EgeBalci/poe2-utils
- [POEFIRE] poefire, MIT (accessed 2026-11-16): https://github.com/trigun0x2/poefire
- [GGG-DEV] GGG developer docs, third-party tool and overlay rules (accessed 2026-11-16):
  https://www.pathofexile.com/developer/docs
- [SEARCH-PATHS] Forum threads for install paths (accessed 2026-11-16):
  https://www.pathofexile.com/forum/view-thread/3829178 and
  https://webcdn.pathofexile.com/forum/view-thread/3827589
- [SEARCH-WHISPER] poe.trade helper forum thread (whisper format, per-language labels) (accessed
  2026-11-16): https://pathofexile.com/forum/view-thread/1755148
- [SEARCH-PARSE-BLOG] "Real-Time Game Log Analysis: Parsing POE2's Client.txt with Rust" (fetch
  returned 404; used only as a search snippet; UNVERIFIED) (accessed 2026-11-16):
  https://davidmeents.com/blog/post/0008-poe2-overlord-log-analysis
- [SEARCH-EVENTS-SNIPPET] Search snippets for death/level/AFK/instance-connect lines (UNVERIFIED
  where not repeated above) (accessed 2026-11-16): https://github.com/trigun0x2/poefire
- [SEARCH-PATHS-PLM] PoE1 default path in poe-log-monitor search result (accessed 2026-11-16):
  https://github.com/klayveR/poe-log-monitor
