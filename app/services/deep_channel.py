from __future__ import annotations

import asyncio
from typing import Any

from app.domain.schemas import PaperResult, SearchIntent, SearchRequest, SearchResponse
from app.llm import LLMClient
from app.prompts import DEEP_JUDGE_SYSTEM_PROMPT, DEEP_JUDGE_USER_PROMPT, render_prompt
from app.services.search_common import (
    assess_relevance,
    build_query_variants,
    clamp_score,
    dedup_results,
    get_channel_settings,
    plan_search_intent,
    recall_results_by_source,
)


def _hard_filter_reason(intent: SearchIntent, result: PaperResult) -> str | None:
    filters = intent.filters if isinstance(intent.filters, dict) else {}
    year_from = filters.get("year_from")
    year_to = filters.get("year_to")
    require_oa = filters.get("is_oa")

    if isinstance(year_from, int) and result.year is not None and result.year < year_from:
        return f"hard filter failed: year {result.year} < {year_from}"
    if isinstance(year_to, int) and result.year is not None and result.year > year_to:
        return f"hard filter failed: year {result.year} > {year_to}"
    if require_oa is True and result.is_oa is False:
        return "hard filter failed: open access required"
    return None


async def _llm_judge(query: str, result: PaperResult, llm_client: LLMClient) -> tuple[float, str, float, str]:
    user_prompt = render_prompt(
        DEEP_JUDGE_USER_PROMPT,
        query=query,
        title=result.title,
        abstract=result.abstract or "",
        year=result.year,
        source=result.source,
        authors=", ".join(result.authors[:8]),
    )
    judgment = await llm_client.complete_json(
        system_prompt=DEEP_JUDGE_SYSTEM_PROMPT.strip(),
        user_prompt=user_prompt,
    )
    relevance = clamp_score(float(judgment.get("relevance", 0.0)))
    confidence = clamp_score(float(judgment.get("confidence", 0.0)))
    decision = str(judgment.get("decision", "maybe")).strip().lower() or "maybe"
    reason = str(judgment.get("reason", "")).strip()
    if decision not in {"keep", "maybe", "drop"}:
        decision = "maybe"
    return relevance, decision, confidence, reason


def _heuristic_decision(score: float, channel_settings: dict[str, Any]) -> str:
    keep_threshold = float(channel_settings.get("keep_threshold", 0.6))
    maybe_threshold = float(channel_settings.get("maybe_threshold", 0.35))
    if score >= keep_threshold:
        return "keep"
    if score >= maybe_threshold:
        return "maybe"
    return "drop"


async def _judge_source_results(
    query: str,
    intent: SearchIntent,
    source_results: list[PaperResult],
    request: SearchRequest,
    channel_settings: dict[str, Any],
) -> list[PaperResult]:
    llm_client = LLMClient()
    llm_enabled = request.enable_llm and llm_client.is_configured()
    llm_weight = float(channel_settings.get("llm_weight", 0.7))
    heuristic_weight = float(channel_settings.get("heuristic_weight", 0.3))
    judge_limit = request.llm_top_n if request.llm_top_n is not None else int(channel_settings.get("llm_top_n_per_source", 4))
    heuristic_floor = float(channel_settings.get("llm_prefilter_min_score", 0.15))

    candidates: list[PaperResult] = []
    dropped: list[PaperResult] = []
    for result in source_results:
        heuristic_score, matched_fields, heuristic_reason = assess_relevance(query, result, intent)
        result.scores["deep_heuristic"] = heuristic_score
        result.matched_fields = matched_fields
        result.reason = heuristic_reason
        result.score = heuristic_score
        result.confidence = clamp_score(0.35 + 0.35 * heuristic_score)

        filter_reason = _hard_filter_reason(intent, result)
        if filter_reason:
            result.scores["deep"] = 0.0
            result.score = 0.0
            result.decision = "drop"
            result.confidence = 0.95
            result.reason = filter_reason
            dropped.append(result)
            continue
        candidates.append(result)

    candidates.sort(key=lambda item: item.scores.get("deep_heuristic", 0.0), reverse=True)

    judged_candidates = [
        result for result in candidates if result.scores.get("deep_heuristic", 0.0) >= heuristic_floor
    ][:judge_limit]
    judged_ids = {id(result) for result in judged_candidates}

    if llm_enabled and judged_candidates:
        judgments = await asyncio.gather(
            *(_llm_judge(query, result, llm_client) for result in judged_candidates),
            return_exceptions=True,
        )
        for result, payload in zip(judged_candidates, judgments):
            heuristic_score = result.scores.get("deep_heuristic", 0.0)
            if isinstance(payload, Exception):
                result.scores["deep_llm"] = heuristic_score
                result.scores["deep"] = heuristic_score
                result.score = heuristic_score
                result.decision = _heuristic_decision(heuristic_score, channel_settings)
                result.reason = f"{result.reason}; llm judge fallback used"
                continue

            llm_relevance, decision, confidence, reason = payload
            deep_score = clamp_score(heuristic_weight * heuristic_score + llm_weight * llm_relevance)
            result.scores["deep_llm"] = llm_relevance
            result.scores["deep"] = deep_score
            result.score = deep_score
            result.decision = decision
            result.confidence = max(result.confidence or 0.0, confidence)
            result.reason = (
                f"llm judge on source={result.source} => relevance={llm_relevance:.3f}, "
                f"heuristic={heuristic_score:.3f}; {reason or result.reason}"
            )

    for result in candidates:
        if id(result) in judged_ids and llm_enabled:
            continue
        heuristic_score = result.scores.get("deep_heuristic", 0.0)
        result.scores["deep"] = heuristic_score
        result.score = heuristic_score
        result.decision = _heuristic_decision(heuristic_score, channel_settings)
        if llm_enabled:
            result.reason = f"{result.reason}; not sent to llm judge for this source"
        else:
            result.reason = f"{result.reason}; llm judge disabled or unavailable"

    return candidates + dropped


async def run_deep_channel(request: SearchRequest) -> SearchResponse:
    intent = await plan_search_intent(request.query, request)
    channel_settings = get_channel_settings("deep")
    query_variants = build_query_variants("deep", request, intent)
    results_by_source, used_sources = await recall_results_by_source("deep", query_variants, request)

    judged_groups = await asyncio.gather(
        *(
            _judge_source_results(request.query, intent, source_results, request, channel_settings)
            for source_results in results_by_source.values()
        )
    )
    merged_results = [result for group in judged_groups for result in group]
    deduped = dedup_results(merged_results)

    decision_priority = {"keep": 2, "maybe": 1, "drop": 0}
    deduped.sort(
        key=lambda item: (
            decision_priority.get(item.decision or "drop", 0),
            item.scores.get("deep", 0.0),
            item.confidence or 0.0,
        ),
        reverse=True,
    )

    return SearchResponse(
        query=request.query,
        rewritten_query=intent.rewritten_query,
        mode="deep",
        used_sources=used_sources,
        total_results=len(deduped),
        intent=intent,
        results=deduped,
    )
