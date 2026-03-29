from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.schemas import SearchRequest
from app.services.search_service import deep_search, quick_search
from scripts.output_utils import print_json_safe, write_json_output, write_text_output


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
        default=None,
        help="Override the maximum number of candidates sent to the LLM per source in deep mode.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the full JSON response instead of a compact summary.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save the response to scripts/outputs.",
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


def format_response_summary(payload: dict) -> str:
    lines = [
        f"query: {payload['query']}",
        f"rewritten_query: {payload.get('rewritten_query') or '-'}",
        f"mode: {payload['mode']}",
        f"used_sources: {', '.join(payload['used_sources']) if payload['used_sources'] else '-'}",
        f"total_results: {payload['total_results']}",
    ]
    intent = payload.get("intent") or {}
    lines.extend(
        [
            f"intent_planner: {intent.get('planner') or '-'}",
            f"must_terms: {', '.join(intent.get('must_terms') or []) or '-'}",
            f"should_terms: {', '.join(intent.get('should_terms') or []) or '-'}",
            f"exclude_terms: {', '.join(intent.get('exclude_terms') or []) or '-'}",
            "",
        ]
    )

    for idx, result in enumerate(payload["results"], start=1):
        lines.append(format_result_summary(result, idx))

    return "\n".join(lines).rstrip() + "\n"


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
    summary_text = format_response_summary(payload)
    json_path = None
    text_path = None
    if not args.no_save:
        label = f"{args.mode}_{query}"
        json_path = write_json_output(payload, prefix="search", label=label)
        text_path = write_text_output(summary_text, prefix="search_summary", label=label)

    if args.raw:
        print_json_safe(payload)
        if json_path:
            print(f"\nSaved JSON: {json_path}")
        if text_path:
            print(f"Saved summary: {text_path}")
        return

    print(summary_text, end="")
    if json_path:
        print(f"saved_json: {json_path}")
    if text_path:
        print(f"saved_summary: {text_path}")


if __name__ == "__main__":
    asyncio.run(main())
