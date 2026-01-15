COPY (SELECT program_id_id, submitter_donor_id, COUNT(*)
FROM mohpackets_comorbidity
GROUP BY program_id_id, submitter_donor_id)
  TO '/tmp/fullsome_comorbidity_count.csv' with (FORMAT CSV, HEADER);