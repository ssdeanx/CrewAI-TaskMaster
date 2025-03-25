"""
Serper API Search Tool for CrewAI
This module provides web search capabilities for CrewAI agents using the Serper API.
"""

import os
import json
import requests
from typing import Type, Dict, Any, List, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

class SerperSearchInput(BaseModel):
    """Input schema for SerperSearch tool."""
    query: str = Field(..., description="The search query to execute.")
    search_type: str = Field("search", description="The type of search to perform: 'search', 'images', 'news', or 'places'.")
    num_results: int = Field(10, description="The number of search results to return (default: 10, max: 100).")
    country_code: Optional[str] = Field(None, description="The country code for localized results (e.g., 'us', 'uk', 'fr').")

class SerperSearch(BaseTool):
    """
    A tool for performing web searches using the Serper API.

    This tool allows CrewAI agents to search the web for information,
    supporting standard search, image search, news search, and places search.
    """

    name: str = "serper_search"
    description: str = (
        "Search the web for current information on any topic. "
        "Useful for finding recent events, news, articles, facts, and information "
        "that might not be in the agent's existing knowledge."
    )
    args_schema: Type[BaseModel] = SerperSearchInput
    api_key: str = None

    def __init__(self, api_key: str = None, **kwargs):
        """
        Initialize the SerperSearch tool.

        Args:
            api_key: The Serper API key. If not provided, tries to load from SERPER_API_KEY environment variable.
            **kwargs: Additional arguments to pass to the BaseTool constructor.
        """
        super().__init__(**kwargs)

        # Use the provided API key or try to get from environment
        self.api_key = api_key or os.environ.get("SERPER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Serper API key is required. Provide it as an argument or "
                "set the SERPER_API_KEY environment variable."
            )

    def _run(self, query: str, search_type: str = "search",
             num_results: int = 10, country_code: Optional[str] = None) -> str:
        """
        Execute a search query using the Serper API.

        Args:
            query: The search query to execute.
            search_type: The type of search to perform ('search', 'images', 'news', or 'places').
            num_results: The number of search results to return.
            country_code: The country code for localized results.

        Returns:
            A formatted string containing the search results.
        """
        # Validate search type
        valid_search_types = ["search", "images", "news", "places"]
        if search_type not in valid_search_types:
            return f"Error: Invalid search type '{search_type}'. Valid options are: {', '.join(valid_search_types)}"

        # Limit number of results
        num_results = min(max(1, num_results), 100)

        # Set up the API request
        url = f"https://google.serper.dev/search"

        # Prepare payload based on search type
        payload = {
            "q": query,
            "num": num_results
        }

        if search_type != "search":
            url = f"https://google.serper.dev/{search_type}"

        if country_code:
            payload["gl"] = country_code

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            # Make the API request
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()  # Raise exception for HTTP errors

            # Parse response
            search_results = response.json()

            # Process and format results based on search type
            formatted_results = self._format_results(search_results, search_type)

            return formatted_results

        except requests.exceptions.RequestException as e:
            return f"Search error: {str(e)}"

    def _format_results(self, search_results: Dict[str, Any], search_type: str) -> str:
        """
        Format the search results as a readable string.

        Args:
            search_results: The raw search results from the API.
            search_type: The type of search performed.

        Returns:
            A formatted string representation of the search results.
        """
        formatted = f"Search Results:\n\n"

        if search_type == "search":
            # For standard search
            organic_results = search_results.get("organic", [])
            for i, result in enumerate(organic_results, 1):
                title = result.get("title", "No Title")
                link = result.get("link", "No Link")
                snippet = result.get("snippet", "No Snippet")
                formatted += f"{i}. {title}\n   URL: {link}\n   {snippet}\n\n"

            # Add knowledge graph if available
            if "knowledgeGraph" in search_results:
                kg = search_results["knowledgeGraph"]
                formatted += "Knowledge Graph:\n"
                formatted += f"  Title: {kg.get('title', 'N/A')}\n"
                formatted += f"  Type: {kg.get('type', 'N/A')}\n"
                if "description" in kg:
                    formatted += f"  Description: {kg['description']}\n"
                formatted += "\n"

        elif search_type == "news":
            # For news search
            news_results = search_results.get("news", [])
            for i, result in enumerate(news_results, 1):
                title = result.get("title", "No Title")
                link = result.get("link", "No Link")
                date = result.get("date", "No Date")
                source = result.get("source", "Unknown Source")
                snippet = result.get("snippet", "No Snippet")
                formatted += f"{i}. {title}\n   Source: {source} | Date: {date}\n   URL: {link}\n   {snippet}\n\n"

        elif search_type == "places":
            # For places search
            places_results = search_results.get("places", [])
            for i, result in enumerate(places_results, 1):
                name = result.get("name", "No Name")
                address = result.get("address", "No Address")
                phone = result.get("phoneNumber", "No Phone")
                rating = result.get("rating", "No Rating")
                reviews = result.get("reviews", "No Reviews")
                formatted += f"{i}. {name}\n   Address: {address}\n   Phone: {phone}\n   Rating: {rating} ({reviews} reviews)\n\n"

        elif search_type == "images":
            # For image search
            images_results = search_results.get("images", [])
            for i, result in enumerate(images_results, 1):
                title = result.get("title", "No Title")
                link = result.get("imageUrl", "No Image URL")
                source_url = result.get("source", "No Source")
                formatted += f"{i}. {title}\n   Image URL: {link}\n   Source: {source_url}\n\n"

        if not formatted.strip().endswith("Search Results:"):
            return formatted
        else:
            return "No results found."

class SerperNewsInput(BaseModel):
    """Input schema for SerperNews tool."""
    query: str = Field(..., description="The news search query to execute.")
    num_results: int = Field(5, description="The number of news results to return (default: 5, max: 100).")
    country_code: Optional[str] = Field(None, description="The country code for localized results (e.g., 'us', 'uk', 'fr').")

class SerperNews(SerperSearch):
    """A specialized tool for searching news articles using the Serper API."""

    name: str = "serper_news"
    description: str = (
        "Search for recent news articles on any topic. "
        "Useful for finding current events, recent developments, and trending stories."
    )
    args_schema: Type[BaseModel] = SerperNewsInput

    def _run(self, query: str, num_results: int = 5, country_code: Optional[str] = None) -> str:
        """Execute a news search query using the Serper API."""
        return super()._run(query=query, search_type="news", num_results=num_results, country_code=country_code)
