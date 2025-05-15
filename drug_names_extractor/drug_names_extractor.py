import pandas as pd
import argparse
import requests as rq


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', type=str, required=True, help="token for the candig deployment you are retrieving data from.")
    parser.add_argument('--url', type=str, required=True, help="URL of the candig deployment you are retrieving data from")
    args = parser.parse_args()
    return args


def grab_sys_therapies(token, url):
    body = {"page_size": 1000000}
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json; charset=utf-8",
               "federation": "true"
               }
    response = rq.get(f"{url}/katsu/v3/authorized/systemic_therapies/", headers=headers, params=body)
    return response.json()


def main():
    args = parse_args()
    sys_therapies_data = grab_sys_therapies(args.token, args.url)
    print(f"Found {len(sys_therapies_data['items'])} systemic therapy objects")
    drug_names = [x['drug_name'] for x in sys_therapies_data['items']]
    drug_ids = [x['drug_reference_identifier'] for x in sys_therapies_data['items']]
    drug_db = [x['drug_reference_database'] for x in sys_therapies_data['items']]
    drugs_dict = {"drug_name": drug_names,
                  "drug_reference_identifier": drug_ids,
                  "drug_reference_database": drug_db}
    drugs_df = pd.DataFrame(drugs_dict)
    drugs_df_counts = drugs_df.value_counts(['drug_name', 'drug_reference_identifier', 'drug_reference_database'], dropna=False).reset_index()
                #drop_duplicates().sort_values('drug_name'))
    print("Writing output to drug_names.csv...")
    drugs_df_counts.to_csv(f"drug_names.csv", index=False)


if __name__ == "__main__":
    main()
