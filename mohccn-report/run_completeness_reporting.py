import copy

import pandas as pd
import argparse
import requests as rq
import subprocess
import sys
import glob
import datetime
import pprint
from pathlib import Path

PSQL_USER="admin"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--psql-user', type=str, required=False, default="admin", help="Username of the postgres admin user, DEFAULT=admin")
    parser.add_argument('--token', type=str, required=True, help="site admin token for the candig deployment you are retrieving data from.")
    parser.add_argument('--url', type=str, required=True, help="URL of the candig deployment you are retrieving data from")
    parser.add_argument('--node', type=str, required=True, help="name of the node running the report, e.g. UHN")
    parser.add_argument('--no-sql', action="store_true", required=False, help="don't run the sql reports again, mainly used for debugging")
    parser.add_argument('--dont-delete-sql-outputs', action="store_true", required=False, help="don't delete the sql outputs, mainly used for debugging")
    args = parser.parse_args()
    return args


# We don't use this for now since the auto completeness is not useful
# def get_site_data(token, url):
#     print("Fetching data completeness data from CanDIG instance")
#     headers = {"Authorization": f"Bearer {token}",
#                "Content-Type": "application/json; charset=utf-8"
#                }
#     response = rq.get(f"{url}/query/discovery/programs", headers=headers)
#     if response:
#         full_clinical_completeness = {
#             "program_id": [],
#             "total_donors": [],
#             "complete_donors": [],
#             "cases_missing_data": []
#         }
#         for program in response.json()['programs']:
#             full_clinical_completeness['program_id'].append(program['program_id'])
#             full_clinical_completeness['total_donors'].append(program['metadata']['summary_cases']['total_cases'])
#             full_clinical_completeness['complete_donors'].append(program['metadata']['summary_cases']['complete_cases'])
#             full_clinical_completeness['cases_missing_data'].append(program['metadata']['cases_missing_data'])
#         return pd.DataFrame(full_clinical_completeness)
#     else:
#         print("Could not retrieve programs, try getting a new token and run the script again.")
#         sys.exit()


def get_genomic_data_by_sql(sample_list):

    print(f"Fetching genomic object data from CanDIG instance at {url}")
    genomic_completeness_dict = {
        "program_id": [],
        "submitter_sample_id": [],
        "expression_file_count": [],
        "variant_sample_file_count": [],
        "read_file_count": []
    }
    sql_statement="SELECT drs_object_1.name, drs_object_1.id, drs_object_1.program_id, drs_object_1.description, drs_object_2.id AS id_1, drs_object_2.description AS analysis_type, content_object.id AS id_2, content_object.drs_object_id, content_object.name AS analysis_name, content_object.contents_id, content_object.drs_uri, content_object.contents FROM content_object JOIN drs_object AS drs_object_1 ON content_object.drs_object_id = drs_object_1.id JOIN drs_object AS drs_object_2 ON content_object.contents_id = drs_object_2.id WHERE drs_object_1.description IN ('wgs', 'wts')"

    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json; charset=utf-8"}
    response = rq.post(f"{url}/drs/ga4gh/drs/v1/experiments", headers=headers,
                       json={"submitter_sample_ids": sample_list})
    if response.status_code == 200:
        """every sample should have 2 genomes, 1 transcriptome"""
        experiment_objects = response.json()
        if experiment_objects and len(experiment_objects) > 0:
            for obj in experiment_objects:
                genomic_completeness_dict['program_id'].append(obj['program'])
                genomic_completeness_dict['submitter_sample_id'].append(obj['experiment_id'])
                genomic_completeness_dict['expression_file_count'].append(len(obj['expressions']))
                genomic_completeness_dict['variant_sample_file_count'].append(len(obj['variants']))
                genomic_completeness_dict['read_file_count'].append(len(obj['reads']))
            genomic_completeness_df = pd.DataFrame(genomic_completeness_dict)
            return genomic_completeness_df
        else:
            return pd.DataFrame(genomic_completeness_dict)
    elif response.status_code == 401:
        print(f"Response status code: {response.status_code}")
        print(f"Returned response:")
        pprint.pprint(response.json())
        print("Could not retrieve genomic data, try getting a new token and run the script again.")
        sys.exit()
    else:
        print(f"Response status code: {response.status_code}")
        print(f"Returned response:")
        pprint.pprint(response.json())
        print("WARN: Could not retrieve genomic data, continuing but if you have genomic data ingested, please reach out for help to debug this.")
        return pd.DataFrame(genomic_completeness_dict)


def get_genomic_data(token, url, sample_list):
    print(f"Fetching genomic object data from CanDIG instance at {url}")
    genomic_completeness_dict = {
        "program_id": [],
        "submitter_sample_id": [],
        "expression_file_count": [],
        "variant_sample_file_count": [],
        "read_file_count": []
    }
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json; charset=utf-8"}
    response = rq.post(f"{url}/drs/ga4gh/drs/v1/experiments", headers=headers,
                       json={"submitter_sample_ids": sample_list})
    if response.status_code == 200:
        """every sample should have 2 genomes, 1 transcriptome"""
        experiment_objects = response.json()
        if experiment_objects and len(experiment_objects) > 0:
            for obj in experiment_objects:
                genomic_completeness_dict['program_id'].append(obj['program'])
                genomic_completeness_dict['submitter_sample_id'].append(obj['experiment_id'])
                genomic_completeness_dict['expression_file_count'].append(len(obj['expressions']))
                genomic_completeness_dict['variant_sample_file_count'].append(len(obj['variants']))
                genomic_completeness_dict['read_file_count'].append(len(obj['reads']))
            genomic_completeness_df = pd.DataFrame(genomic_completeness_dict)
            return genomic_completeness_df
        else:
            return pd.DataFrame(genomic_completeness_dict)
    elif response.status_code == 401:
        print(f"Response status code: {response.status_code}")
        print(f"Returned response:")
        pprint.pprint(response.json())
        print("Could not retrieve genomic data, try getting a new token and run the script again.")
        sys.exit()
    else:
        print(f"Response status code: {response.status_code}")
        print(f"Returned response:")
        pprint.pprint(response.json())
        print("WARN: Could not retrieve genomic data, continuing but if you have genomic data ingested, please reach out for help to debug this.")
        return pd.DataFrame(genomic_completeness_dict)


def check_sample_tier_a_completeness(sample_types: list):
    """
    A donor is considered Tier A complete if there are:
       - 1 normal DNA
       - 1 tumour DNA
       - 1 tumour RNA
    """
    dna_values = ["Total DNA", "Amplified DNA", "ctDNA", "Other DNA enrichments", "Whole cell - DNA"]
    rna_values = ["Total RNA", "Other RNA fractions", "polyA+ RNA", "rRNA-depleted RNA", "Whole cell - RNA"]
    normal_dna_count = 0
    tumour_dna_count = 0
    tumour_rna_count = 0
    for sample_type in sample_types:
        split_type = sample_type.split("~")
        if split_type[0] == "Normal" and split_type[1] in dna_values:
            normal_dna_count += 1
        if split_type[0] == "Tumour":
            if split_type[1] in rna_values:
                tumour_rna_count += 1
            elif split_type[1] in dna_values:
                tumour_dna_count += 1
    if normal_dna_count >= 1 and tumour_dna_count >= 1 and tumour_rna_count >= 1:
        return True
    else:
        return False


def check_sample_tier_b_completeness(sample_types: list):
    """
    A donor is considered Tier B complete if there are:
       - 1 normal DNA
       - 1 tumour DNA
    """
    dna_values = ["Total DNA", "Amplified DNA", "ctDNA", "Other DNA enrichments", "Whole cell - DNA"]
    normal_dna_count = 0
    tumour_dna_count = 0
    for sample_type in sample_types:
        split_type = sample_type.split("~")
        if split_type[0] == "Normal" and split_type[1] in dna_values:
            normal_dna_count += 1
        elif split_type[0] == "Tumour" and split_type[1] in dna_values:
            tumour_dna_count += 1
    if normal_dna_count >= 1 and tumour_dna_count >= 1:
        return True
    else:
        return False


def check_genomic_tier_a_completeness(genomic_stats):
    """
    A donor is considered tier a complete for genomic files if they have:
       - 1 normal DNA sample with 1 variant file
       - 1 tumour DNA sample with 1 variant file
       - 1 tumour RNA sample with 1 expression file
    """
    normal_dna_variant_count = 0
    tumour_dna_variant_count = 0
    tumour_rna_expressions_count = 0
    if len(genomic_stats.loc[(genomic_stats['expression_file_count'] >= 1) &
                             (genomic_stats['tumour_normal_designation'] == "Tumour")]) > 0:
        tumour_rna_expressions_count = len(genomic_stats.loc[(genomic_stats['expression_file_count'] >= 1) &
                                                             (genomic_stats['tumour_normal_designation'] == "Tumour")])
    if len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                             (genomic_stats['tumour_normal_designation'] == "Normal")]) > 0:
        normal_dna_variant_count = len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                                                         (genomic_stats['tumour_normal_designation'] == "Normal")])
    if len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                             (genomic_stats['tumour_normal_designation'] == "Tumour")]) > 0:
        tumour_dna_variant_count = len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                                                         (genomic_stats['tumour_normal_designation'] == "Tumour")])
    if all([normal_dna_variant_count, tumour_rna_expressions_count, tumour_dna_variant_count]) > 0:
        return True
    else:
        return False


def check_genomic_tier_b_completeness(genomic_stats):
    """
    A donor is considered tier b complete for genomic files if they have:
       - 1 normal DNA sample with 1 variant file and 1 reads file
       - 1 tumour DNA sample with 1 variant file and 1 reads file
    """
    normal_dna_variant_count = 0
    tumour_dna_variant_count = 0
    if len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                             (genomic_stats['tumour_normal_designation'] == "Normal")]) > 0:
        normal_dna_variant_count = len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                                                         (genomic_stats['tumour_normal_designation'] == "Normal")])
    if len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                             (genomic_stats['tumour_normal_designation'] == "Tumour")]) > 0:
        tumour_dna_variant_count = len(genomic_stats.loc[(genomic_stats['variant_sample_file_count'] >= 1) &
                                                         (genomic_stats['tumour_normal_designation'] == "Tumour")])
    if all([normal_dna_variant_count, tumour_dna_variant_count]) > 0:
        return True
    else:
        return False


def _run_sql_script(script_name, prefix, db_id):
    """copy script to the docker container, run script, copy outputs, delete outputs"""

    # put all fo the sql outputs into a single sql_output dir, not seperate clinical and drs
    script_name = script_name.replace(f"{db_id}/","")
    stem_name = script_name.split(".sql")[0]
    subprocess.run(["docker", "cp", script_name, f"candigv2_postgres-db_1:/tmp/{script_name}"])
    result = subprocess.run(
        [f"docker exec -i candigv2_postgres-db_1 psql -U {PSQL_USER} -d {db_id} -f /tmp/{script_name}"],
        shell=True, stdout=subprocess.PIPE)
    if stem_name not in ['minimal', 'failed_minimal']:
        subprocess.run(
            ["docker", "cp", f"candigv2_postgres-db_1:/tmp/{stem_name}_count.csv", f"sql_outputs/{stem_name}_count.csv"])
        #subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{stem_name}_count.csv"])
    subprocess.run(
        ["docker", "cp", f"candigv2_postgres-db_1:/tmp/{stem_name}_completeness.csv", f"sql_outputs/{stem_name}_completeness.csv"])
    #subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{stem_name}_completeness.csv"])
    #subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{script_name}"])
    if stem_name == "failed_minimal":
        subprocess.run(["cp", "sql_outputs/failed_minimal_completeness.csv", f"./{prefix}failed_minimal_completeness.csv"])


def bool_str_map(bool_to_map: bool):
    if bool_to_map:
        return "yes"
    else:
        return "no"


def get_minimal_completeness():
    minimal_completeness_df = pd.read_csv("sql_outputs/minimal_completeness.csv", dtype="str")
    minimal_completeness_df['combined_sample_type'] = (
                minimal_completeness_df['tumour_normal_designation'].astype(str) +
                "~" + minimal_completeness_df['sample_type'].astype(str))
    donor_grouped_sample = minimal_completeness_df.groupby(['program_id_id', 'submitter_donor_id'])[
        'combined_sample_type'].agg(list).reset_index()
    donor_grouped_sample['tier_a_samples_complete'] = donor_grouped_sample['combined_sample_type'].map(
        check_sample_tier_a_completeness)
    donor_grouped_sample['tier_b_samples_complete'] = donor_grouped_sample['combined_sample_type'].map(
        check_sample_tier_b_completeness)
    minimal_tier_a_complete_donor_list = list(
        donor_grouped_sample.loc[donor_grouped_sample['tier_a_samples_complete']].submitter_donor_id)
    minimal_tier_b_complete_donor_list = list(
        donor_grouped_sample.loc[donor_grouped_sample['tier_b_samples_complete']].submitter_donor_id)
    minimal_tier_b_complete_donor_list = list(set(minimal_tier_b_complete_donor_list) - set(minimal_tier_a_complete_donor_list))
    minimal_completeness_df['tier_a_clinical_complete'] = minimal_completeness_df['submitter_donor_id'].isin(
        minimal_tier_a_complete_donor_list)
    minimal_completeness_df['tier_b_clinical_complete'] = minimal_completeness_df['submitter_donor_id'].isin(
        minimal_tier_b_complete_donor_list)
    program_minimal_tier_a_complete_df = donor_grouped_sample.loc[
        donor_grouped_sample['tier_a_samples_complete']].groupby('program_id_id').size().to_frame(
        'minimal_complete_clinical_count').reset_index()
    program_minimal_tier_b_complete_df = donor_grouped_sample.loc[
        donor_grouped_sample['tier_b_samples_complete']].groupby('program_id_id').size().to_frame(
        'minimal_complete_clinical_count').reset_index()
    return program_minimal_tier_a_complete_df, program_minimal_tier_b_complete_df, minimal_completeness_df


def check_column_equality(row, col1, col2):
    if row[col1] == row[col2]:
        return True
    else:
        return False


def get_comorbidity_completeness():
    """technically I should check to make sure every time prior_malignancy is listed, the type code is a cancer but I
    don't have time to do that right now.
    For now I will just compare the number of complete comorbidities vs non-complete"""
    comorbidity_comp_df = pd.read_csv("sql_outputs/fullsome_comorbidity_completeness.csv", dtype="str")
    comorbidity_count_df = pd.read_csv("sql_outputs/fullsome_comorbidity_count.csv").rename(columns={'count': 'total_count'})
    comorbidity_comp_df = comorbidity_comp_df.loc[:,
                          ['program_id_id', 'submitter_donor_id', 'prior_malignancy']].groupby(
        ['program_id_id', 'submitter_donor_id'], as_index=False).count().rename(
        columns={'prior_malignancy': 'complete_count'})
    comorbidity_comp_df = pd.merge(comorbidity_count_df, comorbidity_comp_df,
                                   on=['program_id_id', 'submitter_donor_id'], how="left")
    comorbidity_comp_df['donor_comorbidities_complete'] = comorbidity_comp_df['complete_count'] == comorbidity_comp_df[
        'total_count']
    return comorbidity_comp_df.loc[:, ['program_id_id', 'submitter_donor_id', 'total_count', 'complete_count',
                                       'donor_comorbidities_complete']].rename(
        columns={'total_count': 'comorbidity_total_count'})


def get_followups_completeness():
    followup_comp_df = pd.read_csv("sql_outputs/fullsome_followup_completeness.csv", dtype="str")
    followup_count_df = pd.read_csv("sql_outputs/fullsome_followup_count.csv").rename(columns={'count': 'total_count'})
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
    followup_donor_complete = pd.merge(followup_count_df.loc[:, ['program_id_id', 'submitter_donor_id', 'total_count']],
                                       followup_donor_complete,
                                       on=['program_id_id', 'submitter_donor_id'], how="left")
    followup_donor_complete['donor_followups_complete'] = (followup_donor_complete['complete_followup'] ==
                                                           followup_donor_complete['total_count'])
    return followup_donor_complete.rename(columns={"total_count": "followups_total_count"})


def get_radiations_completeness():
    radiation_comp_df = pd.read_csv("sql_outputs/fullsome_treatments_radiation_completeness.csv", dtype="str")
    radiation_count_df = pd.read_csv("sql_outputs/fullsome_treatments_radiation_count.csv").drop('submitter_treatment_id',
                                                                                     axis=1).groupby(
        ['program_id_id', 'submitter_donor_id'], as_index=False).sum().rename(columns={'count': 'total_count'})
    complete_radiations = pd.merge(radiation_count_df, radiation_comp_df.loc[:, ['program_id_id', 'submitter_donor_id',
                                                                                 'treatment_type']].groupby(
        ['program_id_id', 'submitter_donor_id'], as_index=False).count().rename(columns={"treatment_type": "complete_count"}),
                                   on=['program_id_id', 'submitter_donor_id'], how="left")
    complete_radiations['radiation_donor_complete'] = complete_radiations['complete_count'] == complete_radiations[
        'total_count']
    return complete_radiations.rename(columns={"total_count": "radiations_total_count"})


def get_surgeries_completeness():
    surgery_comp_df = pd.read_csv("sql_outputs/fullsome_treatments_surgery_completeness.csv", dtype="str")
    surgery_count_df = pd.read_csv("sql_outputs/fullsome_treatments_surgery_count.csv").drop('submitter_treatment_id',
                                                                                 axis=1).groupby(
        ['program_id_id', 'submitter_donor_id'], as_index=False).sum().rename(columns={'count': 'total_count'})
    surgery_specimens = pd.read_csv("sql_outputs/fullsome_specimen_completeness.csv")
    exception_treatments = list(
        surgery_specimens.loc[surgery_specimens['submitter_treatment_id'].notna()].submitter_treatment_id)
    surgery_comp_df['treatment_exception'] = surgery_comp_df['submitter_treatment_id'].isin(exception_treatments)
    surgery_comp_df['surgery_complete'] = (surgery_comp_df['treatment_exception'] |
                                           (surgery_comp_df['surgery_site'].notna() &
                                            surgery_comp_df['surgery_location'].notna()))
    complete_surgeries = pd.merge(surgery_count_df, surgery_comp_df.loc[:, ["program_id_id", "submitter_donor_id", "surgery_complete"]]
                                  .groupby(["program_id_id", "submitter_donor_id"], as_index=False).sum(),
                                  on=["program_id_id", "submitter_donor_id"], how="left")
    complete_surgeries["surgery_donor_complete"] = (complete_surgeries['surgery_complete'] ==
                                                    complete_surgeries['total_count'])
    return complete_surgeries.rename(columns={"total_count": "surgeries_total_count"})


def get_sys_therapy_completeness():
    sys_therapy_comp_df = pd.read_csv("sql_outputs/fullsome_treatments_sys_therapy_completeness.csv",
                                      dtype="str")
    sys_therapy_count_df = (pd.read_csv("sql_outputs/fullsome_treatments_sys_therapy_count.csv").drop('submitter_treatment_id', axis=1).
                            groupby(['program_id_id', 'submitter_donor_id'], as_index=False).sum().rename(
                            columns={'count': 'total_count'}))
    sys_therapy_comp_df["sys_therapy_complete"] = ((sys_therapy_comp_df['drug_dose_units'].isna() &
                                                   sys_therapy_comp_df['prescribed_cumulative_drug_dose'].isna() &
                                                   sys_therapy_comp_df['actual_cumulative_drug_dose'].isna()) |
                                                   ((sys_therapy_comp_df['prescribed_cumulative_drug_dose'].notna() |
                                                    sys_therapy_comp_df['actual_cumulative_drug_dose'].notna()) &
                                                   sys_therapy_comp_df['drug_dose_units'].notna()))
    complete_sys_therapies = pd.merge(sys_therapy_count_df,
                                      sys_therapy_comp_df.loc[:, ["program_id_id", "submitter_donor_id", 'sys_therapy_complete']].
                                      groupby(["program_id_id", "submitter_donor_id"], as_index=False).sum(), on=["program_id_id", "submitter_donor_id"],
                                      how="left")
    complete_sys_therapies["sys_therapy_donor_complete"] = complete_sys_therapies["total_count"] == complete_sys_therapies["sys_therapy_complete"]
    return complete_sys_therapies.rename(columns={"total_count": "sys_therapies_total_count"})


def get_treatments_completeness():
    treatment_comp_df = pd.read_csv("sql_outputs/fullsome_treatments_completeness.csv", dtype="str")
    sys_therapy_count_df = pd.read_csv("sql_outputs/fullsome_treatments_sys_therapy_count.csv")
    radiation_count_df = pd.read_csv("sql_outputs/fullsome_treatments_radiation_count.csv").rename(columns={'count': 'total_count'})
    surgery_count_df = pd.read_csv("sql_outputs/fullsome_treatments_surgery_count.csv").rename(columns={'count': 'total_count'})
    treatment_count_df = pd.read_csv("sql_outputs/fullsome_treatments_count.csv").rename(
        columns={'count': 'total_count'})
    sys_therapy_treatment_list = list(treatment_comp_df.loc[treatment_comp_df['treatment_type'].str.contains('Systemic therapy', na=False), 'submitter_treatment_id'])
    sys_therapy_treatment_type_intersection = set(sys_therapy_treatment_list).intersection(set(sys_therapy_count_df['submitter_treatment_id']))
    treatment_comp_df["sys_therapy_complete"] = (treatment_comp_df['treatment_type'].str.contains(
        'Systemic therapy', na=False) & treatment_comp_df[
        'submitter_treatment_id'].isin(sys_therapy_treatment_type_intersection))
    treatment_comp_df["sys_therapy_complete"] = treatment_comp_df["sys_therapy_complete"].apply(lambda x: bool_str_map(x))
    treatment_comp_df.loc[~treatment_comp_df["treatment_type"].str.contains('Systemic therapy', na=False), ['sys_therapy_complete']] = None

    radiation_treatment_list = list(treatment_comp_df.loc[treatment_comp_df['treatment_type'].str.contains('Radiation therapy', na=False), 'submitter_treatment_id'])
    radiation_treatment_type_intersection = set(radiation_treatment_list).intersection(
        set(radiation_count_df['submitter_treatment_id']))
    treatment_comp_df["radiation_complete"] = (
                treatment_comp_df['treatment_type'].str.contains('Radiation therapy', na=False) &
                treatment_comp_df['submitter_treatment_id'].isin(radiation_treatment_type_intersection))
    treatment_comp_df["radiation_complete"] = treatment_comp_df["radiation_complete"].apply(lambda x: bool_str_map(x))
    treatment_comp_df.loc[~treatment_comp_df["treatment_type"].str.contains('Radiation therapy', na=False), [
        'radiation_complete']] = None
    surgery_treatment_list = list(treatment_comp_df.loc[treatment_comp_df['treatment_type'].str.contains('Surgery', na=False), 'submitter_treatment_id'])
    surgery_treatment_type_intersection = set(surgery_treatment_list).intersection(
        set(surgery_count_df['submitter_treatment_id']))
    treatment_comp_df["surgery_complete"] = (
            treatment_comp_df['treatment_type'].str.contains('Surgery', na=False) &
            treatment_comp_df['submitter_treatment_id'].isin(surgery_treatment_type_intersection))
    treatment_comp_df["surgery_complete"] = treatment_comp_df["surgery_complete"].apply(lambda x: bool_str_map(x))
    treatment_comp_df.loc[~treatment_comp_df["treatment_type"].str.contains('Surgery', na=False), [
        'surgery_complete']] = None
    treatment_comp_df['treatment_complete'] = ~treatment_comp_df[['sys_therapy_complete', "radiation_complete", "surgery_complete"]].eq(False).any(axis=1)
    complete_treatments = pd.merge(treatment_count_df,
                                   treatment_comp_df.loc[:, ['program_id_id', 'submitter_donor_id', 'treatment_complete']].
                                   groupby(["program_id_id", "submitter_donor_id"], as_index=False).sum(), on=["program_id_id", "submitter_donor_id"], how="left")
    complete_treatments["treatment_donor_complete"] = complete_treatments["treatment_complete"] == complete_treatments["total_count"]
    return complete_treatments.rename(columns={"total_count": "treatments_total_count"})


def get_primary_diagnosis_completeness():
    pd_comp_df = pd.read_csv("sql_outputs/fullsome_primary_diagnosis_completeness.csv",
                             dtype='str')
    pd_count_df = (pd.read_csv("sql_outputs/fullsome_primary_diagnosis_count.csv").rename(
        columns={'count': 'total_count'}))
    pd_comp_df["staging_present"] = ((pd_comp_df['clinical_tumour_staging_system'].notna() & pd_comp_df['clinical_stage_group'].notna()) |
                                     (pd_comp_df['pathological_tumour_staging_system'].notna() & pd_comp_df['pathological_stage_group'].notna()))
    # Check tnms complete if AJCC used for staging, only return False if AJCC was selected, otherwise true
    pd_comp_df["clinical_ajcc_tnm_present"] = ((pd_comp_df['clinical_tumour_staging_system'].str.contains("AJCC") &
                                                pd_comp_df['clinical_t_category'].notna() & pd_comp_df[
                                                    'clinical_n_category'].notna() & pd_comp_df[
                                                    'clinical_m_category'].notna()) |
                                               (~pd_comp_df['clinical_tumour_staging_system'].str.contains("AJCC",
                                                                                                           na=False)))
    pd_comp_df["pathological_ajcc_tnm_present"] = (
                (pd_comp_df['pathological_tumour_staging_system'].str.contains("AJCC", na=False) &
                 pd_comp_df['pathological_t_category'].notna() & pd_comp_df[
                     'pathological_n_category'].notna() & pd_comp_df[
                     'pathological_m_category'].notna()) |
                (~pd_comp_df['pathological_tumour_staging_system'].str.contains("AJCC", na=False)))
    pd_comp_df['pd_complete'] = (pd_comp_df['staging_present'] & pd_comp_df['clinical_ajcc_tnm_present'] &
                                 pd_comp_df['pathological_ajcc_tnm_present'])
    complete_pd_df = pd.merge(pd_count_df, pd_comp_df.loc[:, ['program_id_id', 'submitter_donor_id', 'pd_complete']].groupby(['program_id_id', 'submitter_donor_id'], as_index=False).sum(), on=['program_id_id', 'submitter_donor_id'], how="left")
    complete_pd_df['pd_donor_complete'] = complete_pd_df['total_count'] == complete_pd_df['pd_complete']
    return complete_pd_df.rename(columns={"total_count": "pd_total_count"})


def get_specimens_completeness():
    spec_comp_df = pd.read_csv("sql_outputs/fullsome_specimen_completeness.csv", dtype="str")
    spec_count_df = (pd.read_csv("sql_outputs/fullsome_specimen_count.csv").rename(columns={'count': 'total_count'}))
    spec_comp_df['tumour_spec_complete'] = (
                (spec_comp_df['tumour_normal_designation'].str.contains('Tumour') &
                 spec_comp_df['tumour_histological_type'].notna() &
                 spec_comp_df['reference_pathology_confirmed_diagnosis'].notna() &
                 spec_comp_df['reference_pathology_confirmed_tumour_presence'].notna() &
                 spec_comp_df['tumour_grading_system'].notna() &
                 spec_comp_df['tumour_grade'].notna() &
                 spec_comp_df['percent_tumour_cells_range'].notna() &
                 spec_comp_df['percent_tumour_cells_range'].notna() &
                 spec_comp_df['percent_tumour_cells_measurement_method'].notna()
                 ) | (spec_comp_df['tumour_normal_designation'].str.contains('Normal')))
    complete_specimens_df = pd.merge(
        spec_count_df.drop('submitter_specimen_id', axis=1).groupby(['program_id_id', 'submitter_donor_id'],
                                                                    as_index=False).sum(),
        spec_comp_df.loc[:,
        ['program_id_id', 'submitter_donor_id', 'tumour_spec_complete']].groupby(['program_id_id', 'submitter_donor_id'], as_index=False).sum(),
        on=["program_id_id", "submitter_donor_id"], how="left")
    complete_specimens_df['specimen_donor_complete'] = complete_specimens_df['total_count'] == complete_specimens_df[
        'tumour_spec_complete']
    return complete_specimens_df.rename(columns={"total_count": "specimens_total_count"})


def get_samples_completeness():
    samp_comp_df = pd.read_csv("sql_outputs/fullsome_sample_completeness.csv", dtype="str")
    samp_count_df = pd.read_csv("sql_outputs/fullsome_sample_count.csv")
    samp_count_df['total_count'] = 1
    samp_count_df = samp_count_df.groupby(['program_id_id', 'submitter_donor_id'], as_index=False).sum()
    samp_comp_df['complete_samples_count'] = 1
    samp_comp_df = samp_comp_df.drop(['submitter_sample_id'], axis=1).groupby(['program_id_id', 'submitter_donor_id']).sum()
    samples_complete = pd.merge(samp_count_df, samp_comp_df, on=['program_id_id', 'submitter_donor_id'], how="left")
    samples_complete['sample_donor_complete'] = samples_complete['total_count'] == samples_complete['complete_samples_count']
    return samples_complete.rename(columns={'total_count': 'samples_total_count'})


def get_donors_completeness():
    donor_comp_df = pd.read_csv("sql_outputs/fullsome_donor_completeness.csv", dtype="str")
    donor_count_df = (pd.read_csv("sql_outputs/fullsome_donor_count.csv").rename(columns={'count': 'total_count'}))
    donor_comp_df['vital_status_complete'] = ((donor_comp_df['is_deceased'].str.contains('Yes') &
                                              donor_comp_df['cause_of_death'].notna() &
                                              donor_comp_df['date_of_death'].notna()) |
                                              donor_comp_df['is_deceased'].str.contains('No') |
                                              donor_comp_df['is_deceased'].str.contains('Not Available'))
    donor_comp_df = donor_comp_df.loc[:, ['program_id_id', 'submitter_donor_id', 'vital_status_complete']].groupby(['program_id_id', 'submitter_donor_id'], as_index=False).sum()
    donors_complete = pd.merge(donor_count_df, donor_comp_df, on=['program_id_id', 'submitter_donor_id'], how='left')
    donors_complete['donor_obj_complete'] = donors_complete['total_count'] == donors_complete['vital_status_complete']
    return donors_complete.rename(columns={'total_count': 'donorobj_total_count'})


def main():
    args = parse_args()
    clean_url = args.url.rstrip('/')
    file_prefix = datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + '-' + args.node + '-'
    # get data for clinical postgresdb
    if not args.no_sql:
        print("Fetching data from clinical postgres database")
        subprocess.run(["mkdir", "sql_outputs"])
        for script in glob.glob('clinical/*.sql'):
            _run_sql_script(script, file_prefix,'clinical')
        for script in glob.glob('drs/*.sql'):
            _run_sql_script(script, file_prefix,'drs')
    else:
        print("Not fetching new sql data")
    if not Path("sql_outputs").is_dir():
        print("sql_outputs dir not found, please run script again and ensure --no-sql not specified.")
        sys.exit()
    # Get minimal clinical Completeness stats
    (program_minimal_tier_a_complete_df, program_minimal_tier_b_complete_df,
     complete_donor_samples_df) = get_minimal_completeness()
    failed_minimal_summary = pd.read_csv(f"{file_prefix}failed_minimal_completeness.csv")
    failed_summary_bools = failed_minimal_summary[
        ['gender', 'sex_at_birth', 'date_of_birth', 'date_resolution', 'date_of_diagnosis',
         'cancer_type_code', 'primary_site', 'basis_of_diagnosis', 'cancer_type_code',
         'primary_site', 'basis_of_diagnosis', 'specimen_collection_date',
         'specimen_anatomic_location', 'tumour_normal_designation', 'sample_type',
         'specimen_type']].isnull()
    failed_minimal_program_summary = pd.concat([failed_minimal_summary[['program_id_id']], failed_summary_bools], axis=1).groupby('program_id_id', as_index=False).sum()
    failed_minimal_program_summary.to_csv(f"{file_prefix}per_program_failed_minimal_completeness.csv", index=False)
    complete_donor_samples_df.to_csv(f"{file_prefix}complete_donor_samples.csv", index=False)
    if len(complete_donor_samples_df) == 0:
        print("No minimal complete donors found in the instance")

    # Get Fullsome clinical completeness stats
    followup_comp_df = get_followups_completeness()
    comorbidity_comp_df = get_comorbidity_completeness()
    radiations_comp_df = get_radiations_completeness()
    surgeries_comp_df = get_surgeries_completeness()
    sys_therapies_comp_df = get_sys_therapy_completeness()
    treatments_comp_df = get_treatments_completeness()
    primary_diag_comp_df = get_primary_diagnosis_completeness()
    specimens_comp_df = get_specimens_completeness()
    samples_comp_df = get_samples_completeness()
    donors_comp_df = get_donors_completeness()
    joined_completeness = (
        donors_comp_df.merge(
            samples_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(primary_diag_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(followup_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(comorbidity_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(radiations_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(surgeries_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(sys_therapies_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(treatments_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(specimens_comp_df, on=["program_id_id", "submitter_donor_id"], how="left"))
    # Only count as not complete if any tests are False, nan means the donor didn't have that kind of object
    joined_completeness['donor_fullsome_complete'] = ((~joined_completeness['sample_donor_complete'].eq(False)) &
                                                      (~joined_completeness['donor_obj_complete'].eq(False)) &
                                                      (~joined_completeness['pd_donor_complete'].eq(False)) &
                                                      (~joined_completeness['donor_followups_complete'].eq(False)) &
                                                      (~joined_completeness['donor_comorbidities_complete'].eq(False)) &
                                                      (~joined_completeness['radiation_donor_complete'].eq(False)) &
                                                      (~joined_completeness['surgery_donor_complete'].eq(False)) &
                                                      (~joined_completeness['sys_therapy_donor_complete'].eq(False)) &
                                                      (~joined_completeness['treatment_donor_complete'].eq(False)) &
                                                      (~joined_completeness['specimen_donor_complete'].eq(False)))
    joined_completeness.sort_values(['program_id_id', 'submitter_donor_id']).to_csv(f"{file_prefix}per_donor_clinical_completeness_full_breakdown.csv", index=False)
    all_donor_df = donors_comp_df.loc[:, ["program_id_id", "submitter_donor_id"]]
    minimal_complete_donor_df = complete_donor_samples_df.loc[:, ['program_id_id', 'submitter_donor_id',
                                                                  'tier_a_clinical_complete',
                                                                  'tier_b_clinical_complete']].drop_duplicates(
    ).rename({'tier_a_clinical_complete': 'tier_a_minimal_clinical_complete',
              'tier_b_clinical_complete': 'tier_b_minimal_clinical_complete'})
    samples_count_df = pd.read_csv("sql_outputs/fullsome_sample_count.csv")
    sample_list = list(samples_count_df['submitter_sample_id'])
    donor_list = set(list(samples_count_df['submitter_donor_id']))
    samples_comp_df = pd.read_csv("sql_outputs/fullsome_sample_completeness.csv")
    samples_comp_df['combined_sample_type'] = (
            samples_comp_df['tumour_normal_designation'].astype(str) +
            "~" + samples_comp_df['sample_type'].astype(str))
    # Get genomic completeness status
    if len(sample_list) > 0:
        genomic_stats = get_genomic_data(args.token, clean_url, sample_list)
        if len(genomic_stats) > 0:
            genomic_stats.to_csv(f"{file_prefix}per_sample_genomic_stats.csv", index=False)
            genomic_stats = (pd.merge(genomic_stats, samples_count_df.rename(columns={"program_id_id": "program_id"}),
                                      on=["program_id", "submitter_sample_id"], how="left"))
            donor_genomic_status = {
                "submitter_donor_id": [],
                "tier_a_genomic_files_complete": [],
                "tier_b_genomic_files_complete": []
            }
            for donor in donor_list:
                donor_genomic_status['submitter_donor_id'].append(donor)
                donor_stats = genomic_stats.loc[genomic_stats['submitter_donor_id'] == donor]
                if len(donor_stats) == 0:
                    donor_genomic_status['tier_a_genomic_files_complete'].append(False)
                    donor_genomic_status['tier_b_genomic_files_complete'].append(False)
                else:
                    donor_tier_a_complete = check_genomic_tier_a_completeness(donor_stats)
                    donor_genomic_status['tier_a_genomic_files_complete'].append(donor_tier_a_complete)
                    if donor_tier_a_complete:
                        donor_genomic_status['tier_b_genomic_files_complete'].append(False)
                    else:
                        donor_tier_b_complete = check_genomic_tier_b_completeness(donor_stats)
                        donor_genomic_status['tier_b_genomic_files_complete'].append(donor_tier_b_complete)
            genomic_stats_per_donor = genomic_stats.groupby(['program_id', 'submitter_donor_id'], as_index=False).sum()
            full_genomic_stats = pd.merge(genomic_stats_per_donor, pd.DataFrame(donor_genomic_status),
                                          on='submitter_donor_id').loc[:, ['program_id', 'submitter_donor_id',
                                                                           'expression_file_count',
                                                                           'variant_sample_file_count', 'read_file_count',
                                                                           'tier_a_genomic_files_complete',
                                                                           'tier_b_genomic_files_complete']]
        else:
            print("WARN: No matching genomic information found for samples.")
            full_genomic_stats = copy.deepcopy(samples_count_df).groupby(['program_id_id', 'submitter_donor_id'],
                                                                         as_index=False).sum().drop('submitter_sample_id', axis=1).rename(columns={"program_id_id": "program_id"})
            full_genomic_stats.loc[:, ['expression_file_count', 'variant_sample_file_count', 'read_file_count']] = 0
            full_genomic_stats.loc[:, ['tier_a_genomic_files_complete', 'tier_b_genomic_files_complete']] = False
    else:
        print("WARN: No samples found in database.")
        full_genomic_stats = copy.deepcopy(samples_count_df).groupby(['program_id_id', 'submitter_donor_id'], as_index=False).sum().rename(columns={"program_id_id": "program_id"})
        full_genomic_stats.loc[:, ['expression_file_count', 'variant_sample_file_count', 'read_file_count']] = 0
        full_genomic_stats.loc[:, ['tier_a_genomic_files_complete','tier_b_genomic_files_complete']] = False

    clinical_genomic_completeness = joined_completeness.loc[:,
                                    ['program_id_id', 'submitter_donor_id', 'donor_fullsome_complete']].rename(
        columns={"program_id_id": "program_id"}).merge(full_genomic_stats, on=['program_id', 'submitter_donor_id'],
                                                       how='left').merge(
        minimal_complete_donor_df.rename(columns={"program_id_id": "program_id"}),
        on=['program_id', 'submitter_donor_id'], how='left')
    clinical_genomic_completeness['tier_a_full_complete'] = (clinical_genomic_completeness['tier_a_genomic_files_complete']
                                                             & clinical_genomic_completeness['tier_a_clinical_complete'])
    clinical_genomic_completeness['tier_b_full_complete'] = clinical_genomic_completeness[
                                                                'tier_b_genomic_files_complete'] & \
                                                            clinical_genomic_completeness['tier_b_clinical_complete']
    clinical_genomic_completeness['fully_fullsome_complete'] = (clinical_genomic_completeness['donor_fullsome_complete']
                                                                & clinical_genomic_completeness['tier_a_genomic_files_complete'])
    clinical_genomic_completeness.to_csv(f"{file_prefix}per_donor_full_completeness.csv", index=False)

    # summarize by program for report
    report_table = copy.deepcopy(clinical_genomic_completeness)
    report_table['donor_count'] = 1
    report_table = report_table.drop(['submitter_donor_id', 'donor_fullsome_complete', ], axis=1).groupby(['program_id'], as_index=False).sum()
    report_table['incomplete_donors'] = report_table['donor_count'] - (report_table['tier_a_full_complete'] +
                                                                       report_table['tier_b_full_complete'])
    report_table['node'] = args.node
    report_table = report_table[['node', 'program_id', 'donor_count', 'tier_a_full_complete',
                                 'tier_b_full_complete', 'incomplete_donors',
                                 'fully_fullsome_complete', 'tier_a_clinical_complete', 'tier_a_genomic_files_complete',
                                 'tier_b_clinical_complete', 'tier_b_genomic_files_complete']]
    report_table = report_table.rename(columns={'fully_fullsome_complete': 'fullsome_cg_complete'})
    report_table = report_table.fillna(0)
    report_table.replace(True, 1, inplace=True)
    report_table.replace(False, 0, inplace=True)
    report_table.to_csv(f"{file_prefix}per_program_completeness_report.csv", index=False)
    print(f"Summary Report saved to '{file_prefix}per_program_completeness_report.csv'")
    if args.dont_delete_sql_outputs:
        print("SQL outputs saved in sql_outputs/")
        print("All done!")
        sys.exit()
    else:
        print("Removing sql outputs...")
        subprocess.run(["rm", "-r", "sql_outputs"])
        print("All done!")
        sys.exit()


if __name__ == "__main__":
    main()
