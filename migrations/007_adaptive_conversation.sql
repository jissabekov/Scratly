BEGIN;

-- Reply-signal routing is audited as a first-class decision event.
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'reply_signal_classified';

-- Optional legacy location dimension (not required). V1 stores geography on
-- assessment.constraints; a required duplicate caused re-asks after answers like
-- "Bristow, Oklahoma". See 009_demote_location_dimension.sql for existing DBs.
INSERT INTO assessment.dimensions(key, label, required, ordinal)
VALUES ('location', 'Broad location (legacy; use constraints)', false, 9)
ON CONFLICT (key) DO UPDATE
SET required = false,
    label = EXCLUDED.label;

INSERT INTO assessment.question_intents(key, priority, fallback_template)
VALUES
  ('conversation_repair', 1, 'You’re right — I made an assumption there. Let me stick to what you actually said: what have you been enjoying about it?'),
  ('behavioral_anchor', 3, 'Tell me about the last time you chose to spend a while on something — what kept you with it?')
ON CONFLICT (key) DO NOTHING;

UPDATE assessment.question_intents
SET priority = priority + 2
WHERE key NOT IN ('conversation_repair', 'behavioral_anchor');

COMMIT;
