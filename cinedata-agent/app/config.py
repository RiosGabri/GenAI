import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Carrega o arquivo .env da raiz do projeto
load_dotenv()


def _csv(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, "").split(",") if item.strip())


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "sim"}


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("CINEDATA_DB_PATH", "cinerocket.db")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    model: str = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    # Modelos tentados em ordem quando o principal falha (429, 5xx, modelo inexistente).
    # Ex.: OPENROUTER_FALLBACK_MODELS=google/gemma-4-26b-a4b-it:free,z-ai/glm-5.2:free
    fallback_models: tuple[str, ...] = _csv("OPENROUTER_FALLBACK_MODELS")
    site_url: str = os.getenv("OPENROUTER_SITE_URL", "")
    site_name: str = os.getenv("OPENROUTER_SITE_NAME", "CineData Analytics Agent")
    max_rows: int = int(os.getenv("MAX_ROWS", "100"))
    max_sql_length: int = int(os.getenv("MAX_SQL_LENGTH", "8000"))
    # Cada tentativa extra de SQL custa 1 requisição da cota diária do OpenRouter.
    max_sql_attempts: int = int(os.getenv("MAX_SQL_ATTEMPTS", "2"))
    query_timeout_seconds: float = float(os.getenv("QUERY_TIMEOUT_SECONDS", "5"))
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
    # Uma chamada extra por pergunta para explicar o resultado em português.
    narrate_answer: bool = _flag("NARRATE_ANSWER", "true")
    show_sql: bool = _flag("SHOW_SQL", "false")


settings = Settings()