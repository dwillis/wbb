"""Offline tests for the post-scrape 'Team Impact' honorary-member filter.

Team IMPACT honorees appear on rosters with the program name (any casing) in
their high school or hometown field; they aren't players and are dropped
before CSV/DB output. Uses the orchestration faking from test_manager.py —
no network.
"""
import json

from wbb.models import Player
from wbb.parsing import is_team_impact_value


def _player(**overrides):
    defaults = dict(team_id=47, team='Ball State', name='Real Player', year='JR',
                    position='G', jersey='3', season='2025-26')
    defaults.update(overrides)
    return Player(**defaults)


# --- is_team_impact_value -----------------------------------------------------

def test_matches_every_casing_and_whitespace():
    for v in ("Team Impact", "Team IMPACT", "TEAM IMPACT", "team impact",
              "  Team Impact  ", "TeaM  iMpact"):
        assert is_team_impact_value(v), v
    assert not is_team_impact_value("")
    assert not is_team_impact_value(None)
    # exact match only — real schools containing the phrase stay
    assert not is_team_impact_value("Team Impact Academy")
    assert not is_team_impact_value("Team Impact High School")
    assert not is_team_impact_value("Team Impacts")
    assert not is_team_impact_value("Impact Team")
    assert not is_team_impact_value("St. Francis")


def test_matches_either_field():
    assert is_team_impact_value.__doc__  # sanity: predicate is field-agnostic
    p = _player(high_school='Team IMPACT', hometown='East Lansing, Mich.')
    from wbb.manager import RosterManager
    m = RosterManager.__new__(RosterManager)
    m.entity_type = 'player'
    assert m._drop_team_impact_members([p]) == []   # hs match alone drops


# --- filtering inside the manager ----------------------------------------------

def _manager(players):
    from wbb.manager import RosterManager
    m = RosterManager.__new__(RosterManager)   # skip teams.json load
    m.entity_type = 'player'
    return m


def test_drops_member_on_either_field():
    m = _manager(None)
    hon_hometown = _player(name='Hazel Olah', hometown='Team IMPACT')
    hon_hs = _player(name='Charlee Worcester', high_school='TEAM IMPACT')
    real = _player()
    kept = m._drop_team_impact_members([hon_hometown, hon_hs, real])
    assert kept == [real]


def test_noop_for_coach_entity():
    from wbb.manager import RosterManager
    m = RosterManager.__new__(RosterManager)
    m.entity_type = 'coach'
    coach = Player(team_id=47, team='Ball State', name='Coach X', season='2025-26',
                   hometown='Team IMPACT')   # coach hometown holds alma_mater
    assert m._drop_team_impact_members([coach]) == [coach]


def test_empty_list_noop():
    m = _manager(None)
    assert m._drop_team_impact_members([]) == []


# --- end-to-end through the orchestration (faked scraping, like test_manager) --

def test_filter_applies_via_scrape_team_roster(monkeypatch, tmp_path):
    from wbb import manager as manager_mod

    hon = _player(team_id=9001, team='Good U', name='Emily C.', high_school='Team IMPACT')
    real = _player(team_id=9001, team='Good U', name='Grace Santiago', hometown='Troy, N.Y.')

    teams = [{'team': 'Good U', 'url': 'https://good.example/sports/wbb',
              'ncaa_id': 9001, 'team_state': 'TX'}]
    teams_file = tmp_path / 'teams.json'
    teams_file.write_text(json.dumps(teams))

    class FakeScraper:
        def scrape_roster(self, team, season, url_format):
            return [hon, real]

    monkeypatch.setattr(manager_mod.ScraperFactory, 'create_scraper',
                        classmethod(lambda cls, t, entity_type='player', **kw: FakeScraper()))
    monkeypatch.setattr(manager_mod.RosterManager, '_verify_team_season_with_format',
                        lambda self, team, season, url_format: True)
    monkeypatch.setattr(manager_mod.RosterManager, '_verify_team_season',
                        lambda self, team, season: True)

    m = manager_mod.RosterManager(teams_file=str(teams_file), entity_type='player')
    players = m.scrape_multiple_teams('2025-26')

    assert [p.name for p in players] == ['Grace Santiago']
    assert m.team_results == [manager_mod.TeamOutcome(9001, 'Good U', 1, 'ok', None)]