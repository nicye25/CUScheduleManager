from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


DEFAULT_COURSE_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "fall_2026_all_courses_flat.json"


@lru_cache(maxsize=4)
def load_course_rows(data_path: str | Path = DEFAULT_COURSE_DATA_PATH) -> list[dict[str, object]]:
    path = Path(data_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected {path} to contain a JSON array.")

    rows: list[dict[str, object]] = []
    for row in data:
        if isinstance(row, dict):
            rows.append(row)
    return rows
