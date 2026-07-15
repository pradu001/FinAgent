from pydantic import BaseModel, Field
from typing import List, Dict, Any

class PromptTemplate(BaseModel):
    """Validates the structure of a prompt file, including its raw text"""
    name: str = Field(..., description="Unique identifier for the prompt (e.g., 'macro_agent')")
    raw_template: str = Field(..., description="The raw, unformatted prompt string from the text file")
    required_variables: List[str] = Field(
        default_factory=list,
        description="List of placeholder variables expected in the prompt (e.g., ['search_results'])"
    )

    def format(self, inputs: Dict[str, Any]) -> str:
        """Safely injects variables into the raw template after validating all requides inputs are present"""
        missing = [var for var in self.required_variables if var not in inputs]
        if missing:
            raise KeyError(
                f"Missing required formatting variables for prompt '{self.name}': {missing}"
            )
        
        format_dict = {var: inputs[var] for var in self.required_variables}
        return self.raw_template.format(**format_dict)
