import re


FORBIDDEN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|UPSERT|ATTACH|DETACH|"
    r"VACUUM|REINDEX|PRAGMA|BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|"
    r"TRIGGER|VIEW"
    r")\b",
    re.IGNORECASE,
)


def validate_sql(sql: str, max_length: int = 8000) -> str:
    sql = sql.strip()

    if not sql:
        raise ValueError("O modelo não retornou SQL.")

    if len(sql) > max_length:
        raise ValueError("SQL excede o tamanho máximo permitido.")

    # Remove apenas um ponto e vírgula final; múltiplas instruções são proibidas.
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()

    if ";" in sql:
        raise ValueError("Múltiplas instruções SQL não são permitidas.")

    if not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise ValueError("Somente consultas SELECT/WITH são permitidas.")

    if FORBIDDEN.search(sql):
        raise ValueError("SQL contém uma operação não permitida.")

    return sql
