COPY (SELECT program_id_id, submitter_donor_id, prior_malignancy, comorbidity_type_code
FROM mohpackets_comorbidity)
TO '/tmp/all_comorbidity_completeness.csv' with (FORMAT CSV, HEADER);
