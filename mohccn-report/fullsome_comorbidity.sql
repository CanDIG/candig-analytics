COPY (SELECT program_id_id, submitter_donor_id, prior_malignancy, comorbidity_type_code
FROM mohpackets_comorbidity
WHERE comorbidity_type_code IS NOT NULL)
  TO '/tmp/fullsome_comorbidity_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT program_id_id, submitter_donor_id, COUNT(*)
FROM mohpackets_comorbidity
GROUP BY submitter_donor_id)
  TO '/tmp/fullsome_comorbidity_count.csv' with (FORMAT CSV, HEADER);