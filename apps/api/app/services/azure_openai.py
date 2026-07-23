"""Azure OpenAI client via Entra (DefaultAzureCredential).

Uses the Responses API when api_version >= 2025-03-01-preview; otherwise
falls back to chat.completions structured parse (needed for 2024-12-01-preview).
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel
from azure.identity.aio import (
    AzureCliCredential,
    ChainedTokenCredential,
    ClientSecretCredential,
    get_bearer_token_provider,
)
from openai import AsyncAzureOpenAI

from app.config import get_settings
from app.contracts import MemorySnapshotOutput, QuestionResponse

AuditWriter = Callable[..., Awaitable[Any]]

_PROMPTS_ROOT = Path(__file__).resolve().parents[2] / "prompts"
_RESPONSES_MIN_VERSION = (2025, 3, 1)

# Compose often injects blank AZURE_* keys; EnvironmentCredential rejects empties.
_AZURE_ENV_KEYS = (
    "AZURE_CLIENT_ID",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_SECRET",
    "AZURE_CLIENT_CERTIFICATE_PATH",
    "AZURE_USERNAME",
    "AZURE_PASSWORD",
)


def _sanitize_empty_azure_env() -> None:
    for key in _AZURE_ENV_KEYS:
        if key in os.environ and not os.environ[key].strip():
            del os.environ[key]


def _build_credential():
    """Prefer service principal (containers), then Azure CLI (`az login` on host).

    Avoids DefaultAzureCredential's broken Arc/local Managed Identity probes.
    """
    _sanitize_empty_azure_env()
    credentials = []
    tenant = os.getenv("AZURE_TENANT_ID", "").strip()
    client_id = os.getenv("AZURE_CLIENT_ID", "").strip()
    secret = os.getenv("AZURE_CLIENT_SECRET", "").strip()
    if tenant and client_id and secret:
        credentials.append(
            ClientSecretCredential(
                tenant_id=tenant, client_id=client_id, client_secret=secret
            )
        )
    credentials.append(AzureCliCredential())
    if len(credentials) == 1:
        return credentials[0]
    return ChainedTokenCredential(*credentials)


def _parse_api_version(version: str) -> tuple[int, int, int]:
    """Extract YYYY-MM-DD from preview/GA version strings."""
    core = version.strip().split("-preview")[0].split("-beta")[0]
    parts = core.split("-")
    if len(parts) < 3:
        return (0, 0, 0)
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return (0, 0, 0)


def _supports_responses_api(version: str) -> bool:
    return _parse_api_version(version) >= _RESPONSES_MIN_VERSION


class _ContextEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, UUID):
            return str(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if is_dataclass(o) and not isinstance(o, type):
            return asdict(o)
        if hasattr(o, "model_dump"):
            return o.model_dump()
        if hasattr(o, "__dict__"):
            return {k: v for k, v in vars(o).items() if not k.startswith("_")}
        return super().default(o)


class AzureOpenAIService:
    """Structured LLM calls. Never mutates profile or stage."""

    def __init__(self, audit_writer: AuditWriter | None = None):
        settings = get_settings()
        if not settings.azure_openai_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is required for AzureOpenAIService")
        _sanitize_empty_azure_env()
        self._credential = _build_credential()
        token = get_bearer_token_provider(
            self._credential, "https://cognitiveservices.azure.com/.default"
        )
        self.api_version = settings.azure_openai_api_version
        self.use_responses = _supports_responses_api(self.api_version)
        self.client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            azure_ad_token_provider=token,
            api_version=self.api_version,
        )
        self.deployments = {
            "analyzer": settings.azure_openai_analyzer_deployment,
            "writer": settings.azure_openai_writer_deployment,
            "summary": settings.azure_openai_summary_deployment,
        }
        self.audit = audit_writer
        self._session_id: UUID | None = None
        self._turn_id: UUID | None = None
        self.last_llm_run_id: UUID | None = None

    def set_turn_context(self, session_id: UUID | None, turn_id: UUID | None) -> None:
        self._session_id = session_id
        self._turn_id = turn_id

    async def close(self) -> None:
        await self.client.close()
        await self._credential.close()

    async def structured(self, deployment, prompt_name, prompt_version, model, context):
        deployment_name = self.deployments[deployment]
        system = _prompt(prompt_name, prompt_version)
        user = json.dumps(context, cls=_ContextEncoder)
        if self.use_responses:
            response = await self.client.responses.parse(
                model=deployment_name,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                text_format=model,
            )
            parsed = response.output_parsed
            response_id = response.id
            usage = response.usage
        else:
            # 2024-12-01-preview and earlier: chat.completions structured outputs.
            parse = getattr(self.client.chat.completions, "parse", None)
            if parse is None:
                parse = self.client.beta.chat.completions.parse
            response = await parse(
                model=deployment_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format=model,
            )
            message = response.choices[0].message
            parsed = message.parsed
            if parsed is None:
                raise RuntimeError(
                    f"structured chat completion returned no parsed output "
                    f"(refusal={getattr(message, 'refusal', None)})"
                )
            response_id = response.id
            usage = response.usage
        self.last_llm_run_id = None
        if self.audit is not None:
            run_id = await self.audit(
                prompt_name=prompt_name,
                prompt_version=prompt_version,
                deployment=deployment_name,
                response_id=response_id,
                usage=usage,
                session_id=self._session_id,
                turn_id=self._turn_id,
            )
            if run_id is not None:
                self.last_llm_run_id = run_id
        return parsed

    async def memory(self, context):
        return await self.structured(
            "summary", "memory_compactor", "v1", MemorySnapshotOutput, context
        )

    async def web_search(self, query: str, user_location: dict | None = None):
        """Bounded web search via Responses API web_search tool."""
        if not self.use_responses:
            raise RuntimeError("web_search_requires_responses_api")
        deployment_name = self.deployments["analyzer"]
        tools = [{"type": "web_search"}]
        # user_location improves geo relevance when provided by the application.
        tool_cfg: dict[str, Any] = {"type": "web_search"}
        if user_location:
            tool_cfg["user_location"] = user_location
            tools = [tool_cfg]
        response = await self.client.responses.create(
            model=deployment_name,
            tools=tools,
            include=["web_search_call.action.sources"],
            input=f"Find public opportunities relevant to: {query}. Cite sources.",
        )
        self.last_llm_run_id = None
        if self.audit is not None:
            run_id = await self.audit(
                prompt_name="web_research",
                prompt_version="v1",
                deployment=deployment_name,
                response_id=getattr(response, "id", None),
                usage=getattr(response, "usage", None),
                session_id=self._session_id,
                turn_id=self._turn_id,
            )
            if run_id is not None:
                self.last_llm_run_id = run_id
        return response


class LocalFallbackLLM:
    """Used when Azure OpenAI is not configured. Triggers seeded question fallbacks."""

    def __init__(self):
        self.last_llm_run_id = None
        self.audit = None

    def set_turn_context(self, session_id: UUID | None, turn_id: UUID | None) -> None:
        return None

    async def structured(self, deployment, prompt_name, prompt_version, model, context):
        from app.contracts import (
            EvidencePacket,
            ProfileReviewOutput,
            ProjectComposeOutput,
            StudentAnswerOutput,
            TurnIntentPacket,
        )

        name = getattr(model, "__name__", "")
        if model is EvidencePacket or name == "EvidencePacket":
            return EvidencePacket(
                items=[], no_evidence_reason="azure_openai_not_configured"
            )
        if model is TurnIntentPacket or name == "TurnIntentPacket":
            text = ""
            msg = (context or {}).get("student_message") or {}
            if isinstance(msg, dict):
                text = msg.get("content") or ""
            from app.services.turn_intent_classifier import heuristic_classify

            return heuristic_classify(text)
        if model is StudentAnswerOutput or name == "StudentAnswerOutput":
            from app.contracts import TurnIntentPacket as TIP
            from app.services.student_answerer import seeded_student_answer

            intent = (context or {}).get("intent")
            if isinstance(intent, dict):
                intent = TIP.model_validate(intent)
            elif not isinstance(intent, TIP):
                intent = TIP(
                    primary_intent="student_question", question_topic="process"
                )
            return seeded_student_answer(
                intent,
                public_profile=(context or {}).get("public_profile_summary"),
                last_target_key=(context or {}).get("last_target_key"),
                student_text=(context or {}).get("student_text")
                or ((context or {}).get("student_message") or {}).get("content"),
            )
        if model is ProfileReviewOutput or name == "ProfileReviewOutput":
            return ProfileReviewOutput(
                narrative="Here is a short summary of what we have so far.",
                confirmations=["Preferences captured so far look right"],
                corrections_requested=[],
            )
        if model is ProjectComposeOutput or name == "ProjectComposeOutput":
            from app.services.project_composer import _seeded_compose

            return _seeded_compose(context or {})
        raise RuntimeError("azure_openai_not_configured")

    async def memory(self, context):
        raise RuntimeError("azure_openai_not_configured")

    async def web_search(self, query: str, user_location: dict | None = None):
        raise RuntimeError("web_search_unconfigured")


class QuestionWriter:
    def __init__(self, llm):
        self.llm = llm

    async def write(self, context) -> str:
        result = await self.llm.structured(
            "writer", "question_writer", "v3", QuestionResponse, context
        )
        return result.question


def _prompt(name: str, version: str) -> str:
    path = _PROMPTS_ROOT / name / version / "system.txt"
    return path.read_text(encoding="utf-8")


def build_llm(audit_writer: AuditWriter | None = None):
    settings = get_settings()
    if not settings.azure_openai_endpoint.strip():
        return LocalFallbackLLM()
    try:
        return AzureOpenAIService(audit_writer=audit_writer)
    except Exception:
        return LocalFallbackLLM()


def _json_default(value: Any) -> Any:
    """Serializer for json.dumps(..., default=_json_default).

    Mirrors _ContextEncoder for callers that prefer a default function.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Unsupported prompt context type: {type(value).__name__}")
