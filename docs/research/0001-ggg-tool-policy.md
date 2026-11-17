# Grinding Gear Games third-party tool policy

Research date: 2026-11-16; re-read 2026-11-17 (ROADMAP RES-POLICY, section at the end). Not legal advice. GGG staff reportedly say they "cannot comment on the legality of third-party tools" and cannot guarantee a tool stays allowed (from search-result summaries of staff replies; verbatim text UNVERIFIED).

## Official policy (developer docs)

- Source: https://www.pathofexile.com/developer/docs (accessed 2026-11-16).
- Apps separate from the game are tolerated: "Ordinarily we only allow the creation of applications that run completely separate from the game."
- Apps that interact with the game or its files are banned: "This behaviour is strictly against our Terms of Use." The docs also say creation or use of such apps "will result in immediate account termination."
- Tone: "We don't encourage players to download or run "tools" on their machine" (https://www.pathofexile.com/developer/docs/index, accessed 2026-11-16).
- Apps must state non-affiliation: "This product isn't affiliated with or endorsed by Grinding Gear Games in any way." (https://www.pathofexile.com/developer/docs, accessed 2026-11-16).
- Macros must be invoked manually; timers or other automated invocation are not allowed (https://www.pathofexile.com/developer/docs/index, accessed 2026-11-16).
- Do not embed keys or credentials in a distributed binary; do not share app credentials (same page, accessed 2026-11-16).

## Terms of Use

- Source: https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy (accessed 2026-11-16).
- Forbidden: "Utilise any automated software or 'bots' in relation to your access or use of the Website, Materials or Services."
- Forbidden: "Connect to the Servers through any software other than the authorised game client software."
- Forbidden: "Modify or adapt (including through third parties and third-party tools) the game client or its data"
- Forbidden: "Use any data gathering and extraction tools or software to extract information from the Website"
- API clause: "you must comply with the Website API call limits" and "not attempt to circumvent those limits."
- Same page: no PoE2-specific tool section; terms cover both games ("'Path of Exile' and/or 'Path of Exile 2' online games") (accessed 2026-11-16).

## Macros: one action per key press

- Source: community guide thread https://www.pathofexile.com/forum/view-thread/2077975 (accessed 2026-11-16). It is a player guide, not official policy; it says it may not be exhaustive and does not cover PoE 2. The rule it states: "one action per key press." A server action (flask, chat command) counts as one action.
- Allowed per guide: chat commands and messages (e.g. /hideout), alternative mouse cursors, attacking in place (reluctant approval). Method (AutoHotkey, vendor software) does not matter; what the player gets does.
- Forbidden per guide: multiple actions per press (several flasks), alternating or rotating actions, chat command plus another action, moving the cursor and clicking ("definitely constitute botting"), timers, anything automatic (e.g. auto flask or logout at a health threshold).
- Staff statement (thread 3474232): "automation of any kind is botting and will get you banned." and "Bans are at the sole discretion of GGG." (Chulainn_GGG; https://www.pathofexile.com/forum/view-thread/3474232, accessed 2026-11-16). Same thread: Awakened PoE Trade is widely used, but "there are aspects about it that I think probably violate the ToS."

## Explicit allow/forbid for the items asked

- Reading Client.txt: no official statement found in fetched sources. UNVERIFIED. It is a log file the game writes to disk; widely used by community tools.
- Clipboard item copy (Ctrl+C in game), overlays, trade site usage: no official page fetched explicitly permits them. UNVERIFIED.
- Memory reading, injection, packet modification, automation, botting: forbidden by the ToU lines above (client modification, non-client server connections, bots) and by the developer docs ("interact with the game or game files").

## PoE2 vs PoE1

- ToU covers both games with the same restrictions (ToU URL above, accessed 2026-11-16). No separate PoE2 tool policy found. PoE2 anti-cheat or client-change specifics: UNVERIFIED.
- The macro guide predates PoE2 and says so.

## Official API rules

- OAuth registration: "We are currently unable to process new applications." (https://www.pathofexile.com/developer/docs, accessed 2026-11-16). A new app cannot get an OAuth client right now.
- User-Agent: "Any application that interacts with our API must set an identifiable User Agent header"; format "User-Agent: OAuth {$clientId}/{$version} (contact: {$contact}) ..." (https://www.pathofexile.com/developer/docs/index, accessed 2026-11-16).
- Rate limits: headers "should be parsed and followed by your application": X-Rate-Limit-Policy, X-Rate-Limit-Rules, X-Rate-Limit-{rule}, X-Rate-Limit-{rule}-State, Retry-After. Each rule value is max hits, period seconds, restriction seconds. "Exceeding these limits frequently will result in your application access being revoked." (same pages, accessed 2026-11-16).
- Unofficial endpoints: "We can only support resources defined in our API Reference or listed in our Data Exports." Requests for other internal website APIs "will be denied." (https://www.pathofexile.com/developer/docs, accessed 2026-11-16). Trade site endpoints are not named in the docs. Third-party use of undocumented trade endpoints: UNVERIFIED; treat as unsupported and risky (ToU bars data extraction tools on the Website).

## Trademark and fan content

- ToU: GGG "is the owner or licensee of all rights including all copyright, trade marks" (ToU URL, accessed 2026-11-16). The GGG logo or trademark may not be used in link graphics; no hidden meta tags with the GGG name.
- ToU clause 8 licenses streaming and video of gameplay with conditions; it does not cover software tools.
- No dedicated GGG fan-content or tool-branding page found. Whether "Path of Exile" may appear in a tool name: UNVERIFIED. Safe practice: use it only descriptively ("for Path of Exile 2"), include the non-affiliation line, use no GGG logos or art.

## Design consequences for this app

- Never read game process memory, inject code, or hook the client. Touch game files only via read-only Client.txt (UNVERIFIED as officially allowed; make it opt-in and documented).
- Never send or synthesize keyboard or mouse input to the game. No auto-click, no macros, no timers acting on the game.
- Clipboard: read only after a user-initiated Ctrl+C; never trigger the copy for the user.
- Screen capture is passive only (UNVERIFIED as officially allowed); never act on captured data automatically.
- Run as a separate, always-on-top window of our own; do not attach to or draw into the game process.
- No packet inspection or modification; no traffic proxying.
- Call only documented API or data-export endpoints; no scraping of undocumented trade endpoints; obey X-Rate-Limit headers and Retry-After; set the documented User-Agent with a contact.
- Ship no embedded credentials. OAuth registration is closed, so design for no-API operation.
- Show a visible notice: "This product isn't affiliated with or endorsed by Grinding Gear Games in any way."
- Branding: no GGG logos or art; "Path of Exile" only descriptively.
- Disclaim that GGG does not guarantee any tool stays allowed.

## Sources

- https://www.pathofexile.com/developer/docs (accessed 2026-11-16)
- https://www.pathofexile.com/developer/docs/index (accessed 2026-11-16)
- https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy (accessed 2026-11-16)
- https://www.pathofexile.com/forum/view-thread/2077975 (accessed 2026-11-16)
- https://www.pathofexile.com/forum/view-thread/3474232 (accessed 2026-11-16)
- https://web.poecdn.com/forum/view-thread/3734853 (fetch returned 403; seen only in search results; accessed 2026-11-16)

## Verified quotes (re-read 2026-11-16 by the orchestrator)

Re-read of https://www.pathofexile.com/developer/docs (accessed 2026-11-16).
These lines supersede any UNVERIFIED marker above on the same point:

- "Apps that use information sourced from the screen, the clipboard, or the game's logs must follow our overlay rules:"
- "You may only read this information as long as the user is aware of what you are doing with that data."
- "Reading from the screen or clipboard may only be performed once per manual key press."
- "Macros must be invoked manually by the user" and automated invocations "such as but not limited to: timers, reacting to file changes, ... or from reading the screen are not allowed."
- "Each macro invocation must have one set function (it cannot cycle between actions)."
- "The resulting function may only perform one action that interacts with the game (sending a single chat message or command counts as one action)."
- Standalone executables: "While not encouraged, these are permitted." They "must use a public OAuth client if interacting with our APIs."
- Interacting with the game or its files "is strictly against our Terms of Use (sections 7b, 7c, 7i)"; "Creation or use of these type of applications will result in immediate account termination."
- Required visible statement: "This product isn't affiliated with or endorsed by Grinding Gear Games in any way."

Consequences that bind Ashlight (go into CLAUDE.md as the ToS floor):
- Client.txt (the game's log) may be tailed continuously, but only with the
  user aware: an opt-in first-run consent naming exactly what is read and what
  it is used for, and a visible "reading Client.txt" indicator.
- Screen capture / OCR and clipboard reads happen ONLY once per manual key
  press of the user: no timers, no continuous screen polling, no clipboard
  polling. A hotkey triggers exactly one read.
- Ashlight sends no input to the game at all (stricter than the macro rule).
- The affiliation statement above is shown in the README, the dashboard footer
  and the About panel.

## Re-read 2026-11-17 (ROADMAP RES-POLICY)

Pages re-read anonymously on 2026-11-17:
https://www.pathofexile.com/developer/docs,
https://www.pathofexile.com/developer/docs/changelog and
https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy (all
accessed 2026-11-17).

Verdict: GGG policy UNCHANGED in substance since the 2026-11-16 verified
quotes above. Every overlay, macro, standalone-app, game-interaction and
non-affiliation quote above is still on the page word for word.

What the changelog says:
- The latest entry is dated 12/11/2026 (DD/MM), 3.30.0 (Covens of Umbra):
  "Clarified Policy wording on macros and overlays", plus new Character,
  LeagueAccount and PassiveNode API properties and a fix to the PoE2
  Account Leagues docs
  (https://www.pathofexile.com/developer/docs/changelog, accessed
  2026-11-17). That date is before the 2026-11-16 re-read, so the verified
  quotes above already reflect the clarified wording. No policy entry
  since then.

Current Policy section layout (developer docs, accessed 2026-11-17): three
app classes. "Websites and web apps" ("Little to no risk for end users").
"Executable apps that run independently from the game" ("While not
encouraged, these are permitted"; macro rules and overlay rules apply).
"Executable apps that interact with the game or game files" ("strictly
against our Terms of Use (sections 7b, 7c, 7i)"). AshLight is in the
second class. The policy section itself does not mention PoE2. The only
explicit PoE2 item on the page is the file-format entry "Build Planner
(PoE2 only)". The docs still state no "last updated" date.

Lines on the 2026-11-17 page that this note did not quote before (all from
https://www.pathofexile.com/developer/docs, accessed 2026-11-17):
- "As a general rule, we cannot allow our Intellectual Property to be used
  to generate commercial revenue." The next sentence says this includes
  creating and selling physical items or copying GGG's assets to make other
  games.
- "You may not present your project or tool in a way that could be
  construed as it being developed or officially authorised" by GGG (the
  quote is shortened; the rest of the sentence is not quoted here).
- "Introducing features against these guidelines or our Terms of Use can
  result in account termination for you" (the sentence goes on to say the
  same applies to the tool's users).
- "We reserve the right to remove access to any or all of our APIs and
  services without notice at our discretion."
- "It is against our Terms of Use (section 7i) to reverse-engineer
  endpoints outside of this documentation." (Research 0004 already
  recorded this point on 2026-11-16.)
- The rate limits "are dynamic and can change at any time".
- In the macro rule, automated invocation "such as but not limited to:
  timers, reacting to file changes, or from reading the screen" is not
  allowed. This binds only input automation, and AshLight sends no input
  at all.

Terms of Use (accessed 2026-11-17): titled "PATH OF EXILE & PATH OF EXILE 2
- TERMS OF USE". It shows no effective date; the privacy policy on the
same page reads "Last Updated: October 2024". The section 7 restriction
lines quoted above are unchanged: modify or adapt the client or its data,
automated software or bots, connecting through non-authorised client
software, data gathering and extraction tools, and "Reverse engineer,
de-compile or disassemble the Website, Materials or Services". The fetcher
rendered the items as numbers (7.2, 7.3, 7.5, 7.6, 7.9), while the
developer docs cite letters (7b, 7c, 7i). The API clause still requires
following "the Website API call limits set out in the API Policies".

### Proposed CLAUDE.md "Game ToS floor" changes (NOT applied; for MAIN / operator)

Nothing in GGG's rules has loosened or tightened, so the floor stays valid.
The re-read found three places where the floor's wording is incomplete:

1. Tighten: add "No commercial revenue from GGG intellectual property (no
   paid tier, no sale of GGG-derived data or assets)". Source: the
   commercial-revenue line above. The floor does not cover this today.
2. Tighten: extend the branding bullet to "never present AshLight as
   developed, authorised or endorsed by GGG". Source: the "construed as it
   being developed or officially authorised" line. The floor has the
   non-affiliation statement and the no-trademark rule, but not this
   presentation rule.
3. Clarify: the floor calls the trade source the "official trade API".
   The trade2 endpoints are not in GGG's API Reference, and the docs bar
   reverse-engineering undocumented endpoints (ToU 7i; research 0004).
   Proposed wording: "the trade site's trade2 endpoints only as an opt-in,
   best-effort dependency (undocumented; X-Rate-Limit-* headers obeyed
   dynamically)". Whether the trade2 price check is allowed at all is
   already settled in decisions 0013 and 0015. This change only makes the
   floor accurate; it is not a ruling on that question.
