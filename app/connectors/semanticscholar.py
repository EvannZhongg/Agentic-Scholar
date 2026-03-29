from __future__ import annotations

from typing import Any

from app.connectors.base import BaseSourceClient
from app.domain.schemas import PaperResult


class SemanticScholarClient(BaseSourceClient):
    async def quick_search(self, query: str, limit: int = 5) -> list[PaperResult]:
        headers: dict[str, str] = {}
        if self.settings.get("api_key"):
            headers["x-api-key"] = self.settings["api_key"]

        params: dict[str, Any] = {
            "query": query,
            "limit": min(limit, self.settings.get("max_limit", 100)),
            "fields": "paperId,title,abstract,year,url,externalIds,isOpenAccess,openAccessPdf,authors",
        }

        url = f"{self.settings['graph_base_url']}{self.settings['paper_search_path']}"
        async with self.build_client() as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()

        results: list[PaperResult] = []
        for item in payload.get("data", []):
            pdf_obj = item.get("openAccessPdf") or {}
            external_ids = item.get("externalIds") or {}
            results.append(
                PaperResult(
                    source=self.name,
                    source_id=item.get("paperId"),
                    title=item.get("title") or "",
                    abstract=item.get("abstract"),
                    year=item.get("year"),
                    doi=external_ids.get("DOI"),
                    url=item.get("url"),
                    pdf_url=pdf_obj.get("url"),
                    is_oa=item.get("isOpenAccess"),
                    authors=[author.get("name") for author in item.get("authors", []) if author.get("name")],
                    raw=item,
                )
            )
        return results

