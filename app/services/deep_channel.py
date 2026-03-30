from __future__ import annotations

import asyncio
from typing import Any

from app.domain.schemas import CriterionJudgment, PaperResult, SearchCriterion, SearchIntent, SearchRequest, SearchResponse
from app.llm import LLMClient
from app.prompts import DEEP_JUDGE_SYSTEM_PROMPT, DEEP_JUDGE_USER_PROMPT, render_prompt
from app.services.search_common import (
    assess_criteria_match,
    build_query_bundle,
    clamp_score,
    dedup_results,
    get_channel_settings,
    plan_search_intent,
    recall_results_by_source,
    resolve_criterion_supported_threshold,
    unique_preserve_order,
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


def _render_criteria_prompt(criteria: list[SearchCriterion]) -> str:
    if not criteria:
        return "- id=topic_match; required=true; description=The paper matches the user query."

    lines: list[str] = []
    for criterion in criteria:
        terms = ", ".join(criterion.terms) if criterion.terms else "-"
        query_hints = ", ".join(criterion.query_hints) if criterion.query_hints else "-"
        lines.append(
            f"- id={criterion.id}; required={str(criterion.required).lower()}; "
            f"description={criterion.description}; terms={terms}; query_hints={query_hints}"
        )
    return "\n".join(lines)


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return default


def _coerce_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _parse_llm_criterion_judgments(
    raw_criteria: object,
    criteria: list[SearchCriterion],
    channel_settings: dict[str, Any] | None = None,
) -> list[CriterionJudgment]:
    items_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(raw_criteria, list):
        for item in raw_criteria:
            if not isinstance(item, dict):
                continue
            criterion_id = str(item.get("criterion_id") or item.get("id") or "").strip()
            if criterion_id:
                items_by_id[criterion_id] = item

    parsed: list[CriterionJudgment] = []
    for criterion in criteria:
        raw_item = items_by_id.get(criterion.id, {})
        threshold = resolve_criterion_supported_threshold(criterion, channel_settings or {})
        try:
            score = clamp_score(float(raw_item.get("score", 1.0 if _coerce_bool(raw_item.get("supported")) else 0.0)))
        except (TypeError, ValueError):
            score = 0.0
        try:
            confidence = clamp_score(float(raw_item.get("confidence", score)))
        except (TypeError, ValueError):
            confidence = score

        evidence = unique_preserve_order(_coerce_string_list(raw_item.get("evidence", [])))
        parsed.append(
            CriterionJudgment(
                criterion_id=criterion.id,
                description=criterion.description,
                required=criterion.required,
                supported=_coerce_bool(raw_item.get("supported"), default=score >= threshold) and score >= threshold,
                score=score,
                confidence=confidence,
                evidence=evidence[:4],
                reason=str(raw_item.get("reason", "")).strip() or None,
            )
        )

    return parsed


def _required_judgments(judgments: list[CriterionJudgment]) -> list[CriterionJudgment]:
    required = [judgment for judgment in judgments if judgment.required]
    return required or judgments


def _required_coverage(judgments: list[CriterionJudgment]) -> float:
    required = _required_judgments(judgments)
    if not required:
        return 0.0
    supported = sum(1 for judgment in required if judgment.supported)
    return supported / len(required)


def _required_average_score(judgments: list[CriterionJudgment]) -> float:
    required = _required_judgments(judgments)
    if not required:
        return 0.0
    return sum(judgment.score or 0.0 for judgment in required) / len(required)


def _coverage_signal(judgments: list[CriterionJudgment]) -> float:
    coverage = _required_coverage(judgments)
    average = _required_average_score(judgments)
    return clamp_score(0.6 * coverage + 0.4 * average)


def _blend_llm_criterion_judgments(
    heuristic_judgments: list[CriterionJudgment],
    llm_judgments: list[CriterionJudgment],
    channel_settings: dict[str, Any],
) -> list[CriterionJudgment]:
    heuristic_by_id = {judgment.criterion_id: judgment for judgment in heuristic_judgments}
    llm_by_id = {judgment.criterion_id: judgment for judgment in llm_judgments}
    ordered_ids = unique_preserve_order([*heuristic_by_id.keys(), *llm_by_id.keys()])

    blended: list[CriterionJudgment] = []
    for criterion_id in ordered_ids:
        heuristic = heuristic_by_id.get(criterion_id)
        llm = llm_by_id.get(criterion_id)
        anchor = llm or heuristic
        if anchor is None:
            continue

        threshold = resolve_criterion_supported_threshold(
            SearchCriterion(
                id=anchor.criterion_id,
                description=anchor.description,
                required=anchor.required,
            ),
            channel_settings,
        )

        if heuristic is not None and llm is not None:
            combined_score = llm.score if llm.score is not None else heuristic.score
            combined_confidence = max(heuristic.confidence or 0.0, llm.confidence or 0.0)
            combined_evidence = unique_preserve_order([*heuristic.evidence, *llm.evidence])
            combined_reason = llm.reason or heuristic.reason
            combined_supported = bool(llm.supported) and (combined_score or 0.0) >= threshold
        else:
            selected = llm or heuristic
            combined_score = selected.score
            combined_confidence = selected.confidence
            combined_evidence = list(selected.evidence)
            combined_reason = selected.reason
            combined_supported = bool(selected.supported) and (combined_score or 0.0) >= threshold

        blended.append(
            CriterionJudgment(
                criterion_id=anchor.criterion_id,
                description=anchor.description,
                required=anchor.required,
                supported=combined_supported,
                score=combined_score,
                confidence=combined_confidence,
                evidence=combined_evidence[:6],
                reason=combined_reason,
            )
        )

    return blended


def _resolve_judge_limit(
    request: SearchRequest,
    channel_settings: dict[str, Any],
    intent: SearchIntent,
) -> int:
    base_limit = request.llm_top_n if request.llm_top_n is not None else int(channel_settings.get("llm_top_n_per_source", 4))
    required_count = max(1, len([criterion for criterion in intent.criteria if criterion.required]))
    bonus_per_extra = max(0, int(channel_settings.get("llm_top_n_per_source_complex_bonus", 2) or 2))
    dynamic_limit = base_limit + max(0, required_count - 1) * bonus_per_extra
    max_dynamic = max(base_limit, int(channel_settings.get("max_dynamic_llm_top_n_per_source", max(base_limit, 8)) or max(base_limit, 8)))
    return max(1, min(dynamic_limit, max_dynamic))


def _resolve_prefilter_floor(channel_settings: dict[str, Any], intent: SearchIntent) -> float:
    base_floor = float(channel_settings.get("llm_prefilter_min_score", 0.15))
    required_count = max(1, len([criterion for criterion in intent.criteria if criterion.required]))
    return max(0.05, base_floor - 0.03 * max(0, required_count - 1))


def _heuristic_decision(score: float, coverage: float, intent: SearchIntent, channel_settings: dict[str, Any]) -> str:
    keep_threshold = float(channel_settings.get("keep_threshold", 0.6))
    maybe_threshold = float(channel_settings.get("maybe_threshold", 0.35))
    required_count = len([criterion for criterion in intent.criteria if criterion.required])

    if intent.logic == "AND" and required_count > 1:
        if coverage >= 1.0 and score >= keep_threshold:
            return "keep"
        if coverage >= max(1.0 / required_count, 0.5) and score >= maybe_threshold:
            return "maybe"
        return "drop"

    if score >= keep_threshold:
        return "keep"
    if score >= maybe_threshold:
        return "maybe"
    return "drop"


def _apply_coverage_guard(decision: str, coverage: float, intent: SearchIntent) -> str:
    required_count = len([criterion for criterion in intent.criteria if criterion.required])
    if intent.logic != "AND" or required_count <= 1:
        return decision
    if coverage >= 1.0:
        return decision
    if coverage >= max(1.0 / required_count, 0.5):
        return "maybe" if decision == "keep" else decision
    return "drop"


async def _llm_judge(
    query: str,
    intent: SearchIntent,
    result: PaperResult,
    llm_client: LLMClient,
    channel_settings: dict[str, Any],
) -> tuple[float, str, float, str, list[CriterionJudgment]]:
    user_prompt = render_prompt(
        DEEP_JUDGE_USER_PROMPT,
        query=query,
        logic=intent.logic,
        criteria=_render_criteria_prompt(intent.criteria),
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
    criterion_judgments = _parse_llm_criterion_judgments(judgment.get("criteria"), intent.criteria, channel_settings)
    return relevance, decision, confidence, reason, criterion_judgments


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
    judge_limit = _resolve_judge_limit(request, channel_settings, intent)
    heuristic_floor = _resolve_prefilter_floor(channel_settings, intent)
    scoring_query = intent.rewritten_query or query

    candidates: list[PaperResult] = []
    dropped: list[PaperResult] = []
    for result in source_results:
        (
            heuristic_score,
            matched_fields,
            heuristic_reason,
            criterion_judgments,
            required_coverage,
            criterion_average,
        ) = assess_criteria_match(scoring_query, result, intent, channel_settings)
        result.scores["deep_heuristic"] = heuristic_score
        result.scores["deep_required_coverage"] = required_coverage
        result.scores["deep_criteria_score"] = criterion_average
        result.criteria_coverage = required_coverage
        result.criterion_judgments = criterion_judgments
        result.matched_fields = matched_fields
        result.reason = heuristic_reason
        result.score = heuristic_score
        result.confidence = clamp_score(0.35 + 0.3 * heuristic_score + 0.3 * required_coverage)

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

    candidates.sort(
        key=lambda item: (
            item.scores.get("deep_required_coverage", 0.0),
            item.scores.get("deep_heuristic", 0.0),
            item.scores.get("deep_criteria_score", 0.0),
        ),
        reverse=True,
    )

    judged_candidates = [
        result
        for result in candidates
        if result.scores.get("deep_heuristic", 0.0) >= heuristic_floor
        or (result.criteria_coverage or 0.0) > 0.0
    ][:judge_limit]
    judged_ids = {id(result) for result in judged_candidates}

    if llm_enabled and judged_candidates:
        judgments = await asyncio.gather(
            *(_llm_judge(scoring_query, intent, result, llm_client, channel_settings) for result in judged_candidates),
            return_exceptions=True,
        )
        for result, payload in zip(judged_candidates, judgments):
            heuristic_score = result.scores.get("deep_heuristic", 0.0)
            heuristic_judgments = result.criterion_judgments
            if isinstance(payload, Exception):
                coverage_signal = _coverage_signal(heuristic_judgments)
                deep_score = clamp_score(0.5 * coverage_signal + 0.5 * heuristic_score)
                result.scores["deep_llm"] = heuristic_score
                result.scores["deep"] = deep_score
                result.score = deep_score
                result.decision = _heuristic_decision(deep_score, result.criteria_coverage or 0.0, intent, channel_settings)
                result.reason = f"{result.reason}; llm judge fallback used"
                continue

            llm_relevance, decision, confidence, reason, llm_judgments = payload
            merged_judgments = _blend_llm_criterion_judgments(heuristic_judgments, llm_judgments, channel_settings)
            required_coverage = _required_coverage(merged_judgments)
            criterion_average = _required_average_score(merged_judgments)
            coverage_signal = _coverage_signal(merged_judgments)
            blended_relevance = clamp_score(heuristic_weight * heuristic_score + llm_weight * llm_relevance)
            deep_score = clamp_score(0.55 * coverage_signal + 0.45 * blended_relevance)

            result.criterion_judgments = merged_judgments
            result.criteria_coverage = required_coverage
            result.scores["deep_llm"] = llm_relevance
            result.scores["deep"] = deep_score
            result.scores["deep_required_coverage"] = required_coverage
            result.scores["deep_criteria_score"] = criterion_average
            result.score = deep_score
            result.decision = _apply_coverage_guard(decision, required_coverage, intent)
            result.confidence = max(result.confidence or 0.0, confidence)
            result.reason = (
                f"llm judge on source={result.source} => relevance={llm_relevance:.3f}, "
                f"heuristic={heuristic_score:.3f}, coverage={required_coverage:.3f}; {reason or result.reason}"
            )

    for result in candidates:
        if id(result) in judged_ids and llm_enabled:
            continue
        heuristic_score = result.scores.get("deep_heuristic", 0.0)
        coverage_signal = _coverage_signal(result.criterion_judgments)
        deep_score = clamp_score(0.5 * coverage_signal + 0.5 * heuristic_score)
        result.scores["deep"] = deep_score
        result.score = deep_score
        result.decision = _heuristic_decision(deep_score, result.criteria_coverage or 0.0, intent, channel_settings)
        if llm_enabled:
            result.reason = f"{result.reason}; not sent to llm judge for this source"
        else:
            result.reason = f"{result.reason}; llm judge disabled or unavailable"

    return candidates + dropped


async def run_deep_channel(request: SearchRequest) -> SearchResponse:
    intent = await plan_search_intent(request.query, request)
    channel_settings = get_channel_settings("deep")
    query_bundle = build_query_bundle("deep", request, intent)
    query_variants = [item.query for item in query_bundle]
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
            item.criteria_coverage or 0.0,
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
        query_bundle=query_bundle,
        results=deduped,
    )
