from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
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
    r"^(?P<days>.+?)\s+"
    r"(?P<start>\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))\s*-\s*"
    r"(?P<end>\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))$"
)
DAY_ALIASES = {
    "M": "M",
    "T": "T",
    "W": "W",
    "R": "Th",
    "F": "F",
    "S": "S",
    "U": "Su",
}


@dataclass(frozen=True)
class Department:
    name: str
    url: str
    slug: str


@dataclass(frozen=True)
class CourseHeader:
    course_code: str
    name: str
    credit_hrs: float | str | None


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

    def scrape_course_rows(
        self,
        term: str | None = None,
        department_filters: Iterable[str] | None = None,
        max_departments: int | None = None,
    ) -> tuple[list[dict[str, object]], int, int]:
        departments = filter_departments(self.fetch_department_links(), department_filters)
        if max_departments is not None:
            departments = departments[:max_departments]

        course_rows: list[dict[str, object]] = []
        seen_call_numbers: set[tuple[str, str]] = set()
        duplicate_count = 0

        for index, department in enumerate(departments):
            if index > 0 and self.delay_seconds > 0:
                time.sleep(self.delay_seconds)

            print(f"Scraping {department.name} ({department.url})", file=sys.stderr)
            for section_term, row in self.scrape_department_rows(department, term):
                call_number = row.get("call number")
                if not isinstance(call_number, str) or not call_number:
                    continue

                section_key = (section_term, call_number)
                if section_key in seen_call_numbers:
                    duplicate_count += 1
                    continue

                seen_call_numbers.add(section_key)
                course_rows.append({"course_id": len(course_rows) + 1, **row})

        return course_rows, len(departments), duplicate_count

    def scrape_department_rows(self, department: Department, term: str | None) -> list[tuple[str, dict[str, object]]]:
        soup = self.fetch_soup(department.url)
        container = soup.select_one("#coursestextcontainer") or soup.select_one("#sc_sccourseblock") or soup
        rows: list[tuple[str, dict[str, object]]] = []

        for course_block in container.select("div.courseblock"):
            rows.extend(parse_course_rows(course_block, department, term))

        return rows

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


def parse_course_rows(
    course_block: Tag,
    department: Department,
    requested_term: str | None,
) -> list[tuple[str, dict[str, object]]]:
    course_header = parse_course_header(course_block)
    if course_header is None:
        return []

    rows: list[tuple[str, dict[str, object]]] = []
    for schedule_table in course_block.select("table.scheduletbl"):
        current_term: str | None = None

        for table_row in schedule_table.select("tr"):
            term_header = table_row.select_one(".desc_sched_header")
            if term_header is not None:
                current_term = parse_term_header(term_header)
                continue

            if table_row.find("th") is not None or current_term is None:
                continue
            if requested_term is not None and current_term != requested_term:
                continue

            cells = table_row.find_all("td", recursive=False)
            if len(cells) < 6:
                continue

            section_row = build_section_row(course_header, department, cells)
            if section_row is not None:
                rows.append((current_term, section_row))

    return rows


def parse_course_header(course_block: Tag) -> CourseHeader | None:
    title_node = course_block.select_one("p.courseblocktitle")
    if title_node is None:
        return None

    first_strong = title_node.find("strong")
    if first_strong is None:
        return None

    code_and_title = clean_text(first_strong.get_text(" ", strip=True)).rstrip(".")
    match = COURSE_CODE_RE.match(code_and_title)
    if match is None:
        return None

    credits_node = title_node.find("em")
    credits_text = clean_text(credits_node.get_text(" ", strip=True)).rstrip(".") if credits_node else None
    course_code = f"{match.group('subject')} {match.group('catalog_number')}"
    return CourseHeader(
        course_code=course_code,
        name=clean_text(match.group("title")).rstrip("."),
        credit_hrs=clean_credit_hours(points=None, catalog_credits=credits_text),
    )


def build_section_row(course_header: CourseHeader, department: Department, cells: list[Tag]) -> dict[str, object] | None:
    raw_section_call = clean_text(cells[1].get_text(" ", strip=True))
    section, call_number = parse_section_call(raw_section_call)
    if call_number is None:
        return None

    times_location_lines = clean_lines(cells[2])
    section_points = clean_text(cells[4].get_text(" ", strip=True)) or None
    location = clean_locations(times_location_lines)

    row: dict[str, object] = {
        "course_code": course_header.course_code,
        "name": course_header.name,
        "section": section,
        "credit_hrs": clean_credit_hours(points=section_points, catalog_credits=course_header.credit_hrs),
        "location": location,
        "prof_name": clean_text(cells[3].get_text(" ", strip=True)) or None,
        "department": department.name,
        "call number": call_number,
    }
    row.update(clean_meeting_fields(times_location_lines))
    return row


def parse_term_header(header: Tag) -> str | None:
    header_text = clean_text(header.get_text(" ", strip=True))
    if not header_text:
        return None

    term, _, _ = header_text.partition(":")
    return clean_text(term) or None


def parse_section_call(raw_section_call: str) -> tuple[str | None, str | None]:
    if not raw_section_call:
        return None, None
    section, separator, call_number = raw_section_call.partition("/")
    if not separator:
        return clean_text(section) or None, None
    return clean_text(section) or None, clean_text(call_number) or None


def clean_meeting_fields(times_location_lines: list[str]) -> dict[str, object]:
    meetings = [meeting for line in times_location_lines if (meeting := parse_meeting(line)) is not None]
    if not meetings:
        return {}

    first_meeting = meetings[0]
    days = list(first_meeting["days"])
    for meeting in meetings[1:]:
        if meeting["start_time"] != first_meeting["start_time"] or meeting["end_time"] != first_meeting["end_time"]:
            break
        for day in meeting["days"]:
            append_unique(days, day)

    return {
        "days": days,
        "start_time": first_meeting["start_time"],
        "end_time": first_meeting["end_time"],
    }


def parse_meeting(line: str) -> dict[str, object] | None:
    match = MEETING_RE.match(line)
    if match is None:
        return None

    days = parse_meeting_days(match.group("days"))
    if not days:
        return None

    return {
        "days": days,
        "start_time": normalize_time(match.group("start")),
        "end_time": normalize_time(match.group("end")),
    }


def parse_meeting_days(days_text: str) -> list[str]:
    days: list[str] = []
    index = 0
    text = clean_text(days_text).replace(",", " ")

    while index < len(text):
        if text[index].isspace():
            index += 1
            continue

        two_character_day = text[index : index + 2].lower()
        if two_character_day == "th":
            append_unique(days, "Th")
            index += 2
            continue
        if two_character_day == "sa":
            append_unique(days, "Sa")
            index += 2
            continue
        if two_character_day == "su":
            append_unique(days, "Su")
            index += 2
            continue

        day = DAY_ALIASES.get(text[index].upper())
        if day is not None:
            append_unique(days, day)
        index += 1

    return days


def clean_credit_hours(points: str | None, catalog_credits: object) -> float | str | None:
    if isinstance(points, str) and points.strip():
        parsed_points = parse_numeric_text(points)
        return parsed_points if parsed_points is not None else clean_text(points)

    if isinstance(catalog_credits, int | float):
        return float(catalog_credits)
    if isinstance(catalog_credits, str):
        match = CREDIT_RE.search(catalog_credits)
        if match is None:
            return clean_text(catalog_credits) or None

        min_credits = float(match.group("min"))
        max_credits = float(match.group("max")) if match.group("max") else min_credits
        if min_credits == max_credits:
            return min_credits
        return f"{min_credits:g}-{max_credits:g}"

    return None


def clean_locations(times_location_lines: list[str]) -> str | None:
    locations: list[str] = []
    for line in times_location_lines:
        if parse_meeting(line) is None:
            append_unique(locations, line)
    return "; ".join(locations) if locations else None


def clean_text(text: object) -> str:
    if text is None:
        return ""
    return SPACE_RE.sub(" ", str(text).replace("\xa0", " ")).strip()


def clean_lines(node: Tag) -> list[str]:
    return [line for line in (clean_text(piece) for piece in node.stripped_strings) if line]


def normalize_time(time_text: str) -> str:
    return clean_text(time_text).replace(" ", "").lower()


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


def write_json(path: Path, rows: list[dict[str, object]], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rows, indent=2 if pretty else None, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Columbia Bulletin scheduled sections into clean JSON rows.")
    parser.add_argument("--seed-url", default=DEFAULT_SEED_URL, help="Bulletin departments seed URL.")
    parser.add_argument("--department", action="append", help="Limit scraping to department name/slug matches.")
    parser.add_argument("--max-departments", type=positive_int, help="Limit the number of department pages scraped.")
    parser.add_argument("--delay", type=float, default=0.25, help="Seconds to wait between department requests.")
    parser.add_argument("--retries", type=int, default=3, help="Retry count for transient request failures.")
    parser.add_argument("--term", help='Limit sections to a term, such as "Fall 2026".')
    parser.add_argument("--output", type=Path, default=Path("backend/data/columbia_college_courses.json"))
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    scraper = ColumbiaBulletinScraper(seed_url=args.seed_url, delay_seconds=args.delay, max_retries=args.retries)
    rows, department_count, duplicate_count = scraper.scrape_course_rows(
        term=args.term,
        department_filters=args.department,
        max_departments=args.max_departments,
    )
    write_json(args.output, rows, args.pretty)

    print(
        f"Wrote {len(rows)} clean course rows from {department_count} departments to {args.output}; "
        f"skipped {duplicate_count} duplicate call numbers.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())