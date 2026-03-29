from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.domain.schemas import PaperResult, ProbeResult


class BaseSourceClient(ABC):
    def __init__(self, name: str, settings: dict[str, Any]):
        self.name = name
        self.settings = settings
        self.timeout = settings.get("request_timeout_seconds", 30)

    @property
    def enabled(self) -> bool:
        return bool(self.settings.get("enabled", False))

    @property
    def public_enabled(self) -> bool:
        return bool(self.settings.get("public_enabled", False))

    def supports_mode(self, mode: str) -> bool:
        return bool(self.settings.get(f"supports_{mode}", False))

    def has_credentials(self) -> bool:
        for key in ("api_key", "email", "app_key", "app_secret", "app_code", "session_cookie"):
            if self.settings.get(key):
                return True
        return False

    def build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)

    async def probe(self) -> ProbeResult:
        if not self.enabled:
            return ProbeResult(
                name=self.name,
                status="disabled",
                message="provider disabled in config",
                used_credentials=self.has_credentials(),
            )

        start = time.perf_counter()
        try:
            sample = await self.quick_search("transformer", limit=1)
            latency_ms = int((time.perf_counter() - start) * 1000)
            return ProbeResult(
                name=self.name,
                status="ok",
                message="probe succeeded",
                latency_ms=latency_ms,
                used_credentials=self.has_credentials(),
                sample_title=sample[0].title if sample else None,
            )
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return ProbeResult(
                name=self.name,
                status="error",
                message=str(exc),
                http_status=exc.response.status_code,
                latency_ms=latency_ms,
                used_credentials=self.has_credentials(),
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return ProbeResult(
                name=self.name,
                status="error",
                message=str(exc),
                latency_ms=latency_ms,
                used_credentials=self.has_credentials(),
            )

    @abstractmethod
    async def quick_search(self, query: str, limit: int = 5) -> list[PaperResult]:
        raise NotImplementedError
