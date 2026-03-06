COPY (SELECT mohpackets_donor.program_id_id, mohpackets_donor.submitter_donor_id,
  gender, sex_at_birth, date_of_birth, date_resolution, date_of_diagnosis,
  cancer_type_code, primary_site, basis_of_diagnosis, specimen_collection_date,
  specimen_anatomic_location, specimen_tissue_source,
mohpackets_sampleregistration.submitter_sample_id, tumour_normal_designation,
sample_type, specimen_type
FROM mohpackets_donor
LEFT JOIN mohpackets_primarydiagnosis ON mohpackets_donor.submitter_donor_id = mohpackets_primarydiagnosis.submitter_donor_id
LEFT JOIN mohpackets_specimen ON mohpackets_primarydiagnosis.submitter_primary_diagnosis_id = mohpackets_specimen.submitter_primary_diagnosis_id
LEFT JOIN mohpackets_sampleregistration ON mohpackets_specimen.submitter_specimen_id = mohpackets_sampleregistration.submitter_specimen_id
WHERE
  gender IS NULL
  OR sex_at_birth IS NULL
  OR date_of_birth IS NULL
  OR date_resolution IS NULL
  OR date_of_diagnosis IS NULL
  OR cancer_type_code IS NULL
  OR primary_site IS NULL
  OR basis_of_diagnosis IS NULL
  OR specimen_collection_date IS NULL
  OR specimen_anatomic_location IS NULL
  OR specimen_tissue_source IS NULL
  OR tumour_normal_designation IS NULL
  OR specimen_type IS NULL
  OR sample_type IS NULL) TO '/tmp/failed_minimal_completeness.csv' with (FORMAT CSV, HEADER);