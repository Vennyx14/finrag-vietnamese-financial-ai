"""Unit tests for HTML table parser and number conversion."""

from src.ingestion.table_parser import (
    inspect_table_structure,
    normalize_whitespace,
    parse_html_table,
    parse_vietnamese_number,
)


def test_parse_simple_html_table():
    """Verify that a basic HTML table is converted into a list of row cells."""
    html = """
    <table>
        <tr><th>Col 1</th><th>Col 2</th></tr>
        <tr><td>Val 1</td><td>Val 2</td></tr>
    </table>
    """
    rows = parse_html_table(html)
    assert len(rows) == 2
    assert rows[0] == ["Col 1", "Col 2"]
    assert rows[1] == ["Val 1", "Val 2"]


def test_parse_malformed_html_table():
    """Verify that malformed or unclosed HTML tables do not crash the parser."""
    html_broken = "<table><tr><td>Cell 1<td>Cell 2<tr><td>Cell 3"
    rows = parse_html_table(html_broken)
    assert isinstance(rows, list)
    assert len(rows) > 0

    # Completely invalid text should return empty list without crashing
    rows_empty = parse_html_table("just plain text without table")
    assert rows_empty == []


def test_detect_line_code_header():
    """Verify that line-code headers ('Mã số') are identified."""
    table = [
        ["TÀI SẢN", "Mã số", "Thuyết minh", "31/12/2020", "01/01/2020"],
        ["Tiền", "110", "V.01", "100.000.000", "80.000.000"],
    ]
    info = inspect_table_structure(table)
    assert info["has_line_code"] is True
    assert info["line_code_col"] == 1
    assert info["label_col"] == 0
    assert 2 in info["note_cols"]
    assert info["value_cols"] == [3, 4]


def test_detect_line_code_header_at_col_zero():
    """Verify detection when 'Mã số' is the first column."""
    table = [
        ["Mã số", "Chỉ tiêu", "Năm nay", "Năm trước"],
        ["01", "Doanh thu", "500.000", "400.000"],
    ]
    info = inspect_table_structure(table)
    assert info["has_line_code"] is True
    assert info["line_code_col"] == 0
    assert info["label_col"] == 1
    assert info["value_cols"] == [2, 3]


def test_parse_numeric_values_standard():
    """Verify standard Vietnamese thousand-separated numbers."""
    assert parse_vietnamese_number("1.071.561.008.455") == 1071561008455.0
    assert parse_vietnamese_number("414.721") == 414721.0
    assert parse_vietnamese_number("1,234,567") == 1234567.0


def test_parse_numeric_values_negative():
    """Verify negative numbers formatted with parentheses or explicit minus signs."""
    # Accounting parentheses
    assert parse_vietnamese_number("(11.078.921.256)") == -11078921256.0
    assert parse_vietnamese_number("(50.000)") == -50000.0
    # Explicit minus sign
    assert parse_vietnamese_number("-123.456") == -123456.0
    assert parse_vietnamese_number("- 123.456") == -123456.0


def test_parse_numeric_values_decimals():
    """Verify decimal numbers with comma and dot conventions."""
    # Comma decimal (Vietnamese standard)
    assert parse_vietnamese_number("11.116.022,66") == 11116022.66
    assert parse_vietnamese_number("12,34") == 12.34
    assert parse_vietnamese_number("(12,34)") == -12.34

    # Dot decimal
    assert parse_vietnamese_number("11,116,022.66") == 11116022.66
    assert parse_vietnamese_number("12.34") == 12.34


def test_parse_numeric_values_special():
    """Verify zero/dash and percentage parsing."""
    assert parse_vietnamese_number("-") == 0.0
    assert parse_vietnamese_number("–") == 0.0
    assert parse_vietnamese_number("—") == 0.0
    assert parse_vietnamese_number("17,08%") == 17.08
    assert parse_vietnamese_number("text only") is None
    assert parse_vietnamese_number("") is None
