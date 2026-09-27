from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "mock"
    gemini_api_key: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    embedding_provider: str = "mock"
    embedding_dim: int = 768

    postgres_user: str = "supplychain"
    postgres_password: str = "supplychain"
    postgres_db: str = "supplychain"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str = (
        "postgresql+psycopg2://supplychain:supplychain@localhost:5432/supplychain"
    )

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    log_level: str = "INFO"

    solver_backend: str = "ortools"
    risk_penalty_weight: float = 1.25
    max_replan: int = 2

    @property
    def resolved_gemini_key(self) -> str:
        return self.gemini_api_key or self.google_api_key

    @property
    def effective_llm_provider(self) -> str:
        if self.llm_provider != "mock":
            return self.llm_provider
        if self.resolved_gemini_key:
            return "gemini"
        return "mock"

    @property
    def effective_embedding_provider(self) -> str:
        if self.embedding_provider != "mock":
            return self.embedding_provider
        if self.resolved_gemini_key and self.llm_provider == "gemini":
            return "gemini"
        return self.embedding_provider


settings = Settings()
