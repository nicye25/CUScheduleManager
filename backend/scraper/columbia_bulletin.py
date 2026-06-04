from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup, Tag


DEFAULT_SEED_URL = "https://bulletin.columbia.edu/columbia-college/departments-instruction/"
DEFAULT_USER_AGENT = "SchedulePlannerCourseScraper/0.1"

SPACE_RE = re.compile(r"\s+")
COURSE_CODE_RE = re.compile(
    r"^(?P<subject>[A-Z]{2,5})\s+(?P<catalog_number>[A-Z]{1,4}\d{4}[A-Z]?)\s+(?P<title>.+)$"
)
CREDIT_RE = re.compile(r"(?P<min>\d+(?:\.\d+)?)(?:\s*-\s*(?P<max>\d+(?:\.\d+)?))?")
MEETING_RE = re.compile(
    r"^(?P<days>(?:Th|M|T|W|R|F|S|U)(?:\s*(?:Th|M|T|W|R|F|S|U))*)\s+"
    r"(?P<start>\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))\s*-\s*"
    r"(?P<end>\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))$"
)
ENROLLMENT_RE = re.compile(r"^(?P<enrolled>\d+)\s*/\s*(?P<capacity>\d+)$")
DAY_TOKEN_RE = re.compile(r"Th|M|T|W|R|F|S|U", re.IGNORECASE)


@dataclass(frozen=True)
class Department:
    name: str
    url: str
    slug: str


@dataclass(frozen=True)
class Meeting:
    raw: str
    days: list[str]
    start_time: str | None
    end_time: str | None
    location: str | None


@dataclass(frozen=True)
class CourseSection:
    term: str
    scheduled_course_code: str | None
    course_number: str
    section: str | None
    call_number: str | None
    times_location: str | None
    instructor: str | None
    points: str | None
    enrollment: str | None
    enrolled: int | None
    capacity: int | None
    meetings: list[Meeting]


@dataclass(frozen=True)
class Course:
    department: str
    department_slug: str
    department_url: str
    source_url: str
    code: str
    subject: str
    catalog_number: str
    title: str
    credits: str | None
    min_credits: float | None
    max_credits: float | None
    description: str | None
    prerequisites: str | None
    corequisites: str | None
    sections: list[CourseSection]


class ColumbiaBulletinScraper:
    def __init__(
        self,
        seed_url: str = DEFAULT_SEED_URL,
        delay_seconds: float = 0.25,
        timeout_seconds: float = 30,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.seed_url = ensure_trailing_slash(seed_url)
        self.department_prefix = self.seed_url
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Connection": "close"})

    def fetch_department_links(self) -> list[Department]:
        soup = self.fetch_soup(self.seed_url)
        container = soup.select_one("#textcontainer") or soup
        departments: list[Department] = []
        seen_urls: set[str] = set()

        for anchor in container.select("a[href]"):
            raw_href = anchor.get("href")
            if not raw_href:
                continue

            absolute_url, fragment = urldefrag(urljoin(self.seed_url, raw_href))
            absolute_url = ensure_trailing_slash(absolute_url)
            if fragment or not absolute_url.startswith(self.department_prefix):
                continue
            if absolute_url == self.seed_url or "/search/" in absolute_url:
                continue
            if absolute_url in seen_urls:
                continue

            name = clean_text(anchor.get_text(" ", strip=True))
            if not name:
                continue

            departments.append(Department(name=name, url=absolute_url, slug=slug_from_url(absolute_url)))
            seen_urls.add(absolute_url)

        return departments

    def scrape(
        self,
        department_filters: Iterable[str] | None = None,
        max_departments: int | None = None,
    ) -> tuple[list[Department], list[Course]]:
        departments = filter_departments(self.fetch_department_links(), department_filters)
        if max_departments is not None:
            departments = departments[:max_departments]

        courses: list[Course] = []
        for index, department in enumerate(departments):
            if index > 0 and self.delay_seconds > 0:
                time.sleep(self.delay_seconds)
            print(f"Scraping {department.name} ({department.url})", file=sys.stderr)
            courses.extend(self.scrape_department(department))

        return departments, dedupe_courses(courses)

    def scrape_department(self, department: Department) -> list[Course]:
        soup = self.fetch_soup(department.url)
        container = soup.select_one("#coursestextcontainer") or soup.select_one("#sc_sccourseblock") or soup
        courses: list[Course] = []

        for course_block in container.select("div.courseblock"):
            parsed_course = parse_course_block(course_block, department)
            if parsed_course is not None:
                courses.append(parsed_course)

        return courses

    def fetch_soup(self, url: str) -> BeautifulSoup:
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout_seconds)
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")
            except requests.RequestException as error:
                if attempt >= self.max_retries:
                    raise

                wait_seconds = self.retry_delay_seconds * (2**attempt)
                print(
                    f"Request failed for {url}: {error}. Retrying in {wait_seconds:.1f}s.",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)

        raise RuntimeError(f"Unable to fetch {url}")


def parse_course_block(course_block: Tag, department: Department) -> Course | None:
    title_node = course_block.select_one("p.courseblocktitle")
    if title_node is None:
        return None

    parsed_title = parse_title_node(title_node)
    if parsed_title is None:
        return None

    subject, catalog_number, title, credits, min_credits, max_credits = parsed_title
    code = f"{subject} {catalog_number}"

    description_parts: list[str] = []
    for paragraph in course_block.find_all("p", recursive=False):
        classes = set(paragraph.get("class", []))
        if "courseblocktitle" in classes:
            continue
        text = clean_text(paragraph.get_text(" ", strip=True))
        if text:
            description_parts.append(text)

    return Course(
        department=department.name,
        department_slug=department.slug,
        department_url=department.url,
        source_url=department.url,
        code=code,
        subject=subject,
        catalog_number=catalog_number,
        title=title,
        credits=credits,
        min_credits=min_credits,
        max_credits=max_credits,
        description="\n\n".join(description_parts) if description_parts else None,
        prerequisites=first_class_text(course_block, "prereq"),
        corequisites=first_class_text(course_block, "coreq"),
        sections=parse_sections(course_block),
    )


def parse_title_node(title_node: Tag) -> tuple[str, str, str, str | None, float | None, float | None] | None:
    first_strong = title_node.find("strong")
    if first_strong is None:
        return None

    code_and_title = clean_text(first_strong.get_text(" ", strip=True)).rstrip(".")
    match = COURSE_CODE_RE.match(code_and_title)
    if match is None:
        return None

    credits_node = title_node.find("em")
    credits = clean_text(credits_node.get_text(" ", strip=True)).rstrip(".") if credits_node else None
    min_credits, max_credits = parse_credits(credits)

    return (
        match.group("subject"),
        match.group("catalog_number"),
        clean_text(match.group("title")).rstrip("."),
        credits,
        min_credits,
        max_credits,
    )


def parse_sections(course_block: Tag) -> list[CourseSection]:
    sections: list[CourseSection] = []

    for schedule_table in course_block.select("table.scheduletbl"):
        current_term: str | None = None
        current_scheduled_course_code: str | None = None

        for row in schedule_table.select("tr"):
            header = row.select_one(".desc_sched_header")
            if header is not None:
                current_term, current_scheduled_course_code = parse_term_header(header)
                continue

            if row.find("th") is not None or current_term is None:
                continue

            cells = row.find_all("td", recursive=False)
            if len(cells) < 6:
                continue

            raw_section_call = clean_text(cells[1].get_text(" ", strip=True))
            section, call_number = parse_section_call(raw_section_call)
            times_location_lines = clean_lines(cells[2])
            enrollment = clean_text(cells[5].get_text(" ", strip=True)) or None
            enrolled, capacity = parse_enrollment(enrollment)

            sections.append(
                CourseSection(
                    term=current_term,
                    scheduled_course_code=current_scheduled_course_code,
                    course_number=clean_text(cells[0].get_text(" ", strip=True)),
                    section=section,
                    call_number=call_number,
                    times_location=" | ".join(times_location_lines) if times_location_lines else None,
                    instructor=clean_text(cells[3].get_text(" ", strip=True)) or None,
                    points=clean_text(cells[4].get_text(" ", strip=True)) or None,
                    enrollment=enrollment,
                    enrolled=enrolled,
                    capacity=capacity,
                    meetings=parse_meetings(times_location_lines),
                )
            )

    return sections


def parse_term_header(header: Tag) -> tuple[str | None, str | None]:
    header_text = clean_text(header.get_text(" ", strip=True))
    if not header_text:
        return None, None

    term, separator, scheduled_course_code = header_text.partition(":")
    return clean_text(term), clean_text(scheduled_course_code) if separator else None


def parse_meetings(times_location_lines: list[str]) -> list[Meeting]:
    meeting_matches: list[tuple[str, re.Match[str]]] = []
    location_parts: list[str] = []

    for line in times_location_lines:
        match = MEETING_RE.match(line)
        if match is not None:
            meeting_matches.append((line, match))
        elif line:
            location_parts.append(line)

    location = " ".join(location_parts) or None
    return [
        Meeting(
            raw=line,
            days=parse_meeting_days(match.group("days")),
            start_time=normalize_time(match.group("start")),
            end_time=normalize_time(match.group("end")),
            location=location,
        )
        for line, match in meeting_matches
    ]


def parse_section_call(raw_section_call: str) -> tuple[str | None, str | None]:
    if not raw_section_call:
        return None, None
    section, separator, call_number = raw_section_call.partition("/")
    if not separator:
        return clean_text(section) or None, None
    return clean_text(section) or None, clean_text(call_number) or None


def parse_credits(credits: str | None) -> tuple[float | None, float | None]:
    if credits is None:
        return None, None

    match = CREDIT_RE.search(credits)
    if match is None:
        return None, None

    min_credits = float(match.group("min"))
    max_credits = float(match.group("max")) if match.group("max") else min_credits
    return min_credits, max_credits


def parse_enrollment(enrollment: str | None) -> tuple[int | None, int | None]:
    if not enrollment:
        return None, None
    match = ENROLLMENT_RE.match(enrollment)
    if match is None:
        return None, None
    return int(match.group("enrolled")), int(match.group("capacity"))


def first_class_text(course_block: Tag, class_name: str) -> str | None:
    node = course_block.select_one(f".{class_name}")
    if node is None:
        return None
    return clean_text(node.get_text(" ", strip=True)) or None


def clean_text(text: str | None) -> str:
    if text is None:
        return ""
    return SPACE_RE.sub(" ", text.replace("\xa0", " ")).strip()


def clean_lines(node: Tag) -> list[str]:
    return [line for line in (clean_text(piece) for piece in node.stripped_strings) if line]


def normalize_time(time_text: str) -> str:
    return clean_text(time_text).replace(" ", "").lower()


def parse_meeting_days(days_text: str) -> list[str]:
    return [day_token.title() for day_token in DAY_TOKEN_RE.findall(clean_text(days_text).replace(" ", ""))]


def ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def slug_from_url(url: str) -> str:
    return ensure_trailing_slash(urldefrag(url)[0]).rstrip("/").split("/")[-1]


def filter_departments(departments: list[Department], filters: Iterable[str] | None) -> list[Department]:
    filter_values = [clean_text(value).lower() for value in filters or [] if clean_text(value)]
    if not filter_values:
        return departments

    return [
        department
        for department in departments
        if any(filter_value in f"{department.name} {department.slug} {department.url}".lower() for filter_value in filter_values)
    ]


def dedupe_courses(courses: list[Course]) -> list[Course]:
    seen: set[tuple[str, str, str]] = set()
    unique_courses: list[Course] = []

    for course in courses:
        key = (course.department_slug, course.code, course.title)
        if key in seen:
            continue
        seen.add(key)
        unique_courses.append(course)

    return unique_courses


def build_payload(seed_url: str, departments: list[Department], courses: list[Course]) -> dict[str, object]:
    return {
        "source": seed_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "department_count": len(departments),
        "course_count": len(courses),
        "section_count": sum(len(course.sections) for course in courses),
        "departments": [asdict(department) for department in departments],
        "courses": [asdict(course) for course in courses],
    }


def build_flat_section_payload(
    seed_url: str,
    departments: list[Department],
    courses: list[Course],
    term: str | None,
) -> dict[str, object]:
    course_entries = flatten_courses_by_section(courses, term)
    source_section_count = count_matching_sections(courses, term)

    return {
        "source": seed_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "term": term,
        "department_count": len(departments),
        "source_section_count": source_section_count,
        "duplicate_source_section_count": source_section_count - len(course_entries),
        "unique_catalog_course_count": len(unique_catalog_course_keys(course_entries)),
        "course_entry_count": len(course_entries),
        "courses": course_entries,
    }


def flatten_courses_by_section(courses: list[Course], term: str | None) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    entries_by_call_number: dict[tuple[str, str], dict[str, object]] = {}

    for course in courses:
        for section in course.sections:
            if term is not None and section.term != term:
                continue

            if section.call_number is not None:
                call_number_key = (section.term, section.call_number)
                existing_entry = entries_by_call_number.get(call_number_key)
                if existing_entry is not None:
                    add_catalog_course_ref(existing_entry, course)
                    continue

            entry = build_flat_section_entry(course, section, len(entries))
            entries.append(entry)
            if section.call_number is not None:
                entries_by_call_number[(section.term, section.call_number)] = entry

    return entries


def build_flat_section_entry(course: Course, section: CourseSection, entry_index: int) -> dict[str, object]:
    return {
        "entry_index": entry_index,
        "entry_id": build_section_entry_id(course, section),
        "term": section.term,
        "department": course.department,
        "department_slug": course.department_slug,
        "department_url": course.department_url,
        "source_url": course.source_url,
        "catalog_course_key": build_catalog_course_key(course),
        "catalog_course_refs": [build_catalog_course_ref(course)],
        "code": course.code,
        "subject": course.subject,
        "catalog_number": course.catalog_number,
        "title": course.title,
        "credits": course.credits,
        "min_credits": course.min_credits,
        "max_credits": course.max_credits,
        "description": course.description,
        "prerequisites": course.prerequisites,
        "corequisites": course.corequisites,
        "scheduled_course_code": section.scheduled_course_code,
        "course_number": section.course_number,
        "section": section.section,
        "call_number": section.call_number,
        "times_location": section.times_location,
        "instructor": section.instructor,
        "points": section.points,
        "enrollment": section.enrollment,
        "enrolled": section.enrolled,
        "capacity": section.capacity,
        "meetings": [asdict(meeting) for meeting in section.meetings],
    }


def count_matching_sections(courses: list[Course], term: str | None) -> int:
    return sum(
        1
        for course in courses
        for section in course.sections
        if term is None or section.term == term
    )


def unique_catalog_course_keys(entries: list[dict[str, object]]) -> set[str]:
    catalog_course_keys: set[str] = set()

    for entry in entries:
        catalog_course_refs = entry.get("catalog_course_refs")
        if not isinstance(catalog_course_refs, list):
            continue
        for catalog_course_ref in catalog_course_refs:
            if isinstance(catalog_course_ref, dict) and isinstance(catalog_course_ref.get("catalog_course_key"), str):
                catalog_course_keys.add(catalog_course_ref["catalog_course_key"])

    return catalog_course_keys


def add_catalog_course_ref(entry: dict[str, object], course: Course) -> None:
    catalog_course_refs = entry.get("catalog_course_refs")
    if not isinstance(catalog_course_refs, list):
        return

    catalog_course_key = build_catalog_course_key(course)
    if any(
        isinstance(catalog_course_ref, dict) and catalog_course_ref.get("catalog_course_key") == catalog_course_key
        for catalog_course_ref in catalog_course_refs
    ):
        return

    catalog_course_refs.append(build_catalog_course_ref(course))


def build_catalog_course_ref(course: Course) -> dict[str, str | None]:
    return {
        "catalog_course_key": build_catalog_course_key(course),
        "code": course.code,
        "title": course.title,
        "department": course.department,
        "department_slug": course.department_slug,
        "department_url": course.department_url,
    }


def build_catalog_course_key(course: Course) -> str:
    return f"{course.department_slug}:{course.code}"


def build_section_entry_id(course: Course, section: CourseSection) -> str:
    return ":".join(
        part
        for part in [section.term, course.code, section.section, section.call_number]
        if part
    )


def build_clean_flat_section_entries(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    return [build_clean_flat_section_entry(entry, course_id) for course_id, entry in enumerate(entries, start=1)]


def build_clean_flat_section_entry(entry: dict[str, object], course_id: int) -> dict[str, object]:
    clean_entry: dict[str, object] = {
        "course_id": course_id,
        "course_code": entry.get("code"),
        "name": entry.get("title"),
        "section": entry.get("section"),
        "credit_hrs": clean_credit_hours(entry),
    }

    meeting_fields = clean_meeting_fields(entry)
    if meeting_fields is not None:
        clean_entry.update(meeting_fields)

    clean_entry.update(
        {
        "location": clean_locations(entry),
        "prof_name": entry.get("instructor"),
        "department": entry.get("department"),
        "call number": entry.get("call_number"),
        }
    )
    return clean_entry


def clean_credit_hours(entry: dict[str, object]) -> float | str | None:
    points = entry.get("points")
    if isinstance(points, str) and points.strip():
        parsed_points = parse_numeric_text(points)
        return parsed_points if parsed_points is not None else clean_text(points)

    min_credits = entry.get("min_credits")
    max_credits = entry.get("max_credits")
    if isinstance(min_credits, int | float) and isinstance(max_credits, int | float):
        if min_credits == max_credits:
            return float(min_credits)
        return f"{min_credits:g}-{max_credits:g}"

    return None


def clean_meeting_fields(entry: dict[str, object]) -> dict[str, object] | None:
    meetings = clean_meeting_records(entry)
    if not meetings:
        return None

    if len(meetings) == 1:
        meeting = meetings[0]
        return {
            "days": meeting["days"],
            "start_time": meeting["start_time"],
            "end_time": meeting["end_time"],
        }

    start_times = [meeting["start_time"] for meeting in meetings]
    end_times = [meeting["end_time"] for meeting in meetings]
    same_time_range = len(set(start_times)) == 1 and len(set(end_times)) == 1
    if same_time_range:
        days: list[str] = []
        for meeting in meetings:
            for day in meeting["days"]:
                append_unique(days, day)

        return {
            "days": days,
            "start_time": start_times[0],
            "end_time": end_times[0],
        }

    return {
        "days": [meeting["days"] for meeting in meetings],
        "start_time": start_times,
        "end_time": end_times,
    }


def clean_meeting_records(entry: dict[str, object]) -> list[dict[str, object]]:
    meetings = entry.get("meetings")
    clean_meetings: list[dict[str, object]] = []

    if isinstance(meetings, list):
        for meeting in meetings:
            if not isinstance(meeting, dict):
                continue
            days = meeting.get("days")
            start_time = meeting.get("start_time")
            end_time = meeting.get("end_time")
            if isinstance(days, list) and isinstance(start_time, str) and isinstance(end_time, str):
                clean_meetings.append(
                    {
                        "days": [str(day) for day in days],
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                )

    if clean_meetings:
        return clean_meetings

    times_location = entry.get("times_location")
    if isinstance(times_location, str):
        for time_part in split_times_location(times_location):
            match = MEETING_RE.match(time_part)
            if match is None:
                continue
            clean_meetings.append(
                {
                    "days": parse_meeting_days(match.group("days")),
                    "start_time": normalize_time(match.group("start")),
                    "end_time": normalize_time(match.group("end")),
                }
            )

    return clean_meetings


def clean_locations(entry: dict[str, object]) -> str | None:
    locations: list[str] = []
    meetings = entry.get("meetings")
    if isinstance(meetings, list):
        for meeting in meetings:
            if isinstance(meeting, dict) and isinstance(meeting.get("location"), str):
                append_unique(locations, meeting["location"])

    if locations:
        return "; ".join(locations)

    times_location = entry.get("times_location")
    if isinstance(times_location, str):
        location_parts = [part for part in split_times_location(times_location) if not MEETING_RE.match(part)]
        return "; ".join(location_parts) if location_parts else None

    return None


def split_times_location(times_location: str) -> list[str]:
    return [clean_text(part) for part in times_location.split("|") if clean_text(part)]


def append_unique(values: list[str], value: str) -> None:
    cleaned_value = clean_text(value)
    if cleaned_value and cleaned_value not in values:
        values.append(cleaned_value)


def parse_numeric_text(value: str) -> float | None:
    cleaned_value = clean_text(value)
    try:
        return float(cleaned_value)
    except ValueError:
        return None


def write_payload(payload: object, output_path: Path, pretty: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2 if pretty else None, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Columbia College Bulletin courses and scheduled sections.")
    parser.add_argument("--seed-url", default=DEFAULT_SEED_URL, help="Columbia College departments seed URL.")
    parser.add_argument("--department", action="append", help="Limit scraping to department name/slug matches.")
    parser.add_argument("--max-departments", type=positive_int, help="Limit the number of department pages scraped.")
    parser.add_argument("--delay", type=float, default=0.25, help="Seconds to wait between department requests.")
    parser.add_argument("--retries", type=int, default=3, help="Retry count for transient request failures.")
    parser.add_argument("--term", help='Limit flattened section output to a term, such as "Fall 2026".')
    parser.add_argument("--flat-sections", action="store_true", help="Write one top-level course entry per section.")
    parser.add_argument("--clean", action="store_true", help="For flattened sections, write only schedule-planner fields.")
    parser.add_argument("--output", type=Path, default=Path("backend/data/columbia_college_courses.json"))
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    scraper = ColumbiaBulletinScraper(seed_url=args.seed_url, delay_seconds=args.delay, max_retries=args.retries)
    departments, courses = scraper.scrape(department_filters=args.department, max_departments=args.max_departments)
    if args.flat_sections:
        payload = build_flat_section_payload(scraper.seed_url, departments, courses, args.term)
        if args.clean:
            payload = build_clean_flat_section_entries(payload["courses"])
    else:
        payload = build_payload(scraper.seed_url, departments, courses)
    write_payload(payload, args.output, args.pretty)

    if args.flat_sections and args.clean:
        print(
            f"Wrote {len(payload)} clean flattened course entries to {args.output}",
            file=sys.stderr,
        )
    elif args.flat_sections:
        print(
            f"Wrote {payload['course_entry_count']} flattened course entries "
            f"from {payload['department_count']} departments to {args.output}",
            file=sys.stderr,
        )
    else:
        print(
            f"Wrote {payload['course_count']} courses and {payload['section_count']} sections "
            f"from {payload['department_count']} departments to {args.output}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
