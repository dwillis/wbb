import csv
from Levenshtein import distance

results = []

with open("person20201204.csv", "r") as hhs_persons_file:
    hhs_persons_csv = csv.DictReader(hhs_persons_file)
    for row in hhs_persons_csv:
        
