from pdfreader import SimplePDFViewer

fd = open('DAy 3 USA NGRpdf.pdf', "rb")

viewer = SimplePDFViewer(fd)
viewer.navigate(1)
viewer.render()
strings = viewer.canvas.strings

team1 = strings[10]
team2 = strings[12].strip()
date = strings[13]
location = strings[17].strip() + ' ' + strings[18].strip()
team1_score = strings[20].strip()

# players

team1_players_start = strings.index('Min')+1
team1_players_end = strings.index('Team')-1
team1_players_num = int((team1_players_end - team1_players_start)/16)

team1_players = []
for x in range(1, team1_players_num+1):
    # starters have an additional element, an asterisk
    if x < 6:
        player_end = team1_players_start + 17
    else:
        player_end = team1_players_start + 16
    # handle Katie Lou Samuelson, who has two first names
    if strings[team1_players_start+3][0] == ' ':
        strings[team1_players_start+2] = strings[team1_players_start+2] + strings[team1_players_start+3]
        del(strings[team1_players_start+3])
        team1_players.append(strings[team1_players_start:player_end])
    else:
        team1_players.append(strings[team1_players_start:player_end])
    team1_players_start = player_end

team1_totals = strings[strings.index('Totals'):strings.index('Totals')+14]

team2_players_start = strings.index('Min', team1_players_start)+1
team2_players_end = strings.index('Team', team2_players_start)-1
team2_players_num = int((team2_players_end - team2_players_start)/16)

team2_players = []
for x in range(1, team2_players_num+1):
    if x < 6:
        player_end = team2_players_start + 17
    else:
        player_end = team2_players_start + 16
    if strings[team2_players_start+3][0] == ' ':
        strings[team2_players_start+2] = strings[team2_players_start+2] + strings[team2_players_start+3]
        del(strings[team2_players_start+3])
        team2_players.append(strings[team2_players_start:player_end])
    else:
        team2_players.append(strings[team2_players_start:player_end])
    team2_players_start = player_end

team2_totals = strings[strings.index('Totals', team2_players_end):strings.index('Totals', team2_players_end)+14]

team1_technical_fouls = strings[strings.index('Technical')+2].strip()
team2_technical_fouls = strings[strings.index('Technical')+3].strip()

team1_score_by_periods = strings[strings.index(team1, strings.index('Technical')):strings.index(team1, strings.index('Technical'))+6]
team2_score_by_periods = strings[strings.index(team2, strings.index('Technical')):strings.index(team2, strings.index('Technical'))+6]
