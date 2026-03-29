from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


SearchMode = Literal["quick", "deep", "fusion"]
ProviderStatusState = Literal["ok", "error", "disabled", "skipped"]


class PaperResult(BaseModel):
    source: str
    source_id: str | None = None
    title: str
    abstract: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    is_oa: bool | None = None
    authors: list[str] = Field(default_factory=list)
    score: float | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    decision: str | None = None
    confidence: float | None = None
    reason: str | None = None
    matched_fields: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    sources: list[str] | None = None
    limit_per_source: int = Field(default=5, ge=1, le=25)
    public_only: bool = True
    llm_top_n: int | None = Field(default=None, ge=1, le=25)
    enable_llm: bool = True
    enable_intent_planner: bool = True


class SearchIntent(BaseModel):
    original_query: str
    rewritten_query: str
    must_terms: list[str] = Field(default_factory=list)
    should_terms: list[str] = Field(default_factory=list)
    exclude_terms: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    planner: str = "heuristic"
    reasoning: str | None = None


class SearchResponse(BaseModel):
    query: str
    rewritten_query: str
    mode: SearchMode
    used_sources: list[str]
    total_results: int
    intent: SearchIntent
    results: list[PaperResult]


class ProviderConfigSummary(BaseModel):
    name: str
    enabled: bool
    public_enabled: bool
    supports_quick: bool
    supports_deep: bool
    supports_fusion: bool
    has_credentials: bool


class ProbeResult(BaseModel):
    name: str
    status: ProviderStatusState
    message: str
    http_status: int | None = None
    latency_ms: int | None = None
    used_credentials: bool = False
    sample_title: str | None = None


class ProvidersStatusResponse(BaseModel):
    mode: SearchMode = "quick"
    providers: list[ProbeResult]
