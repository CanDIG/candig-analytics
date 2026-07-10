COPY (SELECT program_id_id, submitter_donor_id, submitter_sample_id, submitter_specimen_id,
specimen_tissue_source, tumour_normal_designation, specimen_type, sample_type
FROM mohpackets_sampleregistration)
TO '/tmp/all_sample_completeness.csv' with (FORMAT CSV, HEADER);
