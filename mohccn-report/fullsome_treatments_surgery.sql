COPY (SELECT mohpackets_donor.program_id_id, mohpackets_donor.submitter_donor_id, mohpackets_primarydiagnosis.submitter_primary_diagnosis_id,
mohpackets_treatment.submitter_treatment_id, treatment_type, surgery_site, surgery_location
FROM mohpackets_donor LEFT JOIN mohpackets_primarydiagnosis ON mohpackets_donor.submitter_donor_id = mohpackets_primarydiagnosis.submitter_donor_id
LEFT JOIN mohpackets_treatment ON mohpackets_primarydiagnosis.submitter_primary_diagnosis_id = mohpackets_treatment.submitter_primary_diagnosis_id
RIGHT JOIN mohpackets_surgery ON mohpackets_treatment.submitter_treatment_id = mohpackets_surgery.submitter_treatment_id
WHERE mohpackets_donor.program_id_id IS NOT NULL
  AND treatment_type IS NOT NULL
  AND is_primary_treatment IS NOT NULL
  AND treatment_start_date IS NOT NULL
  AND treatment_end_date IS NOT NULL
  AND treatment_intent IS NOT NULL
  AND surgery_reference_database IS NOT NULL
  AND surgery_type IS NOT NULL) TO '/tmp/fullsome_treatments_surgery_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT program_id_id, submitter_donor_id, COUNT(*)
FROM mohpackets_surgery
GROUP BY program_id_id, submitter_donor_id)
  TO '/tmp/fullsome_treatments_surgery_count.csv' with (FORMAT CSV, HEADER);