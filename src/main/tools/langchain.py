"""
LangChain Tool Integration for CrewAI
This module provides integration with LangChain tools for CrewAI agents.
"""

from typing import List, Dict, Any, Optional, Union, Type
from pydantic import BaseModel, Field, create_model
import inspect
import logging
from crewai.tools import BaseTool
from langchain.tools import BaseTool as LangchainBaseTool
from langchain.agents import Tool as LangchainTool

# Setup logging
logger = logging.getLogger(__name__)

class LangChainToolAdapter(BaseTool):
    """
    Adapter class to use LangChain tools within CrewAI.
    This adapter wraps LangChain tools and makes them compatible with CrewAI's tool interface.
    """

    name: str
    description: str
    langchain_tool: Union[LangchainBaseTool, LangchainTool]
    args_schema: Optional[Type[BaseModel]] = None

    def __init__(self, langchain_tool: Union[LangchainBaseTool, LangchainTool], **data):
        """
        Initialize a LangChain tool adapter.

        Args:
            langchain_tool: The LangChain tool to adapt
            **data: Additional parameters for the CrewAI tool
        """
        tool_name = getattr(langchain_tool, "name", None) or data.get("name")
        tool_description = getattr(langchain_tool, "description", None) or data.get("description")

        if not tool_name or not tool_description:
            raise ValueError("Tool must have name and description")

        # Create a Pydantic model for the tool's arguments
        args_schema = self._create_args_schema(langchain_tool)

        # Initialize the CrewAI BaseTool with the LangChain tool's metadata
        super().__init__(
            name=tool_name,
            description=tool_description,
            langchain_tool=langchain_tool,
            args_schema=args_schema,
            **data
        )

    def _run(self, *args, **kwargs) -> Any:
        """
        Run the LangChain tool with the given arguments.

        Args:
            *args: Positional arguments for the tool
            **kwargs: Keyword arguments for the tool

        Returns:
            The result of the tool invocation
        """
        try:
            # Handle different LangChain tool interfaces
            if hasattr(self.langchain_tool, "_run"):
                # LangChain BaseTool
                result = self.langchain_tool._run(*args, **kwargs)
            elif hasattr(self.langchain_tool, "func"):
                # LangChain Tool
                if kwargs and not args:
                    result = self.langchain_tool.func(**kwargs)
                else:
                    result = self.langchain_tool.func(*args, **kwargs)
            else:
                raise ValueError(f"Unsupported LangChain tool type: {type(self.langchain_tool)}")

            return result
        except Exception as e:
            logger.error(f"Error running LangChain tool {self.name}: {str(e)}")
            return f"Error: {str(e)}"

    def _create_args_schema(self, langchain_tool: Union[LangchainBaseTool, LangchainTool]) -> Type[BaseModel]:
        """
        Create a Pydantic model for the tool's arguments based on the LangChain tool's schema.

        Args:
            langchain_tool: The LangChain tool

        Returns:
            A Pydantic model class representing the tool's arguments
        """
        # Try to get the arguments schema from the LangChain tool
        if hasattr(langchain_tool, "args_schema") and langchain_tool.args_schema:
            return langchain_tool.args_schema

        # If not available, try to infer from the function signature
        tool_func = None
        if hasattr(langchain_tool, "_run"):
            tool_func = langchain_tool._run
        elif hasattr(langchain_tool, "func"):
            tool_func = langchain_tool.func

        if not tool_func:
            # Create a minimal schema with a single text argument
            return create_model(
                f"{self.name}Schema",
                argument=(str, Field(description=f"Argument for {self.name}"))
            )

        # Inspect the function signature to create a schema
        try:
            sig = inspect.signature(tool_func)
            fields = {}
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Try to determine the parameter type
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else str

                # Set default value if available
                default = ... if param.default == inspect.Parameter.empty else param.default

                # Add to fields dictionary
                fields[param_name] = (param_type, Field(default=default, description=f"Parameter {param_name}"))

            # Create and return the dynamic model
            schema_class = create_model(f"{self.name}Schema", **fields)
            return schema_class

        except Exception as e:
            logger.warning(f"Failed to create schema for {self.name}: {str(e)}")
            # Fallback to minimal schema
            return create_model(
                f"{self.name}Schema",
                argument=(str, Field(description=f"Argument for {self.name}"))
            )


class LangChainToolRegistry:
    """
    Registry for LangChain tools that can be used with CrewAI.
    This registry manages the conversion of LangChain tools to CrewAI-compatible tools.
    """

    def __init__(self):
        """Initialize the tool registry."""
        self._tools = {}

    def register_tool(self, langchain_tool: Union[LangchainBaseTool, LangchainTool], **kwargs) -> LangChainToolAdapter:
        """
        Register a LangChain tool and convert it to a CrewAI-compatible tool.

        Args:
            langchain_tool: The LangChain tool to register
            **kwargs: Additional parameters for the tool adapter

        Returns:
            The registered tool adapter
        """
        tool_name = getattr(langchain_tool, "name", None) or kwargs.get("name")
        if not tool_name:
            raise ValueError("Tool must have a name")

        # Create the adapter
        adapter = LangChainToolAdapter(langchain_tool, **kwargs)

        # Register the tool
        self._tools[tool_name] = adapter

        return adapter

    def register_tools(self, langchain_tools: List[Union[LangchainBaseTool, LangchainTool]]) -> List[LangChainToolAdapter]:
        """
        Register multiple LangChain tools at once.

        Args:
            langchain_tools: List of LangChain tools to register

        Returns:
            List of registered tool adapters
        """
        adapters = []
        for tool in langchain_tools:
            adapter = self.register_tool(tool)
            adapters.append(adapter)
        return adapters

    def get_tool(self, name: str) -> Optional[LangChainToolAdapter]:
        """
        Get a registered tool by name.

        Args:
            name: The name of the tool

        Returns:
            The tool adapter if found, None otherwise
        """
        return self._tools.get(name)

    def list_tools(self) -> List[LangChainToolAdapter]:
        """
        List all registered tools.

        Returns:
            List of all registered tool adapters
        """
        return list(self._tools.values())

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()


# Global instance of the registry
registry = LangChainToolRegistry()

def adapt_langchain_tool(langchain_tool: Union[LangchainBaseTool, LangchainTool], **kwargs) -> LangChainToolAdapter:
    """
    Convert a LangChain tool to a CrewAI-compatible tool.

    Args:
        langchain_tool: The LangChain tool to convert
        **kwargs: Additional parameters for the tool adapter

    Returns:
        A CrewAI-compatible tool adapter
    """
    return LangChainToolAdapter(langchain_tool, **kwargs)

def adapt_langchain_tools(langchain_tools: List[Union[LangchainBaseTool, LangchainTool]]) -> List[LangChainToolAdapter]:
    """
    Convert multiple LangChain tools to CrewAI-compatible tools.

    Args:
        langchain_tools: List of LangChain tools to convert

    Returns:
        List of CrewAI-compatible tool adapters
    """
    return [adapt_langchain_tool(tool) for tool in langchain_tools]

# Example usage:
# from langchain.tools import BaseTool as LangchainBaseTool
#
# class MyLangChainTool(LangchainBaseTool):
#     name = "my_langchain_tool"
#     description = "A sample LangChain tool"
#
#     def _run(self, query: str) -> str:
#         return f"Result for {query}"
#
# # Convert to CrewAI tool
# crewai_tool = adapt_langchain_tool(MyLangChainTool())
