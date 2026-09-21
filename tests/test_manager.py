"""Offline test for RosterManager orchestration — scraper and season
verification are faked, so this never touches the network."""
import json

import pytest

from wbb.manager import RosterManager


class FakeScraper:
    """Returns canned players per team id."""

    def __init__(self, players_by_team):
        self.players_by_team = players_by_team

    def scrape_roster(self, team, season, url_format):
        return list(self.players_by_team.get(team['ncaa_id'], []))


@pytest.fixture
def fake_teams(tmp_path):
    teams = [
        {'team': 'Good U', 'url': 'https://good.example/sports/wbb', 'ncaa_id': 9001, 'team_state': 'TX'},
        {'team': 'Empty U', 'url': 'https://empty.example/sports/wbb', 'ncaa_id': 9002},
        {'team': 'Boom U', 'url': 'https://boom.example/sports/wbb', 'ncaa_id': 9003},
    ]
    teams_file = tmp_path / 'teams.json'
    teams_file.write_text(json.dumps(teams))
    return str(teams_file)


@pytest.fixture
def canned_players():
    def make(team_id, team, n):
        from wbb.models import Player
        return [Player(team_id=team_id, team=team, name=f'P{i}', year='JR',
                       position='G', jersey=str(i), season='2025-26') for i in range(n)]
    return make


def test_orchestration_outcomes_and_sidecars(monkeypatch, tmp_path, fake_teams, canned_players):
    from wbb import manager as manager_mod

    players_by_team = {9001: canned_players(9001, 'Good U', 3)}
    monkeypatch.setattr(manager_mod.ScraperFactory, 'create_scraper',
                        classmethod(lambda cls, t, entity_type='player', **kw: FakeScraper(players_by_team)))
    # Season verification: fail only for Empty U, never hit the network
    monkeypatch.setattr(manager_mod.RosterManager, '_verify_team_season_with_format',
                        lambda self, team, season, url_format: team['ncaa_id'] != 9002)
    monkeypatch.setattr(manager_mod.RosterManager, '_verify_team_season',
                        lambda self, team, season: team['ncaa_id'] != 9002)
    # Boom U raises before any URL-format loop can swallow the error
    # (scrape_team_roster catches per-format exceptions and returns [], so
    # an 'error' outcome requires the failure to escape scrape_team_roster).
    real_get_config = manager_mod.TeamConfig.get_config

    def fake_get_config(team_id):
        if team_id == 9003:
            raise ValueError('no config for Boom U')
        return real_get_config(team_id)

    monkeypatch.setattr(manager_mod.TeamConfig, 'get_config', staticmethod(fake_get_config))

    outcomes = []
    m = RosterManager(teams_file=fake_teams, entity_type='player', on_team=outcomes.append)
    players = m.scrape_multiple_teams('2025-26')

    assert len(players) == 3                     # only Good U contributed rows
    assert {o.team_id for o in m.team_results} == {9001, 9002, 9003}
    statuses = {o.team_id: o.status for o in m.team_results}
    assert statuses[9001] == 'ok'
    assert statuses[9003] == 'error'
    assert statuses[9002] == 'failed_verification'
    # scraper-error teams land in the zero-player sidecar; failed-verification does not
    assert [z['team_id'] for z in m.zero_player_teams] == [9003]
    assert [f['team_id'] for f in m.failed_year_check_teams] == [9002]

    # on_team callback saw every outcome
    assert len(outcomes) == 3


def test_outcome_player_counts(monkeypatch, tmp_path, fake_teams, canned_players):
    from wbb import manager as manager_mod

    players_by_team = {9001: canned_players(9001, 'Good U', 2),
                       9002: canned_players(9002, 'Empty U', 0)}
    monkeypatch.setattr(manager_mod.ScraperFactory, 'create_scraper',
                        classmethod(lambda cls, t, entity_type='player', **kw: FakeScraper(players_by_team)))
    monkeypatch.setattr(manager_mod.RosterManager, '_verify_team_season_with_format',
                        lambda self, team, season, url_format: True)
    monkeypatch.setattr(manager_mod.RosterManager, '_verify_team_season',
                        lambda self, team, season: True)

    m = RosterManager(teams_file=fake_teams, entity_type='player')
    m.scrape_multiple_teams('2025-26')

    by_id = {o.team_id: o for o in m.team_results}
    assert by_id[9001].n_players == 2 and by_id[9001].status == 'ok'
    assert by_id[9002].n_players == 0 and by_id[9002].status == 'zero'


def test_save_to_csv_delegates(tmp_path, canned_players):
    m = RosterManager.__new__(RosterManager)  # skip teams.json load
    m.entity_type = 'player'
    m.teams_data = []
    m.zero_player_teams = []
    m.failed_year_check_teams = []
    out = tmp_path / 'out.csv'
    m.save_to_csv(canned_players(47, 'Ball State', 2), str(out))
    assert out.exists()
    m.save_zero_player_teams_to_csv(str(tmp_path / 'z.csv'))  # empty -> no-op, no file
    assert not (tmp_path / 'z.csv').exists()
    m.save_failed_year_check_teams_to_csv(str(tmp_path / 'f.csv'))
    assert not (tmp_path / 'f.csv').exists()