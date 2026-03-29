from __future__ import annotations

import json
from typing import Any

import httpx

from config import get_settings


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings().get("llm", {})
        self.timeout = self.settings.get("request_timeout_seconds", 60)

    def is_configured(self) -> bool:
        return bool(self.settings.get("api_key") and self.settings.get("api_base") and self.settings.get("model"))

    def preferred_interface(self) -> str:
        api_interface = self.settings.get("api_interface", "auto")
        if api_interface != "auto":
            return api_interface
        return self.settings.get("api_interface_preference", "responses")

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("LLM client is not configured")

        preference = self.preferred_interface()
        if preference == "responses":
            try:
                return await self._responses_json(system_prompt, user_prompt)
            except Exception:
                if self.settings.get("api_interface", "auto") == "auto":
                    return await self._chat_json(system_prompt, user_prompt)
                raise

        if preference == "chat_completions":
            try:
                return await self._chat_json(system_prompt, user_prompt)
            except Exception:
                if self.settings.get("api_interface", "auto") == "auto":
                    return await self._responses_json(system_prompt, user_prompt)
                raise

        raise RuntimeError(f"Unsupported LLM interface preference: {preference}")

    async def _responses_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        url = f"{self.settings['api_base'].rstrip('/')}/responses"
        payload = {
            "model": self.settings["model"],
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.get("temperature", 0.2),
        }
        max_output_tokens = self.settings.get("max_output_tokens", 0)
        if max_output_tokens:
            payload["max_output_tokens"] = max_output_tokens

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            data = response.json()

        text = data.get("output_text") or self._extract_response_text(data)
        return self._parse_json_text(text)

    async def _chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        url = f"{self.settings['api_base'].rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.get("temperature", 0.2),
        }
        max_output_tokens = self.settings.get("max_output_tokens", 0)
        if max_output_tokens:
            payload["max_tokens"] = max_output_tokens

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            data = response.json()

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content", "")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            content = "\n".join(parts)
        return self._parse_json_text(content)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings['api_key']}",
            "Content-Type": "application/json",
        }

    def _extract_response_text(self, data: dict[str, Any]) -> str:
        parts: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))
        return "\n".join(parts)

    def _parse_json_text(self, text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            raise RuntimeError("LLM returned empty content")

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise
