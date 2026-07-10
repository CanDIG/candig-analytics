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

PSQL_USER = "admin"

# The required fields checked for MOHCCN minimal clinical completeness (see README).
MINIMAL_REQUIRED_FIELDS = [
    'gender', 'sex_at_birth', 'date_of_birth', 'date_resolution',
    'date_of_diagnosis', 'cancer_type_code', 'primary_site', 'basis_of_diagnosis',
    'specimen_collection_date', 'specimen_anatomic_location', 'specimen_tissue_source',
    'tumour_normal_designation', 'specimen_type', 'sample_type'
]

RELAPSE_PROGRESSION_STATUSES = ['Distant progression', 'Loco-regional progression',
                                'Progression not otherwise specified', 'Relapse or recurrence']


def _agg_field_score_by_donor(df, total_per_row, complete_per_row):
    """Sum per-row required/complete field counts up to one row per donor."""
    tmp = df.loc[:, ['program_id_id', 'submitter_donor_id']].copy()
    tmp['_total'] = total_per_row
    tmp['_complete'] = complete_per_row
    return tmp.groupby(['program_id_id', 'submitter_donor_id'], as_index=False)[['_total', '_complete']].sum()


def _parse_bool_flag(series):
    """
    Parse a boolean-typed database column that was read in as a string column (every all_*.sql
    frame is read with dtype="str" so that date/id columns aren't coerced by pandas' type
    inference). Postgres CSV export renders booleans as 't'/'f'; pandas-authored CSVs (e.g. our
    own synthetic test fixtures) may instead say 'True'/'False'. Either way, comparing the raw
    string to the Python bool True is always False, so this must be parsed explicitly rather than
    via `series.eq(True)`.
    """
    return series.astype(str).str.strip().str.lower().isin(['t', 'true', '1'])


def _record_pass_by_donor(df, total_per_row, complete_per_row, out_col):
    """
    Per donor: True if every record has complete_per_row == total_per_row, False if at least one
    record fails, NaN if the donor has zero records of this type (so it's excluded from
    AND-combination downstream when merged into tier_a/b_full_clinical_complete, matching the old
    SQL-filter pipeline's behaviour where a donor with no records of a given type simply never
    appears in that category's completeness file and so contributes NaN via the later left-merge).
    """
    tmp = df.loc[:, ['program_id_id', 'submitter_donor_id']].copy()
    tmp['_pass'] = (complete_per_row == total_per_row)
    grouped = tmp.groupby(['program_id_id', 'submitter_donor_id'], as_index=False)['_pass'].all()
    return grouped.rename(columns={'_pass': out_col})


def _treatment_base_pass(treatment_df, require_end_date_unconditionally):
    """
    Per-treatment-row pass/fail for the 5 base Treatment fields, keyed by
    (program_id_id, submitter_treatment_id). If require_end_date_unconditionally is True,
    treatment_end_date is required regardless of status_of_treatment (matches the old
    fullsome_treatments_radiation.sql / fullsome_treatments_surgery.sql queries, which never
    exempted "Treatment ongoing" for radiation/surgery); otherwise the "Treatment ongoing"
    exemption applies (matches the old fullsome_treatments.sql / fullsome_treatments_sys_therapy.sql
    queries).
    """
    base_ok = treatment_df[['treatment_type', 'is_primary_treatment', 'treatment_start_date',
                            'treatment_intent']].notna().all(axis=1)
    if require_end_date_unconditionally:
        end_date_ok = treatment_df['treatment_end_date'].notna()
    else:
        ongoing = treatment_df['status_of_treatment'].astype(str) == 'Treatment ongoing'
        end_date_ok = treatment_df['treatment_end_date'].notna() | ongoing
    result = treatment_df[['program_id_id', 'submitter_treatment_id']].copy()
    result['_treatment_base_pass'] = base_ok & end_date_ok
    return result


def _donor_object_field_score(df):
    """donor: gender, sex_at_birth, date_of_birth, date_resolution, is_deceased always required;
    cause_of_death & date_of_death required only if is_deceased == 'Yes'."""
    total = pd.Series(5, index=df.index)
    complete = (df['gender'].notna().astype(int) + df['sex_at_birth'].notna().astype(int) +
                df['date_of_birth'].notna().astype(int) + df['date_resolution'].notna().astype(int) +
                df['is_deceased'].notna().astype(int))
    deceased = df['is_deceased'].astype(str).str.strip() == 'Yes'
    total = total + deceased.astype(int) * 2
    complete = complete + (deceased & df['cause_of_death'].notna()).astype(int)
    complete = complete + (deceased & df['date_of_death'].notna()).astype(int)
    return _agg_field_score_by_donor(df, total, complete)


def _primary_diagnosis_field_score(df):
    """primary diagnosis: 4 always-required fields; staging_present (one clinical OR pathological
    stage pair) counted as 1 composite field; clinical/pathological T/N/M categories required only
    if that staging system is AJCC."""
    total = pd.Series(4, index=df.index)
    complete = (df['date_of_diagnosis'].notna().astype(int) + df['cancer_type_code'].notna().astype(int) +
                df['primary_site'].notna().astype(int) + df['basis_of_diagnosis'].notna().astype(int))

    total = total + 1
    clinical_pair = df['clinical_tumour_staging_system'].notna() & df['clinical_stage_group'].notna()
    pathological_pair = df['pathological_tumour_staging_system'].notna() & df['pathological_stage_group'].notna()
    complete = complete + (clinical_pair | pathological_pair).astype(int)

    clinical_ajcc = df['clinical_tumour_staging_system'].astype(str).str.contains('AJCC', na=False)
    total = total + clinical_ajcc.astype(int) * 3
    complete = complete + (clinical_ajcc & df['clinical_t_category'].notna()).astype(int)
    complete = complete + (clinical_ajcc & df['clinical_n_category'].notna()).astype(int)
    complete = complete + (clinical_ajcc & df['clinical_m_category'].notna()).astype(int)

    pathological_ajcc = df['pathological_tumour_staging_system'].astype(str).str.contains('AJCC', na=False)
    total = total + pathological_ajcc.astype(int) * 3
    complete = complete + (pathological_ajcc & df['pathological_t_category'].notna()).astype(int)
    complete = complete + (pathological_ajcc & df['pathological_n_category'].notna()).astype(int)
    complete = complete + (pathological_ajcc & df['pathological_m_category'].notna()).astype(int)
    return _agg_field_score_by_donor(df, total, complete)


def _specimen_field_score(df):
    """specimen: 2 always-required fields; 7 tumour-histology fields required only when
    tumour_normal_designation is Tumour."""
    total = pd.Series(2, index=df.index)
    complete = (df['specimen_collection_date'].notna().astype(int) +
                df['specimen_anatomic_location'].notna().astype(int))
    is_tumour = df['tumour_normal_designation'].astype(str).str.contains('Tumour', na=False)
    tumour_fields = ['tumour_histological_type', 'reference_pathology_confirmed_diagnosis',
                      'reference_pathology_confirmed_tumour_presence', 'tumour_grading_system', 'tumour_grade',
                      'percent_tumour_cells_range', 'percent_tumour_cells_measurement_method']
    total = total + is_tumour.astype(int) * len(tumour_fields)
    for field in tumour_fields:
        complete = complete + (is_tumour & df[field].notna()).astype(int)
    return _agg_field_score_by_donor(df, total, complete)


def _sample_registration_field_score(df):
    """sample registration: specimen_tissue_source, tumour_normal_designation, specimen_type,
    sample_type - all always required."""
    fields = ['specimen_tissue_source', 'tumour_normal_designation', 'specimen_type', 'sample_type']
    total = pd.Series(len(fields), index=df.index)
    complete = sum(df[field].notna().astype(int) for field in fields)
    return _agg_field_score_by_donor(df, total, complete)


def _followup_field_score(df):
    """follow-up: date_of_followup & disease_status_at_followup always required. If the followup
    reports relapse/progression, date_of_relapse, relapse_type, method_of_progression_status are
    also required, plus anatomic_site_progression_or_recurrence unless it's a Biochemical
    progression relapse."""
    total = pd.Series(2, index=df.index)
    complete = (df['date_of_followup'].notna().astype(int) + df['disease_status_at_followup'].notna().astype(int))
    relapse_prog = df['disease_status_at_followup'].isin(RELAPSE_PROGRESSION_STATUSES)
    total = total + relapse_prog.astype(int) * 3
    complete = complete + (relapse_prog & df['date_of_relapse'].notna()).astype(int)
    complete = complete + (relapse_prog & df['relapse_type'].notna()).astype(int)
    complete = complete + (relapse_prog & df['method_of_progression_status'].notna()).astype(int)
    biochemical = df['relapse_type'].astype(str) == 'Biochemical progression'
    anatomic_required = relapse_prog & ~biochemical
    total = total + anatomic_required.astype(int)
    complete = complete + (anatomic_required & df['anatomic_site_progression_or_recurrence'].notna()).astype(int)
    return _agg_field_score_by_donor(df, total, complete)


def _comorbidity_field_score(df):
    """comorbidity: prior_malignancy and comorbidity_type_code both always required."""
    fields = ['prior_malignancy', 'comorbidity_type_code']
    total = pd.Series(len(fields), index=df.index)
    complete = sum(df[field].notna().astype(int) for field in fields)
    return _agg_field_score_by_donor(df, total, complete)


def _treatment_field_score(df):
    """treatment (base record, shared by all treatment types): treatment_type, is_primary_treatment,
    treatment_start_date, treatment_intent always required; treatment_end_date required unless the
    treatment status is 'Treatment ongoing'."""
    total = pd.Series(4, index=df.index)
    complete = (df['treatment_type'].notna().astype(int) + df['is_primary_treatment'].notna().astype(int) +
                df['treatment_start_date'].notna().astype(int) + df['treatment_intent'].notna().astype(int))
    total = total + 1
    ongoing = df['status_of_treatment'].astype(str) == 'Treatment ongoing'
    complete = complete + (df['treatment_end_date'].notna() | ongoing).astype(int)
    return _agg_field_score_by_donor(df, total, complete)


def _radiation_field_score(df):
    """radiation (subtype-specific fields only - base treatment fields are scored separately):
    radiation_therapy_modality, radiation_therapy_type, anatomical_site_irradiated always required;
    fractions and dosage each required unless their "not available" flag is set."""
    total = pd.Series(3, index=df.index)
    complete = (df['radiation_therapy_modality'].notna().astype(int) +
                df['radiation_therapy_type'].notna().astype(int) +
                df['anatomical_site_irradiated'].notna().astype(int))
    total = total + 2
    fractions_ok = df['radiation_therapy_fractions'].notna() | _parse_bool_flag(
        df['radiation_therapy_fractions_not_available'])
    dosage_ok = df['radiation_therapy_dosage'].notna() | _parse_bool_flag(
        df['radiation_therapy_dosage_not_available'])
    complete = complete + fractions_ok.astype(int) + dosage_ok.astype(int)
    return _agg_field_score_by_donor(df, total, complete)


def _surgery_field_score(df, specimen_linked_treatment_ids):
    """surgery (subtype-specific fields only): surgery_reference_database and surgery_type always
    required. surgery_site and surgery_location required unless the treatment already has a linked
    specimen record documenting the surgery."""
    total = pd.Series(2, index=df.index)
    complete = (df['surgery_reference_database'].notna().astype(int) + df['surgery_type'].notna().astype(int))
    has_specimen_exception = df['submitter_treatment_id'].isin(specimen_linked_treatment_ids)
    needs_site_location = ~has_specimen_exception
    total = total + needs_site_location.astype(int) * 2
    complete = complete + (needs_site_location & df['surgery_site'].notna()).astype(int)
    complete = complete + (needs_site_location & df['surgery_location'].notna()).astype(int)
    return _agg_field_score_by_donor(df, total, complete)


def _sys_therapy_field_score(df):
    """systemic therapy (subtype-specific fields only): systemic_therapy_type, start_date,
    drug_reference_database, drug_reference_identifier, drug_name always required; end_date
    required unless status is 'Treatment ongoing'; drug_dose_units required only if a cumulative
    drug dose (prescribed or actual) was reported."""
    total = pd.Series(5, index=df.index)
    complete = (df['systemic_therapy_type'].notna().astype(int) + df['start_date'].notna().astype(int) +
                df['drug_reference_database'].notna().astype(int) +
                df['drug_reference_identifier'].notna().astype(int) + df['drug_name'].notna().astype(int))
    total = total + 1
    ongoing = df['status_of_treatment'].astype(str) == 'Treatment ongoing'
    complete = complete + (df['end_date'].notna() | ongoing).astype(int)
    dose_reported = df['prescribed_cumulative_drug_dose'].notna() | df['actual_cumulative_drug_dose'].notna()
    total = total + dose_reported.astype(int)
    complete = complete + (dose_reported & df['drug_dose_units'].notna()).astype(int)
    return _agg_field_score_by_donor(df, total, complete)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--psql-user', type=str, required=False, default="admin",
                        help="Username of the postgres admin user, DEFAULT=admin")
    parser.add_argument('--token', type=str, required=True,
                        help="site admin token for the candig deployment you are retrieving data from.")
    parser.add_argument('--url', type=str, required=True,
                        help="URL of the candig deployment you are retrieving data from")
    parser.add_argument('--node', type=str, required=True, help="name of the node running the report, e.g. UHN")
    parser.add_argument('--no-sql', action="store_true", required=False,
                        help="don't run the sql reports again, mainly used for debugging")
    parser.add_argument('--dont-delete-sql-outputs', action="store_true", required=False,
                        help="don't delete the sql outputs, mainly used for debugging")
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
        print(
            "WARN: Could not retrieve genomic data, continuing but if you have genomic data ingested, please reach out for help to debug this.")
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


def _run_sql_script(script_name, prefix):
    """copy script to the docker container, run script, copy outputs, delete outputs"""
    stem_name = script_name.split(".sql")[0]
    subprocess.run(["docker", "cp", script_name, f"candigv2_postgres-db_1:/tmp/{script_name}"])
    result = subprocess.run(
        [f"docker exec -i candigv2_postgres-db_1 psql -U {PSQL_USER} -d clinical -f /tmp/{script_name}"],
        shell=True, stdout=subprocess.PIPE)
    # 'failed_minimal' and every 'all_*' script is a single unfiltered/simple query with no
    # companion _count.csv (unlike the old fullsome_*.sql / minimal.sql scripts they replaced,
    # which each produced a completeness file AND a separate count file for comparison).
    if stem_name not in ['failed_minimal', 'all_minimal', 'all_donor', 'all_primary_diagnosis',
                         'all_specimen', 'all_sample', 'all_followup', 'all_comorbidity', 'all_treatments_raw',
                         'all_radiation', 'all_surgery', 'all_sys_therapy']:
        subprocess.run(
            ["docker", "cp", f"candigv2_postgres-db_1:/tmp/{stem_name}_count.csv",
             f"sql_outputs/{stem_name}_count.csv"])
        subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{stem_name}_count.csv"])
    subprocess.run(
        ["docker", "cp", f"candigv2_postgres-db_1:/tmp/{stem_name}_completeness.csv",
         f"sql_outputs/{stem_name}_completeness.csv"])
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{stem_name}_completeness.csv"])
    subprocess.run(["docker", "exec", "-i", "candigv2_postgres-db_1", "rm", f"/tmp/{script_name}"])
    if stem_name == "failed_minimal":
        subprocess.run(
            ["cp", "sql_outputs/failed_minimal_completeness.csv", f"./{prefix}failed_minimal_completeness.csv"])


def get_minimal_completeness(all_minimal_df):
    """
    Per-sample-row minimal clinical completeness, derived directly from all_minimal_completeness.csv
    (already fetched for get_minimal_field_score) instead of re-querying postgres with a second,
    separately WHERE-filtered minimal.sql script.

    Returns one row per (program, donor, sample) that passes all 14 MINIMAL_REQUIRED_FIELDS -
    matching the old minimal.sql query's filtered output - with tier_a_min_clinical_complete /
    tier_b_min_clinical_complete columns added, reflecting that donor's overall tier status
    (broadcast to every one of that donor's passing sample rows, matching the old per-row
    representation written to complete_donor_samples.csv). Donors with zero passing samples are
    absent entirely, exactly as with the old minimal.sql-filtered query.

    NOTE: this returns every column from all_minimal_completeness.csv (donor/diagnosis/specimen
    fields included), which is a superset of the old minimal.sql output's columns - the
    complete_donor_samples.csv this feeds now has some extra columns as a result, but every column
    consumers previously relied on (submitter_sample_id, tumour_normal_designation, sample_type,
    tier_a/b_min_clinical_complete) is still present under the same name.
    """
    df = all_minimal_df.copy()
    passes_minimal = df[MINIMAL_REQUIRED_FIELDS].notna().all(axis=1)
    passing = df.loc[passes_minimal].copy()
    if passing.empty:
        cols = list(all_minimal_df.columns) + ['combined_sample_type', 'tier_a_min_clinical_complete',
                                               'tier_b_min_clinical_complete']
        return pd.DataFrame(columns=cols)
    passing['combined_sample_type'] = (passing['tumour_normal_designation'].astype(str) +
                                       "~" + passing['sample_type'].astype(str))
    donor_grouped_sample = passing.groupby(['program_id_id', 'submitter_donor_id'])[
        'combined_sample_type'].agg(list).reset_index()
    donor_grouped_sample['tier_a_samples_complete'] = donor_grouped_sample['combined_sample_type'].map(
        check_sample_tier_a_completeness)
    donor_grouped_sample['tier_b_samples_complete'] = donor_grouped_sample['combined_sample_type'].map(
        check_sample_tier_b_completeness)
    minimal_tier_a_complete_donor_list = list(
        donor_grouped_sample.loc[donor_grouped_sample['tier_a_samples_complete']].submitter_donor_id)
    minimal_tier_b_complete_donor_list = list(
        donor_grouped_sample.loc[donor_grouped_sample['tier_b_samples_complete']].submitter_donor_id)
    minimal_tier_b_complete_donor_list = list(
        set(minimal_tier_b_complete_donor_list) - set(minimal_tier_a_complete_donor_list))
    passing['tier_a_min_clinical_complete'] = passing['submitter_donor_id'].isin(
        minimal_tier_a_complete_donor_list)
    passing['tier_b_min_clinical_complete'] = passing['submitter_donor_id'].isin(
        minimal_tier_b_complete_donor_list)
    return passing


def check_column_equality(row, col1, col2):
    if row[col1] == row[col2]:
        return True
    else:
        return False


def get_comorbidity_completeness(all_comorbidity_df):
    """
    technically I should check to make sure every time prior_malignancy is listed, the type code is
    a cancer but I don't have time to do that right now.

    Derived directly from all_comorbidity_completeness.csv (prior_malignancy and
    comorbidity_type_code both always required), instead of a second, separately-filtered
    fullsome_comorbidity.sql query.
    """
    if all_comorbidity_df.empty:
        return pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'donor_comorbidities_complete'])
    fields = ['prior_malignancy', 'comorbidity_type_code']
    total = pd.Series(len(fields), index=all_comorbidity_df.index)
    complete = sum(all_comorbidity_df[field].notna().astype(int) for field in fields)
    return _record_pass_by_donor(all_comorbidity_df, total, complete, 'donor_comorbidities_complete')


def get_followups_completeness(all_followup_df):
    """
    follow-up: date_of_followup & disease_status_at_followup always required. If the followup
    reports relapse/progression, date_of_relapse, relapse_type, method_of_progression_status are
    also required, plus anatomic_site_progression_or_recurrence unless it's a Biochemical
    progression relapse. Derived directly from all_followup_completeness.csv instead of a second,
    separately-filtered fullsome_followup.sql query.
    """
    if all_followup_df.empty:
        return pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'donor_followups_complete'])
    total = pd.Series(2, index=all_followup_df.index)
    complete = (all_followup_df['date_of_followup'].notna().astype(int) +
                all_followup_df['disease_status_at_followup'].notna().astype(int))
    relapse_prog = all_followup_df['disease_status_at_followup'].isin(RELAPSE_PROGRESSION_STATUSES)
    total = total + relapse_prog.astype(int) * 3
    complete = complete + (relapse_prog & all_followup_df['date_of_relapse'].notna()).astype(int)
    complete = complete + (relapse_prog & all_followup_df['relapse_type'].notna()).astype(int)
    complete = complete + (relapse_prog & all_followup_df['method_of_progression_status'].notna()).astype(int)
    biochemical = all_followup_df['relapse_type'].astype(str) == 'Biochemical progression'
    anatomic_required = relapse_prog & ~biochemical
    total = total + anatomic_required.astype(int)
    complete = complete + (
            anatomic_required & all_followup_df['anatomic_site_progression_or_recurrence'].notna()).astype(int)
    return _record_pass_by_donor(all_followup_df, total, complete, 'donor_followups_complete')


def get_radiations_completeness(all_radiation_df, all_treatments_df):
    """
    radiation (subtype-specific fields + base treatment fields): radiation_therapy_modality,
    radiation_therapy_type, anatomical_site_irradiated always required; fractions and dosage each
    required unless their "not available" flag is set. The old fullsome_treatments_radiation.sql
    query joined back to the base Treatment record and required its fields too, with
    treatment_end_date required unconditionally (no "Treatment ongoing" exemption, unlike the base
    Treatment category) - _treatment_base_pass(..., require_end_date_unconditionally=True)
    replicates that. Derived directly from all_radiation_completeness.csv +
    all_treatments_raw_completeness.csv instead of a second, separately-filtered SQL query.
    """
    if all_radiation_df.empty:
        return pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'radiation_donor_complete'])
    total = pd.Series(3, index=all_radiation_df.index)
    complete = (all_radiation_df['radiation_therapy_modality'].notna().astype(int) +
                all_radiation_df['radiation_therapy_type'].notna().astype(int) +
                all_radiation_df['anatomical_site_irradiated'].notna().astype(int))
    total = total + 2
    fractions_ok = all_radiation_df['radiation_therapy_fractions'].notna() | _parse_bool_flag(
        all_radiation_df['radiation_therapy_fractions_not_available'])
    dosage_ok = all_radiation_df['radiation_therapy_dosage'].notna() | _parse_bool_flag(
        all_radiation_df['radiation_therapy_dosage_not_available'])
    complete = complete + fractions_ok.astype(int) + dosage_ok.astype(int)
    subtype_pass = (complete == total)

    base_pass_df = _treatment_base_pass(all_treatments_df, require_end_date_unconditionally=True)
    merged = all_radiation_df.merge(base_pass_df, on=['program_id_id', 'submitter_treatment_id'], how='left')
    record_pass = (subtype_pass.values & merged['_treatment_base_pass'].astype('boolean').fillna(False).values).astype(bool)

    result = all_radiation_df.loc[:, ['program_id_id', 'submitter_donor_id']].copy()
    result['_pass'] = record_pass
    grouped = result.groupby(['program_id_id', 'submitter_donor_id'], as_index=False)['_pass'].all()
    return grouped.rename(columns={'_pass': 'radiation_donor_complete'})


def get_surgeries_completeness(all_surgery_df, specimen_linked_treatment_ids, all_treatments_df):
    """
    surgery (subtype-specific fields + base treatment fields): surgery_reference_database and
    surgery_type always required. surgery_site and surgery_location required unless the treatment
    already has a linked specimen record documenting the surgery (specimen_linked_treatment_ids).
    Like radiation, the base Treatment fields are required with treatment_end_date required
    unconditionally (no "Treatment ongoing" exemption). Derived directly from
    all_surgery_completeness.csv + all_treatments_raw_completeness.csv instead of a second,
    separately-filtered SQL query.
    """
    if all_surgery_df.empty:
        return pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'surgery_donor_complete'])
    total = pd.Series(2, index=all_surgery_df.index)
    complete = (all_surgery_df['surgery_reference_database'].notna().astype(int) +
                all_surgery_df['surgery_type'].notna().astype(int))
    has_exception = all_surgery_df['submitter_treatment_id'].isin(specimen_linked_treatment_ids)
    needs_site_location = ~has_exception
    total = total + needs_site_location.astype(int) * 2
    complete = complete + (needs_site_location & all_surgery_df['surgery_site'].notna()).astype(int)
    complete = complete + (needs_site_location & all_surgery_df['surgery_location'].notna()).astype(int)
    subtype_pass = (complete == total)

    base_pass_df = _treatment_base_pass(all_treatments_df, require_end_date_unconditionally=True)
    merged = all_surgery_df.merge(base_pass_df, on=['program_id_id', 'submitter_treatment_id'], how='left')
    record_pass = (subtype_pass.values & merged['_treatment_base_pass'].astype('boolean').fillna(False).values).astype(bool)

    result = all_surgery_df.loc[:, ['program_id_id', 'submitter_donor_id']].copy()
    result['_pass'] = record_pass
    grouped = result.groupby(['program_id_id', 'submitter_donor_id'], as_index=False)['_pass'].all()
    return grouped.rename(columns={'_pass': 'surgery_donor_complete'})


def get_sys_therapy_completeness(all_sys_therapy_df, all_treatments_df):
    """
    systemic therapy (subtype-specific fields + base treatment fields): systemic_therapy_type,
    start_date, drug_reference_database, drug_reference_identifier, drug_name always required;
    end_date required unless status is 'Treatment ongoing'; drug_dose_units required only if a
    cumulative drug dose (prescribed or actual) was reported. Unlike radiation/surgery, systemic
    therapy's base Treatment fields use the same "Treatment ongoing" exemption on
    treatment_end_date as the base Treatment category. Derived directly from
    all_sys_therapy_completeness.csv + all_treatments_raw_completeness.csv instead of a second,
    separately-filtered SQL query.
    """
    if all_sys_therapy_df.empty:
        return pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'sys_therapy_donor_complete'])
    total = pd.Series(5, index=all_sys_therapy_df.index)
    complete = (all_sys_therapy_df['systemic_therapy_type'].notna().astype(int) +
                all_sys_therapy_df['start_date'].notna().astype(int) +
                all_sys_therapy_df['drug_reference_database'].notna().astype(int) +
                all_sys_therapy_df['drug_reference_identifier'].notna().astype(int) +
                all_sys_therapy_df['drug_name'].notna().astype(int))
    total = total + 1
    ongoing = all_sys_therapy_df['status_of_treatment'].astype(str) == 'Treatment ongoing'
    complete = complete + (all_sys_therapy_df['end_date'].notna() | ongoing).astype(int)
    dose_reported = (all_sys_therapy_df['prescribed_cumulative_drug_dose'].notna() |
                     all_sys_therapy_df['actual_cumulative_drug_dose'].notna())
    total = total + dose_reported.astype(int)
    complete = complete + (dose_reported & all_sys_therapy_df['drug_dose_units'].notna()).astype(int)
    subtype_pass = (complete == total)

    base_pass_df = _treatment_base_pass(all_treatments_df, require_end_date_unconditionally=False)
    merged = all_sys_therapy_df.merge(base_pass_df, on=['program_id_id', 'submitter_treatment_id'], how='left')
    record_pass = (subtype_pass.values & merged['_treatment_base_pass'].astype('boolean').fillna(False).values).astype(bool)

    result = all_sys_therapy_df.loc[:, ['program_id_id', 'submitter_donor_id']].copy()
    result['_pass'] = record_pass
    grouped = result.groupby(['program_id_id', 'submitter_donor_id'], as_index=False)['_pass'].all()
    return grouped.rename(columns={'_pass': 'sys_therapy_donor_complete'})


def get_treatments_completeness(all_treatments_df):
    """
    treatment (base record, shared by all treatment types): treatment_type, is_primary_treatment,
    treatment_start_date, treatment_intent always required; treatment_end_date required unless the
    treatment status is 'Treatment ongoing'. Derived directly from
    all_treatments_raw_completeness.csv instead of a second, separately-filtered
    fullsome_treatments.sql query.

    NOTE: the old fullsome_treatments.sql-based version additionally cross-checked each treatment
    row against the subtype-specific radiation/surgery/sys_therapy completeness files, effectively
    duplicating those checks here too. That cross-check is redundant with (and always at least as
    strict as) the dedicated radiation_donor_complete / surgery_donor_complete /
    sys_therapy_donor_complete columns already computed by get_radiations_completeness() /
    get_surgeries_completeness() / get_sys_therapy_completeness(), which now also require these
    same base Treatment fields via _treatment_base_pass(). This function is scoped to just the
    base Treatment fields to avoid re-checking the same subtype fields twice.
    """
    if all_treatments_df.empty:
        return pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'treatment_donor_complete'])
    total = pd.Series(4, index=all_treatments_df.index)
    complete = (all_treatments_df['treatment_type'].notna().astype(int) +
                all_treatments_df['is_primary_treatment'].notna().astype(int) +
                all_treatments_df['treatment_start_date'].notna().astype(int) +
                all_treatments_df['treatment_intent'].notna().astype(int))
    total = total + 1
    ongoing = all_treatments_df['status_of_treatment'].astype(str) == 'Treatment ongoing'
    complete = complete + (all_treatments_df['treatment_end_date'].notna() | ongoing).astype(int)
    return _record_pass_by_donor(all_treatments_df, total, complete, 'treatment_donor_complete')


def get_primary_diagnosis_completeness(all_pd_df):
    """
    primary diagnosis: 4 always-required fields; staging_present (one clinical OR pathological
    stage pair) counted as 1 composite requirement; clinical/pathological T/N/M categories
    required only if that staging system is AJCC. Derived directly from
    all_primary_diagnosis_completeness.csv instead of a second, separately-filtered
    fullsome_primary_diagnosis.sql query.
    """
    if all_pd_df.empty:
        return pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'pd_donor_complete'])
    total = pd.Series(4, index=all_pd_df.index)
    complete = (all_pd_df['date_of_diagnosis'].notna().astype(int) + all_pd_df['cancer_type_code'].notna().astype(int) +
                all_pd_df['primary_site'].notna().astype(int) + all_pd_df['basis_of_diagnosis'].notna().astype(int))
    total = total + 1
    clinical_pair = all_pd_df['clinical_tumour_staging_system'].notna() & all_pd_df['clinical_stage_group'].notna()
    pathological_pair = (all_pd_df['pathological_tumour_staging_system'].notna() &
                         all_pd_df['pathological_stage_group'].notna())
    complete = complete + (clinical_pair | pathological_pair).astype(int)
    clinical_ajcc = all_pd_df['clinical_tumour_staging_system'].astype(str).str.contains('AJCC', na=False)
    total = total + clinical_ajcc.astype(int) * 3
    complete = complete + (clinical_ajcc & all_pd_df['clinical_t_category'].notna()).astype(int)
    complete = complete + (clinical_ajcc & all_pd_df['clinical_n_category'].notna()).astype(int)
    complete = complete + (clinical_ajcc & all_pd_df['clinical_m_category'].notna()).astype(int)
    pathological_ajcc = all_pd_df['pathological_tumour_staging_system'].astype(str).str.contains('AJCC', na=False)
    total = total + pathological_ajcc.astype(int) * 3
    complete = complete + (pathological_ajcc & all_pd_df['pathological_t_category'].notna()).astype(int)
    complete = complete + (pathological_ajcc & all_pd_df['pathological_n_category'].notna()).astype(int)
    complete = complete + (pathological_ajcc & all_pd_df['pathological_m_category'].notna()).astype(int)
    return _record_pass_by_donor(all_pd_df, total, complete, 'pd_donor_complete')


def get_specimens_completeness(all_specimen_df, all_sample_df):
    """
    specimen: 2 always-required fields; 7 tumour-histology fields required only when
    tumour_normal_designation is Tumour. The old fullsome_specimen.sql query joined each specimen
    to its matched sample registration and additionally required specimen_tissue_source /
    specimen_type / sample_type on that matched sample (on top of tumour_normal_designation) - a
    specimen with no matched sample, or a match missing those fields, was silently excluded from
    the old filtered completeness file, so it's replicated explicitly here via
    sample_registration_ok. Derived directly from all_specimen_completeness.csv +
    all_sample_completeness.csv instead of a second, separately-filtered SQL query.
    """
    if all_specimen_df.empty:
        return pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'specimen_donor_complete'])
    sample_cols = all_sample_df[['program_id_id', 'submitter_donor_id', 'submitter_specimen_id',
                                 'specimen_tissue_source', 'specimen_type', 'sample_type']].copy()
    sample_cols['_sample_registration_ok'] = sample_cols[
        ['specimen_tissue_source', 'specimen_type', 'sample_type']].notna().all(axis=1)
    # a specimen can have zero, one, or many matched samples; ALL matches must be registration-ok
    sample_agg = sample_cols.groupby(['program_id_id', 'submitter_donor_id', 'submitter_specimen_id'],
                                     as_index=False).agg(_has_sample=('specimen_tissue_source', 'size'),
                                                         _sample_registration_ok=('_sample_registration_ok', 'all'))

    df = all_specimen_df.merge(sample_agg, on=['program_id_id', 'submitter_donor_id', 'submitter_specimen_id'],
                               how='left')
    has_matched_sample = df['_has_sample'].fillna(0) > 0
    sample_registration_ok = (has_matched_sample & df['_sample_registration_ok'].astype('boolean').fillna(False)).astype(bool)

    base_ok = df[['specimen_collection_date', 'specimen_anatomic_location']].notna().all(axis=1)
    is_tumour = df['tumour_normal_designation'].astype(str).str.contains('Tumour', na=False)
    is_normal = df['tumour_normal_designation'].astype(str).str.contains('Normal', na=False)
    tumour_fields = ['tumour_histological_type', 'reference_pathology_confirmed_diagnosis',
                      'reference_pathology_confirmed_tumour_presence', 'tumour_grading_system', 'tumour_grade',
                      'percent_tumour_cells_range', 'percent_tumour_cells_measurement_method']
    tumour_fields_ok = df[tumour_fields].notna().all(axis=1)

    designation_ok = (is_tumour & tumour_fields_ok) | is_normal
    record_pass = base_ok & sample_registration_ok & designation_ok

    result = df.loc[:, ['program_id_id', 'submitter_donor_id']].copy()
    result['_pass'] = record_pass
    grouped = result.groupby(['program_id_id', 'submitter_donor_id'], as_index=False)['_pass'].all()
    return grouped.rename(columns={'_pass': 'specimen_donor_complete'})


def get_samples_completeness(all_sample_df):
    """
    sample registration: specimen_tissue_source, tumour_normal_designation, specimen_type,
    sample_type - all always required. Derived directly from all_sample_completeness.csv instead
    of a second, separately-filtered fullsome_sample.sql query.
    """
    if all_sample_df.empty:
        return pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'sample_donor_complete'])
    fields = ['specimen_tissue_source', 'tumour_normal_designation', 'specimen_type', 'sample_type']
    total = pd.Series(len(fields), index=all_sample_df.index)
    complete = sum(all_sample_df[field].notna().astype(int) for field in fields)
    return _record_pass_by_donor(all_sample_df, total, complete, 'sample_donor_complete')


def get_donors_completeness(all_donor_df):
    """
    donor: gender, sex_at_birth, date_of_birth, date_resolution, is_deceased always required;
    cause_of_death & date_of_death required only if is_deceased == 'Yes'. Derived directly from
    all_donor_completeness.csv instead of a second, separately-filtered fullsome_donor.sql query.
    """
    if all_donor_df.empty:
        return pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'donor_obj_complete'])
    total = pd.Series(5, index=all_donor_df.index)
    complete = (all_donor_df['gender'].notna().astype(int) + all_donor_df['sex_at_birth'].notna().astype(int) +
                all_donor_df['date_of_birth'].notna().astype(int) + all_donor_df['date_resolution'].notna().astype(int) +
                all_donor_df['is_deceased'].notna().astype(int))
    deceased = all_donor_df['is_deceased'].astype(str).str.strip() == 'Yes'
    total = total + deceased.astype(int) * 2
    complete = complete + (deceased & all_donor_df['cause_of_death'].notna()).astype(int)
    complete = complete + (deceased & all_donor_df['date_of_death'].notna()).astype(int)
    return _record_pass_by_donor(all_donor_df, total, complete, 'donor_obj_complete')


def load_all_category_dataframes():
    """
    Reads every all_*_completeness.csv export exactly once. These unfiltered, denormalized
    per-record tables are the single source of truth for the fullsome/minimal field-level scores
    (get_minimal_field_score / get_fullsome_field_score) AND the per-category completeness
    booleans (get_donors_completeness, get_samples_completeness, etc.) - both consume the same
    dataframes, so postgres is only queried once per category instead of twice (once via an
    unfiltered all_*.sql script, once via a second, separately-filtered fullsome_*.sql/minimal.sql
    script computing an overlapping pass/fail boolean from the same underlying rows).
    """
    return {
        'donor': pd.read_csv("sql_outputs/all_donor_completeness.csv", dtype="str"),
        'primary_diagnosis': pd.read_csv("sql_outputs/all_primary_diagnosis_completeness.csv", dtype="str"),
        'specimen': pd.read_csv("sql_outputs/all_specimen_completeness.csv", dtype="str"),
        'sample': pd.read_csv("sql_outputs/all_sample_completeness.csv", dtype="str"),
        'followup': pd.read_csv("sql_outputs/all_followup_completeness.csv", dtype="str"),
        'comorbidity': pd.read_csv("sql_outputs/all_comorbidity_completeness.csv", dtype="str"),
        'treatments': pd.read_csv("sql_outputs/all_treatments_raw_completeness.csv", dtype="str"),
        'radiation': pd.read_csv("sql_outputs/all_radiation_completeness.csv", dtype="str"),
        'surgery': pd.read_csv("sql_outputs/all_surgery_completeness.csv", dtype="str"),
        'sys_therapy': pd.read_csv("sql_outputs/all_sys_therapy_completeness.csv", dtype="str"),
        'minimal': pd.read_csv("sql_outputs/all_minimal_completeness.csv", dtype="str"),
    }


def get_specimen_linked_treatment_ids(all_specimen_df):
    """
    Treatment IDs that have at least one linked specimen record documenting the associated
    surgery - used by get_surgeries_completeness() to exempt surgery_site/surgery_location when
    a specimen record already documents the surgery. Shared between get_fullsome_field_score() and
    get_surgeries_completeness() so it's only computed once.
    """
    return set(all_specimen_df.loc[all_specimen_df['submitter_treatment_id'].notna(), 'submitter_treatment_id'])


def get_minimal_field_score(all_minimal_df):
    """
    Per-donor count and percentage of the MINIMAL_REQUIRED_FIELDS (see README "Minimal clinical
    completeness") that are complete.

    Scored per row (one row per sample in all_minimal.csv, joined to donor/primary-diagnosis/
    specimen/sample-registration) and summed across all of a donor's rows, using the same
    row-level partial-credit methodology as get_fullsome_field_score() (via
    _agg_field_score_by_donor). This keeps the two scores on a directly comparable scale: a donor
    with 10 samples missing one field on only 1 of them loses 1/10 of that field's weight, not the
    whole field.

    NOTE: an earlier version of this function required a field to be non-null on EVERY one of a
    donor's rows to count at all (matching the strict pass/fail logic behind
    tier_a_min_clinical_complete / tier_b_min_clinical_complete). That all-or-nothing rule made
    minimal scores drop far more sharply than fullsome scores for the exact same isolated data
    gaps, which could make a donor look LESS complete under the smaller minimal field set than
    under the larger fullsome field set - the opposite of what should be possible since fullsome's
    required fields are a superset of minimal's. Switching to row-level partial credit removes
    that systematic bias. tier_a/b_min_clinical_complete themselves are unaffected by this change;
    they're computed separately in get_minimal_completeness() and still use the strict logic.
    """
    total = pd.Series(len(MINIMAL_REQUIRED_FIELDS), index=all_minimal_df.index)
    complete = all_minimal_df[MINIMAL_REQUIRED_FIELDS].notna().sum(axis=1)
    field_complete = _agg_field_score_by_donor(all_minimal_df, total, complete)
    field_complete = field_complete.rename(columns={'_complete': 'minimal_required_fields_complete',
                                                     '_total': 'minimal_required_fields_total'})
    field_complete['minimal_required_fields_pct'] = (
            100 * field_complete['minimal_required_fields_complete'] /
            field_complete['minimal_required_fields_total']
    ).round(1)
    return field_complete.loc[:, ['program_id_id', 'submitter_donor_id',
                                  'minimal_required_fields_complete', 'minimal_required_fields_total',
                                  'minimal_required_fields_pct']]


def get_fullsome_field_score(dfs, specimen_linked_treatment_ids):
    """
    Per-donor count and percentage of every individual required/conditionally-required fullsome
    field that is complete, across all record types the donor has (donor, primary diagnosis,
    specimen, sample registration, follow-up, comorbidity, treatment, radiation, surgery, systemic
    therapy). Each record contributes only the fields applicable to it (e.g. a Normal specimen
    doesn't contribute the tumour-only fields; a donor with no follow-ups contributes nothing for
    that category), so donors are only scored against fields that actually apply to their data.

    `dfs` is the dict returned by load_all_category_dataframes() and `specimen_linked_treatment_ids`
    is the set returned by get_specimen_linked_treatment_ids() - both shared with the per-category
    completeness functions so each all_*.csv is only read/derived once per run.
    """
    all_donor_df = dfs['donor']
    all_pd_df = dfs['primary_diagnosis']
    all_specimen_df = dfs['specimen']
    all_sample_df = dfs['sample']
    all_followup_df = dfs['followup']
    all_comorbidity_df = dfs['comorbidity']
    all_treatments_df = dfs['treatments']
    all_radiation_df = dfs['radiation']
    all_surgery_df = dfs['surgery']
    all_sys_therapy_df = dfs['sys_therapy']

    category_scores = [
        _donor_object_field_score(all_donor_df),
        _primary_diagnosis_field_score(all_pd_df),
        _specimen_field_score(all_specimen_df),
        _sample_registration_field_score(all_sample_df),
        _followup_field_score(all_followup_df),
        _comorbidity_field_score(all_comorbidity_df),
        _treatment_field_score(all_treatments_df),
        _radiation_field_score(all_radiation_df),
        _surgery_field_score(all_surgery_df, specimen_linked_treatment_ids),
        _sys_therapy_field_score(all_sys_therapy_df),
    ]

    result = all_donor_df.loc[:, ['program_id_id', 'submitter_donor_id']].drop_duplicates().reset_index(drop=True)
    result['fullsome_required_fields_complete'] = 0
    result['fullsome_required_fields_total'] = 0
    for cat_df in category_scores:
        merged = result.merge(cat_df, on=['program_id_id', 'submitter_donor_id'], how='left')
        result['fullsome_required_fields_complete'] = (
                result['fullsome_required_fields_complete'] + merged['_complete'].fillna(0))
        result['fullsome_required_fields_total'] = (
                result['fullsome_required_fields_total'] + merged['_total'].fillna(0))
    result['fullsome_required_fields_pct'] = (
            100 * result['fullsome_required_fields_complete'] /
            result['fullsome_required_fields_total'].replace(0, pd.NA)
    ).round(1)
    return result


# (bucket suffix, exclusive lower bound, inclusive upper bound). Bounds are half-open (low, high]
# so that every percentage value - including non-integer pcts like 60.6% - lands in exactly one
# bucket, with no gaps between e.g. the "51-60%" and "61-70%" buckets.
PCT_COMPLETENESS_BUCKETS = [
    ('91_100_pct_complete', 90, 100),
    ('81_90_pct_complete', 80, 90),
    ('71_80_pct_complete', 70, 80),
    ('61_70_pct_complete', 60, 70),
    ('51_60_pct_complete', 50, 60),
]


def get_donor_pct_distribution(df, pct_col, column_prefix, program_col='program_id_id'):
    """
    Per-program count of donors falling into each completeness percentage bucket
    (91-100%, 81-90%, 71-80%, 61-70%, 51-60%, <=50%), plus the average donor completeness
    percentage for that program, based on `pct_col`.

    Buckets are half-open, (low, high], e.g. "61-70%" is 60 < pct <= 70 and "<=50%" is pct <= 50 -
    this keeps every possible percentage (including fractional values like 60.6%) in exactly one
    bucket. Donors with a null pct (e.g. no applicable required fields at all) are excluded from
    every bucket and from the average.
    """
    scored = df.loc[:, [program_col, pct_col]].dropna(subset=[pct_col]).copy()
    programs = df.loc[:, [program_col]].drop_duplicates()
    result = programs.copy()
    for suffix, low, high in PCT_COMPLETENESS_BUCKETS:
        col_name = f'{column_prefix}_{suffix}'
        bucket_counts = scored.loc[(scored[pct_col] > low) & (scored[pct_col] <= high)].groupby(
            program_col).size().rename(col_name)
        result = result.merge(bucket_counts, on=program_col, how='left')
        result[col_name] = result[col_name].fillna(0).astype(int)
    under_50_col = f'{column_prefix}_under_50_pct_complete'
    under_50_counts = scored.loc[scored[pct_col] <= 50].groupby(program_col).size().rename(under_50_col)
    result = result.merge(under_50_counts, on=program_col, how='left')
    result[under_50_col] = result[under_50_col].fillna(0).astype(int)
    avg_col = f'{column_prefix}_avg_pct_complete'
    avg_values = scored.groupby(program_col)[pct_col].mean().round(1).rename(avg_col)
    result = result.merge(avg_values, on=program_col, how='left')
    return result


def main():
    args = parse_args()
    clean_url = args.url.rstrip('/')
    file_prefix = datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + '-' + args.node + '-'
    # get data for clinical postgresdb
    if not args.no_sql:
        print("Fetching data from clinical postgres database")
        subprocess.run(["mkdir", "sql_outputs"])
        for script in glob.glob('*.sql'):
            _run_sql_script(script, file_prefix)
    else:
        if not Path("sql_outputs").is_dir():
            print("sql_outputs dir not found, please run script again and ensure --no-sql not specified.")
            sys.exit()
        subprocess.run(
            ["cp", "sql_outputs/failed_minimal_completeness.csv", f"./{file_prefix}failed_minimal_completeness.csv"])
        print("Not fetching new sql data")

    # Load every all_*_completeness.csv export once; this is the single source of truth for both
    # the per-donor field scores (get_minimal_field_score / get_fullsome_field_score) and the
    # per-category completeness booleans below, instead of re-querying postgres a second time per
    # category with a separately-filtered fullsome_*.sql/minimal.sql script.
    dfs = load_all_category_dataframes()
    specimen_linked_treatment_ids = get_specimen_linked_treatment_ids(dfs['specimen'])

    # Get minimal clinical Completeness stats
    complete_donor_samples_df = get_minimal_completeness(dfs['minimal'])
    failed_minimal_summary = pd.read_csv(f"{file_prefix}failed_minimal_completeness.csv")
    failed_summary_bools = failed_minimal_summary[
        ['gender', 'sex_at_birth', 'date_of_birth', 'date_resolution', 'date_of_diagnosis',
         'cancer_type_code', 'primary_site', 'basis_of_diagnosis', 'cancer_type_code',
         'primary_site', 'basis_of_diagnosis', 'specimen_collection_date',
         'specimen_anatomic_location', 'tumour_normal_designation', 'sample_type',
         'specimen_type']].isnull()
    failed_minimal_program_summary = pd.concat([failed_minimal_summary[['program_id_id']], failed_summary_bools],
                                               axis=1).groupby('program_id_id', as_index=False).sum()
    failed_minimal_program_summary.to_csv(f"{file_prefix}per_program_failed_minimal_completeness.csv", index=False)
    complete_donor_samples_df.to_csv(f"{file_prefix}complete_donor_samples.csv", index=False)
    if len(complete_donor_samples_df) == 0:
        print("No minimal complete donors found in the instance")

    # Get Fullsome clinical completeness stats
    followup_comp_df = get_followups_completeness(dfs['followup'])
    comorbidity_comp_df = get_comorbidity_completeness(dfs['comorbidity'])
    radiations_comp_df = get_radiations_completeness(dfs['radiation'], dfs['treatments'])
    surgeries_comp_df = get_surgeries_completeness(dfs['surgery'], specimen_linked_treatment_ids, dfs['treatments'])
    sys_therapies_comp_df = get_sys_therapy_completeness(dfs['sys_therapy'], dfs['treatments'])
    treatments_comp_df = get_treatments_completeness(dfs['treatments'])
    primary_diag_comp_df = get_primary_diagnosis_completeness(dfs['primary_diagnosis'])
    specimens_comp_df = get_specimens_completeness(dfs['specimen'], dfs['sample'])
    samples_comp_df = get_samples_completeness(dfs['sample'])
    donors_comp_df = get_donors_completeness(dfs['donor'])
    # samples_total_count feeds the tier_a/b_full_clinical_complete sample-count checks below;
    # it's no longer a byproduct of a separately-filtered fullsome_sample.sql count query, just a
    # plain group-by size over the same all_sample_completeness.csv rows used everywhere else.
    samples_total_count_df = dfs['sample'].groupby(['program_id_id', 'submitter_donor_id']).size().rename(
        'samples_total_count').reset_index()
    joined_completeness = (
        donors_comp_df.merge(
            samples_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(samples_total_count_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(primary_diag_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(followup_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(comorbidity_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(radiations_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(surgeries_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(sys_therapies_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(treatments_comp_df, on=["program_id_id", "submitter_donor_id"], how="left").
        merge(specimens_comp_df, on=["program_id_id", "submitter_donor_id"], how="left"))
    # Only count as not complete if any tests are False, nan means the donor didn't have that kind of object
    joined_completeness['tier_a_full_clinical_complete'] = (
            (~joined_completeness['sample_donor_complete'].eq(False)) &
            (joined_completeness['samples_total_count'] >= 3) &
            (~joined_completeness['donor_obj_complete'].eq(False)) &
            (~joined_completeness['pd_donor_complete'].eq(False)) &
            (~joined_completeness['donor_followups_complete'].eq(False)) &
            (~joined_completeness['donor_comorbidities_complete'].eq(False)) &
            (~joined_completeness['radiation_donor_complete'].eq(False)) &
            (~joined_completeness['surgery_donor_complete'].eq(False)) &
            (~joined_completeness['sys_therapy_donor_complete'].eq(False)) &
            (~joined_completeness['treatment_donor_complete'].eq(False)) &
            (~joined_completeness['specimen_donor_complete'].eq(False)))
    joined_completeness['tier_b_full_clinical_complete'] = (
            (~joined_completeness['sample_donor_complete'].eq(False)) &
            (joined_completeness['samples_total_count'] == 2) &
            (~joined_completeness['donor_obj_complete'].eq(False)) &
            (~joined_completeness['pd_donor_complete'].eq(False)) &
            (~joined_completeness['donor_followups_complete'].eq(False)) &
            (~joined_completeness['donor_comorbidities_complete'].eq(False)) &
            (~joined_completeness['radiation_donor_complete'].eq(False)) &
            (~joined_completeness['surgery_donor_complete'].eq(False)) &
            (~joined_completeness['sys_therapy_donor_complete'].eq(False)) &
            (~joined_completeness['treatment_donor_complete'].eq(False)) &
            (~joined_completeness['specimen_donor_complete'].eq(False)))
    joined_completeness.sort_values(['program_id_id', 'submitter_donor_id']).to_csv(
        f"{file_prefix}per_donor_clinical_completeness_full_breakdown.csv", index=False)

    # Per-donor completeness scores: count + percentage of required fields complete
    minimal_field_score_df = get_minimal_field_score(dfs['minimal'])
    fullsome_field_score_df = get_fullsome_field_score(dfs, specimen_linked_treatment_ids)
    all_donor_df = donors_comp_df.loc[:, ["program_id_id", "submitter_donor_id"]]
    minimal_complete_donor_df = complete_donor_samples_df.loc[:, ['program_id_id', 'submitter_donor_id',
                                                                  'tier_a_min_clinical_complete',
                                                                  'tier_b_min_clinical_complete']].drop_duplicates(
    ).rename({'tier_a_min_clinical_complete': 'tier_a_minimal_clinical_complete',
              'tier_b_min_clinical_complete': 'tier_b_minimal_clinical_complete'})
    samples_count_df = dfs['sample'].loc[:, ['program_id_id', 'submitter_donor_id', 'submitter_sample_id',
                                             'tumour_normal_designation', 'sample_type']].copy()
    sample_list = list(samples_count_df['submitter_sample_id'])
    donor_list = set(list(samples_count_df['submitter_donor_id']))
    # Get genomic completeness status
    if len(sample_list) > 0:
        genomic_stats = get_genomic_data(args.token, clean_url, sample_list)
        if len(genomic_stats) > 0:
            genomic_stats.to_csv(f"{file_prefix}per_sample_genomic_stats.csv", index=False)
            genomic_stats = (pd.merge(genomic_stats, samples_count_df.rename(columns={"program_id_id": "program_id"}),
                                      on=["program_id", "submitter_sample_id"], how="outer"))
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
                                                                           'variant_sample_file_count',
                                                                           'read_file_count',
                                                                           'tier_a_genomic_files_complete',
                                                                           'tier_b_genomic_files_complete']]
        else:
            print("WARN: No matching genomic information found for samples.")
            full_genomic_stats = copy.deepcopy(samples_count_df).groupby(['program_id_id', 'submitter_donor_id'],
                                                                         as_index=False).sum().drop(
                'submitter_sample_id', axis=1).rename(columns={"program_id_id": "program_id"})
            full_genomic_stats.loc[:, ['expression_file_count', 'variant_sample_file_count', 'read_file_count']] = 0
            full_genomic_stats.loc[:, ['tier_a_genomic_files_complete', 'tier_b_genomic_files_complete']] = False
    else:
        print("WARN: No samples found in database.")
        full_genomic_stats = copy.deepcopy(samples_count_df).groupby(['program_id_id', 'submitter_donor_id'],
                                                                     as_index=False).sum().rename(
            columns={"program_id_id": "program_id"})
        full_genomic_stats.loc[:, ['expression_file_count', 'variant_sample_file_count', 'read_file_count']] = 0
        full_genomic_stats.loc[:, ['tier_a_genomic_files_complete', 'tier_b_genomic_files_complete']] = False

    clinical_genomic_completeness = joined_completeness.loc[:,
                                    ['program_id_id', 'submitter_donor_id', 'tier_a_full_clinical_complete',
                                     'tier_b_full_clinical_complete']].rename(
        columns={"program_id_id": "program_id"}).merge(full_genomic_stats, on=['program_id', 'submitter_donor_id'],
                                                       how='left').merge(
        minimal_complete_donor_df.rename(columns={"program_id_id": "program_id"}),
        on=['program_id', 'submitter_donor_id'], how='left')
    clinical_genomic_completeness['tier_a_min_cg_complete'] = (
                clinical_genomic_completeness['tier_a_genomic_files_complete']
                & clinical_genomic_completeness['tier_a_min_clinical_complete'])
    clinical_genomic_completeness['tier_b_min_cg_complete'] = (clinical_genomic_completeness[
                                                                 'tier_b_genomic_files_complete'] &
                                                             clinical_genomic_completeness[
                                                                 'tier_b_min_clinical_complete']) | \
                                                            (clinical_genomic_completeness[
                                                                 'tier_b_genomic_files_complete'] &
                                                             clinical_genomic_completeness[
                                                                 'tier_a_min_clinical_complete'])
    clinical_genomic_completeness['tier_a_full_cg_complete'] = (clinical_genomic_completeness['tier_a_full_clinical_complete']
                                                                 & clinical_genomic_completeness[
                                                                    'tier_a_genomic_files_complete'])
    clinical_genomic_completeness['tier_b_full_cg_complete'] = (
        (clinical_genomic_completeness['tier_b_full_clinical_complete'] |
         clinical_genomic_completeness['tier_a_full_clinical_complete'])
                & clinical_genomic_completeness[
                    'tier_b_genomic_files_complete'])
    clinical_genomic_completeness = clinical_genomic_completeness.merge(
        minimal_field_score_df.rename(columns={"program_id_id": "program_id"}),
        on=['program_id', 'submitter_donor_id'], how='left').merge(
        fullsome_field_score_df.rename(columns={"program_id_id": "program_id"}),
        on=['program_id', 'submitter_donor_id'], how='left')
    clinical_genomic_completeness.to_csv(f"{file_prefix}per_donor_full_completeness.csv", index=False)

    # Per-program donor-count-by-completeness-percentage-bucket breakdown, for both the minimal
    # and fullsome required-field scores
    minimal_pct_distribution = get_donor_pct_distribution(
        clinical_genomic_completeness, 'minimal_required_fields_pct', 'minimal', program_col='program_id')
    fullsome_pct_distribution = get_donor_pct_distribution(
        clinical_genomic_completeness, 'fullsome_required_fields_pct', 'fullsome', program_col='program_id')

    # summarize by program for report
    report_table = copy.deepcopy(clinical_genomic_completeness)
    report_table['donor_count'] = 1
    report_table = report_table.drop(['submitter_donor_id'], axis=1).groupby(
        ['program_id'], as_index=False).sum()
    report_table['incomplete_min_donors'] = report_table['donor_count'] - (report_table['tier_a_min_cg_complete'] +
                                                                       report_table['tier_b_min_cg_complete'])
    report_table['incomplete_full_donors'] = report_table['donor_count'] - (report_table['tier_a_full_cg_complete'] +
                                                                    report_table['tier_b_full_cg_complete'])
    report_table['node'] = args.node
    report_table = report_table.merge(minimal_pct_distribution, on='program_id', how='left').merge(
        fullsome_pct_distribution, on='program_id', how='left')
    minimal_pct_columns = [c for c in minimal_pct_distribution.columns if c != 'program_id']
    fullsome_pct_columns = [c for c in fullsome_pct_distribution.columns if c != 'program_id']

    # % of all donors in the program with completeness > 80% (i.e. in the 81-90% or 91-100% buckets)
    report_table['minimal_pct_donors_over_80'] = (
            100 * (report_table['minimal_91_100_pct_complete'] + report_table['minimal_81_90_pct_complete']) /
            report_table['donor_count']
    ).round(1)
    report_table['fullsome_pct_donors_over_80'] = (
            100 * (report_table['fullsome_91_100_pct_complete'] + report_table['fullsome_81_90_pct_complete']) /
            report_table['donor_count']
    ).round(1)

    report_table = report_table[['node', 'program_id', 'donor_count',
                                 'tier_a_min_cg_complete', 'tier_b_min_cg_complete', 'incomplete_min_donors',
                                 'tier_a_full_cg_complete', 'tier_b_full_cg_complete', 'incomplete_full_donors',
                                 'tier_a_min_clinical_complete', 'tier_b_min_clinical_complete',
                                 'tier_a_full_clinical_complete', 'tier_b_full_clinical_complete',
                                 'tier_a_genomic_files_complete', 'tier_b_genomic_files_complete',]
                                + minimal_pct_columns + ['minimal_pct_donors_over_80']
                                + fullsome_pct_columns + ['fullsome_pct_donors_over_80']]
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
