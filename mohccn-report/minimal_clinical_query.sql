COPY (SELECT mohpackets_donor.program_id_id, mohpackets_donor.submitter_donor_id,
mohpackets_sampleregistration.submitter_sample_id, tumour_normal_designation,
sample_type, COUNT(*) AS non_null_row_count
FROM
mohpackets_sampleregistration
JOIN mohpackets_specimen ON mohpackets_sampleregistration.submitter_specimen_id = mohpackets_specimen.submitter_specimen_id
JOIN mohpackets_primarydiagnosis ON mohpackets_specimen.submitter_primary_diagnosis_id = mohpackets_primarydiagnosis.submitter_primary_diagnosis_id
JOIN mohpackets_donor ON mohpackets_primarydiagnosis.submitter_donor_id = mohpackets_donor.submitter_donor_id
WHERE mohpackets_donor.program_id_id IS NOT NULL
  AND gender IS NOT NULL
  AND sex_at_birth IS NOT NULL
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
  sample_type) TO '/minimal_completeness.csv' with (FORMAT CSV, HEADER);