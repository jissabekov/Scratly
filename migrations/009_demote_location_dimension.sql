BEGIN;

-- Migration 007 introduced a separate required `location` dimension, but V1
-- stores geography on assessment.constraints. Keeping both required caused
-- re-asks for location after the student already answered (e.g. "Bristow,
-- Oklahoma" stored as constraints/oklahoma while location coverage stayed
-- unknown). Demote the duplicate dimension so candidate selection uses
-- constraints / location_constraint only.

UPDATE assessment.dimensions
   SET required = false,
       label = 'Broad location (legacy; use constraints)'
 WHERE key = 'location';

COMMIT;
