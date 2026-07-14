import pytest
from datetime import datetime, timezone
from app.graph.state import (
    create_initial_state,
    validate_state,
    MacroOutput,
    CompanyEvent
)

def test_create_initial_state_success():
    """Verify state initizlization creates correct structures and formats"""
    state = create_initial_state(
        pipeline_run_id="run-123",
        morning_note_id="note-456",
        manager_id=1,
        company_ticker="PETR4"
    )

    assert state["manager_id"] == 1
    assert state["company_ticker"] == "PETR4"
    assert isinstance(state["company_events"], list)
    assert isinstance(state["confidence_scores"], dict)
    assert state["macro_context"] is None

def test_create_initial_state_invalid_manager():
    """Verify that state initialization fails early with invalid manager_id values"""
    with pytest.raises(ValueError, match="manager_id must be a valid, non-zero integer"):
        create_initial_state("run-123", "note-456", 0, "PETR4")

    with pytest.raises(ValueError, match="manager_id must be a valid, non-zero integer"):
        create_initial_state("run-123", "note-456", None, "PETR4")

def test_validate_state_missing_manager_id():
    """Verify that validate_state raises an explicit error when manager_id is missing"""
    state = create_initial_state("run-123", "note-456", 1, "PETR4")

    state["manager_id"] = None

    with pytest.raises(ValueError, match="State Invariant Violation: 'manager_id' is missing or null"):
        validate_state(state)

def test_validate_state_invalid_types():
    """Verify that validate_state detects incorrect structure types"""
    state = create_initial_state("run-123", "note-456", 1, "PETR4")

    state["company_events"] = "not-a-list"

    with pytest.raises(TypeError, match="must be a list structure"):
        validate_state(state)

def test_validate_state_success():
    """Verify that a healthy state passes validation without throwing errors"""
    state = create_initial_state("run-123", "note-456", 1, "PETR4")

    state["macro_context"] = MacroOutput(
        gdp_growth=1.5,
        inflation_rate=4.2,
        interest_rate=10.5,
        analysis_summary="Stable interest outlook"
    )

    validate_state(state)
