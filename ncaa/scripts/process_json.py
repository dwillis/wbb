import json
import sqlite_utils

# create db

db = sqlite_utils.Database("ncaa.db")

# define table based on following data and also add ncaa_id, team account_name and date
# then grab .json files and iterate through them, inserting data and updating with
# additional fields where they are null before proceeding to next file. grab account_name
# from file name.

f = File.open('aggiewbb.json').readlines()
for line in f:
    j = json.loads(line)
    j['account_name'] = file_name
