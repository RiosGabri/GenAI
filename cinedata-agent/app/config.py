import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Carrega o arquivo .env da raiz do projeto
load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("CINEDATA_DB_PATH", "cinerocket.db")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    model: str = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    site_url: str = os.getenv("OPENROUTER_SITE_URL", "")
    site_name: str = os.getenv(
        "OPENROUTER_SITE_NAME",
        "CineData Analytics Agent",
    )
    max_rows: int = int(os.getenv("MAX_ROWS", "100"))
    max_sql_length: int = int(os.getenv("MAX_SQL_LENGTH", "8000"))


settings = Settings()
