COPY (SELECT program_id_id, submitter_donor_id, date_of_followup, disease_status_at_followup,
relapse_type, date_of_relapse, method_of_progression_status, anatomic_site_progression_or_recurrence
FROM mohpackets_followup)
TO '/tmp/all_followup_completeness.csv' with (FORMAT CSV, HEADER);
