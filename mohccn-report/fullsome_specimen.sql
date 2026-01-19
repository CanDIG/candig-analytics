COPY (SELECT mohpackets_specimen.program_id_id, mohpackets_specimen.submitter_donor_id, mohpackets_specimen.submitter_specimen_id, submitter_treatment_id,
submitter_sample_id, tumour_histological_type, reference_pathology_confirmed_diagnosis, reference_pathology_confirmed_tumour_presence,
tumour_grading_system, tumour_grade, percent_tumour_cells_range, percent_tumour_cells_measurement_method,
tumour_normal_designation
FROM mohpackets_specimen
LEFT JOIN mohpackets_sampleregistration ON mohpackets_specimen.submitter_specimen_id = mohpackets_sampleregistration.submitter_specimen_id
WHERE mohpackets_specimen.program_id_id IS NOT NULL
  AND specimen_collection_date IS NOT NULL
  AND specimen_anatomic_location IS NOT NULL
  AND specimen_tissue_source IS NOT NULL
  AND tumour_normal_designation IS NOT NULL
  AND specimen_type IS NOT NULL
  AND sample_type IS NOT NULL) TO '/tmp/fullsome_specimen_completeness.csv' with (FORMAT CSV, HEADER);
COPY (SELECT  mohpackets_specimen.program_id_id, mohpackets_specimen.submitter_donor_id,
  mohpackets_specimen.submitter_specimen_id, COUNT(*)
  FROM mohpackets_specimen
  LEFT JOIN mohpackets_sampleregistration ON mohpackets_specimen.submitter_specimen_id = mohpackets_sampleregistration.submitter_specimen_id
  GROUP BY mohpackets_specimen.program_id_id, mohpackets_specimen.submitter_donor_id, mohpackets_specimen.submitter_specimen_id)
  TO '/tmp/fullsome_specimen_count.csv' with (FORMAT CSV, HEADER);