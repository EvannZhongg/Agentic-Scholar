from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.schemas import SearchRequest
from app.services.search_service import deep_search, quick_search


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local quick/deep paper search test against the backend service logic."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="User query to search. If omitted, the script will prompt for input.",
    )
    parser.add_argument(
        "--mode",
        choices=["quick", "deep"],
        default="quick",
        help="Search mode to run.",
    )
    parser.add_argument(
        "--limit-per-source",
        type=int,
        default=3,
        help="Maximum number of candidate papers to fetch from each source.",
    )
    parser.add_argument(
        "--sources",
        default=None,
        help="Comma-separated source names, for example: openalex,semanticscholar,core",
    )
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Only use providers marked as public_enabled=true in config.",
    )
    parser.add_argument(
        "--enable-llm",
        action="store_true",
        help="Enable LLM judging in deep mode if LLM_API_KEY is configured.",
    )
    parser.add_argument(
        "--disable-intent-planner",
        action="store_true",
        help="Disable the query intent planner and use direct/heuristic retrieval query handling.",
    )
    parser.add_argument(
        "--llm-top-n",
        type=int,
        default=8,
        help="Maximum number of candidates sent to the LLM in deep mode.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the full JSON response instead of a compact summary.",
    )
    return parser


def parse_sources(raw_sources: str | None) -> list[str] | None:
    if not raw_sources:
        return None
    sources = [item.strip() for item in raw_sources.split(",") if item.strip()]
    return sources or None


def format_result_summary(result: dict, index: int) -> str:
    title = result.get("title") or ""
    source = result.get("source") or ""
    year = result.get("year") or "-"
    score = result.get("score")
    decision = result.get("decision") or "-"
    confidence = result.get("confidence")
    reason = result.get("reason") or ""
    doi = result.get("doi") or "-"
    url = result.get("url") or "-"

    score_text = f"{score:.3f}" if isinstance(score, (int, float)) else "-"
    confidence_text = f"{confidence:.3f}" if isinstance(confidence, (int, float)) else "-"

    return (
        f"[{index}] {title}\n"
        f"  source: {source}\n"
        f"  year: {year}\n"
        f"  score: {score_text}\n"
        f"  decision: {decision}\n"
        f"  confidence: {confidence_text}\n"
        f"  doi: {doi}\n"
        f"  url: {url}\n"
        f"  reason: {reason}\n"
    )


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    query = args.query or input("Input query: ").strip()
    if not query:
        raise SystemExit("Query cannot be empty.")

    request = SearchRequest(
        query=query,
        sources=parse_sources(args.sources),
        limit_per_source=args.limit_per_source,
        public_only=args.public_only,
        enable_llm=args.enable_llm,
        llm_top_n=args.llm_top_n,
        enable_intent_planner=not args.disable_intent_planner,
    )

    if args.mode == "quick":
        response = await quick_search(request)
    else:
        response = await deep_search(request)

    payload = response.model_dump()

    if args.raw:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"query: {payload['query']}")
    print(f"rewritten_query: {payload.get('rewritten_query') or '-'}")
    print(f"mode: {payload['mode']}")
    print(f"used_sources: {', '.join(payload['used_sources']) if payload['used_sources'] else '-'}")
    print(f"total_results: {payload['total_results']}")
    intent = payload.get("intent") or {}
    print(f"intent_planner: {intent.get('planner') or '-'}")
    print(f"must_terms: {', '.join(intent.get('must_terms') or []) or '-'}")
    print(f"should_terms: {', '.join(intent.get('should_terms') or []) or '-'}")
    print(f"exclude_terms: {', '.join(intent.get('exclude_terms') or []) or '-'}")
    print()

    for idx, result in enumerate(payload["results"], start=1):
        print(format_result_summary(result, idx))


if __name__ == "__main__":
    asyncio.run(main())
