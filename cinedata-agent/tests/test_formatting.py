from app.formatting import format_table, format_value


def test_money_columns_are_prefixed_and_use_two_decimals():
    assert format_value("receita_brl", 11094720000) == "R$ 11.094.720.000,00"
    assert format_value("receita_R$", 11094720000) == "R$ 11.094.720.000,00"
    assert format_value("receita_usd", 1.5) == "US$ 1,50"


def test_int_in_float_column_gets_two_decimals():
    table = format_table([{"nota": 7.25}, {"nota": 8}])
    assert "7,25" in table and "8,00" in table


def test_int_only_column_has_no_decimals():
    assert "1.234" in format_table([{"filmes": 1234}])
    assert "1.234," not in format_table([{"filmes": 1234}])


def test_none_empty_and_long_text():
    assert format_value("x", None) == "—"
    assert format_table([]) == "(nenhuma linha)"
    assert len(format_value("sinopse", "a" * 500)) == 60


def test_table_has_header_separator_and_rows():
    lines = format_table([{"titulo": "A", "n": 1}, {"titulo": "B", "n": 22}]).splitlines()
    assert len(lines) == 4 and lines[0].split() == ["titulo", "n"]
