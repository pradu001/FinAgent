import pytest
from unittest.mock import MagicMock, patch
from app.graph.state import AgentState, MacroOutput
from app.agents.macro import macro_agent_node

@pytest.fixture
def base_state() -> AgentState:
    """Provides a fresh, valid AgentState fixture for test runs."""
    return {
        "pipeline_run_id": "test-run-123",
        "morning_note_id": "test-note-456",
        "flags": [],
        "data_freshness": {},
        "macro_context": None
    }

@patch("app.agents.macro.TavilyClient")
@patch("app.agents.macro.OpenAI")
def test_macro_agent_node_success(mock_openai_class, mock_tavily_class, base_state):
    """
    Test Case: Verify successful macro extraction path.
    Mocks Tavily search context and mock-validates the OpenRouter / OpenAI JSON output.
    """
    mock_tavily_instance = MagicMock()
    mock_tavily_instance.get_search_context.return_value = "Mocked Brazilian Economic News Snippets"
    mock_tavily_class.return_value = mock_tavily_instance

    mock_openai_instance = MagicMock()
    
    mock_json_response = """{
        "gdp_growth": 2.16,
        "inflation_rate": 4.72,
        "interest_rate": 14.25,
        "analysis_summary": "Strong core extraction verified by pytest."
    }"""
    
    mock_choice = MagicMock()
    mock_choice.message.content = mock_json_response
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    
    mock_openai_instance.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_openai_instance

    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake_key", "TAVILY_API_KEY": "fake_key"}):
        updated_state = macro_agent_node(base_state)

    assert updated_state["macro_context"] is not None
    assert isinstance(updated_state["macro_context"], MacroOutput)
    assert updated_state["macro_context"].gdp_growth == 2.16
    assert updated_state["macro_context"].interest_rate == 14.25
    assert len(updated_state["flags"]) == 0
    assert "macro" in updated_state["data_freshness"]


@patch("app.agents.macro.TavilyClient")
@patch("app.agents.macro.OpenAI")
def test_macro_agent_node_api_failure(mock_openai_class, mock_tavily_class, base_state):
    """
    Test Case: Verify error recovery workflow.
    Simulates an OpenRouter rate limit/API exception and asserts high-priority flag registration.
    """
    mock_tavily_instance = MagicMock()
    mock_tavily_instance.get_search_context.return_value = "Search context okay."
    mock_tavily_class.return_value = mock_tavily_instance

    mock_openai_instance = MagicMock()
    mock_openai_instance.chat.completions.create.side_with = Exception("OpenRouter API Error")
    mock_openai_class.return_value = mock_openai_instance

    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake_key", "TAVILY_API_KEY": "fake_key"}):
        updated_state = macro_agent_node(base_state)

    assert updated_state["macro_context"] is None
    assert len(updated_state["flags"]) == 1
    assert updated_state["flags"][0].source == "macro_agent"
    assert updated_state["flags"][0].flag_type == "high"
