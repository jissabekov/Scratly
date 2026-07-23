from dataclasses import dataclass
from app.services.question_policy import InterviewPhase


@dataclass(frozen=True)
class QuestionIntent:
    key: str
    question_class: str
    phase: InterviewPhase
    purpose: str
    target_dimensions: tuple[str, ...]
    allowed_formats: tuple[str, ...]
    fallback_template: str
    requires_behavioral_followup: bool = False


ANCHORS = (
    QuestionIntent('voluntary_attention','discover',InterviewPhase.BROAD_DISCOVERY,'Find repeated voluntary attention.',('attraction',),('open',),'Think about the last couple of months: what did you end up spending more free time on than you expected?'),
    QuestionIntent('attraction_mechanism','deepen',InterviewPhase.BEHAVIORAL_EVIDENCE,'Resolve what rewards the volunteered activity.',('attraction','reward'),('open',),'Pick one of those—what keeps pulling you back to it?'),
    QuestionIntent('active_engagement','deepen',InterviewPhase.BEHAVIORAL_EVIDENCE,'Distinguish consuming, investigating, making, competing, and organizing.',('operating_style',),('open','bounded_examples'),'What do you actually end up doing with that interest?'),
    QuestionIntent('friction','discover',InterviewPhase.BROAD_DISCOVERY,'Find problem sensitivity and values.',('attraction','reward'),('behavioral',),'What regularly annoys you more than it seems to annoy other people?'),
    QuestionIntent('natural_contribution','evidence',InterviewPhase.BEHAVIORAL_EVIDENCE,'Observe contribution in a successful group.',('operating_style','reality'),('behavioral',),'Think of a group situation that went well—what did you do that helped it work?'),
    QuestionIntent('persistence_mechanism','evidence',InterviewPhase.BEHAVIORAL_EVIDENCE,'Observe what sustains effort after novelty fades.',('reward','reality'),('behavioral',),'What is something difficult you kept doing after it stopped being fun, and what kept you going?'),
    QuestionIntent('natural_competence','evidence',InterviewPhase.BEHAVIORAL_EVIDENCE,'Use requests for help as a competence proxy.',('reality',),('behavioral',),'What do people around you tend to ask you for help with?'),
    QuestionIntent('aspirational_attraction','counterfactual',InterviewPhase.PROJECT_FIT_PROBING,'Capture aspiration separately from demonstrated behavior.',('attraction',),('counterfactual',),'If you became unusually good at one thing over the next three years, what would be exciting to be good at?'),
)

BY_KEY = {intent.key: intent for intent in ANCHORS}
