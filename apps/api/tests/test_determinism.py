from dataclasses import dataclass
from uuid import uuid4
from app.contracts import ProposedEvidence
from app.services.grounding_validator import validate_grounding
from app.services.profile_reducer import reduce_profile
from app.services.question_policy import Target,select_next,derive_stage
from app.services.project_matcher import rank_projects
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
 profile=reduce_profile(accepted); assert profile.reducer_version=='v1' and profile.dimensions[0].value=='a' and profile.dimensions[0].status=='established'
def test_question_priority_and_stages():
 targets=[Target('profile_validation','z','z'),Target('contradiction','a','a')]
 assert select_next(targets).kind=='contradiction'; assert derive_stage(coverage=.95,contradictions=0,reviewed=False,projects_ready=False)=='profile_review'
def test_contexts_are_independent_and_writer_bounded():
 c=ContextBuilder(); transcript=list(range(20)); q=c.question_writer('x',transcript,'memory','profile'); m=c.memory(transcript,20)
 assert q['recent_messages']==list(range(14,20)) and 'raw_transcript' not in q and 'profile' not in m
def test_project_weights_constraints_and_capability_not_eligibility():
 profile={'topics':['x'],'work_modes':['y'],'motivations':['z'],'constraints':{'age':'ok'},'capability_gaps':['code']}
 result=rank_projects(profile,[{'id':'p','topics':['x'],'work_modes':['y'],'motivations':[],'hard_constraints':{'age':'ok'}}])[0]
 assert result.eligible and result.score==.8 and result.scope_adjustments==('scaffold:code',)
