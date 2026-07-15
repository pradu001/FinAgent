import pytest
import tempfile
import os
from app.prompts.schemas.prompt_schema import PromptTemplate
from app.prompts.services.prompt_loader import PromptManagementService

def test_prompt_template_successful_formatting():
    """Checks that PromptTemplate correctly formats variables when all inputs are present"""
    template = PromptTemplate(
        name="test_prompt",
        raw_template="Hello {user_name}, welcome to {project_name}!",
        required_variables=["user_name", "project_name"]
    )
    formatted = template.format({"user_name": "Gabriel", "project_name": "FinAgent"})
    assert formatted == "Hello Gabriel, welcome to FinAgent!"

def test_prompt_template_missing_variables_raises_key_error():
    """Verifies that missing required variables raise a KeyError"""
    template = PromptTemplate(
        name="test_prompt",
        raw_template="Hello {user_name}, welcome to {project_name}!",
        required_variables=["user_name", "project_name"]
    )
    with pytest.raises(KeyError) as exc_info:
        template.format({"user_name": "Gabriel"})
    assert "Missing required formatting variables" in str(exc_info.value)

def test_prompt_loader_loads_registered_prompt():
    """Verifies the loader can read the real macro_agent.txt prompt correctly"""
    loader = PromptManagementService()
    template = loader.load_prompt("macro_agent")

    assert template.name == "macro_agent"
    assert "search_results" in template.required_variables
    assert "{search_results}" in template.raw_template

def test_prompt_loader_unregistered_prompt_raises_value_error():
    """Checs that trying to load an unregistered prompt template raises a ValueError"""
    loader = PromptManagementService()
    with pytest.raises(ValueError) as exc_info:
        loader.load_prompt("non_existent_agent")
    assert "is not registered" in str(exc_info.value)

def test_prompt_loader_missing_file_raises_file_not_found():
    """Ensures a registered prompt with a missing file raises FileNotFoundError"""
    loader = PromptManagementService()
    loader._registry["missing_agent"] = ["some_var"]

    with pytest.raises(FileNotFoundError):
        loader.load_prompt("missing_agent")
