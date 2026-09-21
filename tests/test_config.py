"""Parity guards for the big verbatim moves in wbb.config — team type
resolution, URL building, and the quirk that VueDataScraper is only used
by teams whose VUE_DATA_TEAMS entry overrides 'type'."""
from wbb.config import TeamConfig, URLBuilder, ENTITY_CONFIGS


def test_get_config_known_types():
    assert TeamConfig.get_config(47)['type'] == 'javascript'      # Ball State (nuxt)
    assert TeamConfig.get_config(433)['type'] == 'table'          # Ole Miss
    assert TeamConfig.get_config(1050)['type'] == 'table'
    assert TeamConfig.get_config(1050).get('url_format') == 'season_first'
    assert TeamConfig.get_config(202)['type'] == 'standard'       # Eastern Kentucky
    assert TeamConfig.get_config(72)['type'] == 'vue_data'        # only VUE_DATA override wins


def test_get_config_unknown_team_falls_back_to_standard():
    cfg = TeamConfig.get_config(999999)
    assert cfg['type'] == 'standard'


def test_get_config_vue_data_merge_quirk():
    # Most VUE_DATA_TEAMS entries declare 'type': 'standard' and the entry
    # spread overrides the vue_data base — only ids whose entry omits
    # 'type' (72, 731) actually scrape with VueDataScraper.
    resolved = {tid: TeamConfig.get_config(tid)['type']
                for tid in TeamConfig.VUE_DATA_TEAMS}
    assert {tid for tid, t in resolved.items() if t == 'vue_data'} == {72, 731}


def test_build_url_default_formats():
    base = 'https://example.com/sports/womens-basketball'
    assert URLBuilder.build_url(base, '2025-26') == \
        'https://example.com/sports/womens-basketball/roster/2025-26'
    assert URLBuilder.build_url(base, '2025-26', 'season_path') == \
        'https://example.com/sports/womens-basketball/roster/season/2025-26/'


def test_build_url_coach_entity_uses_coaches_path():
    base = 'https://example.com/sports/womens-basketball'
    assert URLBuilder.build_url(base, '2025-26', entity_type='coach') == \
        'https://example.com/sports/womens-basketball/coaches/2025-26'


def test_build_url_hawaiiathletics_special_case():
    # Hawaii uses four-digit year: 2025-26 -> 2025-2026
    base = 'https://hawaiiathletics.com/sports/womens-beach-volleyball'
    url = URLBuilder.build_url(base, '2025-26')
    assert url == 'https://hawaiiathletics.com/sports/womens-beach-volleyball/roster/2025-2026'


def test_build_url_season_first():
    # season_first appends /{season}/{path} — a year baked into the base URL stays
    base = 'https://example.com/2024-25/sports/womens-basketball'
    url = URLBuilder.build_url(base, '2025-26', 'season_first')
    assert url == 'https://example.com/2024-25/sports/womens-basketball/2025-26/roster'


def test_build_url_no_format_uses_default():
    base = 'https://example.com/sports/wbb'
    assert URLBuilder.build_url(base, '2025-26') == \
        URLBuilder.build_url(base, '2025-26', 'default')


def test_entity_configs_shape():
    assert set(ENTITY_CONFIGS) == {'player', 'coach'}
    for entity, cfg in ENTITY_CONFIGS.items():
        assert 'output_fields' in cfg and cfg['output_fields']
        assert 'name' in cfg['output_fields'] and 'season' in cfg['output_fields']