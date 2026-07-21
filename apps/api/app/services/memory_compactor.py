class MemoryCompactor:
    def __init__(self,llm,interval=8,token_threshold=6000): self.llm=llm; self.interval=interval; self.token_threshold=token_threshold
    def due(self,responses_since_snapshot:int,uncompacted_tokens:int)->bool: return responses_since_snapshot>=self.interval or uncompacted_tokens>=self.token_threshold
    async def compact(self,context_builder,raw_transcript,boundary):
        # Always regenerate from raw messages through the boundary; summaries are never input.
        context=context_builder.memory([m for m in raw_transcript if m['sequence']<=boundary],boundary)
        try: return await self.llm.memory(context)
        except Exception: return None
