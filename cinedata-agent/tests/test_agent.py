import dataclasses
import sqlite3
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.agent import CineDataAgent
from app.config import settings
from app.database import Database


class FakeClient:
    """Simula o cliente da OpenAI sem gastar cota."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        message = SimpleNamespace(content=item)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def rate_limit_error():
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return openai.RateLimitError("429", response=httpx.Response(429, request=request), body=None)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "teste.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE dim_movies (sk_movie_id TEXT PRIMARY KEY, titulo TEXT, ano_lancamento INTEGER);
        INSERT INTO dim_movies VALUES ('m1','Alpha',2020), ('m2','Beta',2023);
        """
    )
    conn.commit()
    conn.close()
    return str(path)


def make_agent(db_path, script, **overrides):
    config = dataclasses.replace(
        settings,
        model="m1",
        fallback_models=("m2",),
        narrate_answer=False,
        max_sql_attempts=2,
        **overrides,
    )
    client = FakeClient(script)
    agent = CineDataAgent(client=client, db=Database(db_path, timeout_seconds=2), settings=config)
    return agent, client


def test_missing_api_key_raises():
    config = dataclasses.replace(settings, openrouter_api_key="")
    with pytest.raises(RuntimeError):
        CineDataAgent(settings=config)


def test_success_uses_one_call(db_path):
    agent, _ = make_agent(db_path, ["SELECT titulo FROM dim_movies ORDER BY titulo"])
    result = agent.ask("liste os filmes")
    assert result.rows == [{"titulo": "Alpha"}, {"titulo": "Beta"}]
    assert result.llm_calls == 1 and result.error is None


def test_sql_error_is_fed_back_once(db_path):
    agent, client = make_agent(
        db_path, ["SELECT coluna_inexistente FROM dim_movies", "SELECT titulo FROM dim_movies"]
    )
    result = agent.ask("liste os filmes")
    assert result.attempts == 2 and len(result.rows) == 2
    assert "no such column" in client.calls[1]["messages"][-1]["content"]
    assert len(result.failures) == 1 and "no such column" in result.failures[0]


def test_gives_up_after_max_attempts_without_touching_db(db_path):
    agent, _ = make_agent(db_path, ["DELETE FROM dim_movies", "DROP TABLE dim_movies"])
    result = agent.ask("apague tudo")
    assert "2 tentativa" in result.error
    assert len(agent.db.execute_readonly("SELECT * FROM dim_movies").rows) == 2


def test_clarification_is_returned_without_executing(db_path):
    agent, _ = make_agent(db_path, ["ESCLARECIMENTO: qual nota você quer usar?"])
    result = agent.ask("filmes com melhor nota")
    assert result.clarification == "qual nota você quer usar?"
    assert result.sql is None


def test_fallback_model_is_used_on_rate_limit(db_path):
    agent, client = make_agent(db_path, [rate_limit_error(), "SELECT 1 AS x"])
    result = agent.ask("teste")
    assert [call["model"] for call in client.calls] == ["m1", "m2"]
    assert result.rows == [{"x": 1}]


def not_found_error():
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return openai.NotFoundError("404", response=httpx.Response(404, request=request), body=None)


def test_nonexistent_model_is_skipped_on_later_questions(db_path):
    agent, client = make_agent(db_path, [not_found_error(), "SELECT 1 AS x", "SELECT 1 AS x"])
    agent.ask("primeira")
    result = agent.ask("segunda")
    assert [call["model"] for call in client.calls] == ["m1", "m2", "m2"]
    assert result.llm_calls == 1 and result.model == "m2"


def test_all_models_failing_reports_error(db_path):
    agent, _ = make_agent(db_path, [rate_limit_error(), rate_limit_error()])
    result = agent.ask("teste")
    assert "Nenhum modelo respondeu" in result.error


def test_narration_adds_second_call(db_path):
    agent, _ = make_agent(db_path, ["SELECT titulo FROM dim_movies", "Resposta final."])
    agent.settings = dataclasses.replace(agent.settings, narrate_answer=True)
    result = agent.ask("liste os filmes")
    assert result.answer == "Resposta final." and result.llm_calls == 2


def test_narration_failure_keeps_database_result(db_path):
    agent, _ = make_agent(db_path, ["SELECT 1 AS x", rate_limit_error(), rate_limit_error()])
    agent.settings = dataclasses.replace(agent.settings, narrate_answer=True)
    result = agent.ask("teste")
    assert result.rows == [{"x": 1}] and result.answer is None and result.error is None
