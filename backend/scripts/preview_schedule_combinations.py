from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from app.services.ascii_schedule import format_combinations_ascii
from app.services.course_catalog import DEFAULT_COURSE_DATA_PATH, load_course_rows
from app.services.schedule_generator import ScheduleGenerationError, generate_schedule_combinations


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview possible non-conflicting course schedules as compact lists.")
    parser.add_argument("course_numbers", nargs="+", help="Course numbers/codes, such as 'COMS W3137'.")
    parser.add_argument("--data", type=Path, default=DEFAULT_COURSE_DATA_PATH, help="Course JSON data path.")
    parser.add_argument("--limit", type=positive_int, default=3, help="Number of valid schedules to render.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = generate_schedule_combinations(
            args.course_numbers,
            load_course_rows(args.data),
            limit=args.limit,
        )
    except ScheduleGenerationError as error:
        print(f"Error: {error}")
        return 1

    print(f"Requested courses: {', '.join(args.course_numbers)}")
    if result["missing_course_numbers"]:
        print(f"Missing courses: {', '.join(result['missing_course_numbers'])}")
    print(f"Total valid combinations: {result['total_valid_combinations']}")
    print(f"Rendering first {result['returned_combinations']} combination(s).")
    print()
    print(format_combinations_ascii(result["combinations"], limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
