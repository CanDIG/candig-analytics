COPY (SELECT program_id_id, submitter_donor_id, submitter_sample_id
FROM mohpackets_sampleregistration
WHERE specimen_tissue_source IS NOT NULL
  AND tumour_normal_designation IS NOT NULL
  AND specimen_type IS NOT NULL
  AND sample_type IS NOT NULL) TO '/tmp/fullsome_sample_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT  program_id_id, submitter_donor_id, submitter_sample_id, COUNT(*)
  FROM mohpackets_sampleregistration)
  TO '/tmp/fullsome_sample_count.csv' with (FORMAT CSV, HEADER);