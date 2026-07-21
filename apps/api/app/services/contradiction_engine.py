from dataclasses import dataclass
from app.contracts import ValidatedEvidence
@dataclass(frozen=True)
class Contradiction: dimension_key:str; evidence_ids:tuple[int,...]; status:str='open'
def find_contradictions(items:list[ValidatedEvidence])->list[Contradiction]:
    accepted=[x for x in items if x.accepted]
    out=[]
    for dimension in sorted({x.dimension_key for x in accepted}):
        group=[x for x in accepted if x.dimension_key==dimension]
        values={x.value_key for x in group if x.polarity.value=='support'}
        if len(values)>1: out.append(Contradiction(dimension,tuple(range(len(group)))))
    return out

def resolve_with_newest(contradiction:Contradiction, explicit_evidence_id:int)->dict:
    return {'status':'resolved','resolution':'explicit_newest','winning_evidence_id':explicit_evidence_id} # never average
