# 0041 - GGG-DOCS-WATCH: daily read of GGG's developer docs

Date: 2026-11-17. Row: ROADMAP GGG-DOCS-WATCH. Input: operator order
2026-11-17 (a daily automatic check of GGG's developer API docs, above all
whether new OAuth application registration has reopened), research 0033
section 1 (registration closed), research 0029 (policy wording watch),
decision 0025 (how a daily read-only check rides the loop tick). Ruled by
the build lane itself (FLEET item 1).

## Decision

1. `tools/ggg_docs_watch.py` (stdlib) reads six pages once per 24 h:
   `https://www.pathofexile.com/developer/docs` and its `/authorization`,
   `/reference`, `/changelog`, `/data` and `/game` pages. One anonymous GET
   per page, sequential with a 1 s gap, through `server/al/webfetch.py`
   (https only, host `www.pathofexile.com` only, truthful AshLight
   User-Agent, no cookie, no token, 1 MB cap, redirects re-checked). A 429
   or 503 stops the run at once and the next run waits for its
   `Retry-After` (at least 1 h); a network error retries after 3 h. The
   24 h slot is claimed in the state file before the first request, so a
   parallel tick never doubles the reads.
2. Only the text inside `<main>` is kept (headings marked `#`, list items
   `-`, whitespace normalised; scripts, navigation and attributes dropped),
   so a Cloudflare token or an image cache key never reads as a change.
   Its sha256 and the text snapshot live in the AL sidecar
   `Cache\ggg_docs\`; the gate state is `Cache\ggg_docs\state.json`.
3. A page whose hash moved writes a unified diff to the sidecar
   `Logs\ggg_docs\<stamp>-<page>.diff` and one ASCII line to the gitignored
   `ops/runtime/ggg_docs/notes.log`, tagged by topic (registration,
   token-lifetime, scopes, redirect, client-type, poe2, rate-limit,
   policy). A new changelog entry is named. Nothing is written to a
   tracked file; diffs stay local.
4. Registration: the index page reads `closed` while it carries "We are
   currently unable to process new applications.", `open` when the page is
   readable (main text and its "Getting Started" section present) and the
   sentence is gone or reworded, else `unknown` (a challenge or error page
   never raises an alarm). The registration section text and any `mailto:`
   link or `<form>` in the page are kept and a change in them is noted.
5. Notification, zero-click: the flag file `ops/runtime/ggg_docs/REG_OPEN`
   exists exactly while the state is `open` and is removed when the
   sentence returns. (a) The core lists a NOTE row "GGG developer API" in
   the existing Checks view (`server/al/diag.py`, snapshot `diag`) while
   the flag exists: one small line, no new panel; a test core never reads
   the live flag. (b) No Windows toast: the stdlib-only paths (`msg.exe`,
   a MessageBox) open a modal, focus-taking window that could pull focus
   from the game mid-fight; a real toast needs a non-stdlib module. (c)
   The loop tick line reads "REGISTRATION MAY BE OPEN (TC-OAUTH-REG)", and
   an interactive session that finds the flag updates ROADMAP
   TC-OAUTH-REG and asks the operator for the application (an operator
   act).
6. The al_loop tick calls the watch BEFORE the HALT short-circuit: it
   runs while the loop is HALTed. Why: it is read-only, six small GETs a
   day, spawns no claude run and edits nothing tracked, and HALT exists to
   stop lane spawns and commits, not to blind the one signal the operator
   asked to get without looking. A dry-run tick never calls it.
7. The docs pages are plain public documentation pages, not API endpoints;
   the floor's "GGG endpoints only if documented" clause concerns API
   calls, and research 0029 already re-reads these pages anonymously by
   hand. Like TC-DRIFT this is dev tooling run by the loop, not an app
   feature, so it does not wait for the player's web_data opt-in (decision
   0013 governs the app's own requests).

## Alternatives

- Hash the raw HTML: Cloudflare script tokens and image keys change on
  every load. Rejected; main text only.
- Fetch in the core: the core runs on player machines and would make GGG
  requests for a developer concern. Rejected; loop tool only.
- Respect HALT: the watch would go silent exactly when the loop is paused
  for a long time, which is when the operator relies on it. Rejected (6).
- `msg.exe` or a PowerShell toast module: focus-taking or non-stdlib.
  Rejected (5b).
- Commit a summary file: the diffs carry GGG's text verbatim and would
  grow the public repo for no reader. Rejected; local only.

## Why

The operator wants to know, without looking, when AshLight can apply for
its own public OAuth client (TC-OAUTH-REG, which unblocks TC-IMPORT). One
read a day of six pages costs GGG nothing measurable and obeys its rate
limit headers; the sentence check is exact, and a page that is not the
known page never raises the alarm.

## Reverses if

GGG asks tools not to read the docs pages automatically or blocks them
(robots or a rate limit aimed at it), the docs move to another host or a
format without `<main>`, the operator rules the watch must respect HALT,
or registration reopens and TC-OAUTH-REG is done (then the watch may drop
to the changelog page only).
