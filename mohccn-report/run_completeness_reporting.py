import pandas as pd
import argparse
import requests as rq
import subprocess
import sys
import glob

PSQL_USER="admin"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--psql-user', type=str, required=False, default="admin", help="Username of the postgres admin user, DEFAULT=admin")
    parser.add_argument('--token', type=str, required=True, help="site admin token for the candig deployment you are retrieving data from.")
    parser.add_argument('--url', type=str, required=True, help="URL of the candig deployment you are retrieving data from")
    parser.add_argument('--node', type=str, required=True, help="name of the node running the report, e.g. UHN")
    args = parser.parse_args()
    return args


def get_site_data(token, url):
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json; charset=utf-8"
               }
    response = rq.get(f"{url}/query/discovery/programs", headers=headers)
    if response:
        full_clinical_completeness = {
            "program_id": [],
            "total_donors": [],
            "complete_donors": [],
            "cases_missing_data": []
        }
        for program in response.json()['programs']:
            full_clinical_completeness['program_id'].append(program['program_id'])
            full_clinical_completeness['total_donors'].append(program['metadata']['summary_cases']['total_cases'])
            full_clinical_completeness['complete_donors'].append(program['metadata']['summary_cases']['complete_cases'])
            full_clinical_completeness['cases_missing_data'].append(program['metadata']['cases_missing_data'])
        return full_clinical_completeness
    else:
        print("Could not retrieve programs, try getting a new token and run the script again.")
        sys.exit()


def get_genomic_data(token, url, sample_list):
    genomic_completeness_dict = {
        "program_id": [],
        "submitter_sample_id": [],
        "expression_file_count": [],
        "variant_sample_file_count": [],
        "read_file_count": []
    }
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json; charset=utf-8"
               }
    response = rq.post(f"{url}/drs/ga4gh/drs/v1/experiments", headers=headers,
                       json={"submitter_sample_ids": sample_list})
    if response:
        """every sample should have 2 genomes, 1 transcriptome"""
        experiment_objects = response.json()
        for obj in experiment_objects:
            genomic_completeness_dict['program_id'].append(obj['program'])
            genomic_completeness_dict['submitter_sample_id'].append(obj['experiment_id'])
            genomic_completeness_dict['expression_file_count'].append(len(obj['expressions']))
            genomic_completeness_dict['variant_sample_file_count'].append(len(obj['variants']))
            genomic_completeness_dict['read_file_count'].append(len(obj['reads']))
        genomic_completeness_df = pd.DataFrame(genomic_completeness_dict)
        return genomic_completeness_df
    else:
        print("Could not retrieve genomic data, try getting a new token and run the script again.")
        sys.exit()


def check_sample_completeness(sample_types: list):
    """
    A donor is considered complete if there are:
       - 1 normal DNA
       - 1 tumour DNA
       - 1 tumour RNA
    """
    normal_dna_count = sample_types.count('Normal~Total DNA')
    tumour_dna_count = sample_types.count('Tumour~Total DNA')
    tumour_rna_count = sample_types.count('Tumour~Total RNA')
    if normal_dna_count >= 1 and tumour_dna_count >= 1 and tumour_rna_count >= 1:
        return True
    else:
        return False


def check_genomic_completeness(genomic_stats):
    """
    A donor is considered for genomic files if they have:
       - 1 normal DNA sample with 1 variant file and 1 reads file
       - 1 tumour DNA sample with 1 variant file and 1 reads file
       - 1 tumour RNA sample with 1 expression file
    """
    normal_dna_reads_count = 0
    normal_dna_variant_count = 0
    tumour_dna_reads_count = 0
    tumour_dna_variant_count = 0
    tumour_rna_expressions_count = 0
    if len(genomic_stats.loc[(genomic_stats['expression_file_count'] >= 1) &
                             (genomic_stats['tumour_normal_designation'] == "Tumour")]) > 0:
        tumour_rna_expressions_count = len(genomic_stats.loc[(genomic_stats['expression_file_count'] >= 1) &
                                                             (genomic_stats['tumour_normal_designation'] == "Tumour")])
    if len(genomic_stats.loc[(genomic_stats['read_file_count'] >= 1) &
                             (genomic_stats['tumour_normal_designation'] == "Tumour")]) > 0:
        tumour_dna_reads_count = len(genomic_stats.loc[(genomic_stats['read_file_count'] >= 1) &
                                                       (genomic_stats['tumour_normal_designation'] == "Tumour")])
    if len(genomic_stats.loc[(genomic_stats['read_file_count'] >= 1) &
                             (genomic_stats['tumour_normal_designation'] == "Normal")]) > 0:
        normal_dna_reads_count = len(genomic_stats.loc[(genomic_stats['read_file_count'] >= 1) &
                                                       (genomic_stats['tumour_normal_designation'] == "Normal")])
    if len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                             (genomic_stats['tumour_normal_designation'] == "Normal")]) > 0:
        normal_dna_variant_count = len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                                                         (genomic_stats['tumour_normal_designation'] == "Normal")])
    if len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                             (genomic_stats['tumour_normal_designation'] == "Tumour")]) > 0:
        tumour_dna_variant_count = len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                                                         (genomic_stats['tumour_normal_designation'] == "Tumour")])
    if all([normal_dna_variant_count, normal_dna_reads_count, tumour_rna_expressions_count, tumour_dna_reads_count,
            tumour_dna_variant_count]) > 0:
        return True
    else:
        return False


def _run_sql_script(script_name):
    """copy script to the docker container, run script, copy outputs, delete outputs"""
    stem_name = script_name.split(".sql")[0]
    subprocess.run(["docker", "cp", script_name, f"candigv2_postgres-db_1:/tmp/{script_name}"])
    result = subprocess.run(
        [f"docker exec -i candigv2_postgres-db_1 psql -U {PSQL_USER} -d clinical -f /tmp/{script_name}"],
        shell=True, stdout=subprocess.PIPE)
    subprocess.run(
        ["docker", "cp", f"candigv2_postgres-db_1:/tmp/{stem_name}_completeness.csv", f"{stem_name}_completeness.csv"])
    subprocess.run(
        ["docker", "cp", f"candigv2_postgres-db_1:/tmp/{stem_name}_completeness.csv", f"{stem_name}_count.csv"])
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{stem_name}_completeness.csv"])
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{stem_name}_count.csv"])
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{script_name}"])


def get_clinical_db_data():
    for script in glob.glob('*.sql'):
        _run_sql_script(script)
    # TODO: change back the path below after linked up
    # minimal_completeness_df = pd.read_csv("../_local/minimal_completeness.csv")
    # minimal_completeness_df['combined_sample_type'] = (
    #             minimal_completeness_df['tumour_normal_designation'].astype(str) +
    #             "~" + minimal_completeness_df['sample_type'].astype(str))
    # donor_grouped_sample = minimal_completeness_df.groupby(['program_id_id', 'submitter_donor_id'])[
    #     'combined_sample_type'].agg(list).reset_index()
    # donor_grouped_sample['samples_complete'] = donor_grouped_sample['combined_sample_type'].map(
    #     check_sample_completeness)
    # minimal_complete_donor_list = list(
    #     donor_grouped_sample.loc[donor_grouped_sample['samples_complete']].submitter_donor_id)
    # complete_donor_samples_df = minimal_completeness_df.loc[minimal_completeness_df['submitter_donor_id'].isin(minimal_complete_donor_list)]
    # program_minimal_complete_df = donor_grouped_sample.loc[donor_grouped_sample['samples_complete']].groupby('program_id_id').size().to_frame('minimal_complete_clinical_count').reset_index()
    # return program_minimal_complete_df, complete_donor_samples_df


def main():
    args = parse_args()
    program_minimal_complete_df, complete_donor_samples_df = get_clinical_db_data()
    # full_completeness = get_site_data(args.token, args.url)
    # sample_list = list(complete_donor_samples_df['submitter_sample_id'])
    # genomic_stats = get_genomic_data(args.token, args.url, sample_list)
    # genomic_stats = pd.merge(genomic_stats, complete_donor_samples_df, on="submitter_sample_id")
    # donor_list = set(list(complete_donor_samples_df['submitter_donor_id']))
    # donor_genomic_status = {
    #     "submitter_donor_id": [],
    #     "donors_with_genomic_files_complete": []
    # }
    # for donor in donor_list:
    #     donor_genomic_status['submitter_donor_id'].append(donor)
    #     donor_stats = genomic_stats.loc[genomic_stats['submitter_donor_id'] == donor]
    #     if len(donor_stats) == 0:
    #         donor_genomic_status['donors_with_genomic_files_complete'].append(False)
    #     else:
    #         donor_complete = check_genomic_completeness(donor_stats)
    #         donor_genomic_status['donors_with_genomic_files_complete'].append(donor_complete)
    # genomic_stats_per_donor = genomic_stats.groupby(['program_id', 'submitter_donor_id'], as_index=False).sum()
    # full_genomic_stats = pd.merge(genomic_stats_per_donor, pd.DataFrame(donor_genomic_status),
    #                               on='submitter_donor_id').loc[:, ['program_id', 'submitter_donor_id',
    #                                                                'submitter_sample_id', 'expression_file_count',
    #                                                                'variant_sample_file_count', 'read_file_count',
    #                                                                'donors_with_genomic_files_complete']]
    # genomic_per_program = (full_genomic_stats.loc[:, ['program_id', 'expression_file_count', 'variant_sample_file_count',
    #                                                  'read_file_count', 'donors_with_genomic_files_complete']].
    #                        groupby(['program_id'], as_index=False).sum())
    #
    # print("hello")


if __name__ == "__main__":
    main()