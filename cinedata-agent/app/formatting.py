from typing import Any

_MAX_CELL_WIDTH = 60


def _pt_number(value: float, decimals: int) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def format_value(column: str, value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, (int, float)):
        name = column.lower()
        if name.endswith("brl"):
            return f"R$ {_pt_number(value, 2)}"
        if name.endswith("usd"):
            return f"US$ {_pt_number(value, 2)}"
        return _pt_number(value, 0 if isinstance(value, int) else 2)

    text = str(value).replace("\n", " ")
    if len(text) > _MAX_CELL_WIDTH:
        text = text[: _MAX_CELL_WIDTH - 1] + "…"
    return text


def format_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(nenhuma linha)"

    columns = list(rows[0].keys())
    cells = [
        [
            (format_value(col, row.get(col)), isinstance(row.get(col), (int, float)))
            for col in columns
        ]
        for row in rows
    ]
    widths = [
        max(len(col), *(len(line[i][0]) for line in cells)) for i, col in enumerate(columns)
    ]

    def render(items: list[tuple[str, bool]]) -> str:
        return "  ".join(
            text.rjust(widths[i]) if numeric else text.ljust(widths[i])
            for i, (text, numeric) in enumerate(items)
        ).rstrip()

    header = render([(col, False) for col in columns])
    separator = "  ".join("-" * width for width in widths)
    return "\n".join([header, separator, *(render(line) for line in cells)])
