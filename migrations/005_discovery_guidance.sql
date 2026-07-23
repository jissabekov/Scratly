-- Soften discovery ask language: interests-first feel, no "non-negotiable" opener.
UPDATE assessment.question_intents
   SET fallback_template = 'What kinds of projects or topics are you drawn to?'
 WHERE key = 'required_hard_variable';

UPDATE assessment.question_intents
   SET fallback_template = 'Which topic or kind of project would you most like to explore?'
 WHERE key = 'project_critical_unknown';

UPDATE assessment.question_intents
   SET fallback_template = 'Where are you based (city or region), or is remote work fine?'
 WHERE key = 'location_constraint';
