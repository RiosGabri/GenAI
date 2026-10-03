import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    NotFoundError,
    OpenAI,
)

from .config import Settings
from .config import settings as default_settings
from .database import Database, QueryResult, QueryTimeoutError
from .formatting import format_table
from .prompts import ANSWER_SYSTEM_PROMPT, RETRY_PROMPT, build_sql_prompt
from .sql_guard import validate_sql

logger = logging.getLogger(__name__)

CLARIFICATION_PREFIX = "ESCLARECIMENTO:"
NARRATION_MAX_ROWS = 30


class LLMUnavailableError(Exception):
    """Nenhum modelo configurado conseguiu responder."""


@dataclass
class AgentResult:
    question: str
    sql: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    answer: str | None = None
    clarification: str | None = None
    error: str | None = None
    attempts: int = 0
    llm_calls: int = 0
    model: str | None = None
    failures: list[str] = field(default_factory=list)


class CineDataAgent:
    def __init__(
        self,
        client: Any = None,
        db: Database | None = None,
        settings: Settings = default_settings,
    ):
        self.settings = settings

        if client is None:
            if not settings.openrouter_api_key:
                raise RuntimeError(
                    "OPENROUTER_API_KEY não configurada. "
                    "Defina a variável de ambiente antes de executar."
                )
            headers = {}
            if settings.site_url:
                headers["HTTP-Referer"] = settings.site_url
            if settings.site_name:
                headers["X-Title"] = settings.site_name

            # max_retries=0: o SDK repetiria 429/5xx sozinho e cada tentativa
            # consome a cota diária de 50 requisições.
            client = OpenAI(
                api_key=settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers=headers,
                max_retries=0,
                timeout=settings.request_timeout_seconds,
            )

        self.client = client
        self.db = db or Database(settings.db_path, settings.query_timeout_seconds)
        self.models = list(dict.fromkeys([settings.model, *settings.fallback_models]))
        self._llm_calls = 0
        self._dead_models: set[str] = set()
        self.last_model: str | None = None

    # ------------------------------------------------------------------ LLM

    def _chat(self, messages: list[dict[str, str]]) -> str:
        errors = []
        for model in self.models:
            if model in self._dead_models:
                continue  # id inexistente: repetir só gastaria a cota diária
            self._llm_calls += 1
            try:
                response = self.client.chat.completions.create(
                    model=model, temperature=0, messages=messages
                )
            except AuthenticationError as exc:
                raise LLMUnavailableError(
                    "Chave do OpenRouter inválida ou ausente (401)."
                ) from exc
            except (APIStatusError, APIConnectionError) as exc:
                if isinstance(exc, NotFoundError):
                    self._dead_models.add(model)
                logger.warning("Modelo %s falhou: %s", model, type(exc).__name__)
                errors.append(f"{model}: {type(exc).__name__}")
                continue

            self.last_model = model
            choices = getattr(response, "choices", None)
            return (choices[0].message.content or "") if choices else ""

        if not errors:
            errors = ["todos os modelos configurados foram descartados nesta sessão"]
        raise LLMUnavailableError(
            "Nenhum modelo respondeu (" + "; ".join(errors) + "). "
            "Pode ser pool lotado (tente outro modelo) ou cota diária esgotada."
        )

    # ---------------------------------------------------------------- fluxo

    def ask(self, question: str) -> AgentResult:
        result = AgentResult(question=question)
        calls_before = self._llm_calls

        try:
            self._generate_and_execute(question, result)
            if result.sql and not result.error and self.settings.narrate_answer:
                result.answer = self._narrate(question, result)
        except LLMUnavailableError as exc:
            result.error = str(exc)

        result.llm_calls = self._llm_calls - calls_before
        result.model = self.last_model if result.llm_calls else None
        return result

    def _generate_and_execute(self, question: str, result: AgentResult) -> None:
        messages = [
            {"role": "system", "content": build_sql_prompt(self.db.schema())},
            {"role": "user", "content": question},
        ]
        last_error = ""

        for attempt in range(1, self.settings.max_sql_attempts + 1):
            result.attempts = attempt
            raw = self._chat(messages)

            if raw.strip().upper().startswith(CLARIFICATION_PREFIX):
                result.clarification = raw.strip()[len(CLARIFICATION_PREFIX) :].strip()
                result.sql = None
                return

            try:
                sql = validate_sql(raw, self.settings.max_sql_length)
                result.sql = sql
                query = self.db.execute_readonly(sql, self.settings.max_rows)
            except (ValueError, sqlite3.Error, QueryTimeoutError) as exc:
                last_error = str(exc)
                result.failures.append(f"{last_error} (resposta do modelo: {raw.strip()[:200]!r})")
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": RETRY_PROMPT.format(error=last_error)})
                continue

            self._fill(result, query)
            return

        result.error = (
            f"não consegui gerar um SQL válido após {self.settings.max_sql_attempts} "
            f"tentativa(s). Último erro: {last_error}"
        )

    @staticmethod
    def _fill(result: AgentResult, query: QueryResult) -> None:
        result.rows = query.rows
        result.truncated = query.truncated

    def _narrate(self, question: str, result: AgentResult) -> str | None:
        payload = {
            "pergunta": question,
            "sql": result.sql,
            "linhas_exibidas": min(len(result.rows), NARRATION_MAX_ROWS),
            "total_linhas_retornadas": len(result.rows),
            "resultado_truncado": result.truncated,
            "linhas": result.rows[:NARRATION_MAX_ROWS],
        }
        messages = [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ]
        try:
            return self._chat(messages).strip() or None
        except LLMUnavailableError:
            # O resultado do banco já existe; não o perca por causa da explicação.
            return None

    # ------------------------------------------------------------- saída

    def render(self, result: AgentResult) -> str:
        if result.clarification:
            body = f"Preciso de um esclarecimento: {result.clarification}"
        elif result.error:
            body = f"Não consegui responder: {result.error}"
            if self.settings.show_sql and result.sql:
                body += f"\n\nÚltimo SQL tentado:\n{result.sql}"
            body += self._failures_block(result)
        else:
            parts = []
            if result.answer:
                parts.append(result.answer)
            parts.append(format_table(result.rows))
            if result.truncated:
                parts.append(f"(resultado limitado às primeiras {self.settings.max_rows} linhas)")
            if self.settings.show_sql:
                parts.append(f"SQL executado:\n{result.sql}")
            body = "\n\n".join(parts) + self._failures_block(result)

        footer = f"chamadas ao modelo nesta pergunta: {result.llm_calls}"
        if result.model:
            footer += f"; último modelo que respondeu: {result.model}"
        return f"{body}\n\n[{footer}]"

    def _failures_block(self, result: AgentResult) -> str:
        """Tentativas descartadas (cada uma custou uma chamada); só com SHOW_SQL."""

        if not (self.settings.show_sql and result.failures):
            return ""
        lines = "\n".join(f"- {failure}" for failure in result.failures)
        return f"\n\nTentativas descartadas:\n{lines}"

    def answer_text(self, question: str) -> str:
        return self.render(self.ask(question))