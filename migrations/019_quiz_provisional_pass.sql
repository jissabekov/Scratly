BEGIN;

-- Plan 04 §4.1: at the attempt cap, a student who is demonstrably close
-- (BKT P(mastery) >= 0.8 on every critical objective) gets a provisional pass
-- instead of a dead end. `passed` stays the strict 4/5 + critical-coverage
-- result so the two are never conflated; unlock = passed OR provisional.

ALTER TABLE learning.quiz_attempts
    ADD COLUMN provisional boolean NOT NULL DEFAULT false;

COMMIT;
