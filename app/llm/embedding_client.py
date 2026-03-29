from __future__ import annotations

import httpx

from config import get_settings


class EmbeddingClient:
    def __init__(self) -> None:
        self.settings = get_settings().get("embedding", {})
        self.timeout = self.settings.get("request_timeout_seconds", 60)
        self.batch_size = max(1, int(self.settings.get("batch_size", 10) or 10))

    def is_configured(self) -> bool:
        return bool(self.settings.get("api_key") and self.settings.get("api_base") and self.settings.get("model"))

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.is_configured():
            raise RuntimeError("Embedding client is not configured")

        cleaned = [(text or " ").strip() or " " for text in texts]
        vectors: list[list[float]] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for idx in range(0, len(cleaned), self.batch_size):
                batch = cleaned[idx : idx + self.batch_size]
                response = await client.post(
                    f"{self.settings['api_base'].rstrip('/')}/embeddings",
                    headers=self._headers(),
                    json={
                        "model": self.settings["model"],
                        "input": batch,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data", [])
                vectors.extend([item.get("embedding", []) for item in data])

        if len(vectors) != len(cleaned):
            raise RuntimeError("Embedding response size mismatch")

        return vectors

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings['api_key']}",
            "Content-Type": "application/json",
        }
