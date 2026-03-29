from __future__ import annotations

from typing import Any

from app.connectors.base import BaseSourceClient
from app.domain.schemas import PaperResult


class CoreClient(BaseSourceClient):
    async def quick_search(self, query: str, limit: int = 5) -> list[PaperResult]:
        headers: dict[str, str] = {}
        params: dict[str, Any] = {"q": f'title:"{query}"', "limit": min(limit, self.settings.get("default_limit", 25))}
        if self.settings.get("api_key"):
            headers["x-api-key"] = self.settings["api_key"]

        url = f"{self.settings['base_url']}{self.settings['works_search_path']}/"
        async with self.build_client() as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()

        results: list[PaperResult] = []
        for item in payload.get("results", []):
            authors = []
            for author in item.get("authors", []):
                if isinstance(author, dict) and author.get("name"):
                    authors.append(author["name"])
                elif isinstance(author, str):
                    authors.append(author)
            results.append(
                PaperResult(
                    source=self.name,
                    source_id=str(item.get("id")) if item.get("id") is not None else None,
                    title=item.get("title") or "",
                    abstract=item.get("abstract"),
                    year=item.get("yearPublished"),
                    doi=item.get("doi"),
                    url=item.get("downloadUrl") or (item.get("outputs", [None])[0] if item.get("outputs") else None),
                    pdf_url=item.get("downloadUrl"),
                    is_oa=None,
                    authors=authors,
                    raw=item,
                )
            )
        return results

