from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def load_course_entries(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected {path} to contain a JSON array")
    return data


def merge_entries(input_paths: Iterable[Path]) -> tuple[list[dict[str, object]], int]:
    merged_entries: list[dict[str, object]] = []
    seen_call_numbers: set[str] = set()
    duplicate_count = 0

    for input_path in input_paths:
        for entry in load_course_entries(input_path):
            call_number = entry.get("call number")
            if not isinstance(call_number, str) or not call_number:
                raise ValueError(f"Entry in {input_path} is missing a call number: {entry}")

            if call_number in seen_call_numbers:
                duplicate_count += 1
                continue

            seen_call_numbers.add(call_number)
            merged_entry = dict(entry)
            merged_entry["course_id"] = len(merged_entries) + 1
            merged_entries.append(merged_entry)

    return merged_entries, duplicate_count


def write_json(path: Path, entries: list[dict[str, object]], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries, indent=2 if pretty else None, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge clean course JSON exports and dedupe by call number.")
    parser.add_argument("inputs", nargs="+", type=Path, help="Clean course JSON arrays to merge in priority order.")
    parser.add_argument("--output", required=True, type=Path, help="Combined JSON output path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    merged_entries, duplicate_count = merge_entries(args.inputs)
    write_json(args.output, merged_entries, args.pretty)
    print(
        f"Wrote {len(merged_entries)} merged entries to {args.output}; "
        f"skipped {duplicate_count} duplicate call numbers."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
