import sqlite3

import pytest

from app.database import Database, QueryTimeoutError


@pytest.fixture
def db_path(tmp_path):
    folder = tmp_path / "área de teste"  # acento e espaço, como no caminho real
    folder.mkdir()
    path = folder / "teste.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE dim_movies (
            sk_movie_id TEXT PRIMARY KEY, titulo TEXT NOT NULL,
            ano_lancamento INTEGER, status_filme TEXT);
        CREATE TABLE dim_people (
            sk_person_id TEXT PRIMARY KEY, nome_pessoa TEXT, tipo_pessoa TEXT);
        CREATE TABLE bridge_movie_person (
            sk_movie_id TEXT REFERENCES dim_movies(sk_movie_id),
            sk_person_id TEXT REFERENCES dim_people(sk_person_id),
            PRIMARY KEY (sk_movie_id, sk_person_id));
        INSERT INTO dim_movies VALUES
            ('m1','Alpha',2020,'Lançado'), ('m2','Beta',2023,'Lançado'),
            ('m3','Gamma',2021,'Lançado'), ('m4','Delta',2022,'Lançado'),
            ('m5','Epsilon',2019,'Lançado'), ('m6','Zeta',2029,'Planejado');
        INSERT INTO dim_people VALUES ('p1','Ana','Ator'), ('p2','Bruno','Diretor');
        """
    )
    conn.commit()
    conn.close()
    return str(path)


def test_select_returns_rows(db_path):
    result = Database(db_path).execute_readonly("SELECT titulo FROM dim_movies ORDER BY titulo")
    assert result.rows[0] == {"titulo": "Alpha"}
    assert not result.truncated


def test_connection_is_read_only(db_path):
    with pytest.raises(sqlite3.OperationalError):
        Database(db_path).execute_readonly("DELETE FROM dim_movies")


def test_truncation_is_reported(db_path):
    result = Database(db_path).execute_readonly("SELECT * FROM dim_movies", max_rows=3)
    assert len(result.rows) == 3
    assert result.truncated


def test_runaway_query_times_out(db_path):
    db = Database(db_path, timeout_seconds=0.2)
    sql = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT COUNT(*) FROM c"
    with pytest.raises(QueryTimeoutError):
        db.execute_readonly(sql)


def test_schema_is_read_from_database(db_path):
    schema = Database(db_path).schema()
    assert "dim_movies" in schema
    assert "sk_movie_id TEXT [PK, NOT NULL" in schema or "sk_movie_id TEXT [PK" in schema
    assert "-> dim_movies.sk_movie_id" in schema
    assert '"Ator"' in schema and '"Diretor"' in schema
    assert "(status_filme = 'Lançado') é 2023" in schema
    assert "2029" not in schema  # filme planejado não define a referência


def test_missing_database_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Database(str(tmp_path / "nao_existe.db")).connect()