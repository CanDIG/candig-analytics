COPY (SELECT program_id_id, submitter_donor_id, date_of_followup, disease_status_at_followup
FROM mohpackets_followup
WHERE date_of_followup IS NOT NULL
  AND disease_status_at_followup IS NOT NULL)
  TO '/tmp/fullsome_followup_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT program_id_id, submitter_donor_id, COUNT(*)
FROM mohpackets_followup
GROUP BY submitter_donor_id)
  TO '/tmp/fullsome_followup_count.csv' with (FORMAT CSV, HEADER);