COPY (SELECT mohpackets_donor.program_id_id, mohpackets_donor.submitter_donor_id, mohpackets_primarydiagnosis.submitter_primary_diagnosis_id,
mohpackets_treatment.submitter_treatment_id, treatment_type, status_of_treatment
FROM
mohpackets_donor
LEFT JOIN mohpackets_primarydiagnosis
ON mohpackets_donor.submitter_donor_id = mohpackets_primarydiagnosis.submitter_donor_id
AND mohpackets_donor.program_id_id = mohpackets_primarydiagnosis.program_id_id
LEFT JOIN mohpackets_treatment
ON mohpackets_primarydiagnosis.submitter_primary_diagnosis_id = mohpackets_treatment.submitter_primary_diagnosis_id
AND mohpackets_primarydiagnosis.program_id_id = mohpackets_treatment.program_id_id
WHERE mohpackets_donor.program_id_id IS NOT NULL
  AND treatment_type IS NOT NULL
  AND is_primary_treatment IS NOT NULL
  AND treatment_start_date IS NOT NULL
  AND (treatment_end_date IS NOT NULL
  OR status_of_treatment = 'Treatment ongoing')
  AND treatment_intent IS NOT NULL
  ) TO '/tmp/fullsome_treatments_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT program_id_id, submitter_donor_id, COUNT(*)
FROM mohpackets_treatment
GROUP BY program_id_id, submitter_donor_id)
  TO '/tmp/fullsome_treatments_count.csv' with (FORMAT CSV, HEADER);