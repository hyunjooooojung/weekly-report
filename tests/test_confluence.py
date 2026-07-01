from weekly_report.confluence_publisher import _next_cursor, markdown_to_storage


def test_markdown_to_storage_basic():
    html = markdown_to_storage("# 제목\n\n- 하나\n- 둘")
    assert "<h1>" in html
    assert "<li>하나</li>" in html


def test_markdown_to_storage_table_and_code():
    md = "```python\nprint(1)\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |"
    html = markdown_to_storage(md)
    assert "<table>" in html
    assert "<code" in html


def test_next_cursor_extraction():
    data = {"_links": {"next": "/wiki/api/v2/pages?space-id=1&cursor=ABC123"}}
    assert _next_cursor(data) == "ABC123"


def test_next_cursor_none_when_missing():
    assert _next_cursor({"_links": {}}) is None
    assert _next_cursor({}) is None
