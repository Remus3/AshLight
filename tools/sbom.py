#!/usr/bin/env python3
"""SBOM tool (REL-SBOM, F-148, DEP-08): a deterministic bill of materials.

    sbom.py --commit REV [--out FILE] [--root DIR]

It names everything a release of AshLight relies on, each with a hash, read
from tracked files at the given commit (git blobs, never the working tree):

    app/package-lock.json      every npm package (sha512 from "integrity")
    config/electron_pin.json   the Electron binary (electron.exe sha256 for
                               x64; both arch zips as distribution refs)
    config/runtime_pins.json   the embeddable CPython zip (sha256)
    config/tc_pins.json        the optional calc pins: PoB-PoE2, LuaJIT and
                               the WinLibs toolchain archive (sha256)

The output is CycloneDX-shaped JSON (specVersion 1.5): ASCII, sorted keys,
LF. metadata.timestamp is the commit time (UTC) and serialNumber is
urn:uuid:<uuid5 of the full commit id in the AshLight SBOM namespace>, so
two runs over one commit give the same bytes. Nothing reads the clock, the
host name or a random source; no network; nothing is fetched or copied: the
SBOM names Electron, CPython, PoB and LuaJIT, it does not carry them.
Stdlib only. Without --out the JSON goes to stdout.
"""
import argparse
import base64
import datetime
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent

LOCK_REL = "app/package-lock.json"
ELECTRON_REL = "config/electron_pin.json"
RUNTIME_REL = "config/runtime_pins.json"
TC_REL = "config/tc_pins.json"
INIT_REL = "server/al/__init__.py"
INPUTS = (LOCK_REL, ELECTRON_REL, RUNTIME_REL, TC_REL)

SPEC_VERSION = "1.5"
# Fixed namespace: serialNumber = uuid5(SBOM_NAMESPACE, <full commit id>).
SBOM_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "ashlight:sbom")
ELECTRON_PRIMARY_ARCH = "x64"
CALC_PINS = ("pob2", "luajit", "toolchain")

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SPDX = re.compile(r"^[A-Za-z0-9.+-]+$")
_INIT_LINE = re.compile(r'^VERSION = "([^"]*)"$', re.M)


class SbomError(Exception):
    """A refusal; nothing has been written."""


# --- git -------------------------------------------------------------------

def _git(root, *args):
    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          check=False)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise SbomError("git %s failed: %s" % (args[0], err[-1] if err else
                                               "exit %d" % proc.returncode))
    return proc.stdout


def resolve(root, rev):
    """(full commit id, commit time as int seconds) for rev."""
    commit = _git(root, "rev-parse", "-q", "--verify",
                  "%s^{commit}" % rev).decode("ascii", "replace").strip()
    if not _HEX40.match(commit):
        raise SbomError("no commit for %r" % rev)
    when = _git(root, "show", "-s", "--format=%ct", commit)
    return commit, int(when.decode("ascii").strip())


def read_inputs(root, commit):
    """{rel: bytes} of the input files (and the VERSION file) at commit."""
    out = {}
    for rel in INPUTS + (INIT_REL,):
        out[rel] = _git(root, "cat-file", "blob", "%s:%s" % (commit, rel))
    return out


# --- components ------------------------------------------------------------

def _json(data, rel):
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SbomError("%s: not JSON (%s)" % (rel, exc))


def _sha256(value, what):
    if not isinstance(value, str) or not _HEX64.match(value):
        raise SbomError("%s: missing or malformed sha256" % what)
    return {"alg": "SHA-256", "content": value}


def _licenses(text):
    if not text:
        return None
    if _SPDX.match(text):
        return [{"license": {"id": text}}]
    return [{"license": {"name": text}}]


def _component(ctype, name, version, purl, hashes, licence=None, refs=None,
               props=None, scope=None, group=None):
    comp = {"bom-ref": purl, "type": ctype, "name": name, "version": version,
            "purl": purl, "hashes": hashes}
    if group:
        comp["group"] = group
    lic = _licenses(licence)
    if lic:
        comp["licenses"] = lic
    if refs:
        comp["externalReferences"] = refs
    if props:
        comp["properties"] = sorted(
            ({"name": k, "value": str(v)} for k, v in props.items()),
            key=lambda p: p["name"])
    if scope:
        comp["scope"] = scope
    return comp


def npm_components(data):
    lock = _json(data, LOCK_REL)
    packages = lock.get("packages")
    if not isinstance(packages, dict):
        raise SbomError("%s: no packages map (lockfile v2 or v3 needed)"
                        % LOCK_REL)
    out = []
    for key in sorted(packages):
        if not key:
            continue  # the root project itself
        entry = packages[key]
        name = key.rsplit("node_modules/", 1)[-1]
        version = entry.get("version")
        integrity = entry.get("integrity", "")
        if not version or not integrity.startswith("sha512-"):
            raise SbomError("%s: %s lacks a version or sha512 integrity"
                            % (LOCK_REL, key))
        try:
            digest = base64.b64decode(integrity[len("sha512-"):],
                                      validate=True).hex()
        except ValueError:
            raise SbomError("%s: %s integrity is not base64" % (LOCK_REL, key))
        if len(digest) != 128:
            raise SbomError("%s: %s integrity is not sha512" % (LOCK_REL, key))
        group, _, short = name.rpartition("/")
        purl = "pkg:npm/%s@%s" % (
            (quote(group, safe="") + "/" + short) if group else short, version)
        refs = None
        if entry.get("resolved"):
            refs = [{"type": "distribution", "url": entry["resolved"]}]
        props = {"npm:path": key}
        if entry.get("dev"):
            props["npm:dev"] = "true"
        out.append(_component(
            "library", short, version, purl,
            [{"alg": "SHA-512", "content": digest}],
            licence=entry.get("license"), refs=refs, props=props,
            group=group or None))
    return out


def electron_component(data, licence=None):
    pin = _json(data, ELECTRON_REL)
    version = pin.get("version")
    arches = pin.get("arch")
    if not version or not isinstance(arches, dict) \
            or ELECTRON_PRIMARY_ARCH not in arches:
        raise SbomError("%s: missing version or %s arch"
                        % (ELECTRON_REL, ELECTRON_PRIMARY_ARCH))
    main = arches[ELECTRON_PRIMARY_ARCH]
    refs = []
    props = {"electron:primary_arch": ELECTRON_PRIMARY_ARCH}
    for arch in sorted(arches):
        row = arches[arch]
        refs.append({"type": "distribution", "url": row.get("zip_url", ""),
                     "comment": "%s zip" % arch,
                     "hashes": [_sha256(row.get("zip_sha256"),
                                        "%s %s zip" % (ELECTRON_REL, arch))]})
        props["electron:%s:exe_sha256" % arch] = _sha256(
            row.get("exe_sha256"), "%s %s exe" % (ELECTRON_REL, arch))["content"]
        props["electron:%s:exe_size" % arch] = row.get("exe_size", "")
    purl = "pkg:generic/electron@%s?arch=%s" % (version, ELECTRON_PRIMARY_ARCH)
    return _component(
        "application", "electron", version, purl,
        [_sha256(main.get("exe_sha256"), "%s exe" % ELECTRON_REL)],
        licence=licence, refs=refs, props=props)


def cpython_component(data):
    pins = _json(data, RUNTIME_REL)
    try:
        py = pins["runtimes"]["python"]
    except (KeyError, TypeError):
        raise SbomError("%s: no runtimes.python" % RUNTIME_REL)
    version = py.get("version")
    if not version or not py.get("url"):
        raise SbomError("%s: python lacks version or url" % RUNTIME_REL)
    purl = "pkg:generic/cpython@%s?arch=%s&file_name=%s" % (
        version, py.get("arch", ""), quote(py.get("file", ""), safe=""))
    return _component(
        "application", "cpython", version, purl,
        [_sha256(py.get("sha256"), "%s python" % RUNTIME_REL)],
        licence=py.get("licence"),
        refs=[{"type": "distribution", "url": py["url"]}],
        props={"runtime:size": py.get("size", ""), "runtime:file":
               py.get("file", "")})


def calc_components(data):
    pins = _json(data, TC_REL)
    out = []
    for key in CALC_PINS:
        pin = pins.get(key)
        if not isinstance(pin, dict) or not pin.get("repo") \
                or not pin.get("archive_url"):
            raise SbomError("%s: %s pin missing" % (TC_REL, key))
        version = pin.get("tag") or pin.get("version") or pin.get("commit")
        ref = pin.get("commit") or pin.get("tag")
        if not version or not ref:
            raise SbomError("%s: %s lacks a version" % (TC_REL, key))
        owner, _, repo = pin["repo"].partition("/")
        purl = "pkg:github/%s/%s@%s" % (owner.lower(), repo.lower(), ref)
        props = {"calc:pin": key, "calc:archive_size":
                 pin.get("archive_size", "")}
        if pin.get("commit"):
            props["calc:commit"] = pin["commit"]
        out.append(_component(
            "library" if key != "toolchain" else "application",
            pin.get("name", key), version, purl,
            [_sha256(pin.get("archive_sha256"), "%s %s" % (TC_REL, key))],
            licence=pin.get("license"),
            refs=[{"type": "distribution", "url": pin["archive_url"]}],
            props=props, scope="optional"))
    return out


def _electron_licence(runtime_data):
    try:
        return _json(runtime_data, RUNTIME_REL)["runtimes"]["electron"]["licence"]
    except (KeyError, TypeError):
        return None


def timestamp(commit_time):
    stamp = datetime.datetime.fromtimestamp(int(commit_time),
                                            tz=datetime.timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def serial(commit):
    return "urn:uuid:%s" % uuid.uuid5(SBOM_NAMESPACE, commit)


def build(inputs, commit, commit_time):
    """The SBOM dict from {rel: bytes}, the full commit id and its time."""
    if not _HEX40.match(commit or ""):
        raise SbomError("commit must be a full 40-hex id")
    for rel in INPUTS:
        if rel not in inputs:
            raise SbomError("%s is missing" % rel)
    version = "0.0.0"
    found = _INIT_LINE.findall(inputs.get(INIT_REL, b"").decode(
        "utf-8", "replace"))
    if len(found) == 1:
        version = found[0]
    components = (npm_components(inputs[LOCK_REL])
                  + [electron_component(inputs[ELECTRON_REL],
                                        _electron_licence(inputs[RUNTIME_REL])),
                     cpython_component(inputs[RUNTIME_REL])]
                  + calc_components(inputs[TC_REL]))
    refs = [c["bom-ref"] for c in components]
    if len(set(refs)) != len(refs):
        raise SbomError("duplicate component bom-ref")
    components.sort(key=lambda c: c["bom-ref"])
    root_ref = "pkg:generic/ashlight@%s" % version
    return {
        "bomFormat": "CycloneDX",
        "specVersion": SPEC_VERSION,
        "serialNumber": serial(commit),
        "version": 1,
        "metadata": {
            "timestamp": timestamp(commit_time),
            "tools": {"components": [{"type": "application",
                                      "name": "AshLight tools/sbom.py"}]},
            "component": {"bom-ref": root_ref, "type": "application",
                          "name": "AshLight", "version": version,
                          "purl": root_ref, "licenses": _licenses("Apache-2.0"),
                          "properties": [{"name": "git:commit",
                                          "value": commit}]},
        },
        "components": components,
        "dependencies": [{"ref": root_ref, "dependsOn": sorted(refs)}],
    }


def render(sbom):
    return (json.dumps(sbom, indent=1, sort_keys=True, ensure_ascii=True)
            + "\n").encode("ascii")


def _write_atomic(path, data):
    path = Path(path)
    if path.parent and not path.parent.is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def main(argv=None, root=None):
    ap = argparse.ArgumentParser(
        prog="sbom.py",
        description="Write a deterministic CycloneDX-shaped SBOM of a commit.")
    ap.add_argument("--commit", default="HEAD", help="git revision (HEAD)")
    ap.add_argument("--out", help="output file (default: stdout)")
    ap.add_argument("--root", help="repository root (default: this checkout)")
    args = ap.parse_args(argv)
    root = Path(args.root) if args.root else (root or ROOT)
    try:
        commit, when = resolve(root, args.commit)
        data = render(build(read_inputs(root, commit), commit, when))
    except SbomError as exc:
        sys.stderr.write("sbom: %s\n" % exc)
        return 2
    if args.out:
        _write_atomic(args.out, data)
        sys.stdout.write("sbom: %s components -> %s\n"
                         % (len(json.loads(data)["components"]), args.out))
    else:
        sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
