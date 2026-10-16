"""JSON loading and saving for problem instances."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from group_discount_optimization.core.model import ProblemInstance


def load_instance(path: str | Path) -> ProblemInstance:
    """Load and validate an instance from a JSON file."""
    file_path = Path(path)
    try:
        raw: dict[str, Any] = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {file_path}: {exc}") from exc
    return ProblemInstance.from_dict(raw)


def save_instance(instance: ProblemInstance, path: str | Path) -> None:
    """Save an instance as readable UTF-8 JSON."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(instance.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
