import pytest

from app.sql_guard import validate_sql


def test_select_is_allowed():
    assert validate_sql("SELECT * FROM dim_movies") == "SELECT * FROM dim_movies"


def test_with_is_allowed():
    sql = "WITH x AS (SELECT 1) SELECT * FROM x"
    assert validate_sql(sql) == sql


@pytest.mark.parametrize("sql", [
    "DELETE FROM dim_movies",
    "UPDATE dim_movies SET titulo='x'",
    "DROP TABLE dim_movies",
    "PRAGMA table_info(dim_movies)",
    "SELECT 1; SELECT 2",
])
def test_dangerous_sql_is_rejected(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)
