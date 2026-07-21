import pytest
from app.services.memory_compactor import MemoryCompactor
from app.services.context_builder import ContextBuilder
class Fail:
 async def memory(self,c): raise RuntimeError()
@pytest.mark.asyncio
async def test_compactor_failure_nonfatal_and_raw_boundary():
 c=MemoryCompactor(Fail()); raw=[{'sequence':1},{'sequence':2},{'sequence':3}]
 assert c.due(8,0) and await c.compact(ContextBuilder(),raw,2) is None
