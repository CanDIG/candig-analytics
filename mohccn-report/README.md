## MOHCCN report

Script that grabs data from the clinical database and CanDIG APIs in order to create a completeness report for all programs at a node

### How to run

1. `ssh` into the VM that is running your CanDIG node. The user should be able to access the `postgres-db` docker container
2. Clone this repo and cd into the mohccn-report directory
``` bash
git clone https://github.com/CanDIG/candig-analytics.git
cd mohccn-report
```
3. Create a virtual environment or conda environment and install requirements

```bash
conda create -n mohccn_report_env python=3.12
conda activate mohccn_report_env
pip install -r requirements.txt
```

4. Run the `run_completeness_reporting.py` script
```bash
python run_completeness_reporting.py --help
usage: run_completeness_reporting.py [-h] [--psql-user PSQL_USER] --token TOKEN --url URL --node NODE

options:
  -h, --help            show this help message and exit
  --psql-user PSQL_USER
                        Username of the postgres admin user, DEFAULT=admin
  --token TOKEN         site admin token for the candig deployment you are retrieving data from.
  --url URL             URL of the candig deployment you are retrieving data from
  --node NODE           name of the node running the report, e.g. UHN
```

You will need to provide:
- `--token`: a site admin token from you candig node
- `--url`: the url of you candig deployment
- `--node`: name of your node

4. Share the output file `per_program_completeness_report.csv`
