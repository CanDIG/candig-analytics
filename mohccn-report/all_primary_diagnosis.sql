COPY (SELECT program_id_id, submitter_donor_id, submitter_primary_diagnosis_id,
date_of_diagnosis, cancer_type_code, primary_site, basis_of_diagnosis,
clinical_tumour_staging_system, clinical_t_category, clinical_n_category, clinical_m_category, clinical_stage_group,
pathological_tumour_staging_system, pathological_t_category, pathological_n_category, pathological_m_category, pathological_stage_group
FROM mohpackets_primarydiagnosis)
TO '/tmp/all_primary_diagnosis_completeness.csv' with (FORMAT CSV, HEADER);
