import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import settings

# Colunas cujos valores distintos são injetados no prompt (o modelo erra
# facilmente 'Ator' vs 'ator' quando não os vê).
_DOMAIN_VALUES = (
    ("dim_people", "tipo_pessoa"),
    ("dim_genres", "nome_genero"),
    ("dim_movies", "status_filme"),
)
_PROGRESS_STEPS = 10_000


class QueryTimeoutError(Exception):
    """A consulta excedeu o tempo máximo permitido."""


@dataclass(frozen=True)
class QueryResult:
    rows: list[dict[str, Any]]
    truncated: bool


class Database:
    def __init__(self, db_path: str, timeout_seconds: float | None = None):
        self.db_path = db_path
        self.timeout_seconds = (
            settings.query_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        self._schema: str | None = None

    def connect(self) -> sqlite3.Connection:
        path = Path(self.db_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Banco não encontrado: {self.db_path}. "
                "Coloque cinerocket.db na raiz do projeto ou defina CINEDATA_DB_PATH."
            )

        # as_uri() codifica espaços e acentos (ex.: "Área de trabalho") corretamente.
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        return conn

    def schema(self) -> str:
        """Schema lido do próprio banco (uma vez por processo)."""

        if self._schema is None:
            self._schema = self._build_schema()
        return self._schema

    def _build_schema(self) -> str:
        conn = self.connect()
        try:
            parts = ["TABELAS (lidas do banco):"]
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                    "AND name != 'alembic_version' ORDER BY name"
                )
            ]

            for table in tables:
                foreign_keys = {
                    fk[3]: f"{fk[2]}.{fk[4] or '?'}"
                    for fk in conn.execute(f'PRAGMA foreign_key_list("{table}")')
                }
                parts.append(f"\n{table}")
                for _, name, col_type, not_null, _, pk in conn.execute(
                    f'PRAGMA table_info("{table}")'
                ):
                    flags = []
                    if pk:
                        flags.append("PK")
                    if not_null:
                        flags.append("NOT NULL")
                    if name in foreign_keys:
                        flags.append(f"-> {foreign_keys[name]}")
                    suffix = f" [{', '.join(flags)}]" if flags else ""
                    parts.append(f"- {name} {col_type}{suffix}")

            domain_lines = []
            for table, column in _DOMAIN_VALUES:
                values = self._distinct(conn, table, column)
                if values:
                    domain_lines.append(
                        f"- {table}.{column}: {json.dumps(values, ensure_ascii=False)}"
                    )
            if domain_lines:
                parts.append("\nVALORES DISTINTOS (use exatamente estes valores nos filtros):")
                parts.extend(domain_lines)

            max_year = self._max_year(conn)
            if max_year is not None:
                parts.append(
                    f"\nREFERÊNCIA TEMPORAL: o maior ano_lancamento dos filmes lançados "
                    f"(status_filme = 'Lançado') é {max_year}. Outros status podem ter anos futuros."
                )

            return "\n".join(parts)
        finally:
            conn.close()

    @staticmethod
    def _distinct(conn: sqlite3.Connection, table: str, column: str) -> list[Any]:
        try:
            cursor = conn.execute(
                f'SELECT DISTINCT "{column}" FROM "{table}" '
                f'WHERE "{column}" IS NOT NULL ORDER BY 1 LIMIT 60'
            )
            return [row[0] for row in cursor]
        except sqlite3.Error:
            return []

    @staticmethod
    def _max_year(conn: sqlite3.Connection) -> int | None:
        # Filmes planejados ou em produção têm anos futuros (o banco chega a 2029);
        # a referência de "últimos N anos" deve vir só dos filmes já lançados.
        for sql in (
            "SELECT MAX(ano_lancamento) FROM dim_movies WHERE status_filme = 'Lançado'",
            "SELECT MAX(ano_lancamento) FROM dim_movies",
        ):
            try:
                year = conn.execute(sql).fetchone()[0]
            except sqlite3.Error:
                return None
            if year is not None:
                return year
        return None

    def execute_readonly(self, sql: str, max_rows: int = 100) -> QueryResult:
        conn = self.connect()
        deadline = time.monotonic() + self.timeout_seconds
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), _PROGRESS_STEPS)
        try:
            # Lê uma linha a mais para saber se o resultado foi truncado.
            fetched = conn.execute(sql).fetchmany(max_rows + 1)
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc).lower():
                raise QueryTimeoutError(
                    f"A consulta excedeu o limite de {self.timeout_seconds:g}s."
                ) from exc
            raise
        finally:
            conn.close()

        return QueryResult(
            rows=[dict(row) for row in fetched[:max_rows]],
            truncated=len(fetched) > max_rows,
        )