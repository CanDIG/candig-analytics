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
    subprocess.run(["docker", "cp", "minimal_clinical_query.sql", "candigv2_postgres-db_1:/minimal_clinical_query.sql"])
    subprocess.run(['CONN="psql -U admin -d clinical"'])
    subprocess.run(['QUERY="$(sed \'s/;//g;/^--/ d;s/--.*//g;\' minimal_clinical_query.sql | tr \'\n\' \' \')"'])
    subprocess.run(['echo "\\copy ($QUERY) to \'minimal_completeness.csv\' with CSV HEADER" | $CONN'])
    #result = subprocess.run(["docker exec -i candigv2_postgres-db_1 psql -U admin -d clinical -c 'COPY ($(cat /minimal_clinical_query.sql)) TO STDOUT with CSV HEADER' > minimal_completeness.csv"],
    #                        shell=True, stdout=subprocess.PIPE)
    subprocess.run(["docker", "cp", "candigv2_postgres-db_1:/minimal_completeness.csv", "minimal_completeness.csv"])
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", "minimal_completeness.csv"])
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", "minimal_clinical_query.sql"])
    # TODO: change back the path below after linked up
    #minimal_completeness_df = pd.read_csv("../_local/minimal_completeness.csv")

    #print(minimal_completeness_df)





if __name__ == "__main__":
    main()