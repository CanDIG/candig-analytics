COPY (
  SELECT drs_object_1.name, drs_object_1.id, drs_object_1.program_id, drs_object_1.description, drs_object_2.id AS id_1, drs_object_2.description AS analysis_type, content_object.id AS id_2, content_object.drs_object_id, content_object.name AS analysis_name, content_object.contents_id, content_object.drs_uri, content_object.contents 
FROM content_object JOIN drs_object AS drs_object_1 ON content_object.drs_object_id = drs_object_1.id JOIN drs_object AS drs_object_2 ON content_object.contents_id = drs_object_2.id 
WHERE drs_object_1.description IN ('wgs', 'wts'))
  TO '/tmp/genomic_completeness.csv' with (FORMAT CSV, HEADER);