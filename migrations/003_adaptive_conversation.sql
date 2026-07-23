BEGIN;

-- Location is opportunity-critical but deliberately broad: exact addresses are never needed.
INSERT INTO assessment.dimensions(key, label, required, ordinal)
VALUES ('location', 'Broad location', true, 9)
ON CONFLICT (key) DO NOTHING;

INSERT INTO assessment.question_intents(key, priority, fallback_template)
VALUES
  ('conversation_repair', 1, 'You’re right — I made an assumption there. Let me stick to what you actually said: what have you been enjoying about it?'),
  ('behavioral_anchor', 3, 'Tell me about the last time you chose to spend a while on something — what kept you with it?')
ON CONFLICT (key) DO NOTHING;

UPDATE assessment.question_intents
SET priority = priority + 2
WHERE key NOT IN ('conversation_repair', 'behavioral_anchor');

COMMIT;
