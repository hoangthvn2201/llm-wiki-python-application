from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(default="sk-missing", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    model_name: str = Field(default="gpt-4o-mini", alias="MODEL_NAME")
    workspace_dir: Path = Field(default=Path("./workspace"), alias="WORKSPACE_DIR")

    # Default iteration cap used when an operation doesn't specify its own.
    max_tool_iterations: int = Field(default=25, alias="MAX_TOOL_ITERATIONS")
    # Per-operation overrides. The hallucination sweep emits one tool call per
    # claim so it routinely needs many more iterations than ingest/query.
    max_tool_iterations_ingest: int = Field(default=25, alias="MAX_TOOL_ITERATIONS_INGEST")
    max_tool_iterations_query: int = Field(default=25, alias="MAX_TOOL_ITERATIONS_QUERY")
    max_tool_iterations_chat: int = Field(default=25, alias="MAX_TOOL_ITERATIONS_CHAT")
    max_tool_iterations_lint: int = Field(default=50, alias="MAX_TOOL_ITERATIONS_LINT")
    max_tool_iterations_hallucination: int = Field(
        default=150, alias="MAX_TOOL_ITERATIONS_HALLUCINATION"
    )

    @property
    def workspace_path(self) -> Path:
        return self.workspace_dir.expanduser().resolve()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
