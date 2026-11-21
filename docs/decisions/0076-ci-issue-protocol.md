# 0076 - CI issue protocol: labelled key issues from a daily watch workflow

Date: 2026-11-21. Source: package AUTO-19 (CI-WATCH, unit F-150) of the
execution plan, docs/plan/06 AUTO-19; adjudicator LE-76 (close-out 2 of
2026-11-18); ruling Q-03 (CI User-Agent contact); decision 0069 (upstream
watcher frame); decision 0013 (web data opt-in).

## Scope

Decision 0013 governs the app and the dev host; the CI watcher runs only on a GitHub runner (GITHUB_ACTIONS true, else it refuses), reads only URLs that pass watch_gate.check_url, never a GGG or poe.ninja host, and is not a web_data path (adjudicator LE-76).

## Decision

1. `.github/workflows/watch.yml` runs once a day off the hour (cron
   minute 37) and on manual dispatch, on a standard GitHub-hosted runner
   (windows-2025, the runner ci.yml already proves), with permissions
   `contents: read` and `issues: write` only, every action pinned by full
   commit id (the same pins as ci.yml), checkout without persisted
   credentials and no repository secret: the job token
   (`github.token`) is the only credential. That token is read-only for
   contents; `issues: write` is its only write scope, the one the issue
   protocol needs. It runs
   `python tools/watch_ci.py --sources <names>`; the entry takes registry
   source names, so a later package (AUTO-20) adds its own workflow
   without editing this one.
2. The sources it runs today: pob-release (a CI tag read: releases/latest
   metadata of the repository in config/tc_pins.json against the pinned
   tag; no trial runs on a runner), repoe-fork and ggg-tree (their own
   metadata checks; the found live version against a tracked BASELINE in
   tools/watch_ci.py), electron (its own check against app/package.json
   and config/electron_pin.json; the 3-day age of a line head counts from
   the GitHub release's published_at). npm-audit stays a loop-home
   source under its own web_data gate (decision 0069) and never runs in
   CI. A name outside that list whose home is not ci or both, ggg-docs
   and npm-audit always, and an unknown name are refused before any
   request. No CI job downloads a repoe-fork
   or tree file.
3. Every source read goes through watch_ci's own fetch: watch_gate.check_url
   on the URL and on every redirect hop, then server/al/webfetch.request
   with the CI User-Agent `AshLight/<version> (local Path of Exile 2
   companion; ci watcher <source>) (contact: <issues page>)`, where the
   issues page is built from the runner's GITHUB_SERVER_URL and
   GITHUB_REPOSITORY (Q-03), no cookie, at most 6 requests per source. The
   job token goes only to api.github.com.
4. Key protocol. A finding becomes the key `<source>:<key>`. The workflow
   keeps one open issue per key, labelled `al-watch`, title
   `al-watch: <key>`, body exactly one line
   `AL-WATCH key=<source>:<key> v=1` (pattern
   `^AL-WATCH key=([a-z][a-z0-9_-]{0,47}):([\x21-\x7e]{1,200}) v=1$`).
   An open issue of a source that ran clean this run whose key is no
   longer found is closed (completed); a source that failed keeps its
   issues (a failed read is not "gone"); a duplicate open key closes the
   newer issue. Only issues opened by the bot account
   (`github-actions[bot]`) whose body matches the pattern are read or
   touched; every other issue is left alone.
5. It never commits, pushes or opens a pull request. The runner keeps no
   state between runs; the comparison is with the tracked pins and the
   tracked baseline, and a session moves a baseline value after acting on
   its finding (the issue then closes on the next run).
6. The tick side (package LOOP-CI-ISSUES) reads the open labelled issues,
   trusts only the bot account and the key pattern, files the row from
   its own template, and fails over to the dev loop when the workflow is
   not active or 48 h silent.

## Alternatives

- Keep every source on the dev loop only. Rejected: the watch stops while
  the dev host is off; standard runners are free on a public repository.
- Persist runner state with a cache or artifact action. Rejected: one more
  pinned action and a mutable store outside git for little gain; the
  tracked pins and baseline plus the open issues carry what is needed.
- Free-text issue bodies or comments carrying data. Rejected: the tick
  must never read upstream or user text; one fixed line with a strict
  pattern is all it accepts.
- A commit or pull request per finding. Rejected: CI never commits
  (decision 0069); rows come only from the tick's tracked templates.
- Reading or setting a web_data value on the runner. Rejected: a runner
  is no user host (LE-76), and a workflow never turns web data on.
- npm advisories in CI. Rejected for now: npm-audit's source reads the
  web_data gate, which only the operator can exempt in writing (decision
  0069); npm advisories in CI would need a CI-native check with no
  web_data flag; out of scope.

## Why

A daily workflow keeps the upstream watch alive while the dev host sleeps,
costs nothing on a public repository and cannot leak: it holds no secret,
writes only issues, and every byte the tick accepts from it is one fixed
line from one account.

## Reverses if

Anonymous issue reads are refused, issue spam makes the label unusable,
GitHub stops granting labels to the job token with `issues: write`, or
GGG or poe.ninja are ever needed by a CI source (then this scope is
re-ruled, never widened silently).
