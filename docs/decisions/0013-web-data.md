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
   rebuilt from a fixed template (pobb.in/pob/<id>, pastebin.com/raw/<id>).
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

- pobb.in and pastebin raw-download paths (ROADMAP TC-URL-VERIFY).
- poe.ninja overview response field names beyond research 0005's summary;
  the parser is defensive (DATA-NINJA-VERIFY).
- trade2 filter names (misc_filters / corrupted) and real limit values
  (research 0004).
- poe.ninja asks for a contact in the User-Agent; AshLight sends name,
  version and purpose only (no contact in tracked files, CLAUDE.md hygiene).

## Reverses if

poe.ninja or a share site changes or forbids these endpoints, GGG's tool
policy changes, or the operator rules web data must be per feature.
