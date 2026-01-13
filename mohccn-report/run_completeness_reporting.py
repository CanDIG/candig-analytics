import pandas as pd
import argparse
import requests as rq
import subprocess

PSQL_USER="admin"


# def parse_args():
#     parser = argparse.ArgumentParser()
#     parser.add_argument('--token', type=str, required=True, help="token for the candig deployment you are retrieving data from.")
#     parser.add_argument('--url', type=str, required=True, help="URL of the candig deployment you are retrieving data from")
#     args = parser.parse_args()
#     return args

def main():
    # args = parse_args()
    with open("minimal_clinical_query.sql", "r") as f:
        minimal_sql_q = f.read()
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "touch", "minimal_completeness.csv"])
    result = subprocess.run([f"cat ./minimal_clinical_query.sql | docker exec -i candigv2_postgres-db_1 psql -U admin -d clinical -c {minimal_sql_q} > minimal_completeness.csv"])




if __name__ == "__main__":
    main()