"""Private runtime files (SEC-ACL-APPLY, finding F-011, decision 0051).

The core gives its runtime dir and config/local.json an explicit ACL:
the player (the user SID of AshLight's own process token), SYSTEM
(S-1-5-18) and the local admins group (SID S-1-5-32-544), each with full
control, inheritance from the parent turned off. The change runs through
System32 icacls by its absolute path (exepin.system_tool) with every
principal given as a SID (`*S-1-...`), so it is locale independent.
On a folder the three entries are inheritable ((OI)(CI)): files and
subfolders that held only inherited entries keep access, and a file made
later (the token, a replaced config) takes the same three.

- make_private(path): apply the ACL; no icacls call when the path is
  already private (idempotent). Returns is_private(path) afterwards.
- principals(path): the SIDs the ACL names, read back through the Win32
  security API (no text parsing). None when unknown or not Windows.
- is_private(path): True / False, or None (unknown or not Windows).

Only AshLight-made folders and files are passed here, never the player's
checkout and never a game folder: a path with a game folder part or a
link / junction is refused before any call. Off Windows every function
is a no-op that returns None.

SEC-ACL-CHECK: audit(runtime, repo, sidecar) only READS the three ACLs
(Win32 API, no icacls) and names the folders anyone else can write to
('runtime', 'app', 'sidecar'); the core runs it once per start on a
background thread and the Checks card shows the row. The player's own
checkout changes only when the player runs the CLI on it.

CLI (SEC-ACL-SETUP): python -m server.al.acl apply <dir>
Stdlib only.
"""

import os
import subprocess
import sys
from pathlib import Path

from . import exepin

SYSTEM_SID = "S-1-5-18"
ADMINS_SID = "S-1-5-32-544"  # the local admins group (well-known SID)
FULL_ACCESS = 0x1F01FF        # FILE_ALL_ACCESS, icacls "F"
INHERIT_FLAGS = 0x1 | 0x2     # OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
ICACLS_TIMEOUT_S = 30.0

_SE_FILE_OBJECT = 1
_OWNER_SECURITY_INFORMATION = 0x1
_DACL_SECURITY_INFORMATION = 0x4
_SE_DACL_PROTECTED = 0x1000
_TOKEN_QUERY = 0x0008
_TOKEN_USER = 1
_REPARSE_POINT = 0x400
# ACE types whose SID sits right after the header and the access mask:
# allowed, denied, allowed callback, denied callback
_ALLOW_TYPES = (0x0, 0x9)
_SIMPLE_TYPES = (0x0, 0x1, 0x9, 0xA)
# denied, denied object, denied callback, denied callback object
_DENY_TYPES = (0x1, 0x6, 0xA, 0xC)

# SEC-ACL-CHECK: any of these rights lets a principal change what is in a
# folder or who may: write / add file, append / add subfolder, write EA,
# delete child, write attributes, DELETE, WRITE_DAC, WRITE_OWNER,
# GENERIC_ALL, GENERIC_WRITE (inherit-only entries carry generic bits)
WRITE_MASK = (0x2 | 0x4 | 0x10 | 0x40 | 0x100 | 0x10000 | 0x40000 | 0x80000
              | 0x10000000 | 0x40000000)
# CREATOR OWNER stands for whoever makes a child: that principal already
# needed write access here, so it adds no writer of its own
CREATOR_OWNER_SID = "S-1-3-0"
AUDIT_NAMES = ("runtime", "app", "sidecar")

_PLAYER_SID = None
_API = None


def _is_windows():
    return os.name == "nt"


def _api():
    """The ctypes handles this module uses (Windows only), made once."""
    global _API
    if _API is None:
        _API = _load_api()
    return _API


def _load_api():
    import ctypes
    from ctypes import wintypes
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.HANDLE)]
    adv.OpenProcessToken.restype = wintypes.BOOL
    adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    adv.GetTokenInformation.restype = wintypes.BOOL
    adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(wintypes.LPWSTR)]
    adv.ConvertSidToStringSidW.restype = wintypes.BOOL
    adv.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p)]
    adv.GetNamedSecurityInfoW.restype = wintypes.DWORD
    adv.GetSecurityDescriptorControl.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD)]
    adv.GetSecurityDescriptorControl.restype = wintypes.BOOL
    adv.GetAce.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    adv.GetAce.restype = wintypes.BOOL
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.LocalFree.argtypes = [ctypes.c_void_p]
    k32.LocalFree.restype = ctypes.c_void_p
    return ctypes, wintypes, adv, k32


def _sid_text(api, psid):
    ctypes, wintypes, adv, k32 = api
    out = wintypes.LPWSTR()
    if not adv.ConvertSidToStringSidW(psid, ctypes.byref(out)):
        return None
    try:
        return out.value
    finally:
        k32.LocalFree(ctypes.cast(out, ctypes.c_void_p))


def player_sid():
    """The user SID of this process's token (the player), e.g.
    S-1-5-21-...; None off Windows or on an API failure."""
    global _PLAYER_SID
    if not _is_windows():
        return None
    if _PLAYER_SID is not None:
        return _PLAYER_SID
    try:
        api = _api()
        ctypes, wintypes, adv, k32 = api
        tok = wintypes.HANDLE()
        if not adv.OpenProcessToken(k32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(tok)):
            return None
        try:
            need = wintypes.DWORD(0)
            adv.GetTokenInformation(tok, _TOKEN_USER, None, 0, ctypes.byref(need))
            if not need.value:
                return None
            buf = ctypes.create_string_buffer(need.value)
            if not adv.GetTokenInformation(tok, _TOKEN_USER, buf, need, ctypes.byref(need)):
                return None
            # TOKEN_USER starts with SID_AND_ATTRIBUTES: the PSID comes first
            psid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
            sid = _sid_text(api, psid)
        finally:
            k32.CloseHandle(tok)
    except (OSError, AttributeError, ValueError):
        return None
    if sid and sid.startswith("S-1-"):
        _PLAYER_SID = sid
    return _PLAYER_SID


def private_sids():
    """The three principals of a private ACL, or None when the player's SID
    cannot be read (then nothing is changed)."""
    me = player_sid()
    if not me:
        return None
    return (me, SYSTEM_SID, ADMINS_SID)


def read_acl(path):
    """The DACL of path as (protected, entries), entries a list of
    (ace_type, ace_flags, mask, sid); sid is None for an ACE type this
    module does not decode. None off Windows or when it cannot be read;
    (protected, None) for a NULL DACL (everyone has access)."""
    if not _is_windows():
        return None
    try:
        api = _api()
        ctypes, wintypes, adv, k32 = api
        dacl = ctypes.c_void_p()
        sd = ctypes.c_void_p()
        rc = adv.GetNamedSecurityInfoW(str(path), _SE_FILE_OBJECT, _DACL_SECURITY_INFORMATION,
                                       None, None, ctypes.byref(dacl), None, ctypes.byref(sd))
        if rc != 0:
            return None
        try:
            control = wintypes.WORD()
            rev = wintypes.DWORD()
            if not adv.GetSecurityDescriptorControl(sd, ctypes.byref(control), ctypes.byref(rev)):
                return None
            protected = bool(control.value & _SE_DACL_PROTECTED)
            if not dacl.value:
                return protected, None
            # ACL header: BYTE rev, BYTE sbz1, WORD size, WORD count, WORD sbz2
            count = ctypes.cast(dacl, ctypes.POINTER(ctypes.c_ushort))[2]
            entries = []
            for i in range(count):
                ace = ctypes.c_void_p()
                if not adv.GetAce(dacl, i, ctypes.byref(ace)):
                    return None
                raw = ctypes.cast(ace, ctypes.POINTER(ctypes.c_ubyte))
                ace_type, ace_flags = raw[0], raw[1]
                if ace_type in _SIMPLE_TYPES:
                    mask = ctypes.cast(ace.value + 4, ctypes.POINTER(ctypes.c_uint32))[0]
                    sid = _sid_text(api, ace.value + 8)
                    if sid is None:
                        return None
                else:
                    mask, sid = 0, None
                entries.append((ace_type, ace_flags, mask, sid))
            return protected, entries
        finally:
            k32.LocalFree(sd)
    except (OSError, AttributeError, ValueError):
        return None


def read_owner(path):
    """The owner SID of path, or None off Windows or when unknown."""
    if not _is_windows():
        return None
    try:
        api = _api()
        ctypes, wintypes, adv, k32 = api
        owner = ctypes.c_void_p()
        sd = ctypes.c_void_p()
        rc = adv.GetNamedSecurityInfoW(str(path), _SE_FILE_OBJECT, _OWNER_SECURITY_INFORMATION,
                                       ctypes.byref(owner), None, None, None, ctypes.byref(sd))
        if rc != 0:
            return None
        try:
            return _sid_text(api, owner.value) if owner.value else None
        finally:
            k32.LocalFree(sd)
    except (OSError, AttributeError, ValueError):
        return None


def others_can_write(path):
    """SEC-ACL-CHECK: True when anyone besides the player, SYSTEM and the
    local admins group can write to path (an allow entry with a write
    right, inherit-only ones too since children take them; an allow entry
    of a type not decoded here; a NULL DACL; another owner, who may rewrite
    the ACL); False when only the three can; None off Windows or when
    unknown. Deny entries are ignored (the stricter reading). Read only."""
    sids = private_sids()
    if sids is None:
        return None
    acl = read_acl(path)
    if acl is None:
        return None
    _, entries = acl
    if entries is None:
        return True
    owner = read_owner(path)
    if owner is not None and owner not in sids:
        return True
    for ace_type, _, mask, sid in entries:
        if ace_type in _DENY_TYPES:
            continue
        if sid is None:
            return True
        if sid in sids or sid == CREATOR_OWNER_SID:
            continue
        if mask & WRITE_MASK:
            return True
    return False


def audit(runtime, repo, sidecar, check=None):
    """SEC-ACL-CHECK: the names of the folders anyone else can write to,
    in AUDIT_NAMES order ('runtime' the runtime dir, 'app' the AshLight
    folder, 'sidecar' the sidecar root). A None or missing folder and an
    unknown answer are left out. Reads only; never changes an ACL.
    `check` (tests) replaces others_can_write."""
    check = check or others_can_write
    out = []
    for name, path in zip(AUDIT_NAMES, (runtime, repo, sidecar)):
        if path is None:
            continue
        try:
            if not os.path.isdir(path):
                continue
            if check(path) is True:
                out.append(name)
        except (OSError, ValueError):
            continue
    return out


def principals(path):
    """Sorted SIDs named by the ACL of path ("?" for an entry of a type not
    decoded here, "*" for a NULL DACL); None off Windows or when unknown."""
    acl = read_acl(path)
    if acl is None:
        return None
    _, entries = acl
    if entries is None:
        return ["*"]
    return sorted({sid or "?" for _, _, _, sid in entries})


def is_private(path):
    """True when exactly the three principals are granted access, each with
    full control (on a folder: inheritable, and inheritance from the parent
    is off); False when anyone else is granted access or one of the three
    is missing; None off Windows or when unknown."""
    sids = private_sids()
    if sids is None:
        return None
    acl = read_acl(path)
    if acl is None:
        return None
    protected, entries = acl
    if entries is None:
        return False
    is_dir = os.path.isdir(path)
    if is_dir and not protected:
        return False
    granted = {}
    for ace_type, ace_flags, mask, sid in entries:
        if sid is None:
            return False
        if ace_type in _ALLOW_TYPES:
            granted.setdefault(sid, []).append((ace_flags, mask))
    if set(granted) != set(sids):
        return False
    for sid in sids:
        ok = any((mask & FULL_ACCESS) == FULL_ACCESS
                 and (not is_dir or (flags & INHERIT_FLAGS) == INHERIT_FLAGS)
                 for flags, mask in granted[sid])
        if not ok:
            return False
    return True


def refused(path):
    """Why path must not be changed here, or None. A game folder part in
    the text or a link / junction (its target could be anywhere)."""
    from .demo import game_path_part  # lazy: demo imports the core
    part = game_path_part(path)
    if part is not None:
        return f"a game folder part ({part!r})"
    try:
        st = os.lstat(path)
    except OSError:
        return "missing"
    if getattr(st, "st_file_attributes", 0) & _REPARSE_POINT or os.path.islink(path):
        return "a link or junction"
    return None


def icacls_argv(path, sids, is_dir, extra=()):
    """The icacls command: inheritance removed, the three SIDs granted full
    control (inheritable on a folder), any other granted SID removed."""
    perm = "(OI)(CI)F" if is_dir else "F"
    argv = [str(exepin.system_tool("icacls.exe")), str(path), "/inheritance:r",
            "/grant:r"] + [f"*{sid}:{perm}" for sid in sids]
    if extra:
        argv += ["/remove"] + [f"*{sid}" for sid in extra]
    return argv + ["/q"]


def _run(argv):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(argv, capture_output=True, timeout=ICACLS_TIMEOUT_S,
                           stdin=subprocess.DEVNULL, creationflags=flags)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def make_private(path, run=None):
    """Give path the private ACL; no icacls call when it already is
    private. Returns is_private(path) afterwards (None off Windows, when
    the player's SID cannot be read or the path is refused)."""
    if not _is_windows():
        return None
    path = Path(os.path.abspath(path))
    if refused(path) is not None:
        return None
    state = is_private(path)
    if state is True:
        return True
    sids = private_sids()
    if sids is None:
        return None
    run = run or _run
    acl = read_acl(path)
    extra = ()
    if acl is not None and acl[1] is not None:
        extra = sorted({sid for t, _, _, sid in acl[1]
                        if sid and t in _ALLOW_TYPES and sid not in sids})
    run(icacls_argv(path, sids, path.is_dir(), extra))
    return is_private(path)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] != "apply":
        print("usage: python -m server.al.acl apply <dir>", file=sys.stderr)
        return 2
    target = argv[1]
    if not _is_windows():
        print("acl: not Windows, nothing to do")
        return 0
    why = refused(target)
    if why is not None:
        print(f"acl: refused, {why}: {target}", file=sys.stderr)
        return 1
    state = make_private(target)
    print(f"acl: {'private' if state else 'NOT private'}: {target}")
    return 0 if state else 1


if __name__ == "__main__":
    sys.exit(main())
