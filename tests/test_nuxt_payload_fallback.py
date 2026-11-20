"""Offline tests for the Nuxt __NUXT_DATA__ payload fallback-fill.

Covers parse_nuxt_roster_payload() and match_nuxt_fields() (wbb/parsing.py)
and their wiring into JavaScriptScraper._process_js_result() — no network,
no browser. Behavior contract: payload values fill ONLY fields the JS
extraction left empty; existing values are never overwritten.
"""

import json

from wbb.parsing import (match_nuxt_fields, norm_person_name,
                         parse_nuxt_roster_payload, slug_from_player_url)
from wbb.scrapers import JavaScriptScraper


def _payload_html(entries) -> str:
    body = json.dumps(entries)
    return ("<html><head>"
            f"<script id=\"__NUXT_DATA__\" type=\"application/json\">{body}</script>"
            "</head><body></body></html>")


# devalue layout: strings live in the flat array; object fields point at them
# by index. Player 1 (camelCase, full fields) and player 2 (city+state split,
# hometown = -1 null sentinel).
DEVALUE = [
    {"config": True},                       # 0
    "Khamil", "Pierre",                     # 1, 2
    "Brooklyn, NY",                         # 3  hometown
    "Bishop Kearney",                       # 4  high school
    "USC",                                  # 5  previous school
    "khamil-pierre",                        # 6  slug
    "Ana", "Lopez",                         # 7, 8
    "San Antonio", "TX",                    # 9, 10 city/state
    "ana-lopez",                            # 11 slug
    {"firstName": 1, "lastName": 2, "hometown": 3, "highSchool": 4,
     "previousSchool": 5, "slug": 6, "rosterPlayerId": 123},        # 12 player 1
    {"firstName": 7, "lastName": 8, "hometown": -1, "city": 9,
     "state": 10, "slug": 11},                                      # 13 player 2
]

TEAM = {"ncaa_id": 736, "team": "Vanderbilt", "url": "https://vanderbilt.com"}


# --- parse_nuxt_roster_payload ------------------------------------------------

def test_parses_devalue_indices_camelcase():
    fields = parse_nuxt_roster_payload(_payload_html(DEVALUE))
    expected = {"hometown": "Brooklyn, NY", "high_school": "Bishop Kearney",
                "previous_school": "USC"}
    assert fields.get("khamil pierre") == expected   # name key
    assert fields.get("khamil-pierre") == expected   # slug key


def test_city_state_fallback_and_sentinel():
    fields = parse_nuxt_roster_payload(_payload_html(DEVALUE))
    assert fields.get("ana lopez") == {"hometown": "San Antonio, TX"}
    assert fields.get("ana-lopez") == fields.get("ana lopez")


def test_snake_case_layout():
    snake = [
        "Jordan", "Lee",            # 0, 1
        "Chicago, IL",              # 2
        "Whitney Young",            # 3
        "jordan-lee",               # 4
        {"first_name": 0, "last_name": 1, "hometown": 2,
         "high_school": 3, "slug": 4},                      # 5
    ]
    fields = parse_nuxt_roster_payload(_payload_html(snake))
    assert fields["jordan lee"] == {"hometown": "Chicago, IL",
                                    "high_school": "Whitney Young"}


def test_literal_string_values_also_resolve():
    direct = [{"firstName": "Jane", "lastName": "Doe",
               "hometown": "Ada, OH", "highSchool": "Ada HS",
               "previousSchool": -1, "slug": "jane-doe"}]
    fields = parse_nuxt_roster_payload(_payload_html(direct))
    assert fields["jane doe"] == {"hometown": "Ada, OH", "high_school": "Ada HS"}


def test_empty_and_broken_payloads_return_empty_map():
    assert parse_nuxt_roster_payload("") == {}
    assert parse_nuxt_roster_payload("<html><body>No payload</body></html>") == {}
    assert parse_nuxt_roster_payload(
        '<script id="__NUXT_DATA__">not json {</script>') == {}
    # data-src variant: script tag present, JSON served externally
    assert parse_nuxt_roster_payload(
        '<script id="__NUXT_DATA__" type="application/json" '
        'data-src="/_payload.json?e6c8e2"></script>') == {}


def test_diacritics_normalize_for_name_keys():
    data = [{"firstName": "Ana", "lastName": "López",
             "hometown": "Madrid, Spain", "slug": "ana-lopez"}]
    fields = parse_nuxt_roster_payload(_payload_html(data))
    assert fields["ana lopez"]["hometown"] == "Madrid, Spain"


def test_nameless_valueless_payload_items_skipped():
    data = [{"state": "TX"},          # no name/slug, no name fields at all
            {"firstName": "Dana", "hometown": ""}]   # name but no usable field
    assert parse_nuxt_roster_payload(_payload_html(data)) == {}


# --- matching helpers ---------------------------------------------------------

def test_norm_person_name_and_url_slug():
    assert norm_person_name("Ana López") == "ana lopez"
    assert norm_person_name("O'Brien, Mary-Jane") == "o brien mary jane"
    assert slug_from_player_url(
        "https://vanderbilt.com/sports/womens-basketball/roster/mikayla-blakes/1234"
    ) == "mikayla-blakes"
    assert slug_from_player_url("/sports/wbb/roster/jane-doe/") == "jane-doe"
    assert slug_from_player_url("") == ""


def test_match_fills_only_empty_fields():
    entity = {"name": "Khamil Pierre", "previous_school": "USC"}
    nuxt = parse_nuxt_roster_payload(_payload_html(DEVALUE))
    assert match_nuxt_fields(entity, nuxt) == {
        "hometown": "Brooklyn, NY", "high_school": "Bishop Kearney"}


def test_match_requires_name_or_slug():
    entity = {"name": "", "url": ""}
    nuxt = parse_nuxt_roster_payload(_payload_html(DEVALUE))
    assert match_nuxt_fields(entity, nuxt) == {}


def test_match_none_or_empty_payload_is_noop():
    assert match_nuxt_fields({"name": "Khamil Pierre"}, None) == {}
    assert match_nuxt_fields({"name": "Khamil Pierre"}, {}) == {}


def test_match_falls_back_to_url_slug():
    entity = {"name": "M. Pierre",   # payload name won't match this
              "url": "https://vanderbilt.com/sports/wbb/roster/khamil-pierre/123"}
    nuxt = parse_nuxt_roster_payload(_payload_html(DEVALUE))
    fill = match_nuxt_fields(entity, nuxt)
    assert fill["hometown"] == "Brooklyn, NY"


# --- JavaScriptScraper wiring -------------------------------------------------

def _js_scraper():
    return JavaScriptScraper()   # use_playwright=False; no network involved


def _team_js_data(**overrides):
    row = {"name": "Khamil Pierre", "jersey": "1", "position": "Guard",
           "year": "Jr", "height": "6-0", "hometown": "", "high_school": "",
           "previous_school": "", "url": "/sports/womens-basketball/roster/khamil-pierre/123"}
    row.update(overrides)
    return [row]


def test_process_js_result_fills_from_payload():
    scraper = _js_scraper()
    nuxt = parse_nuxt_roster_payload(_payload_html(DEVALUE))
    players = scraper._process_js_result(_team_js_data(), TEAM, "2026-27",
                                         "https://vanderbilt.com", nuxt_fields=nuxt)
    p = players[0]
    assert p.hometown == "Brooklyn, NY"
    assert p.high_school == "Bishop Kearney"
    assert p.previous_school == "USC"


def test_process_js_result_never_overwrites_existing_values():
    scraper = _js_scraper()
    nuxt = parse_nuxt_roster_payload(_payload_html(DEVALUE))
    data = _team_js_data(hometown="Existing, TX", high_school="Kept HS")
    players = scraper._process_js_result(data, TEAM, "2026-27",
                                         "https://vanderbilt.com", nuxt_fields=nuxt)
    p = players[0]
    assert p.hometown == "Existing, TX"
    assert p.high_school == "Kept HS"
    assert p.previous_school == "USC"   # payload value, blank before


def test_process_js_result_without_payload_unchanged():
    scraper = _js_scraper()
    players = scraper._process_js_result(_team_js_data(), TEAM, "2026-27",
                                         "https://vanderbilt.com")
    p = players[0]
    assert p.hometown == ""
    assert p.high_school == ""
    # default arg keeps the legacy signature working
    assert p.name == "Khamil Pierre"