"""Check the standalone explorer without importing its optional UI dependencies."""

import ast
from pathlib import Path


def test_monthly_comparison_only_offers_supported_series() -> None:
    """All selectable series support FRED's monthly aggregation."""
    source = Path(__file__).parents[1] / "examples" / "fred_explorer.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    selector = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "multiselect"
    )
    options = ast.literal_eval(
        next(keyword.value for keyword in selector.keywords if keyword.arg == "options")
    )
    # Daily, weekly, and monthly series can aggregate to monthly; GDP is quarterly.
    supported = {"DGS10", "UNRATE", "CPIAUCSL", "FEDFUNDS", "MORTGAGE30US"}
    assert options
    assert set(options) <= supported
