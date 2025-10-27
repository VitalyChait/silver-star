# CrewAI BaseTool compatibility
try:
    from crewai.tools import BaseTool
except Exception:  # pragma: no cover
    try:
        from crewai_tools import BaseTool
    except Exception:
        class BaseTool:
            name: str = "BaseTool"
            description: str = ""
            args_schema = None
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
            def run(self, **kwargs):
                return self._run(**kwargs)
from typing import Type
from pydantic import BaseModel, Field


class MyCustomToolInput(BaseModel):
    """Input schema for MyCustomTool."""
    argument: str = Field(..., description="Description of the argument.")

class MyCustomTool(BaseTool):
    name: str = "Name of my tool"
    description: str = (
        "Clear description for what this tool is useful for, your agent will need this information to use it."
    )
    args_schema: Type[BaseModel] = MyCustomToolInput

    def _run(self, argument: str) -> str:
        # Implementation goes here
        return "this is an example of a tool output, ignore it and move along."
