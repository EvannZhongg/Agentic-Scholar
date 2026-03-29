from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET

import httpx

from app.connectors.base import BaseSourceClient
from app.domain.schemas import PaperResult


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivClient(BaseSourceClient):
    async def quick_search(self, query: str, limit: int = 5) -> list[PaperResult]:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(limit, self.settings.get("max_page_size", 2000)),
        }
        async with self.build_client() as client:
            await asyncio.sleep(self.settings.get("request_interval_seconds", 3.0))
            response = await client.get(self.settings["base_url"], params=params)
            if response.status_code == 429:
                await asyncio.sleep(self.settings.get("request_interval_seconds", 3.0))
                response = await client.get(self.settings["base_url"], params=params)
            response.raise_for_status()
            xml_text = response.text

        root = ET.fromstring(xml_text)
        results: list[PaperResult] = []
        for entry in root.findall("atom:entry", ATOM_NS):
            pdf_url = None
            entry_url = None
            for link in entry.findall("atom:link", ATOM_NS):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")
                if link.get("rel") == "alternate":
                    entry_url = link.get("href")

            authors = [
                author.findtext("atom:name", default="", namespaces=ATOM_NS)
                for author in entry.findall("atom:author", ATOM_NS)
            ]
            published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
            year = int(published[:4]) if published[:4].isdigit() else None
            results.append(
                PaperResult(
                    source=self.name,
                    source_id=entry.findtext("atom:id", default="", namespaces=ATOM_NS),
                    title=(entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip(),
                    abstract=(entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip(),
                    year=year,
                    doi=None,
                    url=entry_url,
                    pdf_url=pdf_url,
                    is_oa=True,
                    authors=[author for author in authors if author],
                    raw={"id": entry.findtext("atom:id", default="", namespaces=ATOM_NS)},
                )
            )
        return results
