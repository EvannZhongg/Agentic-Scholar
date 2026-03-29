from __future__ import annotations

import asyncio
import json

from app.services.provider_registry import list_provider_summaries
from app.services.search_service import run_provider_probes


async def main() -> None:
    print("Configured providers:")
    print(json.dumps([item.model_dump() for item in list_provider_summaries()], ensure_ascii=False, indent=2))
    print()
    print("Live probe results:")
    probes = await run_provider_probes()
    print(json.dumps([item.model_dump() for item in probes], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

