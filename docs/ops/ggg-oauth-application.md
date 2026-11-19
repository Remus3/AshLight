# GGG OAuth application (ready to send)

Status: prepared 2026-11-18 (package DATA-GGG-APPLICATION, decision
0048). Not sent: GGG's developer docs say registration is closed
(research 0035 F1). Sending is one operator act (row TC-OAUTH-REG),
because a registration belongs to the operator's own account.

When to send: the docs watch (decision 0044) writes
`ops/runtime/ggg_docs/REG_OPEN` when the closed-registration sentence
leaves the developer docs index. Its index-page read is under operator
decision A-01 (decision 0078); the operator's own report that
registration is open (the hand-off line `REG OPEN (operator)`) counts as
the same signal. Use whatever channel the reopened page names (research
0035 F2: when last open it was a mail to GGG's OAuth address).

Before sending, fill the two placeholders below in the outgoing copy
only. Never write the account name or any contact value into this file
or any tracked file (CLAUDE.md, Public-repo hygiene).

## The application

The six asks GGG's page listed when registration was open (research 0035
F2, archived copies 2024-01-16 and 2025-01-24), answered:

1. Path of Exile account name: `<ACCOUNT NAME - fill in the sent copy
   only>`.
2. Application name: AshLight. An unofficial, free, open-source companion
   for Path of Exile 2 on Windows: it reads the game's own Client.txt
   log and shows a second-screen dashboard and a click-through overlay.
   It never touches the game process, sends no input to the game and
   modifies no game file. It is not affiliated with or endorsed by
   Grinding Gear Games.
3. Client type: public client. AshLight is a standalone desktop
   executable with no server, so it cannot keep a client secret (D-IDX:
   an executable must use a public client).
4. Grant type: authorization code with PKCE (`code_challenge_method`
   S256, a verifier of at least 32 bytes of entropy), and refresh token
   only if GGG allows it for a desktop client (question 1 below). No
   client-credentials grant, no `service:*` scope.
5. Scopes, each with its reason:
   - `account:characters`: to import the player's own characters
     (equipment, skills and passives) into AshLight's build view, in
     place of a manual Path of Building export and paste.
   That is the whole list. `account:profile` is not requested: the
   token answer already names the account. `account:item_filter` is not
   requested: AshLight never writes a filter the game loads (its filter
   help is a download on the player's click only).
6. Redirect URIs (loopback, one-shot listener bound to 127.0.0.1):
   - `http://127.0.0.1:8979/oauth/callback`
   - `http://127.0.0.1:8978/oauth/callback` (fallback when 8979 is busy)
   Both ports are in AshLight's own port block (8960-8979). If GGG
   registers only one URI, 8979 is the one.

Contact: `<CONTACT - the project's issues page once the repository is
public (ruling Q-03)>`. The same contact goes into the User-Agent,
`OAuth <clientId>/<version> (contact: <contact>)` (D-IDX).

How AshLight will use the API: only `GET /character/poe2` and
`GET /character/poe2/<name>`, for the account's own characters; the
documented `X-Rate-Limit-*` headers and `Retry-After` obeyed
dynamically; no POESESSID, no undocumented endpoint, never another
application's client id. The consent page opens in the player's system
browser, never in an embedded view.

## Questions for GGG

1. Refresh tokens: does a desktop public client get refresh tokens, and
   if so where may they be stored? (D-AUTH says refresh tokens must be
   stored securely on a server; a desktop tool has none. AshLight's
   proposal is the Windows Credential Manager of the player's own
   account; until GGG answers, the access token is held in memory only
   and no refresh token is kept.)
2. Event-triggered reads: may AshLight call the character endpoints when
   the player's own Client.txt log shows a level-up, a character switch
   or a town entry, or when AshLight's core starts, in addition to the
   player's own Connect and Refresh clicks? (Until GGG answers, reads
   happen only on those two clicks.)
3. Currency Exchange: may AshLight call the public Currency Exchange
   endpoint (`https://web.poecdn.com/api/currency-exchange/poe2`), marked
   Public API in the reference, and if so with which User-Agent: the
   `OAuth <clientId>/<version>` form of the granted client, or a plain
   truthful one before a client exists?

Also asked in passing (no answer needed to proceed): whether the
redirect match includes the port (RFC 8252 section 7.3 says a loopback
redirect may use any port), and whether two registered URIs are
accepted.

## After the send

- Record the send date and, when it comes, GGG's answer to each of the
  three questions as dated lines in decision 0048 (row TC-OAUTH-REG).
- A granted client id goes only into gitignored `config/local.json`.
- Rows waiting on the answers: TC-IMPORT (questions 1 and 2), TC-CURX
  (question 3).

Sources: research 0035 (F1 to F6, F8, F11, R2), decisions 0004, 0031,
0033, 0044, 0048 and 0078 (Q-03, A-01).
