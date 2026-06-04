from __future__ import annotations


def format_combinations_ascii(combinations: list[dict[str, object]], limit: int | None = None) -> str:
    visible_combinations = combinations if limit is None else combinations[:limit]
    if not visible_combinations:
        return "No valid schedule combinations."

    return "\n\n".join(format_schedule_ascii(combination) for combination in visible_combinations)


def format_schedule_ascii(combination: dict[str, object]) -> str:
    title = f"Combination {combination.get('combination_id')}"
    sections = combination.get("sections", [])
    if not isinstance(sections, list):
        return f"{title}\nNo sections to display."

    lines = [title]
    for section in sections:
        if isinstance(section, dict):
            lines.append(format_section_line(section))
    return "\n".join(lines)


def format_section_line(section: dict[str, object]) -> str:
    course_code = section.get("course_code")
    section_number = section.get("section")
    days = section.get("days")
    start_time = section.get("start_time")
    end_time = section.get("end_time")
    call_number = section.get("call_number")

    label = " ".join(str(value) for value in [course_code, section_number] if value) or "Unknown section"
    day_text = "/".join(str(day) for day in days) if isinstance(days, list) and days else "TBA"
    time_text = f"{start_time}-{end_time}" if start_time and end_time else "TBA"
    call_text = f" call {call_number}" if call_number else ""
    return f"- {label}: {day_text} {time_text}{call_text}"
