# 0013 - Web data: one opt-in, one fetch path (DATA-NINJA, TC-URL, PRICE-1)

Date: 2026-11-17. Trigger: ROADMAP rows DATA-NINJA, TC-URL (deferred by
decision 0007 F2) and PRICE-1, worked by the data lane. No adjudicator was
needed: every fork below follows from CLAUDE.md, decisions 0003 / 0004 /
0007 and research 0004 / 0005.

## Decision

1. Opt-in. One setting, `"web_data": true|false` in the local config
   (`config/local.json`, gitignored; a test core uses its runtime dir),
   DEFAULT OFF. Nothing on the network is requested while it is off: the
   poe.ninja client, the share-link fetch and the trade2 queue each read it
   at call time (`webfetch.require_opt_in`), the trade queue again right
   before sending. API: `GET /api/web-data`, `POST /api/web-data
   {"enabled": bool}` (token, Host, Origin as every other endpoint). An
   optional `"league"` key in the same file pins the league for poe.ninja.
   Alternatives: (b) one opt-in per feature; (c) opt-in in consent.json.
   Why (a): one clear toggle is the minimal-interaction rule; consent.json
   is the Client.txt consent of decision 0003 and stays separate.
2. One fetch path. `server/al/webfetch.py` is the only outbound HTTP code in
   the core: https only, exact host allowlist per caller, no user info, no
   port but 443, no IP literal, ASCII URL text only; urllib never follows a
   redirect by itself - each Location is checked against the same allowlist
   and at most 3 are followed; response size cap and 10 s timeout; a
   User-Agent naming AshLight and its version is required and a Cookie
   header is refused (no POESESSID, ever). Every client takes an injectable
   transport, so tests never touch the network.
3. DATA-NINJA (`server/al/ninja.py`). Only the documented economy endpoints
   (research 0005): `/poe2/api/economy/leagues` (first entry = current
   league; at most once a day, skipped when a league is configured) and
   `/poe2/api/economy/exchange/current/overview?league=<id>&type=Currency`,
   at most once per hour, conditional on the stored ETag. The last attempt
   time is persisted with the cache (`<sidecar>\Cache\ninja\rates.json`), so
   a restart never refetches early, and a failed attempt counts. `GET
   /api/rates` returns the cached rates with their age and the attribution
   text and starts a due refresh in the background; it never blocks on the
   network. ATTRIBUTION is exposed from the module for the UI row.
4. TC-URL (`server/al/theorycraft/shareurl.py`). Share links from pobb.in
   and pastebin.com only. The pasted URL is never fetched as given: after
   the URL checks, only the paste id is taken and the download URL is
   rebuilt from a fixed template (pastebin.com/raw/<id>; pobb.in/<id>/raw,
   and pobb.in/u/<name>/<id>/raw for a user link, the name in
   [A-Za-z0-9_-] like the id - the public third-party routes in pobb.in's
   README, research 0013; TC-URL-POBBIN-RAW 2026-11-17 replaced the PoB
   import route pobb.in/pob/<id>, which is still accepted when pasted).
   One fetch per paste, no retry; the body (capped at the codec's 2 MB) must
   be a build code or character JSON (never another link) and is loaded
   through the normal paste path, so the build persists as its code and
   reloads on start with no refetch. Alternatives: fetch the pasted URL
   itself (rejected: SSRF surface); add poe.ninja PoB links (rejected:
   undocumented internal endpoints, research 0005).
5. PRICE-1 server part (`server/al/trade.py`). One rate limiter shared by
   every trade2 call, driven only by the response headers
   (X-Rate-Limit-Policy / -Rules / -<rule> / -<rule>-State, Retry-After with
   a 60 s fallback), kinds that name the same policy share its state, one
   hit of headroom, one serial queue. Query builder for a parsed item.
   The clipboard read and the hotkey stay with PRICE-1 (decision 0003).

## Alternatives not taken

- Let urllib follow redirects with a checking handler (as the build-time
  snapshot does): rejected for the runtime path; manual handling makes the
  hop count and every target explicit and testable.
- Proxy poe.ninja through an own backend (poe.ninja's guidance for desktop
  clients, research 0005): no backend exists; mitigated by the hourly gate,
  ETag and one shared poll.

## Open (UNVERIFIED)

- pastebin raw 200 body shape (route confirmed, research 0013); pobb.in
  /<id>/raw verified live, /u/<name>/<id>/raw documented but not fetched
  live (research 0013).
- poe.ninja names live in a top-level `items`, not core.items (verified
  2026-11-17, research 0013); parse_overview reads them since
  DATA-NINJA-NAMES.
  Amendment 2026-11-18 (LOOP-DECISION-TIDY): resolved; verified live
  2026-11-17 and fixed by DATA-NINJA-NAMES, it only sat under this heading.
- trade2 filter names (misc_filters / corrupted) and real limit values
  (research 0004).
  Amendment 2026-11-18 (LOOP-DECISION-TIDY): the limit values are moot
  since decision 0017 (no trade2 call). The filter names stay open: they
  still feed the ?q= trade link (server/al/trade.py type_filters, decision
  0037), and a wrong name only drops that filter.
- poe.ninja asks for a contact in the User-Agent; AshLight sends name,
  version and purpose only (no contact in tracked files, CLAUDE.md hygiene).

## Reverses if

poe.ninja or a share site changes or forbids these endpoints, GGG's tool
policy changes, or the operator rules web data must be per feature.

## Amended by 0017

Amended by 0017 (2026-11-17): item 5 (trade2 calls): the app no longer
calls trade2; trade is a search link the user opens. See
docs/decisions/0017-trade-no-app-calls-and-floor-wording.md.

## Amendment 2026-11-17 (AUDIT-SNAPSHOT-OPTIN, audit finding T1)

Ruled by the adjudicator agent (CLAUDE.md FLEET item 1).
- Decision: this decision now also covers the build-time game-data
  snapshot: it follows the single
  `web_data` opt-in of decision 0013 (default off). `scripts/build.ps1`
  runs it only when config/local.json holds `"web_data": true` (strict
  bool, as the core reads it) or the build is forced with `-Snapshot` /
  env `AL_SNAPSHOT=1` (passed on as `snapshot --opt-in`); `-NoSnapshot` /
  `AL_NO_SNAPSHOT=1` still skip and win. `snapshot.main` checks the same
  setting itself, so a direct run also makes no request while it is off.
  Once web data is on, every build refreshes the snapshot by itself
  (the 24 h gate keeps a re-run a no-op).
- Alternatives: (b) keep the opt-out and write a build-time exception into
  0013 - rejected: users read "nothing hits the network while off"
  literally and a fresh build would still contact two hosts; (c) a second
  `snapshot` setting - rejected: two consent switches contradict 0013's
  one opt-in.
- Why: one consent switch, the promise kept literally, zero-click after
  the opt-in; the app already treats the snapshot as optional (zone levels,
  tree names and the data credit read a missing cache as absent).
- Reverses if: a core feature turns out to need snapshot data and cannot
  degrade, the operator rules that a build-time fetch is not "web data",
  or first-run use shows users missing the data and not finding the switch.
- Tests: tests/test_audit_snapshot_optin.py.
