from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ChatPulse API"
    app_version: str = "0.1.0"
    environment: str = "development"
    frontend_origin: str = "http://localhost:5173"

    twitch_client_id: str = ""
    twitch_client_secret: str = ""
    twitch_redirect_uri: str = "http://localhost:8000/api/auth/twitch/callback"
    twitch_scopes: str = "user:read:chat"
    # OPENAI_API_KEY is retained for the existing OpenAI-compatible gateway config.
    openai_api_key: str = ""
    qwen_api_key: str = ""
    soclaas_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    soclaas_model: str = "qwen-plus"
    llm_analysis_interval_seconds: int = 30
    llm_analysis_window_messages: int = 100
    llm_request_timeout_seconds: int = 90

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

