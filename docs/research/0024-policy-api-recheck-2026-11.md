# 0024 - PoE2 policy / API recheck, last 30 days (to 2026-11-17)

All sources accessed 2026-11-17. Compared against 0001 (policy) and 0018
(state, API). Verdict: NO change that affects the ToS floor.

- Developer docs changelog: newest entry is still 3.30.0 (Covens of
  Umbra, dated 12/11/2026): policy wording on when macros and overlays
  apply clarified (already in 0001), new Character / LeagueAccount /
  PassiveNode / ItemMod fields, PoE2 Account Leagues endpoint documented as
  enabled. Previous: 3.29.3b (05/09/2026, mercenary fields), 3.29.0
  (21/07/2026, Currency Exchange public; covered in 0018). Nothing newer in
  the 30-day window
  (https://www.pathofexile.com/developer/docs/changelog , accessed
  2026-11-17).
- Policy page unchanged in the parts the floor quotes: "Reading from the
  screen or clipboard may only be performed once per manual key press";
  macros "must be invoked manually by the user", one set function, one game
  action; standalone executables "must use a public OAuth client if
  interacting with our APIs"; registration: "We are currently unable to
  process new applications"; UA `OAuth {$clientId}/{$version} (contact:
  {$contact})` (https://www.pathofexile.com/developer/docs , accessed
  2026-11-17). TC-OAUTH-REG stays blocked.
- API Reference: Account Item Filters (`/item-filter`, scope
  `account:item_filter`, realm `poe2`) is present; not new, but first
  recorded here (0022). OAuth only.
- Terms of Use: clause 7 (i) "Reverse engineer, de-compile or disassemble
  the Website, Materials or Services" and 7 (iii) no "automated software or
  'bots'" unchanged; the page shows no ToU date (only the Privacy Policy
  "Last Updated: October 2024")
  (https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy ,
  accessed 2026-11-17).
- poe.ninja API docs: unchanged vs 0019 - economy endpoints "allowed but
  incidental", "no versioning and no SLA", descriptive UA with contact,
  PoE2 leagues / exchange / stash item routes, first league = current
  challenge league, PoE2 data refresh about hourly
  (https://poe.ninja/docs/api , accessed 2026-11-17).
- PoB-PoE2: still v0.23.1 (2026-07-28); TC-DRIFT HOLD stands (0017)
  (https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases ,
  accessed 2026-11-17).

Action: none for the floor. Re-run this check on the 1.0 patch notes
(UTIL-1.0-POST step 1) and when GGG reopens app registration.

## Sources

- https://www.pathofexile.com/developer/docs (accessed 2026-11-17)
- https://www.pathofexile.com/developer/docs/changelog (accessed 2026-11-17)
- https://www.pathofexile.com/developer/docs/reference (accessed 2026-11-17)
- https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy (accessed 2026-11-17)
- https://poe.ninja/docs/api (accessed 2026-11-17)
- https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases (accessed 2026-11-17)
