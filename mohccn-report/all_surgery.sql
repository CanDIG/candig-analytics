COPY (SELECT program_id_id, submitter_donor_id, submitter_treatment_id,
surgery_reference_database, surgery_type, surgery_site, surgery_location
FROM mohpackets_surgery)
TO '/tmp/all_surgery_completeness.csv' with (FORMAT CSV, HEADER);
