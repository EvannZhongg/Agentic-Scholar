from __future__ import annotations

from typing import Any

from app.connectors.base import BaseSourceClient
from app.domain.schemas import PaperResult


class IEEEClient(BaseSourceClient):
    async def quick_search(self, query: str, limit: int = 5) -> list[PaperResult]:
        api_key = self.settings.get("api_key")
        if not api_key:
            raise RuntimeError("IEEE_XPLORE_API_KEY not configured")

        params: dict[str, Any] = {
            "querytext": query,
            "max_records": min(limit, self.settings.get("default_page_size", 25)),
            "apikey": api_key,
            "format": "json",
        }
        url = f"{self.settings['base_url']}{self.settings['metadata_search_path']}"
        async with self.build_client() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        results: list[PaperResult] = []
        for item in payload.get("articles", []):
            doi = item.get("doi")
            authors = []
            for author in item.get("authors", {}).get("authors", []):
                if author.get("full_name"):
                    authors.append(author["full_name"])
            results.append(
                PaperResult(
                    source=self.name,
                    source_id=str(item.get("article_number")) if item.get("article_number") is not None else None,
                    title=item.get("title") or "",
                    abstract=item.get("abstract"),
                    year=int(item["publication_year"]) if str(item.get("publication_year", "")).isdigit() else None,
                    doi=doi,
                    url=item.get("html_url") or item.get("abstract_url"),
                    pdf_url=item.get("pdf_url"),
                    is_oa=(str(item.get("access_type", "")).lower() == "open access"),
                    authors=authors,
                    raw=item,
                )
            )
        return results

