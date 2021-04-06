import json
import dateparser
import requests

class Game(object):

    def __init__(self, url):
        self.json_url = url
        self.json = self.get_json()
        self.date = self.parse_date()
        self.start_time = self._parse_time()
        self.location = self._parse_location()
        self.officials = self._parse_officials()
        self.attendance = self._parse_attendance()
        self.home_team = self._parse_home_team()
        self.home_team_score = self._parse_home_team_score()
        self.home_team_period_scores = self._parse_team_period_scores('HomeTeam')
        self.home_team_period_timeouts = self._parse_team_period_timeouts('HomeTeam')
        self.home_team_leaders_points = self._parse_team_leaders('HomeTeam', 'Points')
        self.home_team_leaders_rebounds = self._parse_team_leaders('HomeTeam', 'Rebounds')
        self.home_team_leaders_assists = self._parse_team_leaders('HomeTeam', 'Assists')
        self.home_team_leaders_blocks = self._parse_team_leaders('HomeTeam', 'Blocks')
        self.home_team_leaders_steals = self._parse_team_leaders('HomeTeam', 'Steals')
        self.home_team_leaders_fouls = self._parse_team_leaders('HomeTeam', 'Personal Fouls')
        self.home_team_leaders_efficiency = self._parse_team_leaders('HomeTeam', 'Efficiency')
        self.home_team_leaders_usage_percent = self._parse_team_leaders('HomeTeam', 'Usage Percentage')
        self.home_team_totals = self._parse_team_totals('HomeTeam')
        self.home_team_player_stats = self._parse_team_player_stats('HomeTeam')
        self.home_team_period_stats = self._parse_team_period_stats('HomeTeam')
        self.visiting_team = self._parse_visiting_team()
        self.visiting_team_score = self._parse_visiting_team_score()
        self.visiting_team_period_scores = self._parse_team_period_scores('VisitingTeam')
        self.visiting_team_period_timeouts = self._parse_team_period_timeouts('VisitingTeam')
        self.visiting_team_leaders_points = self._parse_team_leaders('VisitingTeam', 'Points')
        self.visiting_team_leaders_rebounds = self._parse_team_leaders('VisitingTeam', 'Rebounds')
        self.visiting_team_leaders_assists = self._parse_team_leaders('VisitingTeam', 'Assists')
        self.visiting_team_leaders_blocks = self._parse_team_leaders('VisitingTeam', 'Blocks')
        self.visiting_team_leaders_steals = self._parse_team_leaders('VisitingTeam', 'Steals')
        self.visiting_team_leaders_fouls = self._parse_team_leaders('VisitingTeam', 'Personal Fouls')
        self.visiting_team_leaders_efficiency = self._parse_team_leaders('VisitingTeam', 'Efficiency')
        self.visiting_team_leaders_usage_percent = self._parse_team_leaders('VisitingTeam', 'Usage Percentage')
        self.visiting_team_totals = self._parse_team_totals('VisitingTeam')
        self.visiting_player_stats = self._parse_team_player_stats('VisitingTeam')
        self.visiting_period_stats = self._parse_team_period_stats('VisitingTeam')
        self.plays = self._parse_plays()

    def get_json(self):
        r = requests.get(self.json_url)
        return r.json()

    def parse_date(self):
        return dateparser.parse(self.json['Game']['Date'])

    def _parse_time(self):
        return self.json['Game']['StartTime']

    def _parse_location(self):
        return self.json['Game']['Location']

    def _parse_officials(self):
        raw_officials = self.json['Game']['Officials'].split(',')
        return [o.strip() for o in raw_officials]

    def _parse_attendance(self):
        return self.json['Game']['Attendance']

    def _parse_home_team(self):
        return self.json['Game']['HomeTeam']['Name']

    def _parse_home_team_score(self):
        return int(self.json['Game']['HomeTeam']['Score'])

    def _parse_team_period_scores(self, team):
        return self.json['Game'][team]['PeriodScores']

    def _parse_team_period_timeouts(self, team):
        return self.json['Game'][team]['PeriodTimeouts']

    def _parse_visiting_team(self):
        return self.json['Game']['VisitingTeam']['Name']

    def _parse_visiting_team_score(self):
        return int(self.json['Game']['VisitingTeam']['Score'])

    def _parse_visiting_team_period_scores(self):
        return self.json['Game']['VisitingTeam']['PeriodScores']

    def _parse_team_leaders(self, team, category):
        return self.json['Leaders'][team][category]

    def _parse_team_totals(self, team):
        return self.json['Stats'][team]['Totals']['Values']

    def _parse_team_player_stats(self, team):
        return self.json['Stats'][team]['PlayerGroups']['Players']['Values']

    def _parse_team_period_stats(self, team):
        return [x['Values'] for x in self.json['Stats'][team]['PeriodStats']]

    def _parse_plays(self):
        return self.json['Plays']
