# 0050 - Research dive sources: no free web tools, one host allow-list

Date: 2026-11-18. Source: package AUTO-04 (DIVE-FLOOR), finding F-171
(docs/plan/02-findings.md, floor audit 2026-11-18); ruling Q-07 and
operator decision A-01 (decision 0078, docs/plan/09); the CLAUDE.md Game
ToS floor (GGG endpoints only if they are in the API Reference or Data
Exports); decisions 0013, 0017 and 0044. No web read was made for this
record.

## Decision

1. No agent or tool reads GGG's forum. The idle deep-dive prompt
   (tools/loop_prompts.py deep_dive_prompt) and step 1 of the 1.0 launch
   runbook name only three sources: text the operator pasted, public
   non-GGG repositories through the documented GitHub API, and GGG's API
   Reference and Data Exports pages. The 1.0 patch notes come from
   operator-pasted text only. Research 0029 carries a dated amendment.
2. A dive is spawned without free web tools: tools/loop_base.py
   DEEP_EXTRA grants no WebFetch and no WebSearch, only the gate tools
   (al_lane.GATE_TOOLS, unchanged) plus `Bash(python tools/webfetch.py:*)`.
   The kit spawns with `--setting-sources project`; the project settings
   allow neither web tool, so a headless dive cannot use them.
3. tools/webfetch.py is the dive's one web path, a CLI over
   server/al/webfetch.py (check_url, is_trade_url, user_agent, the
   transport). One function, `allowed(url)`, is the allow-list:
   - GGG hosts (pathofexile.com, pathofexile2.com, grindinggear.com,
     poecdn.com and their subdomains): only
     https://www.pathofexile.com/developer/docs/reference and
     /developer/docs/data, no query, no encoded or dot segments.
     The forum, the trade site and every other GGG path are refused.
     GGG's other developer-docs pages (index, authorization, changelog,
     game) sit behind the constant A01_OTHER_DOCS_PAGES, False until the
     operator answers A-01.
   - https://api.github.com/repos/<owner>/<repo>... for public non-GGG
     repositories; GGG-named owners are refused.
   - poe2db and every wiki host (wiki, fandom) are refused by name, every
     other host by the list.
4. Every request obeys the web-data opt-in (config/local.json `web_data`
   strictly true, read at call time, as webfetch.require_opt_in): while it
   is off nothing is sent and the dive works from sources in the repo.
   Each request carries the truthful AshLight User-Agent (plus the
   configured contact), never a cookie; each redirect hop is re-checked
   against `allowed`, so a redirect cannot leave the two pages; a 429 or
   503 Retry-After (at least one hour) is kept per host and obeyed.
5. Every hop, fetched or refused, appends one ASCII line (time, host,
   path, status or refusal, User-Agent) to dive_fetch/hosts.log in the AL
   sidecar Logs.

## Alternatives

- Keep WebFetch / WebSearch and rely on the prompt. Rejected: a reminder
  is not enforcement (zero-click rule: the floor is enforced in code and
  in the spawn arguments).
- Add `--disallowedTools WebFetch,WebSearch` to the spawn. Not taken: the
  package's accept line requires the spawn arguments to hold neither
  name, and the project-only setting source already leaves both
  unpermitted in a headless run.
- Allow the developer-docs changelog (ruling Q-07 named it). Rejected
  under the stricter reading (floor audit, A-01 default no); one constant
  turns the other docs pages on if the operator allows them.
- Allow poe.ninja or github.com web pages. Rejected: the package names
  only the three sources above; poe.ninja stays the app's own opt-in
  data source (decision 0026), not a dive source.
- Enforce robots.txt in the tool. Not taken: it would add a request to
  /robots.txt, a GGG path outside the two pages; the two pages and the
  documented GitHub API are fetched one GET at a time.

## Why

- The floor allows GGG endpoints only in the API Reference or Data
  Exports; Q-07 reads that clause as binding every GGG host read, and the
  stricter reading wins.
- One allow-list function in code is testable (tests/test_dive_fetch.py)
  and cannot be talked around by a prompt.
- The host log makes every dive read auditable after the fact.

## Reverses if

The operator amends the floor, answers A-01 (then only the constant
changes), or GGG documents the forum as a permitted source.

## Addendum 2026-11-27 (adjudicator ruling): GitHub wikis and raw docs

Decision: tools/webfetch.py adds two hosts to HOSTS, GITHUB_WEB
(github.com) and GITHUB_RAW (raw.githubusercontent.com), and allowed()
narrows each to read-only GET pages with no query string:
- github.com: only `/<owner>/<repo>/wiki` and `/<owner>/<repo>/wiki/<page>`
  (3 or 4 path segments, the third exactly `wiki`); every other github.com
  path is refused with "only repository wiki pages are read".
- raw.githubusercontent.com: `/<owner>/<repo>/<ref>/<path...>`, at least 4
  segments, the file ending in `.md` or `.txt`.
- Both refuse GGG_GITHUB_OWNERS and keep the encoded and dot segment
  checks; poe2db and every wiki host (poe2wiki.net, poewiki.net, fandom)
  stay refused by name. Tests: tests/test_dive_fetch.py.

Alternatives: keep the API-only rule (rejected: public tool wikis and
plain READMEs are where community build tools document formats, and the
API's contents route returns base64 JSON a dive cannot read well); allow
all of github.com (rejected: issues, code search and release assets are
not docs, and the trade-site and GGG-owner rules are easier to keep with a
narrow shape); allow any raw file type (rejected: scripts and images are
not research text).

Why: the two shapes are read-only text pages of public non-GGG
repositories, the same sources the API route already reads, so the floor
(no GGG path outside the two docs pages, no forum, no wiki hosts) is
unchanged.

Reverses if: GitHub asks tools not to read wiki or raw pages
automatically, a dive is seen reading a non-docs file through the raw
host, or the operator limits dives to the API again.
