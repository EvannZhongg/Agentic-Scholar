from __future__ import annotations

import asyncio
import math
import re
from datetime import datetime
from typing import Any

from app.domain.schemas import PaperResult, SearchIntent, SearchRequest
from app.llm import LLMClient
from app.prompts import INTENT_PLANNER_SYSTEM_PROMPT, INTENT_PLANNER_USER_PROMPT, render_prompt
from app.services.provider_registry import get_clients_for_mode
from config import get_settings


def get_retrieval_settings() -> dict[str, Any]:
    settings = get_settings().get("retrieval", {})
    return settings if isinstance(settings, dict) else {}


def get_channel_settings(channel: str) -> dict[str, Any]:
    retrieval_settings = get_retrieval_settings()
    channel_settings = retrieval_settings.get(channel, {})
    return channel_settings if isinstance(channel_settings, dict) else {}


def normalize_text(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-zA-Z0-9]+", (text or "").lower()) if len(token) > 1]


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None

    normalized = doi.strip().lower()
    normalized = re.sub(r"^https?://(dx\.)?doi\.org/", "", normalized)
    normalized = re.sub(r"^doi:\s*", "", normalized)
    normalized = normalized.strip().strip("/")
    return normalized or None


def build_document_text(result: PaperResult) -> str:
    parts = [
        result.title or "",
        result.abstract or "",
        " ".join(result.authors[:8]),
        result.doi or "",
    ]
    return "\n".join(part.strip() for part in parts if part and part.strip())


def current_year() -> int:
    return datetime.now().year


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def compute_recency_score(year: int | None, window_years: int = 10) -> float:
    if not year:
        return 0.0

    max_year = current_year()
    min_year = max_year - max(1, window_years)
    if year <= min_year:
        return 0.0
    if year >= max_year:
        return 1.0
    return clamp_score((year - min_year) / max(max_year - min_year, 1))


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return clamp_score((numerator / (left_norm * right_norm) + 1.0) / 2.0)


def heuristic_plan_intent(query: str) -> SearchIntent:
    tokens = normalize_text(query)
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


async def plan_search_intent(query: str, request: SearchRequest) -> SearchIntent:
    if not request.enable_intent_planner:
        return heuristic_plan_intent(query)

    llm_client = LLMClient()
    if not (request.enable_llm and llm_client.is_configured()):
        return heuristic_plan_intent(query)

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
        return heuristic_plan_intent(query)


def build_query_variants(mode: str, request: SearchRequest, intent: SearchIntent) -> list[str]:
    channel_settings = get_channel_settings(mode)
    max_variants = max(1, int(channel_settings.get("max_query_variants", 1) or 1))
    queries: list[str] = []

    if mode == "quick":
        for candidate in [intent.rewritten_query, request.query]:
            normalized = (candidate or "").strip()
            if normalized and normalized not in queries:
                queries.append(normalized)
            if len(queries) >= max_variants:
                break
        return queries

    must_terms_query = " ".join(intent.must_terms[:6]).strip()
    deep_candidates = [request.query, intent.rewritten_query]
    if channel_settings.get("include_must_terms_query", True) and must_terms_query:
        deep_candidates.append(must_terms_query)

    for candidate in deep_candidates:
        normalized = (candidate or "").strip()
        if normalized and normalized not in queries:
            queries.append(normalized)
        if len(queries) >= max_variants:
            break
    return queries


def _result_identity_key(result: PaperResult) -> str:
    doi = normalize_doi(result.doi)
    if doi:
        return f"doi:{doi}"
    title = re.sub(r"\s+", " ", (result.title or "").strip().lower())
    first_author = (result.authors[0] if result.authors else "").strip().lower()
    return f"title:{title}|year:{result.year or ''}|author:{first_author}"


def merge_paper_results(existing: PaperResult, incoming: PaperResult) -> PaperResult:
    existing_scores = {**existing.scores}
    for key, value in incoming.scores.items():
        existing_scores[key] = max(existing_scores.get(key, value), value)

    merged = existing.model_copy(deep=True)
    merged.scores = existing_scores
    merged.matched_fields = sorted(set(existing.matched_fields) | set(incoming.matched_fields))
    if len(incoming.authors) > len(existing.authors):
        merged.authors = incoming.authors
    merged.abstract = incoming.abstract if len(incoming.abstract or "") > len(existing.abstract or "") else existing.abstract
    merged.title = incoming.title if len(incoming.title or "") > len(existing.title or "") else existing.title
    merged.doi = normalize_doi(existing.doi) or normalize_doi(incoming.doi)
    merged.url = existing.url or incoming.url
    merged.pdf_url = existing.pdf_url or incoming.pdf_url
    merged.is_oa = existing.is_oa or incoming.is_oa
    merged.year = existing.year or incoming.year

    existing_score = existing.score or 0.0
    incoming_score = incoming.score or 0.0
    if incoming_score >= existing_score:
        merged.score = incoming.score
        merged.decision = incoming.decision or existing.decision
        merged.confidence = incoming.confidence if incoming.confidence is not None else existing.confidence
        merged.reason = incoming.reason or existing.reason
        merged.source = incoming.source or existing.source
        merged.source_id = incoming.source_id or existing.source_id
        merged.raw = incoming.raw or existing.raw
    else:
        merged.score = existing.score
        merged.decision = existing.decision or incoming.decision
        merged.confidence = existing.confidence if existing.confidence is not None else incoming.confidence
        merged.reason = existing.reason or incoming.reason
        merged.raw = existing.raw or incoming.raw

    return merged


def dedup_results(results: list[PaperResult]) -> list[PaperResult]:
    deduped_by_key: dict[str, PaperResult] = {}
    order: list[str] = []

    for result in results:
        key = _result_identity_key(result)
        if key not in deduped_by_key:
            deduped_by_key[key] = result.model_copy(deep=True)
            order.append(key)
            continue
        deduped_by_key[key] = merge_paper_results(deduped_by_key[key], result)

    return [deduped_by_key[key] for key in order]


def assess_relevance(query: str, result: PaperResult, intent: SearchIntent | None = None) -> tuple[float, list[str], str]:
    query_tokens = set(normalize_text(query))
    title_tokens = set(normalize_text(result.title))
    abstract_tokens = set(normalize_text(result.abstract or ""))
    merged_tokens = title_tokens | abstract_tokens
    if not query_tokens or not merged_tokens:
        return 0.0, [], "insufficient lexical evidence"

    overlap = query_tokens & merged_tokens
    overlap_ratio = len(overlap) / max(len(query_tokens), 1)
    title_ratio = len(query_tokens & title_tokens) / max(len(query_tokens), 1)

    must_terms = intent.must_terms if intent else []
    should_terms = intent.should_terms if intent else []
    must_hits = 0
    should_hits = 0

    for term in must_terms:
        term_tokens = set(normalize_text(term))
        if term_tokens and term_tokens <= merged_tokens:
            must_hits += 1
    for term in should_terms:
        term_tokens = set(normalize_text(term))
        if term_tokens and term_tokens <= merged_tokens:
            should_hits += 1

    must_ratio = must_hits / max(len(must_terms), 1) if must_terms else 0.0
    should_ratio = should_hits / max(len(should_terms), 1) if should_terms else 0.0
    oa_bonus = 0.05 if result.is_oa else 0.0

    score = clamp_score(0.45 * overlap_ratio + 0.25 * title_ratio + 0.2 * must_ratio + 0.05 * should_ratio + oa_bonus)

    matched_fields: list[str] = []
    if query_tokens & title_tokens:
        matched_fields.append("title")
    if query_tokens & abstract_tokens:
        matched_fields.append("abstract")

    reason_parts: list[str] = []
    if overlap:
        reason_parts.append(f"matched query tokens: {', '.join(sorted(list(overlap))[:6])}")
    if must_hits:
        reason_parts.append(f"matched {must_hits}/{len(must_terms)} must terms")
    if should_hits:
        reason_parts.append(f"matched {should_hits}/{len(should_terms)} should terms")
    if result.is_oa:
        reason_parts.append("open-access bonus applied")

    if not reason_parts:
        reason_parts.append("no meaningful lexical overlap found")

    return score, matched_fields, "; ".join(reason_parts)


async def recall_results_by_source(
    mode: str,
    queries: list[str],
    request: SearchRequest,
) -> tuple[dict[str, list[PaperResult]], list[str]]:
    clients = get_clients_for_mode(mode, sources=request.sources, public_only=request.public_only)
    gathered = await asyncio.gather(
        *(
            asyncio.gather(
                *(client.quick_search(query, limit=request.limit_per_source) for query in queries),
                return_exceptions=True,
            )
            for client in clients
        ),
        return_exceptions=True,
    )

    results_by_source: dict[str, list[PaperResult]] = {}
    used_sources: list[str] = []

    for client, client_payload in zip(clients, gathered):
        source_results: list[PaperResult] = []
        if isinstance(client_payload, Exception):
            continue

        for payload in client_payload:
            if isinstance(payload, Exception):
                continue
            source_results.extend(payload)

        if source_results:
            used_sources.append(client.name)
            results_by_source[client.name] = dedup_results(source_results)

    return results_by_source, used_sources
