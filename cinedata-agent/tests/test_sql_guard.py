import pytest

from app.sql_guard import validate_sql


def test_select_is_allowed():
    assert validate_sql("SELECT * FROM dim_movies") == "SELECT * FROM dim_movies"


def test_with_is_allowed():
    sql = "WITH x AS (SELECT 1) SELECT * FROM x"
    assert validate_sql(sql) == sql


def test_trailing_semicolon_is_removed():
    assert validate_sql("SELECT 1;") == "SELECT 1"


def test_markdown_fence_is_removed():
    assert validate_sql("```sql\nSELECT 1\n```") == "SELECT 1"
    assert validate_sql("```sql\nSELECT 1") == "SELECT 1"


@pytest.mark.parametrize("title", ["A View to a Kill", "Drop Dead Fred", "Begin Again"])
def test_forbidden_words_inside_literals_are_allowed(title):
    sql = f"SELECT * FROM dim_movies WHERE titulo LIKE '%{title}%'"
    assert validate_sql(sql) == sql


def test_semicolon_inside_literal_is_allowed():
    sql = "SELECT * FROM dim_movies WHERE titulo = 'a;b'"
    assert validate_sql(sql) == sql


def test_replace_function_is_allowed():
    sql = "SELECT replace(titulo, 'a', 'b') FROM dim_movies"
    assert validate_sql(sql) == sql


@pytest.mark.parametrize("sql", [
    "DELETE FROM dim_movies",
    "UPDATE dim_movies SET titulo='x'",
    "DROP TABLE dim_movies",
    "PRAGMA table_info(dim_movies)",
    "SELECT 1; SELECT 2",
    "WITH x AS (SELECT 1) DELETE FROM dim_movies",
    "SELECT 1 /* ok */; DROP TABLE dim_movies",
    "Aqui está a consulta: SELECT 1",
    "",
])
def test_dangerous_sql_is_rejected(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)