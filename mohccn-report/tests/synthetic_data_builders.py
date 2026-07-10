"""
Builds the all_*_completeness-style unfiltered dataframes directly from the DONORS master dict
(tests/synthetic_data.py), in memory - no CSV round-trip needed since
run_completeness_reporting's get_*_completeness() functions all take dataframes as arguments.

This mirrors the shape that load_all_category_dataframes() reads from sql_outputs/*.csv on a real
run, so the same get_*_completeness() functions can be tested directly against synthetic data.
"""
import pandas as pd

from synthetic_data import DONORS


def _rows(donors, key):
    """Flatten donors[*][key] (a list of dicts, or None) into a list of rows tagged with donor id."""
    out = []
    for did, d in donors.items():
        for item in d.get(key, []) or []:
            row = dict(item)
            row['program_id_id'] = d['program_id']
            row['submitter_donor_id'] = did
            out.append(row)
    return out


def build_all_donor_df(donors):
    rows = []
    for did, d in donors.items():
        row = dict(d['donor_row'])
        row['program_id_id'] = d['program_id']
        row['submitter_donor_id'] = did
        rows.append(row)
    return pd.DataFrame(rows)


def build_all_primary_diagnosis_df(donors):
    rows = []
    for did, d in donors.items():
        for item in d.get('pd_rows', []) or []:
            row = dict(item)
            row['program_id_id'] = d['program_id']
            row['submitter_donor_id'] = did
            row.pop('id', None)
            rows.append(row)
    return pd.DataFrame(rows)


def build_all_specimen_df(donors):
    rows = []
    for did, d in donors.items():
        for item in d.get('specimens', []) or []:
            row = dict(item)
            row['program_id_id'] = d['program_id']
            row['submitter_donor_id'] = did
            row['submitter_specimen_id'] = row.pop('id')
            row['submitter_treatment_id'] = row.pop('treatment_id', None)
            row.pop('pd_id', None)
            rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'submitter_specimen_id',
                                   'submitter_treatment_id', 'specimen_collection_date',
                                   'specimen_anatomic_location', 'tumour_normal_designation',
                                   'tumour_histological_type', 'reference_pathology_confirmed_diagnosis',
                                   'reference_pathology_confirmed_tumour_presence', 'tumour_grading_system',
                                   'tumour_grade', 'percent_tumour_cells_range',
                                   'percent_tumour_cells_measurement_method'])
    return df


def build_all_sample_df(donors):
    rows = []
    for did, d in donors.items():
        specs = d.get('specimens', []) or []
        default_spec_id = specs[0]['id'] if len(specs) == 1 else None
        for item in d.get('samples', []) or []:
            row = dict(item)
            row['program_id_id'] = d['program_id']
            row['submitter_donor_id'] = did
            row['submitter_sample_id'] = row.pop('id')
            row['submitter_specimen_id'] = row.pop('spec_id', default_spec_id) or default_spec_id
            rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'submitter_sample_id',
                                   'submitter_specimen_id', 'specimen_tissue_source',
                                   'tumour_normal_designation', 'specimen_type', 'sample_type'])
    return df


def build_all_followup_df(donors):
    df = pd.DataFrame(_rows(donors, 'followups'))
    if df.empty:
        df = pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'date_of_followup',
                                   'disease_status_at_followup', 'date_of_relapse', 'relapse_type',
                                   'method_of_progression_status', 'anatomic_site_progression_or_recurrence'])
    return df


def build_all_comorbidity_df(donors):
    df = pd.DataFrame(_rows(donors, 'comorbidities'))
    if df.empty:
        df = pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'prior_malignancy',
                                   'comorbidity_type_code'])
    return df


def build_all_treatments_df(donors):
    rows = []
    for did, d in donors.items():
        for item in d.get('treatments', []) or []:
            row = dict(item)
            row['program_id_id'] = d['program_id']
            row['submitter_donor_id'] = did
            row['submitter_treatment_id'] = row.pop('id')
            rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'submitter_treatment_id',
                                   'treatment_type', 'is_primary_treatment', 'treatment_start_date',
                                   'treatment_end_date', 'treatment_intent', 'status_of_treatment'])
    return df


def build_all_radiation_df(donors):
    rows = []
    for did, d in donors.items():
        for item in d.get('radiations', []) or []:
            row = dict(item)
            row['program_id_id'] = d['program_id']
            row['submitter_donor_id'] = did
            row['submitter_treatment_id'] = row.pop('treatment_id')
            rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'submitter_treatment_id',
                                   'radiation_therapy_modality', 'radiation_therapy_type',
                                   'radiation_therapy_fractions', 'radiation_therapy_fractions_not_available',
                                   'radiation_therapy_dosage', 'radiation_therapy_dosage_not_available',
                                   'anatomical_site_irradiated'])
    return df


def build_all_surgery_df(donors):
    rows = []
    for did, d in donors.items():
        for item in d.get('surgeries', []) or []:
            row = dict(item)
            row['program_id_id'] = d['program_id']
            row['submitter_donor_id'] = did
            row['submitter_treatment_id'] = row.pop('treatment_id')
            rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'submitter_treatment_id',
                                   'surgery_reference_database', 'surgery_type', 'surgery_site',
                                   'surgery_location'])
    return df


def build_all_sys_therapy_df(donors):
    rows = []
    for did, d in donors.items():
        for item in d.get('sys_therapies', []) or []:
            row = dict(item)
            row['program_id_id'] = d['program_id']
            row['submitter_donor_id'] = did
            row['submitter_treatment_id'] = row.pop('treatment_id')
            rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=['program_id_id', 'submitter_donor_id', 'submitter_treatment_id',
                                   'systemic_therapy_type', 'start_date', 'end_date', 'drug_reference_database',
                                   'drug_reference_identifier', 'drug_name', 'prescribed_cumulative_drug_dose',
                                   'actual_cumulative_drug_dose', 'drug_dose_units', 'status_of_treatment'])
    return df


def build_all_minimal_df(donors):
    """One row per donor+specimen+sample combination, mirroring the join chain in all_minimal.sql."""
    rows = []
    for did, d in donors.items():
        donor_row = d['donor_row']
        pds = d.get('pd_rows', []) or []
        specs = d.get('specimens', []) or []
        samples = d.get('samples', []) or []
        default_pd = pds[0] if len(pds) == 1 else None
        default_spec = specs[0] if len(specs) == 1 else None
        for s in samples:
            spec_id = s.get('spec_id')
            spec = next((sp for sp in specs if sp['id'] == spec_id), default_spec)
            pd_row = default_pd
            if spec is not None and len(pds) > 1:
                pd_row = next((p for p in pds if p.get('id') and spec.get('pd_id') == p['id']), default_pd)
            rows.append({
                'program_id_id': d['program_id'], 'submitter_donor_id': did,
                'gender': donor_row['gender'], 'sex_at_birth': donor_row['sex_at_birth'],
                'date_of_birth': donor_row['date_of_birth'], 'date_resolution': donor_row['date_resolution'],
                'date_of_diagnosis': pd_row['date_of_diagnosis'] if pd_row else None,
                'cancer_type_code': pd_row['cancer_type_code'] if pd_row else None,
                'primary_site': pd_row['primary_site'] if pd_row else None,
                'basis_of_diagnosis': pd_row['basis_of_diagnosis'] if pd_row else None,
                'specimen_collection_date': spec['specimen_collection_date'] if spec else None,
                'specimen_anatomic_location': spec['specimen_anatomic_location'] if spec else None,
                'specimen_tissue_source': s['specimen_tissue_source'],
                'submitter_sample_id': s['id'],
                'tumour_normal_designation': s['tumour_normal_designation'],
                'sample_type': s['sample_type'],
                'specimen_type': s['specimen_type'],
            })
    return pd.DataFrame(rows)


def build_all_dataframes(donors=None):
    """
    Returns the same dict shape as run_completeness_reporting.load_all_category_dataframes(),
    built in-memory from the synthetic DONORS master dict instead of sql_outputs/*.csv files.
    """
    donors = DONORS if donors is None else donors
    return {
        'donor': build_all_donor_df(donors),
        'primary_diagnosis': build_all_primary_diagnosis_df(donors),
        'specimen': build_all_specimen_df(donors),
        'sample': build_all_sample_df(donors),
        'followup': build_all_followup_df(donors),
        'comorbidity': build_all_comorbidity_df(donors),
        'treatments': build_all_treatments_df(donors),
        'radiation': build_all_radiation_df(donors),
        'surgery': build_all_surgery_df(donors),
        'sys_therapy': build_all_sys_therapy_df(donors),
        'minimal': build_all_minimal_df(donors),
    }
