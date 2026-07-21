"""FastAPI dependencies for repository and LLM composition."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.repository import AssessmentRepository
from app.services.azure_openai import QuestionWriter, build_llm
from app.services.context_builder import ContextBuilder
from app.services.evidence_extractor import EvidenceExtractor


@lru_cache
def get_llm():
    # Metadata-only llm_runs audit can be bound later; local path uses noop.
    return build_llm(audit_writer=None)


def get_context_builder() -> ContextBuilder:
    return ContextBuilder()


def get_extractor(llm=Depends(get_llm)) -> EvidenceExtractor:
    return EvidenceExtractor(llm)


def get_writer(llm=Depends(get_llm)) -> QuestionWriter:
    return QuestionWriter(llm)


async def get_repo(db: AsyncSession = Depends(get_db)) -> AssessmentRepository:
    return AssessmentRepository(db)
