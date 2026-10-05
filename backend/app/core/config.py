from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_api_key_2: str = ""
    gemini_api_key_3: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
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
    def gemini_keys(self) -> list[str]:
        keys: list[str] = []
        for value in (self.gemini_api_key, self.gemini_api_key_2, self.gemini_api_key_3, self.google_api_key):
            cleaned = (value or "").strip()
            if cleaned and cleaned not in keys:
                keys.append(cleaned)
        return keys

    @property
    def resolved_gemini_key(self) -> str:
        keys = self.gemini_keys
        return keys[0] if keys else ""

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
