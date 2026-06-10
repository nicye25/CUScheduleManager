from __future__ import annotations

import re
from collections import defaultdict


MAX_COURSES = 10
TIME_RE = re.compile(r"^(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?(?P<period>am|pm)$", re.IGNORECASE)


class ScheduleGenerationError(ValueError):
    pass


def generate_schedule_combinations(
    course_numbers: list[str],
    course_rows: list[dict[str, object]],
    limit: int | None = None,
    requirements: object = None,
    target_course_count: object = None,
) -> dict[str, object]:
    normalized_requests = [normalize_course_number(course_number) for course_number in course_numbers]
    validate_requests(normalized_requests)
    parsed_requirements = parse_schedule_requirements(requirements)

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
        parsed_target_course_count = parse_target_course_count(target_course_count, len(requested_groups))
        selected_sections: list[dict[str, object]] = []

        def record_combination() -> None:
            nonlocal total_valid_combinations
            total_valid_combinations += 1
            if limit is None or len(combinations) < limit:
                combinations.append(serialize_combination(total_valid_combinations, selected_sections))

        def backtrack(group_index: int) -> None:
            if len(selected_sections) == parsed_target_course_count:
                record_combination()
                return
            if group_index == len(requested_groups):
                return

            remaining_group_count = len(requested_groups) - group_index
            if len(selected_sections) + remaining_group_count < parsed_target_course_count:
                return

            if len(selected_sections) + remaining_group_count > parsed_target_course_count:
                backtrack(group_index + 1)

            _, _, candidate_sections = requested_groups[group_index]
            for candidate_section in candidate_sections:
                if not section_satisfies_requirements(candidate_section, parsed_requirements):
                    continue
                if any(sections_conflict(candidate_section, selected_section) for selected_section in selected_sections):
                    continue
                selected_sections.append(candidate_section)
                backtrack(group_index + 1)
                selected_sections.pop()

        backtrack(0)
    else:
        parsed_target_course_count = None

    return {
        "requested_course_count": len(course_numbers),
        "matched_course_count": len(requested_groups),
        "target_course_count": parsed_target_course_count,
        "missing_course_numbers": missing_course_numbers,
        "total_valid_combinations": total_valid_combinations,
        "returned_combinations": len(combinations),
        "requirements": serialize_requirements(parsed_requirements),
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


def parse_target_course_count(value: object, matched_course_count: int) -> int:
    if value is None:
        return matched_course_count
    if isinstance(value, bool) or not isinstance(value, int):
        raise ScheduleGenerationError("target_course_count must be an integer.")
    if value < 1:
        raise ScheduleGenerationError("target_course_count must be at least 1.")
    if value > matched_course_count:
        raise ScheduleGenerationError("target_course_count cannot be greater than the number of matched courses.")
    return value


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
    minute = int(match.group("minute") or 0)
    if hour < 1 or hour > 12 or minute < 0 or minute > 59:
        return None
    period = match.group("period").lower()
    if hour == 12:
        hour = 0
    if period == "pm":
        hour += 12
    return hour * 60 + minute


def parse_schedule_requirements(requirements: object) -> dict[str, int | None]:
    if requirements is None:
        requirements = {}
    if not isinstance(requirements, dict):
        raise ScheduleGenerationError("requirements must be an object.")

    no_class_before = parse_requirement_time(requirements.get("no_class_before"), "no_class_before")
    no_class_after = parse_requirement_time(requirements.get("no_class_after"), "no_class_after")

    if no_class_before is not None and no_class_after is not None and no_class_before >= no_class_after:
        raise ScheduleGenerationError("no_class_before must be earlier than no_class_after.")

    return {
        "no_class_before": no_class_before,
        "no_class_after": no_class_after,
    }


def parse_requirement_time(value: object, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ScheduleGenerationError(f"{field_name} must be a time string like '10am' or '5:30pm'.")

    parsed_time = parse_time_to_minutes(value)
    if parsed_time is None:
        raise ScheduleGenerationError(f"Could not parse {field_name}: {value}.")
    return parsed_time


def section_satisfies_requirements(section: dict[str, object], requirements: dict[str, int | None]) -> bool:
    meetings = section_meetings(section)
    if not meetings:
        return True

    no_class_before = requirements["no_class_before"]
    no_class_after = requirements["no_class_after"]
    for _, start_time, end_time in meetings:
        if no_class_before is not None and start_time < no_class_before:
            return False
        if no_class_after is not None and end_time > no_class_after:
            return False
    return True


def serialize_requirements(requirements: dict[str, int | None]) -> dict[str, str | None]:
    return {
        "no_class_before": format_minutes(requirements["no_class_before"]),
        "no_class_after": format_minutes(requirements["no_class_after"]),
    }


def format_minutes(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    hour = minutes // 60
    minute = minutes % 60
    period = "am" if hour < 12 else "pm"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d}{period}"


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
        "prof_name": section.get("prof_name"),
        "location": section.get("location"),
        "section": section.get("section"),
        "days": section.get("days", []),
        "start_time": section.get("start_time"),
        "end_time": section.get("end_time"),
        "call_number": section.get("call number"),
    }
