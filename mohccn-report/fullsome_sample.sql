COPY (SELECT mohpackets_donor.program_id_id, mohpackets_donor.submitter_donor_id,
mohpackets_sampleregistration.submitter_sample_id, mohpackets_specimen.submitter_treatment_id, date_of_death, cause_of_death,
tumour_histological_type, reference_pathology_confirmed_diagnosis, reference_pathology_confirmed_tumour_presence,
tumour_grading_system, tumour_grade, percent_tumour_cells_range, percent_tumour_cells_measurement_method,
clinical_tumour_staging_system, clinical_t_category, clinical_n_category, clinical_m_category, clinical_stage_group,
pathological_tumour_staging_system, pathological_t_category, pathological_n_category, pathological_m_category, pathological_stage_group,
FROM mohpackets_donor LEFT JOIN mohpackets_primarydiagnosis ON mohpackets_donor.submitter_donor_id = mohpackets_primarydiagnosis.submitter_donor_id
LEFT JOIN mohpackets_specimen ON mohpackets_primarydiagnosis.submitter_primary_diagnosis_id = mohpackets_specimen.submitter_primary_diagnosis_id
LEFT JOIN mohpackets_sampleregistration ON mohpackets_specimen.submitter_specimen_id = mohpackets_sampleregistration.submitter_specimen_id
WHERE mohpackets_donor.program_id_id IS NOT NULL
  AND gender IS NOT NULL
  AND sex_at_birth IS NOT NULL
  AND is_deceased IS NOT NULL
  AND date_of_birth IS NOT NULL
  AND date_resolution IS NOT NULL
  AND date_of_diagnosis IS NOT NULL
  AND cancer_type_code IS NOT NULL
  AND primary_site IS NOT NULL
  AND basis_of_diagnosis IS NOT NULL
  AND specimen_collection_date IS NOT NULL
  AND specimen_anatomic_location IS NOT NULL
  AND specimen_tissue_source IS NOT NULL
  AND tumour_normal_designation IS NOT NULL
  AND specimen_type IS NOT NULL
  AND sample_type IS NOT NULL
  GROUP BY mohpackets_donor.program_id_id, mohpackets_donor.submitter_donor_id,
  mohpackets_sampleregistration.submitter_sample_id, tumour_normal_designation,
  sample_type) TO '/tmp/fullsome_sample_completeness.csv' with (FORMAT CSV, HEADER);