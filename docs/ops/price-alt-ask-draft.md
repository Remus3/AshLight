# Price source permission request: poe2scout.com (draft, ready to send)

Row: DATA-PRICE-ALT-ASK (research 0064 G7; decision 0072: silence is not
consent). Status: draft, not sent. The operator sends it from the
project's own contact and adds the sender name and reply address; nothing
personal is in this file. Where to send: the contact route poe2scout lists
on its site or its public repository (https://github.com/poe2scout/poe2scout,
issues or the maintainer's stated contact). After sending, record the date
sent, the answer or its absence, and the operator's ruling in a decision
file (the row's ACCEPT). A yes still needs the operator's ToS-floor
amendment before any provider row; this request changes nothing in the app.

Subject: Permission request: read-only price lookups from AshLight (PoE2 companion)

---

Hello poe2scout team,

I maintain AshLight, an open-source, unofficial companion app for Path of
Exile 2 on Windows (version 0.1.0, Apache-2.0). AshLight isn't affiliated
with or endorsed by Grinding Gear Games in any way.

AshLight runs on the player's own PC. It reads the game's Client.txt log
and, when the player presses its hotkey, the item text they copied. It
never touches the game process and sends nothing to the game. Today its
item price line comes from poe.ninja. We would like to ask whether
AshLight may use poe2scout as a second price source, and on what terms.

What the use would be:

- Read-only price lookups only: currency and item prices by league, from
  your documented public API (https://api.poe2scout.com). No writes, no
  account, no login and no session cookie (AshLight never asks for or
  stores a POESESSID).
- Rate-limited on our side: each install fetches a small set of overview
  lists on a fixed schedule (no more often than hourly per list, ETag or
  If-Modified-Since honoured where you support it), caches them locally
  and answers every price check from that cache. A player's press never
  causes a request of its own. We would honour any lower rate, schedule
  or Retry-After you set.
- Off by default: nothing is requested unless the player turns on
  AshLight's one "web data" setting.
- A truthful User-Agent on every request, naming AshLight, its version
  and a contact address for the project, for example
  "AshLight/0.1.0 (+<project contact>)".
- Attribution: the price line and the app's data credits name poe2scout
  as the source, with a link to your site if you would like one.
- No resale and no revenue: AshLight is free, has no paid tier, ads or
  donation gate, and never sells or republishes your data. Prices stay in
  the player's local cache and are shown only to that player.

What we are asking:

1. Written permission for this use by a desktop client, or the
   conditions under which you would give it.
2. A contact (address or channel) we should use for anything about this
   use, including a request from you to slow down or stop.
3. Your rate terms: requests per minute or per day per client, any
   endpoints you would prefer us to use or avoid, and caching
   expectations.
4. Whether you need an API key, registration or a fee, and if so how to
   obtain it.
5. If you can say: where your price data comes from, so we can describe
   it truthfully to players.

If the answer is no, that is fine too; please just tell us and AshLight
will not call your service. Until we have your written answer, AshLight
makes no request to poe2scout.

Thank you for running poe2scout.

<sender name>
AshLight maintainer
<reply address or project contact>
