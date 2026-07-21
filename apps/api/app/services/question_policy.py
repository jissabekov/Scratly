from dataclasses import dataclass
PRIORITY=('contradiction','required_hard_variable','project_critical_unknown','provisional_dimension','project_discrimination','profile_validation')
STAGES=('discovery','measurement','gap_resolution','profile_review','project_matching','complete')
@dataclass(frozen=True)
class Target: kind:str; key:str; fallback_template:str
def select_next(candidates:list[Target])->Target|None:
    order={v:i for i,v in enumerate(PRIORITY)}
    return min(candidates,key=lambda x:(order[x.kind],x.key)) if candidates else None
def derive_stage(*,coverage:float, contradictions:int, reviewed:bool, projects_ready:bool)->str:
    if projects_ready and reviewed:return 'complete'
    if reviewed:return 'project_matching'
    if coverage>=.9 and contradictions==0:return 'profile_review'
    if contradictions:return 'gap_resolution'
    if coverage>=.4:return 'measurement'
    return 'discovery'
