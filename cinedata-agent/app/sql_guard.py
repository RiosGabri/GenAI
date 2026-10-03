import re

# Cercas de markdown que os modelos costumam devolver mesmo quando proibidas.
_FENCED = re.compile(r"```[a-zA-Z]*\s*(.*?)```", re.DOTALL)

# Literais, identificadores entre aspas e comentários. São removidos antes da
# varredura para que 'Drop Dead Fred' ou "A View to a Kill" não sejam bloqueados.
_OPAQUE = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|--[^\n]*|/\*.*?\*/", re.DOTALL)

# A conexão já é somente leitura (database.py); esta é a segunda camada.
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|VACUUM|REINDEX|PRAGMA)\b",
    re.IGNORECASE,
)


def extract_sql(raw: str) -> str:
    """Remove cercas de markdown (```sql ... ```) da resposta do modelo."""

    text = raw.strip()
    match = _FENCED.search(text)
    if match:
        return match.group(1).strip()

    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    return re.sub(r"\s*```$", "", text).strip()


def validate_sql(sql: str, max_length: int = 8000) -> str:
    sql = extract_sql(sql)

    if not sql:
        raise ValueError("O modelo não retornou SQL.")

    if len(sql) > max_length:
        raise ValueError("SQL excede o tamanho máximo permitido.")

    # Remove apenas ponto e vírgula finais; múltiplas instruções são proibidas.
    while sql.endswith(";"):
        sql = sql[:-1].rstrip()

    code_only = _OPAQUE.sub(" ", sql)

    if ";" in code_only:
        raise ValueError("Múltiplas instruções SQL não são permitidas.")

    if not re.match(r"\s*(SELECT|WITH)\b", code_only, re.IGNORECASE):
        raise ValueError("A resposta deve ser somente uma consulta SELECT/WITH.")

    forbidden = FORBIDDEN.search(code_only)
    if forbidden:
        raise ValueError(f"SQL contém a operação não permitida: {forbidden.group(1).upper()}.")

    return sql