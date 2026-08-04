"""Tavily web search — grounding sources for the Research agent."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel
from tavily import TavilyClient

from app.config import get_settings


class SearchResult(BaseModel):
    title: str
    url: str
    content: str


async def search(query: str, max_results: int = 5) -> list[SearchResult]:
    settings = get_settings()
    client = TavilyClient(api_key=settings.tavily_api_key)

    def _call() -> dict:
        return client.search(query, max_results=max_results)

    response = await asyncio.to_thread(_call)
    return [
        SearchResult(title=r["title"], url=r["url"], content=r.get("content", ""))
        for r in response.get("results", [])
    ]
