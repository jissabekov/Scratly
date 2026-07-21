"""Azure OpenAI client via Entra (DefaultAzureCredential).

Uses the Responses API when api_version >= 2025-03-01-preview; otherwise
falls back to chat.completions structured parse (needed for 2024-12-01-preview).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import UUID

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
        if self.audit is not None:
            await self.audit(
                prompt_name=prompt_name,
                prompt_version=prompt_version,
                deployment=deployment_name,
                response_id=response_id,
                usage=usage,
                session_id=self._session_id,
                turn_id=self._turn_id,
            )
        return parsed

    async def memory(self, context):
        return await self.structured(
            "summary", "memory_compactor", "v1", MemorySnapshotOutput, context
        )


class LocalFallbackLLM:
    """Used when Azure OpenAI is not configured. Triggers seeded question fallbacks."""

    def set_turn_context(self, session_id: UUID | None, turn_id: UUID | None) -> None:
        return None

    async def structured(self, deployment, prompt_name, prompt_version, model, context):
        from app.contracts import EvidencePacket

        if model is EvidencePacket or getattr(model, "__name__", "") == "EvidencePacket":
            return EvidencePacket(
                items=[], no_evidence_reason="azure_openai_not_configured"
            )
        raise RuntimeError("azure_openai_not_configured")

    async def memory(self, context):
        raise RuntimeError("azure_openai_not_configured")


class QuestionWriter:
    def __init__(self, llm):
        self.llm = llm

    async def write(self, context) -> str:
        result = await self.llm.structured(
            "writer", "question_writer", "v1", QuestionResponse, context
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
