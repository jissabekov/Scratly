from dataclasses import dataclass
from uuid import uuid4
from app.contracts import ProposedEvidence
from app.services.grounding_validator import validate_grounding
from app.services.profile_reducer import reduce_profile
from app.services.question_policy import InterviewPhase, QuestionValue, ReplySignal, Target, classify_reply, derive_phase, select_next, derive_stage
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
 assert select_next(targets).kind=='contradiction'; assert derive_stage(coverage=.95,contradictions=0,reviewed=False,projects_ready=False)=='profile_review'
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
def test_contexts_are_independent_and_writer_bounded():
 c=ContextBuilder(); transcript=list(range(20)); q=c.question_writer('x',transcript,'memory','profile'); m=c.memory(transcript,20)
 assert q['recent_messages']==list(range(12,20)) and 'raw_transcript' not in q and 'profile' not in m
def test_project_weights_constraints_and_capability_not_eligibility():
 profile={'topics':['x'],'work_modes':['y'],'motivations':['z'],'constraints':{'age':'ok'},'capability_gaps':['code']}
 result=rank_projects(profile,[{'id':'p','topics':['x'],'work_modes':['y'],'motivations':[],'hard_constraints':{'age':'ok'}}])[0]
 assert result.eligible and result.score==.8 and result.scope_adjustments==('scaffold:code',)
 distribution=fit_distribution([result]); assert distribution=={'p':1.0} and decision_entropy(distribution)==0 and recommendation_ready(distribution)
def test_question_quality_rejects_leaks_and_compound_questions():
 assert validate_question('What kept you coming back?').accepted
 assert not validate_question('Is your profile stable? What next?').accepted
def test_prompt_context_serializes_curated_dataclasses():
 target=Target('behavioral_anchor','voluntary_attention','x')
 context=ContextBuilder().question_writer(target,[],None,{})
 assert json.loads(json.dumps(context,default=_json_default))['curated_intent']['question_class']=='discover'
