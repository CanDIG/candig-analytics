COPY (SELECT program_id_id, submitter_donor_id,
clinical_tumour_staging_system, clinical_t_category, clinical_n_category, clinical_m_category, clinical_stage_group,
pathological_tumour_staging_system, pathological_t_category, pathological_n_category, pathological_m_category, pathological_stage_group
FROM mohpackets_primarydiagnosis
  WHERE date_of_diagnosis IS NOT NULL
  AND cancer_type_code IS NOT NULL
  AND primary_site IS NOT NULL
  AND basis_of_diagnosis IS NOT NULL) TO '/tmp/fullsome_primary_diagnosis_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT program_id_id, submitter_donor_id, COUNT(*)
FROM mohpackets_primarydiagnosis GROUP BY program_id_id, submitter_donor_id)
  TO '/tmp/fullsome_primary_diagnosis_count.csv' with (FORMAT CSV, HEADER);