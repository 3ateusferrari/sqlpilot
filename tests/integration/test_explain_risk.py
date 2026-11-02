"""Integration tests for EXPLAIN (FORMAT JSON) plan cost and cardinality analysis."""

import pytest

from app.db.session import get_readonly_connection
from app.graph.state import ExplainMetrics
from app.security.risk_classifier import (
    analyze_explain_plan,
    evaluate_explain_risk,
)


@pytest.mark.asyncio
async def test_explain_simple_query_low_risk() -> None:
    """Test 1: Simple lightweight query evaluates to low risk."""
    sql = "SELECT * FROM artist LIMIT 5"
    metrics = await analyze_explain_plan(sql)

    assert isinstance(metrics, ExplainMetrics)
    assert metrics.estimated_rows <= 5
    assert metrics.total_cost < 500.0
    assert metrics.raw_plan != {}
    assert "Node Type" in metrics.raw_plan

    risk, reasons = evaluate_explain_risk(metrics)
    assert risk == "low"
    assert reasons == []


@pytest.mark.asyncio
async def test_explain_high_cost_query_high_risk() -> None:
    """Test 2: High-cost / cartesian query evaluates to high risk."""
    sql = "SELECT * FROM track, invoice_line, playlist_track"
    metrics = await analyze_explain_plan(sql)

    assert isinstance(metrics, ExplainMetrics)
    assert metrics.total_cost > 500.0 or metrics.estimated_rows > 1000

    risk, reasons = evaluate_explain_risk(metrics)
    assert risk == "high"
    assert len(reasons) > 0
    assert any("excede o limite tolerado" in r for r in reasons)


def test_evaluate_explain_risk_custom_thresholds() -> None:
    """Test 3: Custom cost and rows thresholds trigger high risk."""
    # Custom cost threshold exceeded
    metrics_cost = ExplainMetrics(total_cost=10.0, estimated_rows=5)
    risk, reasons = evaluate_explain_risk(metrics_cost, cost_threshold=5.0, rows_threshold=100)
    assert risk == "high"
    assert len(reasons) == 1
    assert "Custo estimado do plano de execução (10.0) excede o limite tolerado (5.0)" in reasons[0]

    # Custom rows threshold exceeded
    metrics_rows = ExplainMetrics(total_cost=2.0, estimated_rows=50)
    risk, reasons = evaluate_explain_risk(metrics_rows, cost_threshold=100.0, rows_threshold=10)
    assert risk == "high"
    assert len(reasons) == 1
    assert "Cardinalidade estimada (50 linhas) excede o limite tolerado (10 linhas)" in reasons[0]

    # Both thresholds exceeded
    metrics_both = ExplainMetrics(total_cost=15.5, estimated_rows=150)
    risk, reasons = evaluate_explain_risk(metrics_both, cost_threshold=10.0, rows_threshold=100)
    assert risk == "high"
    assert len(reasons) == 2


@pytest.mark.asyncio
async def test_explain_seq_scan_detection() -> None:
    """Test 4: Detects Seq Scan in execution plan."""
    # artist table has no index on name column, leading to Seq Scan
    sql = "SELECT * FROM artist WHERE name = 'AC/DC'"
    metrics = await analyze_explain_plan(sql)

    assert isinstance(metrics, ExplainMetrics)
    assert metrics.has_seq_scan is True
    assert metrics.raw_plan.get("Node Type") == "Seq Scan" or any(
        sub.get("Node Type") == "Seq Scan" for sub in metrics.raw_plan.get("Plans", [])
    )


@pytest.mark.asyncio
async def test_explain_graceful_error_handling_on_invalid_sql() -> None:
    """Test 5: Graceful error handling on invalid or rejected SQL without crash."""
    invalid_sql = "SELECT * FROM non_existent_table_xyz_123"
    metrics = await analyze_explain_plan(invalid_sql)

    assert isinstance(metrics, ExplainMetrics)
    assert metrics.total_cost == 0.0
    assert metrics.estimated_rows == 0
    assert metrics.has_seq_scan is False
    assert metrics.raw_plan == {}

    risk, reasons = evaluate_explain_risk(metrics)
    assert risk == "low"
    assert reasons == []


@pytest.mark.asyncio
async def test_explain_with_provided_connection() -> None:
    """Validate analyze_explain_plan works when an explicit connection is passed."""
    async with get_readonly_connection() as conn:
        metrics = await analyze_explain_plan("SELECT * FROM genre LIMIT 2", conn=conn)
        assert isinstance(metrics, ExplainMetrics)
        assert metrics.estimated_rows <= 2
        assert metrics.total_cost < 500.0
