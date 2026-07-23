from dataclasses import dataclass
from math import exp, log2
@dataclass(frozen=True)
class Match: project_id:str; eligible:bool; score:float; topic:float; work_mode:float; motivation:float; failed_constraints:tuple[str,...]; scope_adjustments:tuple[str,...]
def _overlap(wanted:set[str], offered:set[str])->float: return len(wanted&offered)/max(1,len(wanted))
def rank_projects(profile:dict,projects:list[dict])->list[Match]:
    matches=[]
    for p in projects:
        failed=tuple(k for k,v in p.get('hard_constraints',{}).items() if profile.get('constraints',{}).get(k)!=v)
        topic=_overlap(set(profile.get('topics',[])),set(p.get('topics',[])))
        work=_overlap(set(profile.get('work_modes',[])),set(p.get('work_modes',[])))
        motivation=_overlap(set(profile.get('motivations',[])),set(p.get('motivations',[])))
        adjustments=tuple(f"scaffold:{x}" for x in profile.get('capability_gaps',[]))
        matches.append(Match(p['id'],not failed,.4*topic+.4*work+.2*motivation,topic,work,motivation,failed,adjustments))
    return sorted(matches,key=lambda m:(not m.eligible,-m.score,m.project_id))


def fit_distribution(matches: list[Match], temperature: float = .2) -> dict[str, float]:
    """Expose uncertainty over eligible project modes instead of only a ranking."""
    eligible = [match for match in matches if match.eligible]
    if not eligible:
        return {}
    scale = max(temperature, .01)
    weights = {match.project_id: exp(match.score / scale) for match in eligible}
    total = sum(weights.values())
    return {key: round(value / total, 6) for key, value in weights.items()}


def decision_entropy(distribution: dict[str, float]) -> float:
    return -sum(probability * log2(probability) for probability in distribution.values() if probability > 0)


def recommendation_ready(distribution: dict[str, float], *, threshold: float = .70) -> bool:
    """Stop when a project mode is decisive; never stop merely because turns elapsed."""
    return bool(distribution) and max(distribution.values()) >= threshold
