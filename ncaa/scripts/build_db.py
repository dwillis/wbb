import os
import json
import datetime
import glob
import sqlite_utils
from game import Game

team_json = json.loads(open('teams.json').read())

db = sqlite_utils.Database('ncaa_games.db')

teams = db['teams']
teams.insert_all(team_json, pk="ncaa_id")

games = db['games']
games.create({
    "season": str,
    "home_team": str,
    "home_team_id": int,
    "visiting_team": str,
    "visiting_team_id": int,
    "location": str,
    "date": datetime.date,
    "time": datetime.time,
    "officials": str,
    "attendance": int,
    "home_team_score": int,
    "visiting_team_score": int,
    "ties": int,
    "home_team_fgm": int,
    "home_team_fga": int,
    "home_team_fgpct": float,
    "home_team_3ptm": int,
    "home_team_3pta": int,
    "home_team_3ptpct": float,
    "home_team_ftm": int,
    "home_team_fta": int,
    "home_team_ftpct": float,
    "home_team_rebounds": int,
    "home_team_rebounds_off": int,
    "home_team_rebounds_def": int,
    "home_team_leads": int,
    "home_team_lead_time": datetime.time,
    "home_team_percent_lead": float,
    "home_team_largest_lead": int,
    "home_team_largest_lead_score": str,
    "home_team_largest_lead_time": datetime.time,
    "home_team_assists": int,
    "home_team_turnovers": int,
    "home_team_bench_points": int,
    "home_team_blocks": int,
    "home_team_fast_break_points": int,
    "home_team_steals": int,
    "home_team_points_off_turnovers": int,
    "home_team_points_paint": int,
    "home_team_points_second_chance": int,
    "home_team_personal_fouls": int,
    "home_team_technical_fouls": int,
    "visiting_team_fgm": int,
    "visiting_team_fga": int,
    "visiting_team_fgpct": float,
    "visiting_team_3ptm": int,
    "visiting_team_3pta": int,
    "visiting_team_3ptpct": float,
    "visiting_team_ftm": int,
    "visiting_team_fta": int,
    "visiting_team_ftpct": float,
    "visiting_team_rebounds": int,
    "visiting_team_rebounds_off": int,
    "visiting_team_rebounds_def": int,
    "visiting_team_leads": int,
    "visiting_team_lead_time": datetime.time,
    "visiting_team_percent_lead": float,
    "visiting_team_largest_lead": int,
    "visiting_team_largest_lead_score": str,
    "visiting_team_largest_lead_time": datetime.time,
    "visiting_team_assists": int,
    "visiting_team_turnovers": int,
    "visiting_team_bench_points": int,
    "visiting_team_blocks": int,
    "visiting_team_fast_break_points": int,
    "visiting_team_steals": int,
    "visiting_team_points_off_turnovers": int,
    "visiting_team_points_paint": int,
    "visiting_team_points_second_chance": int,
    "visiting_team_personal_fouls": int,
    "visiting_team_technical_fouls": int
}, pk="id", hash_id="id")

officials = db['officials']
officials.create({
    "game_id": str,
    "official": str
}, pk=['game_id', 'official'], hash_id="id")

period_scores = db['period_scores']
period_scores.create({
    "game_id": str,
    "team_id": int,
    "period": int,
    "score": int
}, pk=['game_id', 'team', 'period'], hash_id="id")

for dir in glob.glob('/Users/dwillis/code/wbb-game-data/*-*'):
    team_id = dir.split('wbb-game-data/')[1].split('-')[0]
    json_team = [x for x in team_json if x['ncaa_id'] == int(team_id)][0]
    os.chdir(dir)
    for season in glob.glob('*'):
        try:
            os.chdir(season)
        except:
            continue
        for file in glob.glob('*.json'):
            print(file)
            if os.stat(file).st_size == 4:
                continue
            game = Game(file)
            if json_team['team'] in game.home_team:
                home_team_id = team_id
                visiting_team_id = None
            elif json_team['team'] in game.visiting_team:
                visiting_team_id = team_id
                home_team_id = None
            else:
                home_team_id = None
                visiting_team_id = None
            game_id = games.upsert({
                "season": season,
                "home_team": game.home_team,
                "home_team_id": home_team_id,
                "visiting_team": game.visiting_team,
                "visiting_team_id": visiting_team_id,
                "location": game.location,
                "date": game.date,
                "time": game.start_time,
                "officials": game.officials,
                "attendance": game.attendance,
                "home_team_score": game.home_team_score,
                "visiting_team_score": game.visiting_team_score,
                "home_team_fgm": int(game.home_team_totals['Fgam'].split('-')[0]),
                "home_team_fga": int(game.home_team_totals['Fgam'].split('-')[1]),
                "home_team_fgpct": float(game.home_team_totals['ShootingPercentage'].replace('%','')),
                "home_team_3ptm": int(game.home_team_totals['Tpam'].split('-')[0]),
                "home_team_3pta": int(game.home_team_totals['Tpam'].split('-')[1]),
                "home_team_3ptpct": float(game.home_team_totals['Tppercentage'].replace('%','')),
                "home_team_ftm": int(game.home_team_totals['Ftma'].split('-')[0]),
                "home_team_fta": int(game.home_team_totals['Ftma'].split('-')[1]),
                "home_team_ftpct": float(game.home_team_totals['Ftp'].replace('%','')),
                "home_team_rebounds": int(game.home_team_totals['TotalRebounds']),
                "home_team_rebounds_off": int(game.home_team_totals['OffensiveRebounds']),
                "home_team_rebounds_def": int(game.home_team_totals['DefensiveRebounds']),
                "home_team_leads": int(game.home_team_totals['Leads']),
                "home_team_lead_time": game.home_team_totals['TimeWithLead'],
                "home_team_percent_lead": float(game.home_team_totals['PercentLead'].replace('%','')),
                "home_team_largest_lead": int(game.home_team_totals['LargestLead']),
                "home_team_largest_lead_score": game.home_team_totals['LargestLeadScores'],
                "home_team_largest_lead_time": game.home_team_totals['LargestLeadTime'].split(' ')[0],
                "home_team_assists": int(game.home_team_totals['Assists']),
                "home_team_turnovers": int(game.home_team_totals['Turnovers']),
                "home_team_bench_points": int(game.home_team_totals['PointsFromBench']),
                "home_team_blocks": int(game.home_team_totals['Blocks']),
                "home_team_fast_break_points": int(game.home_team_totals['PointsOffFastBreak']),
                "home_team_steals": int(game.home_team_totals['Steals']),
                "home_team_points_off_turnovers": int(game.home_team_totals['PointsOffTurnovers']),
                "home_team_points_paint": int(game.home_team_totals['PointsInPaint']),
                "home_team_points_second_chance": int(game.home_team_totals['PointsOffSecondChance']),
                "home_team_personal_fouls": int(game.home_team_totals['PersonalFouls']),
                "home_team_technical_fouls": int(game.home_team_totals['TechnicalFouls']),
                "visiting_team_fgm": int(game.visiting_team_totals['Fgam'].split('-')[0]),
                "visiting_team_fga": int(game.visiting_team_totals['Fgam'].split('-')[1]),
                "visiting_team_fgpct": float(game.visiting_team_totals['ShootingPercentage'].replace('%','')),
                "visiting_team_3ptm": int(game.visiting_team_totals['Tpam'].split('-')[0]),
                "visiting_team_3pta": int(game.visiting_team_totals['Tpam'].split('-')[1]),
                "visiting_team_3ptpct": float(game.visiting_team_totals['Tppercentage'].replace('%','')),
                "visiting_team_ftm": int(game.visiting_team_totals['Ftma'].split('-')[0]),
                "visiting_team_fta": int(game.visiting_team_totals['Ftma'].split('-')[1]),
                "visiting_team_ftpct": float(game.visiting_team_totals['Ftp'].replace('%','')),
                "visiting_team_rebounds": int(game.visiting_team_totals['TotalRebounds']),
                "visiting_team_rebounds_off": int(game.visiting_team_totals['OffensiveRebounds']),
                "visiting_team_rebounds_def": int(game.visiting_team_totals['DefensiveRebounds']),
                "visiting_team_leads": int(game.visiting_team_totals['Leads']),
                "visiting_team_lead_time": game.visiting_team_totals['TimeWithLead'],
                "visiting_team_percent_lead": float(game.visiting_team_totals['PercentLead'].replace('%','')),
                "visiting_team_largest_lead": int(game.visiting_team_totals['LargestLead']),
                "visiting_team_largest_lead_score": game.visiting_team_totals['LargestLeadScores'],
                "visiting_team_largest_lead_time": game.visiting_team_totals['LargestLeadTime'].split(' ')[0],
                "visiting_team_assists": int(game.visiting_team_totals['Assists']),
                "visiting_team_turnovers": int(game.visiting_team_totals['Turnovers']),
                "visiting_team_bench_points": int(game.visiting_team_totals['PointsFromBench']),
                "visiting_team_blocks": int(game.visiting_team_totals['Blocks']),
                "visiting_team_fast_break_points": int(game.visiting_team_totals['PointsOffFastBreak']),
                "visiting_team_steals": int(game.visiting_team_totals['Steals']),
                "visiting_team_points_off_turnovers": int(game.visiting_team_totals['PointsOffTurnovers']),
                "visiting_team_points_paint": int(game.visiting_team_totals['PointsInPaint']),
                "visiting_team_points_second_chance": int(game.visiting_team_totals['PointsOffSecondChance']),
                "visiting_team_personal_fouls": int(game.visiting_team_totals['PersonalFouls']),
                "visiting_team_technical_fouls": int(game.visiting_team_totals['TechnicalFouls']),
            }, hash_id="id").last_pk
            for official in game.officials:
                officials.upsert({
                    "game_id": game_id,
                    "official": official
                }, hash_id="id", foreign_keys=[("game_id", "games")])

db.add_foreign_keys([
    ("games", "home_team_id", "teams", "ncaa_id"),
    ("games", "visiting_team_id", "teams", "ncaa_id")
])
# create period_scores table & populate from each game
