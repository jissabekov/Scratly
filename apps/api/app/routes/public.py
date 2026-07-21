from uuid import UUID,uuid4
from fastapi import APIRouter,Depends
from app.contracts import TurnRequest
router=APIRouter(tags=['student'])
@router.post('/sessions')
async def start_session(): return {'session_id':uuid4(),'stage':'discovery'}
@router.get('/sessions/{session_id}')
async def resume_session(session_id:UUID): return {'session_id':session_id,'stage':'discovery'}
@router.post('/sessions/{session_id}/turns')
async def submit_turn(session_id:UUID,body:TurnRequest):
    # Wiring is supplied by deployment composition; response intentionally omits numeric profile values.
    return {'session_id':session_id,'idempotency_key':body.idempotency_key,'status':'accepted'}
