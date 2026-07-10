COPY (SELECT program_id_id, submitter_donor_id, gender, sex_at_birth, date_of_birth, date_resolution,
is_deceased, cause_of_death, date_of_death
FROM mohpackets_donor)
TO '/tmp/all_donor_completeness.csv' with (FORMAT CSV, HEADER);
