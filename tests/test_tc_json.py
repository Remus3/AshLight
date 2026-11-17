"""TC-JSON: character JSON paste import into the TC-CODE build model.

Synthetic fixtures only (tests/tc_fixtures.py); no network; the API tests
use an ephemeral port and a tmp runtime.
"""

import json

import pytest

from server.al.theorycraft import charjson, codec, model, paste
from server.al.theorycraft.store import BuildStore
from tc_fixtures import CHAR_JSON, FULL_XML, JSON_TWIN_XML
from test_tc_code_api import env, req  # noqa: F401  (pytest fixture reuse)


def _text(doc=CHAR_JSON):
    return json.dumps(doc, indent=1)


def test_json_maps_to_same_model_as_its_pob_code():
    from_json = charjson.from_json(_text())
    from_code = model.from_code(codec.encode(JSON_TWIN_XML))
    assert from_json.to_dict() == from_code.to_dict()
    d = from_json.to_dict()
    assert d["class_name"] == "Monk" and d["ascendancy"] == "Invoker" and d["level"] == 87
    assert d["tree"]["nodes"] == [10, 20, 30, 40, 50, 60]
    assert d["gear"]["Gloves"]["name"] == "Doom Grip"
    assert "+10% to Fire Resistance" in d["gear"]["Gloves"]["text"]
    assert d["skills"][0]["gems"][0] == {"name": "Example Strike", "skill_id": None,
                                         "level": 19, "quality": 20, "enabled": True}
    # the generated XML is a real build: lossless code round trip
    assert codec.decode(from_json.to_code()) == from_json.raw_xml


def test_bare_character_object_and_minimal():
    bare = charjson.from_json(_text(CHAR_JSON["character"]))
    assert bare.to_dict() == charjson.from_json(_text()).to_dict()
    b = charjson.from_json('{"class": "Warrior", "level": "12"}')
    assert b.class_name == "Warrior" and b.ascendancy is None and b.level == 12
    assert b.gear == {} and b.skills == ()
    unknown_cls = charjson.from_json('{"class": "Newclassname", "level": 3}')
    assert unknown_cls.class_name == "Newclassname" and unknown_cls.ascendancy is None


def test_wrong_types_are_ignored_not_fatal():
    doc = {"class": 5, "level": True, "passives": [1, 2], "equipment": {"x": 1},
           "skills": "nope", "jewels": [None, 3]}
    b = charjson.from_json(json.dumps(doc))
    assert b.class_name is None and b.level is None and b.gear == {}


@pytest.mark.parametrize("text", ["{", "{not json}", '{"a": 1}', '{"character": "x"}',
                                  "{" * 5000, '{"a": ' + "[" * 100000 + "]" * 100000 + "}"])
def test_bad_json_raises_build_error(text):
    with pytest.raises(model.BuildError):
        paste.parse(text)


def test_detect_formats():
    assert paste.detect(_text()) == "json"
    assert paste.detect("  \n{\"class\": 1}") == "json"
    assert paste.detect(codec.encode(FULL_XML)) == "code"
    assert paste.detect("https://pobb.in/AbCd") == "url"
    assert paste.detect("hello!") == "unknown"
    assert paste.parse(codec.encode(FULL_XML)).class_name == "Monk"
    with pytest.raises(codec.ShareUrlError):
        paste.parse("https://pobb.in/AbCd")


def test_store_persists_json_as_code(tmp_path):
    path = tmp_path / "build" / "last-code.txt"
    store = BuildStore(path)
    store.load_code(_text())
    saved = path.read_text(encoding="ascii").strip()
    assert paste.detect(saved) == "code"
    again = BuildStore(path)
    assert again.build.to_dict() == store.build.to_dict()


@pytest.mark.server
def test_api_auto_detects_json_paste(env):  # noqa: F811
    srv = env()
    status, doc = req(srv, "POST", "/api/build-code", {"code": _text()})
    assert status == 200, doc
    assert doc["build"]["ascendancy"] == "Invoker"
    assert doc["build"]["gear"]["Weapon 1"]["rarity"] == "UNIQUE"
    # the character object may also be posted as-is
    status, doc = req(srv, "POST", "/api/build-code", CHAR_JSON)
    assert status == 200 and doc["build"]["level"] == 87
    # a bad JSON paste is a 400 and keeps the good build
    assert req(srv, "POST", "/api/build-code", {"code": "{broken"})[0] == 400
    assert req(srv, "POST", "/api/build-code", {"code": '{"a": 1}'})[0] == 400
    status, doc = req(srv, "GET", "/api/build")
    assert doc["build"]["class_name"] == "Monk"
    # token check untouched
    assert req(srv, "POST", "/api/build-code", {"code": _text()}, token=None)[0] == 401
