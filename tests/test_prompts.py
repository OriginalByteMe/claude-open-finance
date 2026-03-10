from firefly_mcp.prompts import REVIEW_IMPORTS_TEMPLATE, MONTHLY_REVIEW_TEMPLATE


def test_review_imports_template_formats():
    result = REVIEW_IMPORTS_TEMPLATE.format(days_back=14)
    assert "days_back=14" in result
    assert "get_financial_context" in result
    assert "categorize_transactions" in result


def test_monthly_review_template_formats():
    result = MONTHLY_REVIEW_TEMPLATE.format(month="2026-03", start="2026-03-01", end="2026-03-31")
    assert "2026-03-01" in result
    assert "2026-03-31" in result
    assert "get_spending_summary" in result


def test_monthly_review_server_prompt():
    """Test the server-level prompt function handles month parsing."""
    from firefly_mcp.server import monthly_review
    result = monthly_review(month="2026-02")
    assert "2026-02-01" in result
    assert "2026-02-28" in result


def test_monthly_review_server_prompt_default():
    """Test that default month uses current month."""
    from firefly_mcp.server import monthly_review
    result = monthly_review()
    assert "get_spending_summary" in result
