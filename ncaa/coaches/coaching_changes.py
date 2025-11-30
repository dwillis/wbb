import subprocess
import requests
import json

output_dir = "/Users/dwillis/code/wbb/ncaa"

# 23-24
r = requests.get('https://wbbblog.com/wp-json/wp/v2/posts/42030')
# 22-23
#r = requests.get('https://wbbblog.com/wp-json/wp/v2/posts/30448')
transfer_json = r.json()

# Convert JSON to a string
transfer_json_str = json.dumps(transfer_json)

# Construct the initial command without JSON data in it
initial_command = "llm --system 'Return only a CSV file with all fields quoted, no yapping.' -m claude-3-haiku 'Please parse the following json to extract information about women college basketball coaching changes, producing a CSV file based on the following example: team,conference,coach,status,url,date\nAir Force,Mountain West,Chris Gobrecht,retires,https://goairforcefalcons.com/news/2024/4/1/womens-basketball-womens-basketball-head-coach-chris-gobrecht-announces-retirement,2024-04-1. Please complete all of the teams in the JSON, and remember to quote all fields. Here is the JSON:'"

# Command to get more output
more_command = "llm -c more"

# Output file for CSV data
output_file_path = f"{output_dir}/coaching_changes.csv"

def run_command(command, input_data=None, append=False):
    mode = "a" if append else "w"
    with open(output_file_path, mode) as output_file:
        process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=output_file, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(input=input_data)

        if process.returncode != 0:
            print(f"Command failed with exit code {process.returncode}")
            print(stderr)

    return process.returncode, stdout, stderr

try:
    # Execute the initial command and pass JSON data through stdin
    run_command(initial_command, transfer_json_str)

    # Check if more output is needed and append to the same CSV file
    # Here, we assume some condition or flag from initial command output indicating more data is needed
    # Replace the condition below with an actual check if applicable
    need_more_output = True # You need to define how to determine if more output is actually needed

    while need_more_output:
        run_command(more_command, append=True)

except subprocess.CalledProcessError as e:
    print(f"Error: {e}")
