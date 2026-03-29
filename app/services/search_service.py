from __future__ import annotations

import asyncio

from app.domain.schemas import ProbeResult, SearchRequest, SearchResponse
from app.services.deep_channel import run_deep_channel
from app.services.provider_registry import build_clients
from app.services.quick_channel import run_quick_channel


async def run_provider_probes(source_names: list[str] | None = None) -> list[ProbeResult]:
    all_clients = build_clients()
    clients = []
    for name, client in all_clients.items():
        if source_names and name not in source_names:
            continue
        if not client.enabled:
            continue
        clients.append(client)
    probes = await asyncio.gather(*(client.probe() for client in clients))
    return list(probes)


async def quick_search(request: SearchRequest) -> SearchResponse:
    return await run_quick_channel(request)


async def deep_search(request: SearchRequest) -> SearchResponse:
    return await run_deep_channel(request)
