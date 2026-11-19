"""DATA-LEAGUE-IDENTITY (finding F-031): poe.ninja's leagues list parsed
whole as id plus name (server/al/leagues.py). Pure functions; synthetic
bodies in the shape of research 0013 (invented league names)."""

import json

import pytest

from server.al import leagues, ninja

LIST = [{"id": "dawn", "name": "Dawn of Wraeclast"},
        {"id": "Standard", "name": "Standard"},
        {"id": "hc-dawn", "name": "HC Dawn of Wraeclast"}]


def test_parse_list_keeps_unique_ids_with_names():
    body = json.dumps([
        {"id": " dawn ", "name": "Dawn of Wraeclast"},
        {"id": "dawn", "name": "A later duplicate"},  # first id wins
        {"name": "Name Only"},                         # name stands in for the id
        {"id": "id-only"},                             # id stands in for the name
        {"id": "", "name": ""}, {"id": 7}, "junk", None,
        {"id": "x" * 200, "name": "Long"},
        {"id": "Standard", "name": "Standard"}]).encode()
    got = leagues.parse_list(body)
    assert got == [{"id": "dawn", "name": "Dawn of Wraeclast"},
                   {"id": "Name Only", "name": "Name Only"},
                   {"id": "id-only", "name": "id-only"},
                   {"id": "x" * 80, "name": "Long"},
                   {"id": "Standard", "name": "Standard"}]
    ids = [e["id"] for e in got]
    assert len(ids) == len(set(ids))
    # the wrapped form and the old one-id reader agree on the first league
    wrapped = json.dumps({"leagues": LIST}).encode()
    assert leagues.parse_list(wrapped) == LIST
    assert ninja.parse_leagues(body) == "dawn"


def test_parse_list_is_bounded():
    body = json.dumps([{"id": f"L{i}", "name": f"L {i}"} for i in range(500)])
    assert len(leagues.parse_list(body)) == leagues.MAX_LEAGUES


@pytest.mark.parametrize("body", [b"[]", b"{}", b'{"leagues": 3}', b'[{"id": 1}]',
                                  b'["a", "b"]', b"null"])
def test_parse_list_without_a_league_raises_value_error(body):
    with pytest.raises(ValueError):
        leagues.parse_list(body)
    with pytest.raises(ValueError):
        ninja.parse_leagues(body)


def test_name_and_id_lookups_resolve_either_form():
    assert leagues.name_of(LIST, "dawn") == "Dawn of Wraeclast"
    assert leagues.name_of(LIST, "Dawn of Wraeclast") is None  # ids only
    assert leagues.id_of(LIST, "dawn") == "dawn"
    assert leagues.id_of(LIST, "Dawn of Wraeclast") == "dawn"
    assert leagues.id_of(LIST, " hc dawn of wraeclast ") == "hc-dawn"
    assert leagues.id_of(LIST, "Unknown") is None
    assert leagues.id_of(LIST, "") is None and leagues.id_of(LIST, None) is None
    # a hand-edited cache never raises
    for bad in (None, 3, "dawn", [None, {"id": 1, "name": "x"}, {"id": "a"}]):
        assert leagues.id_of(bad, "dawn") is None
        assert leagues.name_of(bad, "dawn") is None
        assert list(leagues.entries(bad)) == []
