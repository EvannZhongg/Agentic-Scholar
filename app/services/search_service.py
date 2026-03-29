from __future__ import annotations

import asyncio
import re
from typing import Any

from app.domain.schemas import PaperResult, ProbeResult, SearchRequest, SearchResponse
from app.llm import LLMClient
from app.domain.schemas import SearchIntent
from app.prompts import (
    DEEP_JUDGE_SYSTEM_PROMPT,
    DEEP_JUDGE_USER_PROMPT,
    INTENT_PLANNER_SYSTEM_PROMPT,
    INTENT_PLANNER_USER_PROMPT,
    render_prompt,
)
from app.services.provider_registry import build_clients, get_clients_for_mode


def _dedup_results(results: list[PaperResult]) -> list[PaperResult]:
    seen: set[str] = set()
    deduped: list[PaperResult] = []
    for result in results:
        key = (result.doi or "").lower().strip()
        if not key:
            key = f"{result.source}:{(result.title or '').strip().lower()}:{result.year or ''}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _normalize_text(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-zA-Z0-9]+", (text or "").lower()) if len(token) > 1]


def _heuristic_plan_intent(query: str) -> SearchIntent:
    tokens = _normalize_text(query)
    unique_tokens = []
    for token in tokens:
        if token not in unique_tokens:
            unique_tokens.append(token)

    rewritten_query = " ".join(unique_tokens[:12]).strip() or query.strip()
    return SearchIntent(
        original_query=query,
        rewritten_query=rewritten_query,
        must_terms=unique_tokens[:4],
        should_terms=unique_tokens[4:8],
        exclude_terms=[],
        filters={},
        planner="heuristic",
        reasoning="fallback heuristic planner used",
    )


async def _plan_search_intent(query: str, request: SearchRequest) -> SearchIntent:
    if not request.enable_intent_planner:
        return _heuristic_plan_intent(query)

    llm_client = LLMClient()
    if not (request.enable_llm and llm_client.is_configured()):
        return _heuristic_plan_intent(query)

    user_prompt = render_prompt(INTENT_PLANNER_USER_PROMPT, query=query)
    try:
        payload = await llm_client.complete_json(
            system_prompt=INTENT_PLANNER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        rewritten_query = str(payload.get("rewritten_query") or query).strip() or query
        must_terms = [str(item).strip() for item in payload.get("must_terms", []) if str(item).strip()]
        should_terms = [str(item).strip() for item in payload.get("should_terms", []) if str(item).strip()]
        exclude_terms = [str(item).strip() for item in payload.get("exclude_terms", []) if str(item).strip()]
        filters = payload.get("filters", {})
        if not isinstance(filters, dict):
            filters = {}
        return SearchIntent(
            original_query=query,
            rewritten_query=rewritten_query,
            must_terms=must_terms,
            should_terms=should_terms,
            exclude_terms=exclude_terms,
            filters=filters,
            planner="llm",
            reasoning=str(payload.get("reasoning", "")).strip() or None,
        )
    except Exception:
        return _heuristic_plan_intent(query)


def _heuristic_deep_assessment(query: str, result: PaperResult) -> tuple[float, list[str], str]:
    query_tokens = set(_normalize_text(query))
    title_tokens = set(_normalize_text(result.title))
    abstract_tokens = set(_normalize_text(result.abstract or ""))
    merged_tokens = title_tokens | abstract_tokens
    if not query_tokens or not merged_tokens:
        return 0.0, [], "insufficient lexical evidence"

    overlap = query_tokens & merged_tokens
    overlap_ratio = len(overlap) / max(len(query_tokens), 1)
    title_ratio = len(query_tokens & title_tokens) / max(len(query_tokens), 1)
    oa_bonus = 0.05 if result.is_oa else 0.0
    score = min(1.0, 0.65 * overlap_ratio + 0.3 * title_ratio + oa_bonus)

    matched_fields: list[str] = []
    if query_tokens & title_tokens:
        matched_fields.append("title")
    if query_tokens & abstract_tokens:
        matched_fields.append("abstract")

    if overlap:
        reason = f"heuristic overlap matched {len(overlap)} query tokens: {', '.join(sorted(list(overlap))[:6])}"
    else:
        reason = "no meaningful lexical overlap found"
    return score, matched_fields, reason


async def _llm_judge(query: str, result: PaperResult, llm_client: LLMClient) -> tuple[float, str, float, str]:
    system_prompt = DEEP_JUDGE_SYSTEM_PROMPT.strip()
    user_prompt = render_prompt(
        DEEP_JUDGE_USER_PROMPT,
        query=query,
        title=result.title,
        abstract=result.abstract or "",
        year=result.year,
        source=result.source,
        authors=", ".join(result.authors[:8]),
    )
    judgment = await llm_client.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)
    relevance = float(judgment.get("relevance", 0.0))
    confidence = float(judgment.get("confidence", 0.0))
    decision = str(judgment.get("decision", "maybe"))
    reason = str(judgment.get("reason", "")).strip()
    return relevance, decision, confidence, reason


def _decorate_quick_results(query: str, results: list[PaperResult]) -> list[PaperResult]:
    for result in results:
        score, matched_fields, reason = _heuristic_deep_assessment(query, result)
        result.score = score
        result.scores["quick"] = score
        result.matched_fields = matched_fields
        result.reason = reason
        result.decision = "keep"
        result.confidence = max(0.4, min(1.0, score + 0.15))
    return results


async def _decorate_deep_results(query: str, results: list[PaperResult], request: SearchRequest) -> list[PaperResult]:
    llm_client = LLMClient()
    llm_enabled = request.enable_llm and llm_client.is_configured()

    heuristic_ranked: list[PaperResult] = []
    for result in results:
        score, matched_fields, reason = _heuristic_deep_assessment(query, result)
        result.scores["heuristic"] = score
        result.matched_fields = matched_fields
        result.reason = reason
        result.score = score
        result.confidence = max(0.35, min(1.0, score + 0.1))
        result.decision = "keep" if score >= 0.2 else "drop"
        heuristic_ranked.append(result)

    heuristic_ranked.sort(key=lambda item: item.scores.get("heuristic", 0.0), reverse=True)

    if llm_enabled:
        for result in heuristic_ranked[: request.llm_top_n]:
            try:
                relevance, decision, confidence, reason = await _llm_judge(query, result, llm_client)
                result.scores["deep"] = relevance
                result.score = relevance
                result.decision = decision
                result.confidence = confidence
                result.reason = reason or result.reason
            except Exception:
                result.scores["deep"] = result.scores.get("heuristic", 0.0)
        for result in heuristic_ranked[request.llm_top_n :]:
            result.scores["deep"] = result.scores.get("heuristic", 0.0)
    else:
        for result in heuristic_ranked:
            heuristic_score = result.scores.get("heuristic", 0.0)
            result.scores["deep"] = heuristic_score
            result.score = heuristic_score
            result.decision = "keep" if heuristic_score >= 0.2 else "drop"
            if result.reason:
                result.reason = f"{result.reason}; llm fallback not used"

    heuristic_ranked.sort(
        key=lambda item: (
            1 if item.decision == "keep" else 0,
            item.scores.get("deep", 0.0),
            item.confidence or 0.0,
        ),
        reverse=True,
    )
    return heuristic_ranked


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
    intent = await _plan_search_intent(request.query, request)
    clients = get_clients_for_mode("quick", sources=request.sources, public_only=request.public_only)
    gathered = await asyncio.gather(
        *(client.quick_search(intent.rewritten_query, limit=request.limit_per_source) for client in clients),
        return_exceptions=True,
    )

    used_sources: list[str] = []
    results: list[PaperResult] = []
    for client, payload in zip(clients, gathered):
        if isinstance(payload, Exception):
            continue
        used_sources.append(client.name)
        results.extend(payload)

    deduped = _decorate_quick_results(request.query, _dedup_results(results))
    return SearchResponse(
        query=request.query,
        rewritten_query=intent.rewritten_query,
        mode="quick",
        used_sources=used_sources,
        total_results=len(deduped),
        intent=intent,
        results=deduped,
    )


async def deep_search(request: SearchRequest) -> SearchResponse:
    intent = await _plan_search_intent(request.query, request)
    clients = get_clients_for_mode("deep", sources=request.sources, public_only=request.public_only)
    gathered = await asyncio.gather(
        *(client.quick_search(intent.rewritten_query, limit=request.limit_per_source) for client in clients),
        return_exceptions=True,
    )

    used_sources: list[str] = []
    results: list[PaperResult] = []
    for client, payload in zip(clients, gathered):
        if isinstance(payload, Exception):
            continue
        used_sources.append(client.name)
        results.extend(payload)

    deduped = _dedup_results(results)
    deep_results = await _decorate_deep_results(request.query, deduped, request)
    return SearchResponse(
        query=request.query,
        rewritten_query=intent.rewritten_query,
        mode="deep",
        used_sources=used_sources,
        total_results=len(deep_results),
        intent=intent,
        results=deep_results,
    )
