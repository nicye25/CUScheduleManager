from __future__ import annotations

import re
from collections import defaultdict


MAX_COURSES = 10
TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})(?P<period>am|pm)$", re.IGNORECASE)


class ScheduleGenerationError(ValueError):
    pass


def generate_schedule_combinations(
    course_numbers: list[str],
    course_rows: list[dict[str, object]],
    limit: int | None = None,
) -> dict[str, object]:
    normalized_requests = [normalize_course_number(course_number) for course_number in course_numbers]
    validate_requests(normalized_requests)

    sections_by_course_code = group_sections_by_course_code(course_rows)
    requested_groups: list[tuple[str, str, list[dict[str, object]]]] = []
    missing_course_numbers: list[str] = []

    for original_course_number, normalized_course_number in zip(course_numbers, normalized_requests):
        sections = sections_by_course_code.get(normalized_course_number, [])
        if not sections:
            missing_course_numbers.append(original_course_number)
            continue
        requested_groups.append((original_course_number, normalized_course_number, sections))

    combinations: list[dict[str, object]] = []
    total_valid_combinations = 0

    if not missing_course_numbers:
        selected_sections: list[dict[str, object]] = []

        def backtrack(group_index: int) -> None:
            nonlocal total_valid_combinations
            if group_index == len(requested_groups):
                total_valid_combinations += 1
                if limit is None or len(combinations) < limit:
                    combinations.append(serialize_combination(total_valid_combinations, selected_sections))
                return

            _, _, candidate_sections = requested_groups[group_index]
            for candidate_section in candidate_sections:
                if any(sections_conflict(candidate_section, selected_section) for selected_section in selected_sections):
                    continue
                selected_sections.append(candidate_section)
                backtrack(group_index + 1)
                selected_sections.pop()

        backtrack(0)

    return {
        "requested_course_count": len(course_numbers),
        "matched_course_count": len(requested_groups),
        "missing_course_numbers": missing_course_numbers,
        "total_valid_combinations": total_valid_combinations,
        "returned_combinations": len(combinations),
        "combinations": combinations,
    }


def validate_requests(normalized_course_numbers: list[str]) -> None:
    if not normalized_course_numbers:
        raise ScheduleGenerationError("Select at least one course.")
    if len(normalized_course_numbers) > MAX_COURSES:
        raise ScheduleGenerationError(f"A maximum of {MAX_COURSES} courses can be selected.")

    duplicate_course_numbers = sorted(
        course_number for course_number in set(normalized_course_numbers) if normalized_course_numbers.count(course_number) > 1
    )
    if duplicate_course_numbers:
        raise ScheduleGenerationError(f"Duplicate course numbers are not allowed: {', '.join(duplicate_course_numbers)}.")


def normalize_course_number(course_number: str) -> str:
    return " ".join(course_number.upper().split())


def group_sections_by_course_code(course_rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    sections_by_course_code: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in course_rows:
        course_code = row.get("course_code")
        if isinstance(course_code, str) and course_code.strip():
            sections_by_course_code[normalize_course_number(course_code)].append(row)
    return dict(sections_by_course_code)


def sections_conflict(first_section: dict[str, object], second_section: dict[str, object]) -> bool:
    for first_meeting in section_meetings(first_section):
        first_days, first_start, first_end = first_meeting
        for second_meeting in section_meetings(second_section):
            second_days, second_start, second_end = second_meeting
            if first_days.isdisjoint(second_days):
                continue
            if first_start < second_end and second_start < first_end:
                return True
    return False


def section_meetings(section: dict[str, object]) -> list[tuple[set[str], int, int]]:
    days = section.get("days")
    start_time = section.get("start_time")
    end_time = section.get("end_time")
    if not isinstance(days, list) or not isinstance(start_time, str) or not isinstance(end_time, str):
        return []

    parsed_start_time = parse_time_to_minutes(start_time)
    parsed_end_time = parse_time_to_minutes(end_time)
    if parsed_start_time is None or parsed_end_time is None or parsed_start_time >= parsed_end_time:
        return []

    day_values = {normalized_day for day in days if isinstance(day, str) and (normalized_day := normalize_meeting_day(day))}
    if not day_values:
        return []

    return [(day_values, parsed_start_time, parsed_end_time)]


def parse_time_to_minutes(time_text: str) -> int | None:
    match = TIME_RE.match(time_text.replace(" ", "").lower())
    if match is None:
        return None

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    period = match.group("period").lower()
    if hour == 12:
        hour = 0
    if period == "pm":
        hour += 12
    return hour * 60 + minute


def normalize_meeting_day(day: str) -> str | None:
    normalized_day = day.strip()
    if not normalized_day:
        return None
    if normalized_day.upper() == "R":
        return "Th"
    if normalized_day.lower() == "th":
        return "Th"
    return normalized_day


def serialize_combination(combination_id: int, sections: list[dict[str, object]]) -> dict[str, object]:
    return {
        "combination_id": combination_id,
        "sections": [serialize_section(section) for section in sections],
    }


def serialize_section(section: dict[str, object]) -> dict[str, object]:
    return {
        "course_code": section.get("course_code"),
        "section": section.get("section"),
        "days": section.get("days", []),
        "start_time": section.get("start_time"),
        "end_time": section.get("end_time"),
        "call_number": section.get("call number"),
    }
