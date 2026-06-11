COPY (SELECT mohpackets_donor.program_id_id, mohpackets_donor.submitter_donor_id, mohpackets_primarydiagnosis.submitter_primary_diagnosis_id,
mohpackets_treatment.submitter_treatment_id, treatment_type, prescribed_cumulative_drug_dose, actual_cumulative_drug_dose, drug_dose_units,
status_of_treatment
FROM mohpackets_donor
LEFT JOIN mohpackets_primarydiagnosis
ON mohpackets_donor.submitter_donor_id = mohpackets_primarydiagnosis.submitter_donor_id
AND mohpackets_donor.program_id_id = mohpackets_primarydiagnosis.program_id_id
LEFT JOIN mohpackets_treatment
ON mohpackets_primarydiagnosis.submitter_primary_diagnosis_id = mohpackets_treatment.submitter_primary_diagnosis_id
AND mohpackets_primarydiagnosis.program_id_id = mohpackets_treatment.program_id_id
RIGHT JOIN mohpackets_systemictherapy
ON mohpackets_treatment.submitter_treatment_id = mohpackets_systemictherapy.submitter_treatment_id
AND mohpackets_treatment.program_id_id = mohpackets_systemictherapy.program_id_id
WHERE mohpackets_donor.program_id_id IS NOT NULL
  AND treatment_type IS NOT NULL
  AND is_primary_treatment IS NOT NULL
  AND treatment_start_date IS NOT NULL
  AND (treatment_end_date IS NOT NULL
  OR status_of_treatment = 'Treatment ongoing')
  AND treatment_intent IS NOT NULL
  AND systemic_therapy_type IS NOT NULL
  AND start_date IS NOT NULL
  AND (end_date IS NOT NULL
  OR status_of_treatment = 'Treatment ongoing')
  AND drug_reference_database IS NOT NULL
  AND drug_reference_identifier IS NOT NULL
  AND drug_name IS NOT NULL) TO '/tmp/fullsome_treatments_sys_therapy_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT program_id_id, submitter_donor_id, submitter_treatment_id, COUNT(*)
FROM mohpackets_systemictherapy
GROUP BY program_id_id, submitter_donor_id, submitter_treatment_id)
  TO '/tmp/fullsome_treatments_sys_therapy_count.csv' with (FORMAT CSV, HEADER);