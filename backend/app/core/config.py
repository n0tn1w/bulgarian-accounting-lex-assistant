"""Application configuration.

Every value is overridable via environment variables (or a .env file) so the same
code runs across dev, CI and prod.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # app
    app_name: str = "Accounting AI Assistant"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # database / multi-tenancy
    # Admin role: runs DDL/bootstrap (extension, tables, RLS, roles).
    database_admin_url: str = Field(
        default="postgresql+psycopg://ledgerly:ledgerly@localhost:5432/ledgerly",
        alias="DATABASE_ADMIN_URL",
    )
    # App role: used for all request queries, NOSUPERUSER so RLS is enforced.
    database_url: str = Field(
        default="postgresql+psycopg://ledgerly_app:ledgerly_app@localhost:5432/ledgerly",
        alias="DATABASE_URL",
    )
    app_db_role: str = "ledgerly_app"
    app_db_password: str = Field(default="ledgerly_app", alias="APP_DB_PASSWORD")

    # auth
    jwt_secret: str = Field(
        default="dev-secret-change-me-0000000000000000", alias="JWT_SECRET"
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # embeddings / vector search — BGE-M3 native dim (shared with the laws RAG)
    embedding_dim: int = 1024

    # LLM (provider-agnostic via LiteLLM)
    # Empty -> the chat uses the deterministic echo stub. Examples:
    #   ollama/llama3.1   (local; set llm_api_base=http://localhost:11434)
    #   claude-3-5-sonnet-latest   (needs ANTHROPIC_API_KEY)
    #   gpt-4o-mini                (needs OPENAI_API_KEY)
    llm_model: str = Field(default="", alias="LLM_MODEL")
    llm_api_base: str = Field(default="", alias="LLM_API_BASE")
    # Provider key (e.g. Gemini/OpenAI/Anthropic). Passed to LiteLLM explicitly so
    # it can live in .env — pydantic loads .env into Settings, not into os.environ.
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_timeout: int = Field(default=60, alias="LLM_TIMEOUT")

    # OCR
    ocr_languages: str = Field(default="bul+eng", alias="OCR_LANGUAGES")
    ocr_dpi: int = Field(default=300, alias="OCR_DPI")

    # comparison / IR (TF-IDF fusion)
    ir_weight_word: float = Field(default=0.65, alias="IR_WEIGHT_WORD")
    ir_weight_char: float = Field(default=0.35, alias="IR_WEIGHT_CHAR")
    ir_word_ngram: tuple[int, int] = (1, 2)
    ir_char_ngram: tuple[int, int] = (3, 5)
    # Score at/above which two documents are flagged a likely duplicate.
    ir_duplicate_threshold: float = Field(default=0.85, alias="IR_DUPLICATE_THRESHOLD")
    # Score below which a "best match" is treated as no match.
    ir_match_threshold: float = Field(default=0.10, alias="IR_MATCH_THRESHOLD")

    # validation
    # Absolute currency tolerance for arithmetic checks (rounding slack).
    validation_amount_tolerance: float = Field(
        default=0.02, alias="VALIDATION_AMOUNT_TOLERANCE"
    )
    # Plausible Bulgarian VAT rates: 0% (exempt/reverse-charge), 9% (reduced), 20% (standard).
    validation_valid_vat_rates: list[float] = Field(
        default_factory=lambda: [0.0, 0.09, 0.20],
        alias="VALIDATION_VALID_VAT_RATES",
    )

    @property
    def ir_weights_normalized(self) -> tuple[float, float]:
        """Word/char weights normalized to sum to 1.0."""
        total = self.ir_weight_word + self.ir_weight_char
        if total <= 0:
            return 0.5, 0.5
        return self.ir_weight_word / total, self.ir_weight_char / total


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (one instance per process)."""
    return Settings()
