# 0048 - AshLight's own GGG OAuth public client: scope, ports, token handling

Date: 2026-11-18. Source: package DATA-GGG-APPLICATION (TC-OAUTH-REG);
findings F-083 and F-149 (docs/plan/02-findings.md, floor audit
2026-11-18); research 0035 (F2 to F6, F8, F11, R2, open question 1);
decisions 0004 (item 4), 0031, 0033 and 0044; rulings Q-03 and A-01
(decision 0078). Docs only, no web read. Amends decision 0004 item 4.

## Decision

1. Client. AshLight applies for its own GGG OAuth public client (realm
   `poe2`), authorization code with PKCE (S256), never another
   application's client id. The ready application is
   docs/ops/ggg-oauth-application.md.
2. Scope: `account:characters` only. `account:profile` is not requested
   (the token answer already names the account; research 0035 F5).
   `account:item_filter` is not requested: it can only create or update
   a filter the game then loads, which the floor (never modify any game
   file) and the download-only decisions 0031 and 0033 do not allow
   (floor audit L3).
3. Redirects: `http://127.0.0.1:8979/oauth/callback`, with 8978 as the
   fallback, both in the AL port block. The redirect needs its own
   one-shot listener because a browser redirect cannot carry the core's
   per-start token (research 0035 R2). The two port constants land with
   the client core (F-116), not here.
4. Tokens. The access token is held in memory only, and no refresh token
   is kept, until GGG answers question 1 (refresh tokens and where they
   may be stored) in writing. Character reads happen only on the
   player's Connect and Refresh clicks until GGG answers question 2
   (reads triggered by the player's own Client.txt lines or by core
   start). The public Currency Exchange endpoint is not called until GGG
   answers question 3 or AshLight holds a client (TC-CURX, F-206).
5. Approval cadence: at best one browser approval per 7 days (the public
   client's refresh ceiling, research 0035 F4), never "one sign-in
   ever".
6. Contact: the application and its `OAuth <clientId>/<version>`
   User-Agent name the project's issues page once the repository is
   public (Q-03); until then it is a placeholder. No account name,
   email or private value is written to a tracked file.
7. Sending. The operator sends the application when
   ops/runtime/ggg_docs/REG_OPEN appears (decision 0044) or reports
   registration open (A-01 fallback). Sending is one operator act,
   because a registration belongs to the operator's account. A granted
   client id goes only into gitignored config/local.json.

## Amends decision 0004 item 4

Decision 0004 item 4 named the scopes `account:profile` +
`account:characters` and a loopback redirect "in the AL port block". This
record narrows the scope to `account:characters`, fixes the redirects on
8979 and 8978 and states the token handling above. Decision 0004's
PoB-interop core and the rest of item 4 (no POESESSID, no undocumented
endpoint, no other app's client id, paste paths until a client exists)
stand.

## Alternatives

- Keep `account:profile` (decision 0004 as written): more data and a
  longer consent for nothing the import needs. Rejected.
- Add `account:item_filter` now, since scopes are fixed at registration
  (research 0035 F5): rejected by the floor audit (a game-loaded file
  write).
- Store a refresh token now, as Path of Building does: GGG's docs ask for
  server-side storage; wait for GGG's written answer.
- Event-driven reads from the start: not until GGG says log-triggered
  reads are fine.
- No own client, paste only: keeps the manual export and paste; TC-IMPORT
  never closes.

## Why

D-IDX requires a public client for an executable; one scope is the
smallest consent that covers the import; two fixed loopback ports hedge
an exact port match; the three questions settle exactly the points the
docs leave open, so nothing is built on a guess.

## Reverses if

GGG requires `account:profile` for consent or the User-Agent, refuses
the loopback ports, or the operator drops live import.

## Record

Dated lines for the send and GGG's answers to questions 1 to 3 go here
(row TC-OAUTH-REG).
