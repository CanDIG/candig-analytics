COPY (SELECT program_id_id, submitter_donor_id, submitter_sample_id, sample_type, tumour_normal_designation
FROM mohpackets_sampleregistration
WHERE specimen_tissue_source IS NOT NULL
  AND tumour_normal_designation IS NOT NULL
  AND specimen_type IS NOT NULL
  AND sample_type IS NOT NULL) TO '/tmp/fullsome_sample_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT  program_id_id, submitter_donor_id, submitter_sample_id, tumour_normal_designation, sample_type COUNT(*)
  FROM mohpackets_sampleregistration
  GROUP BY program_id_id, submitter_donor_id, submitter_sample_id)
  TO '/tmp/fullsome_sample_count.csv' with (FORMAT CSV, HEADER);