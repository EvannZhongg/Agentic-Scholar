from __future__ import annotations

import asyncio
import json
import sys

from app.domain.schemas import SearchRequest
from app.services.search_service import quick_search


async def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "transformer"
    response = await quick_search(SearchRequest(query=query, limit_per_source=3, public_only=False))
    print(json.dumps(response.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

