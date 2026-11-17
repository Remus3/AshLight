# 0013 - Web endpoint verification (DATA-NINJA-VERIFY, TC-URL-VERIFY)

All requests and pages accessed 2026-11-17. Read-only GETs, no cookies,
User-Agent `AshLight/0.1.0 (web endpoint verification; read-only)`, no
contact, 2 s or more between requests, 12 requests in total. Checks the
assumptions of decision 0013 and server/al/ninja.py, shareurl.py.

## poe.ninja (PoE2)

Docs: https://poe.ninja/docs/api (accessed 2026-11-17).

- VERIFIED leagues path: GET https://poe.ninja/poe2/api/economy/leagues ->
  200 application/json, `[{"id","name"},...]`. Body at the time:
  Forbidden Rites, Runes of Aldur, HC Forbidden Rites, HC Runes of Aldur,
  Standard, Hardcore (id equals name). First entry is the newest league
  (Forbidden Rites launched 2026-09-04, Runes of Aldur 2026-05-29:
  https://www.pcgamesn.com/path-of-exile-2/update-forbidden-rites-league
  and https://massivelyop.com/2026/08/28/path-of-exile-2-previews-september-4s-forbidden-rites-league-and-1-0s-new-duelist-class/ ,
  accessed 2026-11-17). Caveat: "first = current" holds only while the newest
  league is listed first and is a softcore challenge league; a short event
  league listed first is still what "current" means to a trader.
  ETag present (`W/...`), `cache-control: no-cache`.
- VERIFIED overview path:
  GET /poe2/api/economy/exchange/current/overview?league=<id>&type=Currency
  -> 200 application/json (22 KB, 44 lines for Runes of Aldur; 26 KB, 51
  for Forbidden Rites). Headers: `Cache-Control: public, max-age=1800,
  stale-while-revalidate=300, stale-if-error=86400`, weak `etag`.
- VERIFIED conditional request: re-sending the weak ETag in If-None-Match
  returned 304 with no body.
- VERIFIED docs terms: ETag + conditional requests, PoE2 data refreshes
  "roughly hourly", polling faster than a few minutes pointless (the hourly
  gate in ninja.py is within the guidance); economy endpoints only; "no
  stability guarantee"; desktop apps "should proxy these requests through
  their own backend"; "Send a descriptive User-Agent that identifies your app
  and a contact" (open: UA-CONTACT). The docs say the HTTP cache is "roughly
  5 minutes"; the live header says 30 minutes.
- Accepted `type` values for PoE2 (docs): Currency, Fragments, Abyss,
  UncutGems, LineageSupportGems, Essences, SoulCores, Idols, Runes, Ritual,
  Expedition, Delirium, Breach, Verisium. `Currency` is valid.
- WRONG (code assumption): names are read from `core.items`. In the real
  response `core.items` lists only the 3 reference currencies (divine,
  exalted, chaos); the names of every line live in a TOP-LEVEL `items`
  array (44 / 51 entries, one per line id). parse_overview therefore names
  3 of 44 rates. The docs table also places `items` under core, so the docs
  are misleading; the live shape wins. Fix row DATA-NINJA-NAMES.
- VERIFIED: `lines[].id`, `primaryValue`, `volumePrimaryValue` exist as
  assumed; extra fields `maxVolumeCurrency`, `maxVolumeRate`, `sparkline`
  are ignored harmlessly. `core.primary` is a string ("divine" for both
  leagues), `core.secondary` ("chaos"), `core.rates` a map id -> rate
  against primary (exalted 531.0, chaos 7.43). primaryValue is in primary
  units, so the primary currency itself has `primaryValue` 1.
- Test fixture note: tests/test_data_ninja.py uses `primary: "exalted"`; the
  real primary is `divine`. Harmless to the parser.

Trimmed real shape (2 of 44 lines, values rounded, image paths removed):

    {"core":{"items":[{"id":"divine","name":"Divine Orb","category":"Currency",
      "detailsId":"divine-orb"}],"rates":{"exalted":531.0,"chaos":7.43},
      "primary":"divine","secondary":"chaos"},
     "lines":[{"id":"exalted","primaryValue":0.001883,"volumePrimaryValue":29.5,
      "maxVolumeCurrency":"divine","maxVolumeRate":531.0,
      "sparkline":{"totalChange":3.06,"data":[0.66,0.58,1.99]}}],
     "items":[{"id":"exalted","name":"Exalted Orb","category":"Currency",
      "detailsId":"exalted-orb"}]}

## pobb.in (share links)

Source for routes: https://github.com/Dav1dde/pasteofexile (README
"Public API"; worker/src/route.rs; accessed 2026-11-17). Live checks used
the public example link https://pobb.in/dEyY_M9tM3Nf (a creator's build
link found by search, accessed 2026-11-17).

- VERIFIED: https://pobb.in/pob/<id> -> 200 `text/plain`, 10 572 bytes of
  base64url build code (starts `eNrt...`); no redirect. The route is the
  "pob://" import route used by Path of Building (route.rs, PobPaste).
- VERIFIED: https://pobb.in/<id>/raw -> 200 `text/plain`, identical body.
  This is the documented third-party route: README "For third-party
  integrations there are currently two public URLs: `/:id/raw` and
  `/u/:username/:id/raw`", and it asks for "a User-Agent which identifies
  your application and includes contact info".
- Missing id: /pob/<id> -> 404 `application/json`
  `{"code":404,"message":"The requested 'paste' does not exist"}`.
- No redirect seen on either path.
- Terms note: https://pobb.in/robots.txt disallows `/pob/` and `/*/raw$`
  (and /*/json$, /*/xml$, /api/) for all crawlers. AshLight issues one
  user-initiated fetch per pasted link, not a crawl, but the documented path
  is /<id>/raw and its contact-in-User-Agent request applies (UA-CONTACT).
- GAP: user-scoped links https://pobb.in/u/<name>/<id> are not handled by
  shareurl.raw_url (it needs exactly one segment); they would need
  /u/<name>/<id>/raw. Not a wrong assumption, a missing case.
- The code's RAW_TEMPLATES path /pob/<id> works today but is not the
  documented API. Fix row TC-URL-POBBIN-RAW (switch to /<id>/raw).

## pastebin.com

- PARTIAL: https://pastebin.com/raw/<id> exists as a route: a missing id
  returns 404 `text/html` ("Not Found (#404)", Cloudflare). No real paste
  id was available to confirm a 200 text/plain body, so the 200 shape is
  UNVERIFIED; the route is the long-standing public raw path.
- https://pastebin.com/robots.txt disallows `/raw/` for crawlers
  (accessed 2026-11-17); same one-fetch-per-click reasoning as pobb.in.
- No redirect seen (the 404 came direct).

## Rate and terms summary

- poe.ninja: hourly gate + ETag within the docs. Contact in UA missing
  (UA-CONTACT, already queued). Desktop-proxy guidance not followed (decision
  0013 records the mitigation).
- pobb.in: contact in UA requested by the project README; same row.
- No cookie or POESESSID is needed on any of these endpoints.
