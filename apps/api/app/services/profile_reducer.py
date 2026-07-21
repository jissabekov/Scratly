from collections import defaultdict
from dataclasses import dataclass
from app.contracts import ValidatedEvidence
@dataclass(frozen=True)
class DimensionState: key:str; status:str; value:str|None; confidence:float
@dataclass(frozen=True)
class ReducedProfile: dimensions:tuple[DimensionState,...]; reducer_version:str

def reduce_profile(evidence:list[ValidatedEvidence], version='v1')->ReducedProfile:
    grouped=defaultdict(list)
    for e in evidence:
        if e.accepted: grouped[e.dimension_key].append(e)
    states=[]
    for key, items in sorted(grouped.items()):
        scores=defaultdict(float)
        for e in items: scores[e.value_key] += e.strength * (1 if e.polarity.value=='support' else -1)
        value,score=max(scores.items(),key=lambda x:x[1])
        confidence=max(0,min(1,score))
        states.append(DimensionState(key,'established' if confidence>=.7 else 'provisional',value,confidence))
    return ReducedProfile(tuple(states),version)
