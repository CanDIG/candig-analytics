import pandas as pd
import numpy as np
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
        ["docker", "cp", f"candigv2_postgres-db_1:/tmp/{stem_name}_count.csv", f"{stem_name}_count.csv"])
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{stem_name}_count.csv"])
    subprocess.run(
        ["docker", "cp", f"candigv2_postgres-db_1:/tmp/{stem_name}_completeness.csv", f"{stem_name}_completeness.csv"])
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{stem_name}_completeness.csv"])
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{script_name}"])


def get_minimal_completeness():
    # TODO: change back the path below after linked up
    minimal_completeness_df = pd.read_csv("minimal_completeness.csv")
    minimal_completeness_df['combined_sample_type'] = (
                minimal_completeness_df['tumour_normal_designation'].astype(str) +
                "~" + minimal_completeness_df['sample_type'].astype(str))
    donor_grouped_sample = minimal_completeness_df.groupby(['program_id_id', 'submitter_donor_id'])[
        'combined_sample_type'].agg(list).reset_index()
    donor_grouped_sample['samples_complete'] = donor_grouped_sample['combined_sample_type'].map(
        check_sample_completeness)
    minimal_complete_donor_list = list(
        donor_grouped_sample.loc[donor_grouped_sample['samples_complete']].submitter_donor_id)
    complete_donor_samples_df = minimal_completeness_df.loc[minimal_completeness_df['submitter_donor_id'].isin(minimal_complete_donor_list)]
    program_minimal_complete_df = donor_grouped_sample.loc[donor_grouped_sample['samples_complete']].groupby('program_id_id').size().to_frame('minimal_complete_clinical_count').reset_index()
    return program_minimal_complete_df, complete_donor_samples_df


def check_column_equality(row, col1, col2):
    if row[col1] == row[col2]:
        return True
    else:
        return False


def get_comorbidity_completeness():
    """technically I should check to make sure every time prior_malignancy is listed, the type code is a cancer but I
    don't have time to do that right now.
    For now I will just compare the number of complete comorbidities vs non-complete"""
    comorbidity_comp_df = pd.read_csv("fullsome_comorbidity_completeness.csv")
    comorbidity_count_df = pd.read_csv("fullsome_comorbidity_count.csv").rename(columns={'count': 'total_count'})
    comorbidity_comp_df = comorbidity_comp_df.loc[:, ['program_id_id', 'submitter_donor_id', 'prior_malignancy']].groupby(['program_id_id', 'submitter_donor_id'], as_index=False).count().rename(columns={'prior_malignancy': 'complete_count'})
    comorbidity_comp_df = pd.merge(comorbidity_count_df, comorbidity_comp_df, on='submitter_donor_id', how="left")
    comorbidity_comp_df['donor_comorbidities_complete'] = comorbidity_comp_df['complete_count'] == comorbidity_comp_df['total_count']
    return comorbidity_comp_df.loc[:, ['program_id_id_x', 'submitter_donor_id', 'total_count', 'complete_count',
                                       'donor_comorbidities_complete']].rename(columns={'program_id_id_x': 'program_id'})


def get_followups_completeness():
    followup_comp_df = pd.read_csv("fullsome_followup_completeness.csv")
    followup_count_df = pd.read_csv("fullsome_followup_count.csv").rename(columns={'count': 'total_count'})
    followup_comp_df['relapse'] = followup_comp_df['disease_status_at_followup'].isin(['Distant progression',
                                                                                       'Loco-regional progression',
                                                                                       'Progression not otherwise specified',
                                                                                       'Relapse or recurrence'])
    followup_comp_df['complete_followup'] = (~followup_comp_df['relapse'] |
                                             (followup_comp_df['relapse'] &
                                              followup_comp_df['date_of_relapse'].notna() &
                                              followup_comp_df['relapse_type'].notna() &
                                              followup_comp_df['method_of_progression_status'].notna() &
                                              followup_comp_df[
                                                  'anatomic_site_progression_or_recurrence'].notna()))
    followup_donor_complete = (followup_comp_df.loc[:, ['program_id_id', 'submitter_donor_id', 'complete_followup']].
                               groupby(['program_id_id', 'submitter_donor_id'], as_index=False).sum())
    followup_donor_complete = pd.merge(followup_count_df.loc[:, ['submitter_donor_id','total_count']],
                                       followup_donor_complete,
                                       on='submitter_donor_id', how="left")
    followup_donor_complete['donor_followups_complete'] = (followup_donor_complete['complete_followup'] ==
                                                           followup_donor_complete['total_count'])
    return followup_donor_complete


def get_radiations_completeness():
    radiation_comp_df = pd.read_csv("fullsome_treatments_radiation_completeness.csv")
    radiation_count_df = pd.read_csv("fullsome_treatments_radiation_count.csv").drop('submitter_treatment_id',
                                                                                     axis=1).groupby(
        ['program_id_id', 'submitter_donor_id'], as_index=False).sum().rename(columns={'count': 'total_count'})
    complete_radiations = pd.merge(radiation_count_df, radiation_comp_df.loc[:, ['submitter_donor_id',
                                                                                 'treatment_type']].groupby(
        'submitter_donor_id', as_index=False).count().rename(columns={"treatment_type": "complete_count"}),
                                   on="submitter_donor_id", how="left")
    complete_radiations['radiation_donor_complete'] = complete_radiations['complete_count'] == complete_radiations[
        'total_count']
    return complete_radiations


def get_surgeries_completeness():
    surgery_comp_df = pd.read_csv("fullsome_treatments_surgery_completeness.csv")
    surgery_count_df = pd.read_csv("fullsome_treatments_surgery_count.csv").drop('submitter_treatment_id',
                                                                                 axis=1).groupby(
        ['program_id_id', 'submitter_donor_id'], as_index=False).sum().rename(columns={'count': 'total_count'})
    surgery_specimens = pd.read_csv("fullsome_sample_completeness.csv")
    exception_treatments = list(
        surgery_specimens.loc[surgery_specimens['submitter_treatment_id'].notna()].submitter_treatment_id)
    surgery_comp_df['treatment_exception'] = surgery_comp_df['submitter_treatment_id'].isin(exception_treatments)
    surgery_comp_df['surgery_complete'] = (surgery_comp_df['treatment_exception'] |
                                           (surgery_comp_df['surgery_site'].notna() &
                                            surgery_comp_df['surgery_location'].notna()))
    complete_surgeries = pd.merge(surgery_count_df, surgery_comp_df.loc[:, ["submitter_donor_id", "surgery_complete"]]
                                  .groupby("submitter_donor_id", as_index=False).sum(),
                                  on="submitter_donor_id", how="left")
    complete_surgeries["surgery_donor_complete"] = (complete_surgeries['surgery_complete'] ==
                                                    complete_surgeries['total_count'])
    return complete_surgeries


def get_sys_therapy_completeness():
    sys_therapy_comp_df = pd.read_csv("fullsome_treatments_sys_therapy_completeness.csv")
    sys_therapy_count_df = (pd.read_csv("fullsome_treatments_sys_therapy_count.csv").drop('submitter_treatment_id', axis=1).
                            groupby(['program_id_id', 'submitter_donor_id'], as_index=False).sum().rename(
                            columns={'count': 'total_count'}))
    sys_therapy_comp_df["sys_therapy_complete"] = ((sys_therapy_comp_df['drug_dose_units'].isna() &
                                                   sys_therapy_comp_df['prescribed_cumulative_drug_dose'].isna() &
                                                   sys_therapy_comp_df['actual_cumulative_drug_dose'].isna()) |
                                                   ((sys_therapy_comp_df['prescribed_cumulative_drug_dose'].notna() |
                                                    sys_therapy_comp_df['actual_cumulative_drug_dose'].notna()) &
                                                   sys_therapy_comp_df['drug_dose_units'].notna()))
    complete_sys_therapies = pd.merge(sys_therapy_count_df,
                                      sys_therapy_comp_df.loc[:, ["submitter_donor_id", 'sys_therapy_complete']].
                                      groupby("submitter_donor_id", as_index=False).sum(), on="submitter_donor_id",
                                      how="left")
    complete_sys_therapies["sys_therapy_donor_complete"] = complete_sys_therapies["total_count"] == complete_sys_therapies["sys_therapy_complete"]
    return complete_sys_therapies


def get_treatments_completeness():
    treatment_comp_df = pd.read_csv("fullsome_treatments_completeness.csv")
    sys_therapy_count_df = pd.read_csv("fullsome_treatments_sys_therapy_count.csv")
    radiation_count_df = pd.read_csv("fullsome_treatments_radiation_count.csv").rename(columns={'count': 'total_count'})
    surgery_count_df = pd.read_csv("fullsome_treatments_surgery_count.csv").rename(columns={'count': 'total_count'})
    treatment_count_df = pd.read_csv("fullsome_treatments_count.csv").rename(
        columns={'count': 'total_count'})

    sys_therapy_treatment_list = list(treatment_comp_df.loc[treatment_comp_df['treatment_type'].str.contains('Systemic therapy', na=False), 'submitter_treatment_id'])
    sys_therapy_treatment_type_intersection = set(sys_therapy_treatment_list).intersection(set(sys_therapy_count_df['submitter_treatment_id']))
    treatment_comp_df["sys_therapy_complete"] = (treatment_comp_df['treatment_type'].str.contains('Systemic therapy', na=False) &
                                                 treatment_comp_df['submitter_treatment_id'].isin(sys_therapy_treatment_type_intersection))
    treatment_comp_df.loc[~treatment_comp_df["treatment_type"].str.contains('Systemic therapy', na=False), ['sys_therapy_complete']] = None

    radiation_treatment_list = list(treatment_comp_df.loc[treatment_comp_df['treatment_type'].str.contains('Radiation therapy', na=False), 'submitter_treatment_id'])
    radiation_treatment_type_intersection = set(radiation_treatment_list).intersection(
        set(radiation_count_df['submitter_treatment_id']))
    treatment_comp_df["radiation_complete"] = (
                treatment_comp_df['treatment_type'].str.contains('Radiation therapy', na=False) &
                treatment_comp_df['submitter_treatment_id'].isin(radiation_treatment_type_intersection))
    treatment_comp_df.loc[~treatment_comp_df["treatment_type"].str.contains('Radiation therapy', na=False), [
        'radiation_complete']] = None
    surgery_treatment_list = list(treatment_comp_df.loc[treatment_comp_df['treatment_type'].str.contains('Surgery', na=False), 'submitter_treatment_id'])
    surgery_treatment_type_intersection = set(surgery_treatment_list).intersection(
        set(surgery_count_df['submitter_treatment_id']))
    treatment_comp_df["surgery_complete"] = (
            treatment_comp_df['treatment_type'].str.contains('Surgery', na=False) &
            treatment_comp_df['submitter_treatment_id'].isin(surgery_treatment_type_intersection))
    treatment_comp_df.loc[~treatment_comp_df["treatment_type"].str.contains('Surgery', na=False), [
        'surgery_complete']] = None
    treatment_comp_df['treatment_complete'] = ~treatment_comp_df[['sys_therapy_complete', "radiation_complete", "surgery_complete"]].eq(False).any(axis=1)
    complete_treatments = pd.merge(treatment_count_df,
                                   treatment_comp_df.loc[:, ['submitter_donor_id', 'treatment_complete']].
                                   groupby("submitter_donor_id").sum(), on="submitter_donor_id", how="left")
    complete_treatments["treatment_donor_complete"] = complete_treatments["treatment_complete"] == complete_treatments["total_count"]
    return complete_treatments


def get_samples_completeness():
    sample_comp_df = pd.read_csv("fullsome_sample_completeness.csv")
    sample_count_df = (pd.read_csv("fullsome_sample_count.csv").drop('submitter_treatment_id', axis=1).rename(
        columns={'count': 'total_count'}))
    # if donor.is_deceased == Yes, date_of_death not null, cause_of_death not null
    tumour_types = ['Metastatic tumour - additional metastatic', 'Metastatic tumour - metastasis local to lymph node',
                    'Metastatic tumour - metastasis to distant location',
                    'Metastatic tumour, Primary tumour - additional new primary', 'Primary tumour - adjacent to normal',
                    'Primary tumour',
                    'Recurrent tumour', 'Tumour - unknown if derived from primary or metastatic tumour']
    # if sample.specimen_type in tumour types, specimen.tumour_histological_type, reference_pathology_confirmed_diagnosis, reference_pathology_confirmed_tumour_presence, tumour_grading_system, tumour_grade, percent_tumour_cells_range, percent_tumour_cells_measurement_method not null
    # clinical_tumour_staging_system | pathological_tumour_staging_system not null
    # if staging_system contains AJCC, t,n,m categories not null

    print("hello")


def main():
    args = parse_args()
    # get data for clinical postgresdb
    for script in glob.glob('*.sql'):
        _run_sql_script(script)
    # program_minimal_complete_df, complete_donor_samples_df = get_minimal_completeness()
    # followup_comp_df = get_followups_completeness()
    # comorbidity_comp_df = get_comorbidity_completeness()
    # radiations_comp_df = get_radiations_completeness()
    # surgeries_comp_df = get_surgeries_completeness()
    # sys_therapies_comp_df = get_sys_therapy_completeness()
    # treatments_comp_df = get_treatments_completeness()
    # samples_comp_df = get_samples_completeness()
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