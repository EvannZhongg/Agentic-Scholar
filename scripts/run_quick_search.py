from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.schemas import SearchRequest
from app.services.search_service import quick_search
from scripts.output_utils import print_json_safe, write_json_output


async def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "transformer"
    response = await quick_search(SearchRequest(query=query, limit_per_source=3, public_only=False))
    payload = response.model_dump()
    output_path = write_json_output(payload, prefix="quick_search", label=query)
    print_json_safe(payload)
    print(f"\nSaved JSON: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
