COPY (SELECT program_id_id, submitter_donor_id, is_deceased, date_of_death
FROM mohpackets_donor
WHERE gender IS NOT NULL
  AND sex_at_birth IS NOT NULL
  AND date_of_birth IS NOT NULL
  AND date_resolution IS NOT NULL) TO '/tmp/fullsome_donor_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT program_id_id, submitter_donor_id, COUNT(*)
  FROM mohpackets_donor
  GROUP BY program_id_id, submitter_donor_id)
  TO '/tmp/fullsome_donor_count.csv' with (FORMAT CSV, HEADER);