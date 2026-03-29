from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.provider_registry import list_provider_summaries
from app.services.search_service import run_provider_probes
from scripts.output_utils import print_json_safe, write_json_output, write_text_output


async def main() -> None:
    configured = [item.model_dump() for item in list_provider_summaries()]
    live_probes = [item.model_dump() for item in await run_provider_probes()]
    payload = {
        "configured_providers": configured,
        "live_probes": live_probes,
    }
    json_path = write_json_output(payload, prefix="provider_probes", label="all")
    summary_lines = [
        "Configured providers:",
        json.dumps(configured, ensure_ascii=False, indent=2),
        "",
        "Live probe results:",
        json.dumps(live_probes, ensure_ascii=False, indent=2),
        "",
        f"saved_json: {json_path}",
    ]
    text_path = write_text_output("\n".join(summary_lines) + "\n", prefix="provider_probes_summary", label="all")
    print("Configured providers:")
    print_json_safe(configured)
    print()
    print("Live probe results:")
    print_json_safe(live_probes)
    print()
    print(f"Saved JSON: {json_path}")
    print(f"Saved summary: {text_path}")


if __name__ == "__main__":
    asyncio.run(main())
