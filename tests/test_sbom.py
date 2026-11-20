"""REL-SBOM: tools/sbom.py writes a deterministic SBOM from the pins and the
lockfile, each component with a hash, no clock, host name, random source or
network."""
import base64
import json
import os
import platform
import random
import socket
import sys
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sbom  # noqa: E402

COMMIT = "0123456789abcdef0123456789abcdef01234567"
WHEN = 1795000000


def _repo_inputs():
    out = {}
    for rel in sbom.INPUTS + (sbom.INIT_REL,):
        out[rel] = (ROOT / rel).read_bytes()
    return out


@pytest.fixture
def no_net(monkeypatch):
    calls = []

    def refuse(*args, **kwargs):
        calls.append(args)
        raise AssertionError("network call in sbom")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    return calls


def _by_kind(doc):
    npm = [c for c in doc["components"] if c["purl"].startswith("pkg:npm/")]
    electron = [c for c in doc["components"]
                if c["purl"].startswith("pkg:generic/electron@")]
    cpython = [c for c in doc["components"]
               if c["purl"].startswith("pkg:generic/cpython@")]
    calc = [c for c in doc["components"] if c.get("scope") == "optional"]
    return npm, electron, cpython, calc


def test_components_from_the_tracked_pins(no_net):
    inputs = _repo_inputs()
    doc = sbom.build(inputs, COMMIT, WHEN)
    npm, electron, cpython, calc = _by_kind(doc)
    lock = json.loads(inputs[sbom.LOCK_REL])
    expected_npm = len([k for k in lock["packages"] if k])
    assert expected_npm == 13  # today's lockfile (app/package-lock.json)
    assert len(npm) == expected_npm
    assert len(electron) == 1 and len(cpython) == 1 and len(calc) == 3
    assert len(doc["components"]) == expected_npm + 5
    for comp in doc["components"]:
        assert comp["hashes"], comp["bom-ref"]
        for h in comp["hashes"]:
            assert h["alg"] in ("SHA-256", "SHA-512")
            assert len(h["content"]) == (64 if h["alg"] == "SHA-256" else 128)
            int(h["content"], 16)
    pin = json.loads(inputs[sbom.ELECTRON_REL])
    assert electron[0]["version"] == pin["version"]
    assert electron[0]["hashes"][0]["content"] == pin["arch"]["x64"]["exe_sha256"]
    rt = json.loads(inputs[sbom.RUNTIME_REL])["runtimes"]["python"]
    assert cpython[0]["hashes"][0]["content"] == rt["sha256"]
    tc = json.loads(inputs[sbom.TC_REL])
    assert sorted(c["hashes"][0]["content"] for c in calc) == sorted(
        tc[k]["archive_sha256"] for k in ("pob2", "luajit", "toolchain"))
    assert no_net == []


def test_npm_hash_is_the_integrity_digest():
    inputs = _repo_inputs()
    doc = sbom.build(inputs, COMMIT, WHEN)
    lock = json.loads(inputs[sbom.LOCK_REL])
    entry = lock["packages"]["node_modules/@electron/get"]
    comp = next(c for c in doc["components"]
                if c["purl"] == "pkg:npm/%40electron/get@" + entry["version"])
    assert comp["group"] == "@electron" and comp["name"] == "get"
    assert comp["hashes"] == [{"alg": "SHA-512", "content": base64.b64decode(
        entry["integrity"][len("sha512-"):]).hex()}]


def test_timestamp_and_serial_come_from_the_commit():
    doc = sbom.build(_repo_inputs(), COMMIT, WHEN)
    assert doc["metadata"]["timestamp"] == "2026-11-18T11:06:40Z"
    assert doc["serialNumber"] == "urn:uuid:%s" % uuid.uuid5(
        sbom.SBOM_NAMESPACE, COMMIT)
    other = sbom.build(_repo_inputs(), "f" * 40, WHEN + 1)
    assert other["serialNumber"] != doc["serialNumber"]
    assert other["metadata"]["timestamp"] != doc["metadata"]["timestamp"]


def test_two_runs_same_bytes_with_clock_host_random_patched(monkeypatch,
                                                            no_net):
    inputs = _repo_inputs()
    first = sbom.render(sbom.build(inputs, COMMIT, WHEN))
    monkeypatch.setattr(time, "time", lambda: 4102444800.0)
    monkeypatch.setattr(time, "time_ns", lambda: 4102444800 * 10 ** 9)
    monkeypatch.setattr(socket, "gethostname", lambda: "other-host")
    monkeypatch.setattr(platform, "node", lambda: "other-host")
    monkeypatch.setattr(os, "urandom", lambda n: b"\x07" * n)
    monkeypatch.setattr(random, "random", lambda: 0.123)
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=7))
    monkeypatch.setattr(uuid, "uuid1", lambda *a, **k: uuid.UUID(int=9))
    second = sbom.render(sbom.build(inputs, COMMIT, WHEN))
    assert first == second
    first.decode("ascii")
    assert b"\r" not in first and first.endswith(b"\n")
    assert no_net == []


def test_output_is_sorted_cyclonedx_shape():
    data = sbom.render(sbom.build(_repo_inputs(), COMMIT, WHEN))
    doc = json.loads(data)
    assert data == (json.dumps(doc, indent=1, sort_keys=True,
                               ensure_ascii=True) + "\n").encode("ascii")
    assert doc["bomFormat"] == "CycloneDX" and doc["specVersion"] == "1.5"
    refs = [c["bom-ref"] for c in doc["components"]]
    assert refs == sorted(refs) and len(set(refs)) == len(refs)
    assert doc["dependencies"][0]["dependsOn"] == sorted(refs)


def test_sbom_names_binaries_never_carries_them():
    data = sbom.render(sbom.build(_repo_inputs(), COMMIT, WHEN))
    assert len(data) < 64 * 1024


def test_bad_pins_refuse():
    inputs = _repo_inputs()
    bad = dict(inputs)
    tc = json.loads(inputs[sbom.TC_REL])
    tc["luajit"]["archive_sha256"] = "xyz"
    bad[sbom.TC_REL] = json.dumps(tc).encode("ascii")
    with pytest.raises(sbom.SbomError):
        sbom.build(bad, COMMIT, WHEN)
    bad = dict(inputs)
    del bad[sbom.ELECTRON_REL]
    with pytest.raises(sbom.SbomError):
        sbom.build(bad, COMMIT, WHEN)
    with pytest.raises(sbom.SbomError):
        sbom.build(inputs, "HEAD", WHEN)
    lock = json.loads(inputs[sbom.LOCK_REL])
    lock["packages"]["node_modules/ms"]["integrity"] = "sha1-abc"
    bad = dict(inputs)
    bad[sbom.LOCK_REL] = json.dumps(lock).encode("ascii")
    with pytest.raises(sbom.SbomError):
        sbom.build(bad, COMMIT, WHEN)


def test_cli_writes_the_file_at_head(tmp_path, no_net, capsys):
    out = tmp_path / "sbom.json"
    assert sbom.main(["--commit", "HEAD", "--out", str(out)], root=ROOT) == 0
    doc = json.loads(out.read_bytes().decode("ascii"))
    commit, when = sbom.resolve(ROOT, "HEAD")
    assert doc["serialNumber"] == sbom.serial(commit)
    assert doc["metadata"]["timestamp"] == sbom.timestamp(when)
    again = tmp_path / "again.json"
    assert sbom.main(["--commit", commit, "--out", str(again)], root=ROOT) == 0
    assert again.read_bytes() == out.read_bytes()
    assert sbom.main(["--commit", "no-such-rev-xyz", "--out",
                      str(tmp_path / "x.json")], root=ROOT) == 2
    assert not (tmp_path / "x.json").exists()
    assert no_net == []
