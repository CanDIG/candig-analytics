"""
Generates a single "master" synthetic dataset (one row per donor per record type) and then
materializes it TWO ways:

1. OLD-style: the filtered `fullsome_*_completeness.csv` / `fullsome_*_count.csv` /
   `minimal_completeness.csv` / `failed_minimal_completeness.csv` files, replicating the exact
   WHERE-clause / JOIN / GROUP BY logic of the corresponding .sql scripts in pandas.
2. NEW-style: the unfiltered `all_*_completeness.csv` files (just a raw dump - no filtering).

Both materializations come from the same master records, so any difference in the final computed
completeness booleans between the OLD get_*_completeness() functions and a proposed NEW
field-score-derived replacement reflects a genuine behavioural difference, not a data-generation
artifact.

Each donor below is designed to exercise one or two specific branches of the completeness logic
(deceased/not, AJCC/no staging, tumour/normal specimen, relapse/biochemical follow-up, treatment
subtype completeness, minimal tier A/B/none, multiple treatments per donor, etc).
"""
import pandas as pd

RELAPSE_PROGRESSION_STATUSES = ['Distant progression', 'Loco-regional progression',
                                'Progression not otherwise specified', 'Relapse or recurrence']

# ---------------------------------------------------------------------------
# Master donor definitions. Each donor dict may omit a category entirely (e.g. no `followup` key)
# to simulate a donor with zero records of that type.
# ---------------------------------------------------------------------------
DONORS = {}

def donor(did, program='PROG1', **kwargs):
    kwargs['program_id'] = program
    kwargs['submitter_donor_id'] = did
    DONORS[did] = kwargs

# D1: everything complete - not deceased, full AJCC staging, tumour specimen complete, sample
# complete, stable followup, comorbidity complete, one complete Surgery treatment. Tier A minimal.
donor('D1',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1960-01-01', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD1', date_of_diagnosis='2020-01-01', cancer_type_code='C34.9', primary_site='Lung',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system='AJCC 8th',
                  clinical_t_category='T2', clinical_n_category='N0', clinical_m_category='M0',
                  clinical_stage_group='IIA', pathological_tumour_staging_system=None,
                  pathological_t_category=None, pathological_n_category=None, pathological_m_category=None,
                  pathological_stage_group=None)],
    specimens=[dict(id='SP1', treatment_id=None, specimen_collection_date='2020-01-05',
                    specimen_anatomic_location='Lung', tumour_normal_designation='Tumour',
                    tumour_histological_type='Adenocarcinoma', reference_pathology_confirmed_diagnosis='Yes',
                    reference_pathology_confirmed_tumour_presence='Yes', tumour_grading_system='AJCC',
                    tumour_grade='G2', percent_tumour_cells_range='60-70%',
                    percent_tumour_cells_measurement_method='Visual estimation')],
    samples=[dict(id='SA1-normal', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA'),
             dict(id='SA1-tumour-dna', specimen_tissue_source='Tumour tissue', tumour_normal_designation='Tumour',
                  specimen_type='DNA', sample_type='Total DNA'),
             dict(id='SA1-tumour-rna', specimen_tissue_source='Tumour tissue', tumour_normal_designation='Tumour',
                  specimen_type='RNA', sample_type='Total RNA')],
    followups=[dict(date_of_followup='2021-01-01', disease_status_at_followup='Stable',
                    date_of_relapse=None, relapse_type=None, method_of_progression_status=None,
                    anatomic_site_progression_or_recurrence=None)],
    comorbidities=[dict(prior_malignancy='No', comorbidity_type_code='Not applicable')],
    treatments=[dict(id='T1', treatment_type='Surgery', is_primary_treatment='Yes',
                     treatment_start_date='2020-01-10', treatment_end_date='2020-01-10',
                     treatment_intent='Curative', status_of_treatment='Treatment completed')],
    surgeries=[dict(treatment_id='T1', surgery_reference_database='NCI Thesaurus', surgery_type='Lobectomy',
                    surgery_site='Lung', surgery_location='Left upper lobe')],
)

# D2: deceased, all vital status fields present -> donor object complete via conditional branch
donor('D2',
    donor_row=dict(gender='Woman', sex_at_birth='Female', date_of_birth='1955-05-05', date_resolution='Year',
                   is_deceased='Yes', date_of_death='2023-01-01', cause_of_death='Cancer'),
    pd_rows=[dict(id='PD2', date_of_diagnosis='2019-01-01', cancer_type_code='C50.9', primary_site='Breast',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system='AJCC 8th', pathological_t_category='T1',
                  pathological_n_category='N0', pathological_m_category='M0', pathological_stage_group='IA')],
    specimens=[dict(id='SP2', treatment_id=None, specimen_collection_date='2019-01-05',
                    specimen_anatomic_location='Breast', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA2', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
)

# D3: deceased, missing cause_of_death -> donor object incomplete
donor('D3',
    donor_row=dict(gender='Woman', sex_at_birth='Female', date_of_birth='1948-02-02', date_resolution='Year',
                   is_deceased='Yes', date_of_death='2022-06-01', cause_of_death=None),
    pd_rows=[dict(id='PD3', date_of_diagnosis='2021-01-01', cancer_type_code='C18.9', primary_site='Colon',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP3', treatment_id=None, specimen_collection_date='2021-01-05',
                    specimen_anatomic_location='Colon', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA3', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
)

# D4: clinical AJCC staging present but missing clinical_n_category -> pd incomplete
donor('D4',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1970-03-03', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD4', date_of_diagnosis='2022-01-01', cancer_type_code='C61', primary_site='Prostate',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system='AJCC 8th',
                  clinical_t_category='T2', clinical_n_category=None, clinical_m_category='M0',
                  clinical_stage_group='II', pathological_tumour_staging_system=None,
                  pathological_t_category=None, pathological_n_category=None, pathological_m_category=None,
                  pathological_stage_group=None)],
    specimens=[dict(id='SP4', treatment_id=None, specimen_collection_date='2022-01-05',
                    specimen_anatomic_location='Prostate', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA4', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
)

# D5: no staging system reported at all (neither clinical nor pathological) -> pd incomplete
donor('D5',
    donor_row=dict(gender='Woman', sex_at_birth='Female', date_of_birth='1966-04-04', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD5', date_of_diagnosis='2023-01-01', cancer_type_code='C50.9', primary_site='Breast',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP5', treatment_id=None, specimen_collection_date='2023-01-05',
                    specimen_anatomic_location='Breast', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA5', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
)

# D6: tumour specimen missing histology fields -> specimen incomplete
donor('D6',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1975-05-05', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD6', date_of_diagnosis='2020-06-01', cancer_type_code='C16.9', primary_site='Stomach',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP6', treatment_id=None, specimen_collection_date='2020-06-05',
                    specimen_anatomic_location='Stomach', tumour_normal_designation='Tumour',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA6', specimen_tissue_source='Tumour tissue', tumour_normal_designation='Tumour',
                  specimen_type='DNA', sample_type='Total DNA')],
)

# D7: follow-up relapse with all conditional fields present -> followup complete
donor('D7',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1962-07-07', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD7', date_of_diagnosis='2020-01-01', cancer_type_code='C34.9', primary_site='Lung',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP7', treatment_id=None, specimen_collection_date='2020-01-05',
                    specimen_anatomic_location='Lung', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA7', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
    followups=[dict(date_of_followup='2021-06-01', disease_status_at_followup='Relapse or recurrence',
                    date_of_relapse='2021-06-01', relapse_type='Local recurrence',
                    method_of_progression_status='Imaging',
                    anatomic_site_progression_or_recurrence='Lung')],
)

# D8: follow-up relapse missing anatomic site, non-biochemical -> followup incomplete
donor('D8',
    donor_row=dict(gender='Woman', sex_at_birth='Female', date_of_birth='1958-08-08', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD8', date_of_diagnosis='2019-01-01', cancer_type_code='C50.9', primary_site='Breast',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP8', treatment_id=None, specimen_collection_date='2019-01-05',
                    specimen_anatomic_location='Breast', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA8', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
    followups=[dict(date_of_followup='2020-06-01', disease_status_at_followup='Distant progression',
                    date_of_relapse='2020-06-01', relapse_type='Local recurrence',
                    method_of_progression_status='Imaging',
                    anatomic_site_progression_or_recurrence=None)],
)

# D9: follow-up Biochemical progression missing anatomic site -> followup COMPLETE (exempt)
donor('D9',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1968-09-09', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD9', date_of_diagnosis='2018-01-01', cancer_type_code='C61', primary_site='Prostate',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP9', treatment_id=None, specimen_collection_date='2018-01-05',
                    specimen_anatomic_location='Prostate', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA9', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
    followups=[dict(date_of_followup='2019-06-01', disease_status_at_followup='Relapse or recurrence',
                    date_of_relapse='2019-06-01', relapse_type='Biochemical progression',
                    method_of_progression_status='Lab test',
                    anatomic_site_progression_or_recurrence=None)],
)

# D10: comorbidity missing prior_malignancy -> comorbidity incomplete
donor('D10',
    donor_row=dict(gender='Woman', sex_at_birth='Female', date_of_birth='1972-10-10', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD10', date_of_diagnosis='2021-01-01', cancer_type_code='C18.9', primary_site='Colon',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP10', treatment_id=None, specimen_collection_date='2021-01-05',
                    specimen_anatomic_location='Colon', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA10', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
    comorbidities=[dict(prior_malignancy=None, comorbidity_type_code='Not applicable')],
)

# D11: two treatments - one complete Surgery (with specimen exception), one incomplete Radiation
# (missing anatomical_site_irradiated) -> tests multi-treatment aggregation
donor('D11',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1959-11-11', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD11', date_of_diagnosis='2020-01-01', cancer_type_code='C34.9', primary_site='Lung',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP11', treatment_id='T11-surgery', specimen_collection_date='2020-01-05',
                    specimen_anatomic_location='Lung', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA11', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
    treatments=[
        dict(id='T11-surgery', treatment_type='Surgery', is_primary_treatment='Yes',
             treatment_start_date='2020-01-10', treatment_end_date='2020-01-10',
             treatment_intent='Curative', status_of_treatment='Treatment completed'),
        dict(id='T11-radiation', treatment_type='Radiation therapy', is_primary_treatment='No',
             treatment_start_date='2020-02-01', treatment_end_date='2020-03-01',
             treatment_intent='Adjuvant', status_of_treatment='Treatment completed'),
    ],
    surgeries=[dict(treatment_id='T11-surgery', surgery_reference_database='NCI Thesaurus',
                    surgery_type='Lobectomy', surgery_site=None, surgery_location=None)],  # exempt via specimen link
    radiations=[dict(treatment_id='T11-radiation', radiation_therapy_modality='EBRT',
                     radiation_therapy_type='3D-CRT', radiation_therapy_fractions='20',
                     radiation_therapy_fractions_not_available=None, radiation_therapy_dosage='60Gy',
                     radiation_therapy_dosage_not_available=None, anatomical_site_irradiated=None)],
)

# D12: systemic therapy ongoing (end_date exempt), dose reported with units -> sys_therapy complete;
# base treatment complete too
donor('D12',
    donor_row=dict(gender='Woman', sex_at_birth='Female', date_of_birth='1980-12-12', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD12', date_of_diagnosis='2022-01-01', cancer_type_code='C50.9', primary_site='Breast',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP12', treatment_id=None, specimen_collection_date='2022-01-05',
                    specimen_anatomic_location='Breast', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA12', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
    treatments=[dict(id='T12', treatment_type='Systemic therapy', is_primary_treatment='Yes',
                     treatment_start_date='2022-02-01', treatment_end_date=None,
                     treatment_intent='Curative', status_of_treatment='Treatment ongoing')],
    sys_therapies=[dict(treatment_id='T12', systemic_therapy_type='Chemotherapy', start_date='2022-02-01',
                        end_date=None, drug_reference_database='NCI Thesaurus', drug_reference_identifier='C1234',
                        drug_name='Doxorubicin', prescribed_cumulative_drug_dose='60',
                        actual_cumulative_drug_dose=None, drug_dose_units='mg/m2',
                        status_of_treatment='Treatment ongoing')],
)

# D13: systemic therapy NOT ongoing, missing end_date, dose reported missing units -> incomplete
donor('D13',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1963-01-13', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD13', date_of_diagnosis='2021-01-01', cancer_type_code='C61', primary_site='Prostate',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP13', treatment_id=None, specimen_collection_date='2021-01-05',
                    specimen_anatomic_location='Prostate', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA13', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
    treatments=[dict(id='T13', treatment_type='Systemic therapy', is_primary_treatment='Yes',
                     treatment_start_date='2021-02-01', treatment_end_date='2021-05-01',
                     treatment_intent='Curative', status_of_treatment='Treatment completed')],
    sys_therapies=[dict(treatment_id='T13', systemic_therapy_type='Chemotherapy', start_date='2021-02-01',
                        end_date=None, drug_reference_database='NCI Thesaurus', drug_reference_identifier='C1234',
                        drug_name='Doxorubicin', prescribed_cumulative_drug_dose='60',
                        actual_cumulative_drug_dose=None, drug_dose_units=None,
                        status_of_treatment='Treatment completed')],
)

# D14/D15/D16: minimal tier boundary donors (Tier A / Tier B / neither), all clinical fields
# minimally complete on every sample
def minimal_complete_pd_specimen(did, pd_id, spec_id):
    return (
        dict(id=pd_id, date_of_diagnosis='2020-01-01', cancer_type_code='C34.9', primary_site='Lung',
             basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
             clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
             pathological_tumour_staging_system=None, pathological_t_category=None,
             pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None),
        dict(id=spec_id, treatment_id=None, specimen_collection_date='2020-01-05',
             specimen_anatomic_location='Lung', tumour_normal_designation='Normal',
             tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
             reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
             tumour_grade=None, percent_tumour_cells_range=None, percent_tumour_cells_measurement_method=None),
    )

pd14, sp14 = minimal_complete_pd_specimen('D14', 'PD14', 'SP14')
donor('D14',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1961-01-14', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[pd14], specimens=[sp14],
    samples=[dict(id='SA14-normal', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA'),
             dict(id='SA14-tumour-dna', specimen_tissue_source='Tumour tissue', tumour_normal_designation='Tumour',
                  specimen_type='DNA', sample_type='Total DNA'),
             dict(id='SA14-tumour-rna', specimen_tissue_source='Tumour tissue', tumour_normal_designation='Tumour',
                  specimen_type='RNA', sample_type='Total RNA')],
)  # Tier A: normal DNA + tumour DNA + tumour RNA

pd15, sp15 = minimal_complete_pd_specimen('D15', 'PD15', 'SP15')
donor('D15',
    donor_row=dict(gender='Woman', sex_at_birth='Female', date_of_birth='1964-01-15', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[pd15], specimens=[sp15],
    samples=[dict(id='SA15-normal', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA'),
             dict(id='SA15-tumour-dna', specimen_tissue_source='Tumour tissue', tumour_normal_designation='Tumour',
                  specimen_type='DNA', sample_type='Total DNA')],
)  # Tier B only: normal DNA + tumour DNA, no tumour RNA

pd16, sp16 = minimal_complete_pd_specimen('D16', 'PD16', 'SP16')
donor('D16',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1967-01-16', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[pd16], specimens=[sp16],
    samples=[dict(id='SA16-tumour-dna', specimen_tissue_source='Tumour tissue', tumour_normal_designation='Tumour',
                  specimen_type='DNA', sample_type='Total DNA')],
)  # Neither tier: tumour DNA only, no normal

# D17: one sample fails minimal completeness (missing primary_site propagates via pd), the other
# sample is fine -> tests that get_minimal_completeness only "sees" the passing sample
donor('D17',
    donor_row=dict(gender='Woman', sex_at_birth='Female', date_of_birth='1969-01-17', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD17a', date_of_diagnosis='2020-01-01', cancer_type_code='C34.9', primary_site=None,
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None),
             dict(id='PD17b', date_of_diagnosis='2020-01-01', cancer_type_code='C34.9', primary_site='Lung',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP17a', treatment_id=None, specimen_collection_date='2020-01-05',
                    specimen_anatomic_location='Lung', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None, pd_id='PD17a'),
              dict(id='SP17b', treatment_id=None, specimen_collection_date='2020-01-05',
                    specimen_anatomic_location='Lung', tumour_normal_designation='Tumour',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None, pd_id='PD17b')],
    samples=[dict(id='SA17-normal', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA', spec_id='SP17a'),
             dict(id='SA17-tumour-dna', specimen_tissue_source='Tumour tissue', tumour_normal_designation='Tumour',
                  specimen_type='DNA', sample_type='Total DNA', spec_id='SP17b')],
)


# --- edge cases added after the real-instance smoke test found gaps in the draft new_derivation.py ---

def _simple_pd_specimen(pd_id, spec_id):
    return (
        dict(id=pd_id, date_of_diagnosis='2020-01-01', cancer_type_code='C34.9', primary_site='Lung',
             basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
             clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
             pathological_tumour_staging_system=None, pathological_t_category=None,
             pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None),
        dict(id=spec_id, treatment_id=None, specimen_collection_date='2020-01-05',
             specimen_anatomic_location='Lung', tumour_normal_designation='Normal',
             tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
             reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
             tumour_grade=None, percent_tumour_cells_range=None, percent_tumour_cells_measurement_method=None),
    )

# D18: ongoing Radiation treatment missing treatment_end_date, but every radiation-specific field
# present -> radiation_donor_complete should be False (radiation requires end_date UNCONDITIONALLY,
# unlike the base Treatment category which exempts it when ongoing)
pd18, sp18 = _simple_pd_specimen('PD18', 'SP18')
donor('D18',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1960-01-18', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[pd18], specimens=[sp18],
    samples=[dict(id='SA18', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
    treatments=[dict(id='T18', treatment_type='Radiation therapy', is_primary_treatment='Yes',
                     treatment_start_date='2020-02-01', treatment_end_date=None,
                     treatment_intent='Palliative', status_of_treatment='Treatment ongoing')],
    radiations=[dict(treatment_id='T18', radiation_therapy_modality='EBRT', radiation_therapy_type='3D-CRT',
                     radiation_therapy_fractions='10', radiation_therapy_fractions_not_available=None,
                     radiation_therapy_dosage='30Gy', radiation_therapy_dosage_not_available=None,
                     anatomical_site_irradiated='Lung')],
)

# D19: ongoing Systemic therapy treatment missing (base) treatment_end_date, own end_date also
# missing but exempt via ongoing, all other sys_therapy fields present, no dose reported ->
# sys_therapy_donor_complete should be True (sys therapy DOES honour the ongoing exemption, both
# at the base Treatment level and its own end_date)
pd19, sp19 = _simple_pd_specimen('PD19', 'SP19')
donor('D19',
    donor_row=dict(gender='Woman', sex_at_birth='Female', date_of_birth='1962-01-19', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[pd19], specimens=[sp19],
    samples=[dict(id='SA19', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
    treatments=[dict(id='T19', treatment_type='Systemic therapy', is_primary_treatment='Yes',
                     treatment_start_date='2021-03-01', treatment_end_date=None,
                     treatment_intent='Curative', status_of_treatment='Treatment ongoing')],
    sys_therapies=[dict(treatment_id='T19', systemic_therapy_type='Chemotherapy', start_date='2021-03-01',
                        end_date=None, drug_reference_database='NCI Thesaurus', drug_reference_identifier='C9999',
                        drug_name='Paclitaxel', prescribed_cumulative_drug_dose=None,
                        actual_cumulative_drug_dose=None, drug_dose_units=None,
                        status_of_treatment='Treatment ongoing')],
)

# D20: Surgery treatment missing (base) treatment_intent, all surgery-specific fields present ->
# surgery_donor_complete should be False (base treatment fields required for the record to count
# at all, matching fullsome_treatments_surgery.sql's join back to Treatment)
pd20, sp20 = _simple_pd_specimen('PD20', 'SP20')
donor('D20',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1964-01-20', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[pd20], specimens=[sp20],
    samples=[dict(id='SA20', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type='DNA', sample_type='Total DNA')],
    treatments=[dict(id='T20', treatment_type='Surgery', is_primary_treatment='Yes',
                     treatment_start_date='2020-04-01', treatment_end_date='2020-04-02',
                     treatment_intent=None, status_of_treatment='Treatment completed')],
    surgeries=[dict(treatment_id='T20', surgery_reference_database='NCI Thesaurus', surgery_type='Excision',
                    surgery_site='Skin', surgery_location='Back')],
)

# D21: specimen with NO matched sample registration record at all -> specimen_donor_complete
# should be False (old code's join+filter silently excludes unmatched specimens)
donor('D21',
    donor_row=dict(gender='Woman', sex_at_birth='Female', date_of_birth='1966-01-21', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD21', date_of_diagnosis='2020-01-01', cancer_type_code='C34.9', primary_site='Lung',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP21', treatment_id=None, specimen_collection_date='2020-01-05',
                    specimen_anatomic_location='Lung', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[],  # no matching sample at all
)

# D22: specimen with a matched sample that's missing specimen_type -> specimen_donor_complete
# should be False (matched sample's registration fields must all be present too)
donor('D22',
    donor_row=dict(gender='Man', sex_at_birth='Male', date_of_birth='1968-01-22', date_resolution='Year',
                   is_deceased='No', date_of_death=None, cause_of_death=None),
    pd_rows=[dict(id='PD22', date_of_diagnosis='2020-01-01', cancer_type_code='C34.9', primary_site='Lung',
                  basis_of_diagnosis='Histology', clinical_tumour_staging_system=None, clinical_t_category=None,
                  clinical_n_category=None, clinical_m_category=None, clinical_stage_group=None,
                  pathological_tumour_staging_system=None, pathological_t_category=None,
                  pathological_n_category=None, pathological_m_category=None, pathological_stage_group=None)],
    specimens=[dict(id='SP22', treatment_id=None, specimen_collection_date='2020-01-05',
                    specimen_anatomic_location='Lung', tumour_normal_designation='Normal',
                    tumour_histological_type=None, reference_pathology_confirmed_diagnosis=None,
                    reference_pathology_confirmed_tumour_presence=None, tumour_grading_system=None,
                    tumour_grade=None, percent_tumour_cells_range=None,
                    percent_tumour_cells_measurement_method=None)],
    samples=[dict(id='SA22', specimen_tissue_source='Blood', tumour_normal_designation='Normal',
                  specimen_type=None, sample_type='Total DNA')],  # specimen_type missing
)


def get_donor_ids():
    return list(DONORS.keys())
