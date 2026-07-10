COPY (SELECT program_id_id, submitter_donor_id, submitter_treatment_id,
treatment_type, is_primary_treatment, treatment_start_date, treatment_end_date, treatment_intent, status_of_treatment
FROM mohpackets_treatment)
TO '/tmp/all_treatments_raw_completeness.csv' with (FORMAT CSV, HEADER);
