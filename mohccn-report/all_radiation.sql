COPY (SELECT program_id_id, submitter_donor_id, submitter_treatment_id,
radiation_therapy_modality, radiation_therapy_type, radiation_therapy_fractions,
radiation_therapy_fractions_not_available, radiation_therapy_dosage, radiation_therapy_dosage_not_available,
anatomical_site_irradiated
FROM mohpackets_radiation)
TO '/tmp/all_radiation_completeness.csv' with (FORMAT CSV, HEADER);
