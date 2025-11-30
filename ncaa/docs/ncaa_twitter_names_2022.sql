select person.hhs_person_id_text, person.full_name, person.twitter_username, team.ncaa_id, team.full_name, team.hhs_team_id_text
from person inner join person_season on person.hhs_person_id_text = person_season.hhs_person_id_text inner join team on person_season.hhs_team_id_text = team.hhs_team_id_text
where end_year = 2022 and person_season.league = 'NCAA'
