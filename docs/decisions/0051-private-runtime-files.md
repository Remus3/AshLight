# 0051 - Private runtime files: an explicit ACL on the runtime dir and local config

Date: 2026-11-18. Source: package SEC-ACL-APPLY (wave 4); finding F-011
(docs/plan/02-findings.md); decisions 0003, 0042 (HOT-RELOAD token reuse)
and 0049 (demo mode); AUDIT-EXE-PATH (System32 tools by absolute path).
This record covers part (a), the core. Part (b), the Checks note, is
SEC-ACL-CHECK; parts (c) and (d), setup.ps1 and the sidecar, are
SEC-ACL-SETUP; part (e) rides the installer (F-050).

## Decision

1. Principals. A private file or folder grants exactly three principals
   full control: the player (the user SID of AshLight's own process
   token), SYSTEM (S-1-5-18) and the local admins group (SID
   S-1-5-32-544). Inheritance from the parent is off. Every principal is
   written as a SID, never a name, so the result does not depend on the
   Windows display language.
2. Tool. The ACL is set by System32 icacls run by its absolute path
   (`exepin.system_tool("icacls.exe")`, no window): `/inheritance:r`,
   `/grant:r *<sid>:(OI)(CI)F` for each of the three on a folder (`F` on a
   file), and `/remove *<sid>` for any other SID that held an allow entry.
   The entries of a folder are inheritable, so files and subfolders that
   held only inherited entries keep access, and a file made later (the
   token, a replaced config) takes the same three.
3. Read back. `server/al/acl.py` reads the DACL through the Win32
   security API (GetNamedSecurityInfoW, ConvertSidToStringSidW; ctypes,
   stdlib only), never by parsing icacls text. `principals(path)` lists
   the SIDs; `is_private(path)` is True only when exactly the three are
   granted access, each with full control (on a folder: inheritable, and
   the DACL protected), False otherwise, None when unknown or off Windows.
   `make_private(path)` makes no icacls call when the path is already
   private (idempotent) and returns `is_private` afterwards.
4. Runtime dir. At every core start `python -m server.al` makes the
   runtime dir private before the token is written. The kept token of a
   code reload (decision 0042) is reused only when the runtime dir was
   private before this start's repair and is private after it (None,
   unknown, keeps the old behaviour); otherwise the reuse mark is dropped
   and a new token is made.
5. Config. After every write of config/local.json (`_write_config`, the
   overlay layout save) the real core re-applies the private ACL to that
   file, because a file replaced through a temp file takes the folder's
   ACL. A test core (runtime given) or a demo core (decision 0049) never
   changes an ACL.
6. Scope. Only AshLight-made folders and files are changed: the runtime
   dir and config/local.json here. Never the player's checkout itself,
   never a game folder. `make_private` refuses a path with a game folder
   part (`steamapps`, `Path of Exile 2`) or a link / junction before any
   call. Off Windows every function is a no-op.
7. CLI. `python -m server.al.acl apply <dir>` (for SEC-ACL-SETUP): exit 0
   when the folder is private afterwards (or off Windows), 1 when not or
   refused, 2 on a usage error.

## Choices the package text left open (ruled by the builder)

- Token reuse reads privacy before AND after the repair. Alternatives:
  only after (the repair would hide that the old token sat in a readable
  folder), only before (a failed repair would still reuse). Why: a kept
  token is only a convenience; a token that was readable by anyone else
  must not outlive the start that found it so.
- A file is private without a protected DACL (the token inherits the
  private folder's entries); a folder needs a protected DACL. Why: a
  folder whose parent changes would change with it; a file in a private
  folder is private as long as the folder is.
- Links, junctions and game folder parts are refused. Alternative: follow
  them. Why: a junction could point the change at a folder AshLight did
  not make.
- Real core = no runtime and no config path given (`Core.private_config`).
  Why: tests and demo cores must never change an ACL outside their tmp
  or scratch dirs; tests set the attribute on a tmp core.

## Alternatives

- A per-file owner-only mode (`os.chmod 0o600`): on Windows it only sets
  the read-only flag and changes no ACL.
- Win32 SetNamedSecurityInfoW through ctypes instead of icacls: more code
  to get the inheritance propagation right; icacls does it and is in
  System32 on every supported Windows.
- Names (the player's account name, the localised group names): break on
  a non-English Windows and on renamed accounts.
- Leaving the parent's inheritance on: any user who may write the
  parent folder (a checkout under a shared drive) could read the token.

## Why

The token in ops/runtime authorises every API and SSE call, and
config/local.json holds the poe.ninja contact. Both sat in folders that
inherit the parent's ACL, which on a shared or non-profile drive lets
other local users read them (F-011).

## Reverses if

The ACL breaks a supported install layout, a player shares the folder on
purpose and objects, or the installed per-user home makes the checkout
case moot.
