from app.contracts import EvidencePacket
class EvidenceExtractor:
    """Proposes evidence. It has no database/profile mutation capability."""
    def __init__(self, llm): self.llm=llm
    async def propose(self, context: dict) -> EvidencePacket:
        return await self.llm.structured('analyzer','evidence_extractor','v1',EvidencePacket,context)
