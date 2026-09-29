from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost/scratly"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_analyzer_deployment: str = "gpt-5.4-mini"
    azure_openai_writer_deployment: str = "gpt-5.4-mini"
    azure_openai_summary_deployment: str = "gpt-5.4-mini"
    # Reasoning effort for structured calls (Plan 01 W1.5 latency). gpt-5.x
    # defaults to a medium reasoning budget, which dominated per-turn latency;
    # "low" keeps structured extraction quality while cutting output tokens.
    # Empty string leaves the provider default untouched.
    azure_openai_reasoning_effort: str = "low"
    memory_response_interval: int = 8
    memory_token_threshold: int = 6000
    reducer_version: str = "v2"
    # Plan 04: pause after a failed quiz attempt before the alternate form is
    # offered (>=10 min by default). Set to 0 to exercise the retry/cap loop in
    # tests without waiting (the e2e suite launches the API this way).
    learning_quiz_cooldown_seconds: int = 600
    # Direct web-search provider for the research path (W1.3). The Azure
    # Responses API web_search tool is used when the resource supports it;
    # otherwise a configured search API (tavily | brave | bing) is used.
    web_research_provider: str = ""
    web_research_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
