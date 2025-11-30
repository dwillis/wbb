require 'remote_table'
require 'csv'

t = RemoteTable.new "ncaa_history.csv"
history = t.entries

t2 = RemoteTable.new "ncaa_games.csv"
games = t2.entries

headers = ['year', 'ncaa_game_id', 'gamedate_east', 'round', 'team_1_id', 'team_1_name', 'team_1_region', 'team_1_seed', 'team_2_id', 'team_2_name', 'team_2_region', 'team_2_seed']
results = []

games.each do |game|

  team1_history = history.detect{|h| h["year"] == game["year"] && h['ncaa_id'] == game['team_1_id']}
  team2_history = history.detect{|h| h["year"] == game["year"] && h['ncaa_id'] == game['team_2_id']}

  if team1_history && team2_history
    results << [game['year'], game['ncaa_game_id'], game['gamedate_east'], game['round'], game['team_1_id'], game['team_1_name'], team1_history['region'], team1_history['seed'], game['team_2_id'], game['team_2_name'], team2_history['region'], team2_history['seed']]
  else
    puts game
    raise
  end
end

CSV.open("ncaa_tourney_games.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
