from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'postgresql+asyncpg://postgres:postgres@localhost/scratly'
    azure_openai_endpoint: str = ''
    azure_openai_analyzer_deployment: str = 'analyzer'
    azure_openai_writer_deployment: str = 'writer'
    azure_openai_summary_deployment: str = 'summary'
    memory_response_interval: int = 8
    memory_token_threshold: int = 6000
    reducer_version: str = 'v1'

@lru_cache
def get_settings() -> Settings: return Settings()
