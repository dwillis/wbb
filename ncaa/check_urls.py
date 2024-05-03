import json
import requests
import csv

def check_url(url):
    try:
        # Perform a HEAD request to minimize data transfer
        response = requests.head(url, allow_redirects=True, timeout=30)
        # Return the status code
        return response.status_code
    except requests.RequestException as e:
        # Return the error encountered
        return str(e)

def main():
    # Load the data from your JSON file
    with open('teams.json', 'r') as file:
        teams_data = json.load(file)

    # Prepare to write to a CSV file
    with open('team_url_checks.csv', 'w', newline='') as csvfile:
        fieldnames = ['URL', 'Status Code']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write the header
        writer.writeheader()

        # Check the status code for each URL in the teams data
        for team in teams_data:
            if 'url' in team:
                url = team['url']
                print(url)
                status_code = check_url(url)
                # Write each URL and its status to the CSV file
                writer.writerow({'URL': url, 'Status Code': status_code})

if __name__ == "__main__":
    main()
