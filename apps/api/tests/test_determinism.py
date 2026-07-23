from dataclasses import dataclass
from uuid import uuid4
from app.contracts import ProposedEvidence
from app.services.grounding_validator import validate_grounding
from app.services.profile_reducer import reduce_profile
from app.services.question_policy import InterviewPhase, PlannerAction, QuestionValue, ReplySignal, Target, classify_reply, derive_phase, plan_next, select_next, derive_stage
from app.services.project_matcher import decision_entropy, fit_distribution, rank_projects, recommendation_ready
from app.services.question_quality import validate_question
from app.services.azure_openai import _json_default
import json
from app.services.context_builder import ContextBuilder
@dataclass
class Msg: id:object; session_id:object; content:str
def item(mid,quote='exact',value='a',strength=.8): return ProposedEvidence(dimension_key='topics',value_key=value,strength=strength,source_message_ids=[mid],exact_source_quote=quote,rationale='test')
def test_invented_and_cross_session_quotes_rejected():
 s,other=uuid4(),uuid4(); m=Msg(uuid4(),s,'an exact answer')
 assert validate_grounding([item(m.id,'invented')],[m],s)[0].rejection_reason=='exact_quote_not_found'
 assert validate_grounding([item(m.id,'exact')],[m],other)[0].rejection_reason=='source_message_unavailable_or_not_owned'
def test_reducer_accepted_only_and_threshold():
 s=uuid4(); m=Msg(uuid4(),s,'exact'); accepted=validate_grounding([item(m.id),item(m.id,value='b',strength=.1)],[m],s)
 profile=reduce_profile(accepted); assert profile.reducer_version=='v2' and profile.dimensions[0].value=='a' and profile.dimensions[0].status=='provisional'
def test_question_priority_and_stages():
 targets=[Target('profile_validation','z','z'),Target('contradiction','a','a')]
 assert select_next(targets).kind=='contradiction'
 assert derive_stage(coverage=.95,contradictions=0,reviewed=False,projects_ready=False)=='profile_review'
 assert derive_stage(coverage_established=0.0,coverage_touched=1.0,contradictions=2,reviewed=False,projects_ready=False)=='measurement'
def test_dialogue_signals_and_question_tiebreaks():
 assert classify_reply('hello') == ReplySignal.GREETING
 assert classify_reply('I said I play, why are you asking about a project?') == ReplySignal.CORRECTION
 assert classify_reply('nothing') == ReplySignal.INSUFFICIENT
 targets=[Target('behavioral_anchor','old','x',information_gain=.9,continuity=.9,asked_count=1),Target('behavioral_anchor','fresh','x',information_gain=.6,continuity=.5)]
 assert select_next(targets).key == 'fresh'
 valuable=Target('project_discrimination','valuable','x',value=QuestionValue(project_discrimination=1,uncertainty_reduction=1))
 weak=Target('required_hard_variable','weak','x',value=QuestionValue(uncertainty_reduction=.1))
 assert select_next([weak,valuable]).key == 'valuable'
 assert derive_phase(anchors_observed=2,strong_evidence=4,contradictions=1,project_modes=3,reviewed=False) == InterviewPhase.UNCERTAINTY_RESOLUTION


def test_planner_enforces_topic_budget_and_rejection():
 current = Target('project_critical_unknown', 'topics', 'x', asked_count=2)
 gap = Target('required_hard_variable', 'capability', 'y', asked_count=0)
 decision = plan_next([current, gap], last_target_key='topics', student_text='more detail')
 assert decision.action == PlannerAction.SWITCH
 assert decision.target.key == 'capability'
 assert decision.reason == 'topic_budget_reached'

 rejected = plan_next(
  [current, gap], last_target_key='topics',
  student_text='Can we talk about something else?'
 )
 assert rejected.action == PlannerAction.SWITCH
 assert rejected.target.key == 'capability'
 assert rejected.avoid_topics == ('topics',)


def test_no_and_unknown_kill_weak_branches():
 assert classify_reply('no') == ReplySignal.INSUFFICIENT
 assert classify_reply("I don't know") == ReplySignal.INSUFFICIENT
 current = Target('project_critical_unknown', 'topics', 'x', asked_count=1)
 gap = Target('required_hard_variable', 'assets', 'y', asked_count=0)
 decision = plan_next([current, gap], last_target_key='topics', student_text='no')
 assert decision.target.key == 'assets'


def test_question_selection_rewards_continuity_but_penalizes_repetition():
 connected = Target(
  'project_critical_unknown', 'topics', 'x', continuity=1,
  value=QuestionValue(uncertainty_reduction=.8, conversational_relevance=1, novelty=1),
 )
 unrelated = Target(
  'project_critical_unknown', 'motivation', 'x', continuity=0,
  value=QuestionValue(uncertainty_reduction=.8, conversational_relevance=0, novelty=1),
 )
 assert select_next([unrelated, connected]).key == 'topics'
 repeated = Target(
  'project_critical_unknown', 'topics', 'x', continuity=1, asked_count=2,
  value=connected.value,
 )
 assert select_next([unrelated, repeated]).key == 'motivation'
def test_contexts_are_independent_and_writer_bounded():
 c=ContextBuilder(); transcript=list(range(20)); q=c.question_writer('x',transcript,'memory','profile'); m=c.memory(transcript,20)
 assert q['recent_messages']==list(range(12,20)) and 'raw_transcript' not in q and 'profile' not in m
def test_project_weights_constraints_and_capability_not_eligibility():
    profile = {
        "topics": ["x"],
        "work_modes": {"build": 4, "investigate": None, "organize": None, "communicate": None},
        "motivations": ["discovery_mastery"],
        "primary_reward": "discovery_mastery",
        "execution": {},
        "constraints": {"age": "ok"},
        "capability_gaps": ["code"],
    }
    result = rank_projects(
        profile,
        [
            {
                "id": "p",
                "topics": ["x"],
                "work_modes": ["build"],
                "motivations": ["discovery_mastery"],
                "hard_constraints": {"age": "ok"},
            }
        ],
    )[0]
    assert result.eligible and result.score >= 0.9 and result.scope_adjustments == (
        "scaffold:code",
    )
    distribution = fit_distribution([result])
    assert distribution == {"p": 1.0}
    assert decision_entropy(distribution) == 0
    assert recommendation_ready(distribution)
def test_question_quality_rejects_leaks_and_compound_questions():
 assert validate_question('What kept you coming back?').accepted
 assert not validate_question('Is your profile stable? What next?').accepted
def test_prompt_context_serializes_curated_dataclasses():
 target=Target('behavioral_anchor','voluntary_attention','x')
 context=ContextBuilder().question_writer(target,[],None,{})
 assert json.loads(json.dumps(context,default=_json_default))['curated_intent']['question_class']=='discover'
