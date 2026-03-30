from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = SCRIPTS_DIR / "outputs"


def ensure_outputs_dir(output_dir: str | Path | None = None) -> Path:
    target = Path(output_dir) if output_dir else OUTPUTS_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def slugify(value: str, max_length: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower()).strip("-")
    if not slug:
        slug = "run"
    return slug[:max_length].rstrip("-") or "run"


def build_output_stem(prefix: str, label: str | None = None) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = slugify(label or "")
    return f"{prefix}_{timestamp}_{suffix}" if suffix else f"{prefix}_{timestamp}"


def write_json_output(payload: dict[str, Any], prefix: str, label: str | None = None, output_dir: str | Path | None = None) -> Path:
    directory = ensure_outputs_dir(output_dir)
    path = directory / f"{build_output_stem(prefix, label)}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_text_output(content: str, prefix: str, label: str | None = None, output_dir: str | Path | None = None) -> Path:
    directory = ensure_outputs_dir(output_dir)
    path = directory / f"{build_output_stem(prefix, label)}.txt"
    path.write_text(content, encoding="utf-8")
    return path


def print_json_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        # Some Windows terminals still use GBK; keep console output readable without affecting saved UTF-8 files.
        fallback = json.dumps(payload, ensure_ascii=True, indent=2)
        sys.stdout.write(fallback + "\n")


def print_text_safe(text: str) -> None:
    try:
        print(text, end="")
    except UnicodeEncodeError:
        fallback = (text or "").encode("ascii", errors="backslashreplace").decode("ascii")
        sys.stdout.write(fallback)
