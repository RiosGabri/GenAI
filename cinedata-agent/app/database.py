import sqlite3
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        if not Path(self.db_path).exists():
            raise FileNotFoundError(
                f"Banco não encontrado: {self.db_path}. "
                "Coloque cinerocket.db na raiz do projeto ou defina CINEDATA_DB_PATH."
            )

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def schema(self) -> str:
        return """
TABELAS E RELACIONAMENTOS:

dim_movies
- sk_movie_id VARCHAR(64) PRIMARY KEY
- id_filme VARCHAR(50)
- titulo VARCHAR(500)
- data_lancamento DATE
- ano_lancamento INTEGER
- duracao_minutos INTEGER
- idioma_original VARCHAR(10)
- status_filme VARCHAR(50)
- sinopse VARCHAR(4000)
- url_poster VARCHAR(2048)
- url_backdrop VARCHAR(2048)

fact_movies_performance
- sk_movie_id VARCHAR(64) PRIMARY KEY -> dim_movies.sk_movie_id
- orcamento_usd NUMERIC(18,2)
- receita_usd NUMERIC(18,2)
- lucro_usd NUMERIC(18,2)
- orcamento_brl NUMERIC(18,2)
- receita_brl NUMERIC(18,2)
- lucro_brl NUMERIC(18,2)
- popularidade DOUBLE
- nota_tmdb DOUBLE
- qtd_tmdb INTEGER
- nota_imdb DOUBLE
- qtd_imdb INTEGER

dim_genres
- sk_genre_id VARCHAR(64) PRIMARY KEY
- nome_genero VARCHAR(50)

bridge_movie_genre
- sk_movie_id VARCHAR(64) PRIMARY KEY -> dim_movies.sk_movie_id
- sk_genre_id VARCHAR(64) PRIMARY KEY -> dim_genres.sk_genre_id

dim_people
- sk_person_id VARCHAR(64) PRIMARY KEY
- nome_pessoa VARCHAR(255)
- tipo_pessoa VARCHAR(20)

bridge_movie_person
- sk_movie_id VARCHAR(64) PRIMARY KEY -> dim_movies.sk_movie_id
- sk_person_id VARCHAR(64) PRIMARY KEY -> dim_people.sk_person_id

dim_companies
- sk_company_id VARCHAR(64) PRIMARY KEY
- nome_produtora VARCHAR(255)

bridge_movie_company
- sk_movie_id VARCHAR(64) PRIMARY KEY -> dim_movies.sk_movie_id
- sk_company_id VARCHAR(64) PRIMARY KEY -> dim_companies.sk_company_id

dim_reviews
- sk_review_id VARCHAR(64) PRIMARY KEY
- sk_movie_id VARCHAR(64) -> dim_movies.sk_movie_id
- qtd_avaliacoes_usuarios INTEGER
- nota_media_usuarios DOUBLE

movie_reviews
- id INTEGER PRIMARY KEY
- sk_movie_review_id VARCHAR(64)
- sk_movie_id VARCHAR(64)
- name VARCHAR(120)
- rating DOUBLE
- text VARCHAR(4000)
- created_at DATETIME

REGRAS SEMÂNTICAS:
- Receita, faturamento e bilheteria são equivalentes.
- Margem de lucro = lucro / receita. Nunca dividir por receita NULL ou zero.
- Para análises em R$, priorizar as colunas *_brl.
- Para maior/menor receita, lucro, orçamento etc., ignorar valores NULL.
- Para "últimos N anos", usar ano_lancamento em relação ao maior ano de lançamento disponível no banco quando a pergunta não fornecer uma data de referência explícita.
- "ator" e "diretor" dependem do valor de tipo_pessoa armazenado no banco. Não inventar valores.
- Para média de diretor, aplicar o mínimo de 5 filmes quando solicitado.
- Para comparar notas, só usar filmes que possuam as duas notas necessárias.
- Evitar duplicação causada por tabelas bridge: usar DISTINCT, GROUP BY apropriado ou agregações antes do JOIN quando necessário.
""".strip()

    def execute_readonly(self, sql: str, max_rows: int = 100) -> list[dict[str, Any]]:
        conn = self.connect()
        try:
            cur = conn.execute(sql)
            rows = cur.fetchmany(max_rows)
            return [dict(row) for row in rows]
        finally:
            conn.close()
