# 0066 - Uninstall consent

Date: 2026-11-19. Source: docs/plan/05-deployment.md ("Uninstall", goal
G7 and G8, decision D6, risk "Wrong folder deleted by the
uninstaller"), finding F-063, package DEP-10. Builds on decision 0059
(the per-user install home), decision 0010 (processes proven ours) and
FLEET item 9 (irreplaceable data goes to the Recycle Bin).

## Decision

1. `scripts/uninstall.ps1` (shipped as `<home>\uninstall.ps1`) is the one
   uninstaller of an installed copy. Windows PowerShell 5.1, no Python,
   self-contained (no dot-sourcing, no module import), so it runs when
   the runtimes are broken or gone.
2. Asked first: nothing by default. One click in Apps and features
   removes AshLight and keeps the player's data (`<home>\data`: consent,
   settings, run history, builds, price watch, visits, local.json).
   `-Purge` is the consent to remove the data too; run by hand without
   `-Yes` it asks once for the typed word PURGE. With `-Quiet` or with
   no one at the keyboard (redirected input) `-Purge` needs `-Yes`, else
   exit 2 with nothing touched. `-DryRun` prints the plan and changes
   nothing (it does not even make the temp copy). `-Quiet` prints only
   the last lines.
3. Validate first: `install.json` beside the script is a JSON object
   with name "AshLight" and integer schema 1, and the home passes the
   path-shape guard of decision 0059 (no `steamapps` or game-folder
   component, path text only; not a drive root). Else exit 2 and nothing
   is touched. The script then re-runs itself from a copy in the user's
   temp folder (process working folder moved there too), so the home can
   be removed; the copy deletes itself at the end.
4. Stop: write `<home>\data\stop.request`, wait up to 10 s, then end only
   processes proven ours: a pid from `core.alive`, `keepalive.json` or
   `overlay.pid` whose recorded creation time is non-zero and matches, or
   a `python`, `pythonw` or `electron` process whose full image path lies
   under `<home>\runtime\`. Real mode asks Windows by those three names
   or by the recorded pids only; no other process is opened. Stricter
   than procs.py: a record without a creation time proves nothing here.
5. Delete by fixed name only, by a direct delete (all replaceable):
   `app`, `runtime`, `cache`, `logs`, `temp`, `build`, `staged`,
   `install.json`, `install.json.bak`, and in `data` the per-run files
   `token`, `token.reuse`, `core.alive`, `keepalive.json`,
   `keepalive.lock`, `overlay.pid`, `stop.request`, `restart.request`,
   `hotreload.json`. No wildcard, no filter. Then `uninstall.ps1`. With
   `-Purge`, `data` goes to the Recycle Bin (FLEET item 9) and the empty
   home is removed; an item the script did not make (any other name) is
   never deleted, so it counts as remaining.
6. Every file probe, listing and delete goes through three helpers that
   refuse a path outside the home. No game folder, Client.txt, Steam
   library, registry value, other install or checkout, or the dev loop
   task is named, listed, stat-ed or opened.
7. Last lines: what stays (`Kept: <home>\data ...` or `Nothing was
   kept.`) and one fixed sentence: AshLight hands out ashlight.filter and
   its .build files as downloads; if the player copied them into the
   game's filter or planner folder they are still there. The script never
   looks, so the output is byte-identical whether or not such files exist.
8. Exit 0 only when nothing but the kept data remains. Else exit 1 with
   the one line `uninstall incomplete: <n> items remain` (n = every
   remaining path outside the kept data, plus run files left in it) and a
   report `AshLight-uninstall-report.txt` in the user's temp folder that
   names them and the errors. No success sentence is printed then.
9. Tests only: the env `AL_UNINSTALL_FAKE` names a JSON file that stands
   in for the process table and the Recycle Bin, so no test lists, stops
   or recycles anything real; the fake recycle folder must lie outside
   the home.

Steps 3 to 5 of the plan (logon task, shortcuts, uninstall key) come with
REL-UNINSTALL-SHELL and `-Checkout` with REL-UNINSTALL-CHECKOUT; checkout
mode never removes `Worktree`, `Scratch`, `ClaudeHistory` or `Install`.

## Checkout mode, added 2026-11-19 (REL-UNINSTALL-CHECKOUT)

Heading record (refute round 1): this section is not headed "Amendment
<date>" because tests/test_audit_batch4.py then requires a Settled line
naming "amend", and a producer may not edit CLAUDE.md. Alternative: edit
the Settled entry (barred for a producer). Reverses if: the integrator adds
"amended 2026-11-19" to the Settled uninstall entry; the heading may then
return to Amendment.

`scripts\uninstall.ps1 -Checkout` treats the folder above `scripts` as the
checkout (refused when it holds `install.json` or lacks `server\al\paths.py`,
`scripts\run.ps1` or `app\package.json`). Guarded roots: the checkout and
the AL sidecar candidates only: `AL_SIDECAR_ROOT` when set, else the fleet
kit default read as text from the checkout's vendored `fleet_lanes.py` plus
`AL`, and the in-checkout fallback `ops\runtime\sidecar`. No folder outside
those is probed, so the kit default is used whether or not it exists (a
missing one just has nothing to remove).

1. Default run: stop (stop.request in `ops\runtime`; ours = a pid-file pid
   with a matching non-zero creation time, or an electron image under the
   checkout's `app\node_modules\electron\dist`), the logon task and the two
   links only when they point into the checkout, then the last lines. No
   file is deleted: everything in a checkout is the player's or rebuildable
   by setup, and run.ps1 clears the stop.request. No uninstall key step: a
   checkout registers none.
2. `-Purge` (typed PURGE, or `-Yes`): delete the sidecar's `Cache`, `Logs`,
   `Build` and, in `Temp`, only top-level items with AshLight's own prefixes
   (`demo-`, `al-brand-`, `state_equiv-`); `ops\runtime` and
   `config\local.json` go to the Recycle Bin. When a sidecar candidate lies
   in `ops\runtime`, its items but that folder are recycled, so a worktree
   kept there is never taken.
3. The dev folders, the installed copy's folder and agent temp folders are
   never named (the script text holds none of their names); the dev loop
   task is never looked at, and the last lines print
   `python tools/loop_task.py remove`.
4. Refused (exit 2, nothing touched): the checkout inside the sidecar's
   Cache, Logs, Build or Temp; a sidecar failing the path-shape guard; in a
   test, the fake without `AL_SIDECAR_ROOT`.

Alternatives: delete the run files in `ops\runtime` by default (rejected:
nothing is gained, and the token is reused by the next start); probe the kit
default folder before use as paths.py does (rejected: a probe outside the
checkout and the AL sidecar). Reverses if: a checkout-run feature writes a
new Temp prefix (add it to the list), or players expect the default run to
remove caches.

## Alternatives

- A question on every uninstall (keep or remove data): rejected, it
  breaks the one-click uninstall (minimal interaction) for the common
  case.
- Remove everything by default: rejected, players lose run history and
  settings they may want after a reinstall.
- Delete everything in the home but `data` by listing it: rejected, a
  wrong home (a mistyped -InstallDir) would lose foreign files; fixed
  names only, the rest is reported.
- Run the uninstall in Python (`boot.py server.al.install uninstall`):
  rejected, it fails when the runtime is broken and must delete itself.
- Look for copied ashlight.filter / .build files and offer to remove
  them: rejected, it reads a game folder (floor audit on F-063).

## Why

One click, and the floor's read list: the uninstaller touches only what
it can prove is AshLight's own, keeps what the player cannot rebuild
unless asked, and never claims success while a file remains.

## Reverses if

Players lose data they wanted kept or keep data they wanted gone, in
practice.
