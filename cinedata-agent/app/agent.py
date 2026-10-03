import json

from openai import OpenAI

from .config import settings
from .database import Database
from .prompts import SYSTEM_PROMPT
from .sql_guard import validate_sql


class CineDataAgent:
    def __init__(self):
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY não configurada. "
                "Defina a variável de ambiente antes de executar."
            )

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
        }

        if settings.site_url:
            headers["HTTP-Referer"] = settings.site_url

        if settings.site_name:
            headers["X-Title"] = settings.site_name

        self.client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers=headers,
        )

        self.db = Database(settings.db_path)

    def generate_sql(self, question: str) -> str:
        prompt = SYSTEM_PROMPT.format(
            schema=self.db.schema()
        )

        response = self.client.chat.completions.create(
            model=settings.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
                {
                    "role": "user",
                    "content": question,
                },
            ],
        )

        content = response.choices[0].message.content or ""

        return validate_sql(
            content,
            settings.max_sql_length,
        )

    def answer(self, question: str) -> dict:
        sql = self.generate_sql(question)

        rows = self.db.execute_readonly(
            sql,
            settings.max_rows,
        )

        return {
            "question": question,
            "sql": sql,
            "rows": rows,
            "row_count_returned": len(rows),
        }

    def answer_text(self, question: str) -> str:
        result = self.answer(question)

        return (
            f"SQL executado:\n"
            f"{result['sql']}\n\n"
            f"Resultado ({result['row_count_returned']} linhas):\n"
            f"{json.dumps(result['rows'], ensure_ascii=False, indent=2, default=str)}"
        )
