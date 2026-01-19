COPY (SELECT mohpackets_donor.program_id_id, mohpackets_donor.submitter_donor_id, mohpackets_primarydiagnosis.submitter_primary_diagnosis_id,
mohpackets_treatment.submitter_treatment_id, treatment_type
FROM mohpackets_donor
LEFT JOIN mohpackets_primarydiagnosis ON mohpackets_donor.submitter_donor_id = mohpackets_primarydiagnosis.submitter_donor_id
LEFT JOIN mohpackets_treatment ON mohpackets_primarydiagnosis.submitter_primary_diagnosis_id = mohpackets_treatment.submitter_primary_diagnosis_id
RIGHT JOIN mohpackets_radiation ON mohpackets_treatment.submitter_treatment_id = mohpackets_radiation.submitter_treatment_id
WHERE mohpackets_donor.program_id_id IS NOT NULL
  AND treatment_type IS NOT NULL
  AND is_primary_treatment IS NOT NULL
  AND treatment_start_date IS NOT NULL
  AND treatment_end_date IS NOT NULL
  AND treatment_intent IS NOT NULL
  AND radiation_therapy_modality IS NOT NULL
  AND radiation_therapy_type IS NOT NULL
  AND radiation_therapy_fractions IS NOT NULL
  AND radiation_therapy_dosage IS NOT NULL
  AND anatomical_site_irradiated IS NOT NULL) TO '/tmp/fullsome_treatments_radiation_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT program_id_id, submitter_donor_id, submitter_treatment_id, COUNT(*)
FROM mohpackets_radiation
GROUP BY program_id_id, submitter_donor_id, submitter_treatment_id)
  TO '/tmp/fullsome_treatments_radiation_count.csv' with (FORMAT CSV, HEADER);