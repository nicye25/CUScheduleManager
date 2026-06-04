from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

import requests


BASE_URL = "https://culpa.info"
DEFAULT_USER_AGENT = "SchedulePlannerCulpaScraper/0.1"
REVIEWS_PER_PAGE = 5
SPACE_RE = re.compile(r"\s+")
NAME_SPLIT_RE = re.compile(r"\s+(?:and|&)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class Department:
    department_id: int
    department_code: str | None
    name: str


@dataclass
class Professor:
    professor_id: int
    first_name: str
    last_name: str
    full_name: str
    normalized_name: str
    nugget: int | None
    status: str | None
    uni: str | None
    departments: dict[int, Department]


@dataclass(frozen=True)
class RatingSummary:
    professor_id: int
    number_of_reviews: int
    rating_count: int
    avg_rating: float | None
    agree_count: int
    disagree_count: int
    funny_count: int
    rating_1_count: int
    rating_2_count: int
    rating_3_count: int
    rating_4_count: int
    rating_5_count: int
    latest_review_date: str | None


@dataclass(frozen=True)
class ProfessorReviewRating:
    review_id: int
    professor_id: int
    course_id: int | None
    course_code: str | None
    course_name: str | None
    rating: int | None
    agree_count: int
    disagree_count: int
    funny_count: int
    submission_date: str | None


class CulpaScraper:
    def __init__(
        self,
        delay_seconds: float = 0.03,
        timeout_seconds: float = 30,
        max_retries: int = 3,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})

    def fetch_departments(self) -> list[Department]:
        data = self.get_json("/api/departments/all")
        return [
            Department(
                department_id=int(department["department_id"]),
                department_code=department.get("department_code"),
                name=clean_text(department["name"]),
            )
            for department in data
        ]

    def fetch_professors_by_department(
        self,
        departments: list[Department],
    ) -> dict[int, Professor]:
        professors_by_id: dict[int, Professor] = {}

        for index, department in enumerate(departments, start=1):
            print(
                f"Fetching CULPA professors for {department.name} ({index}/{len(departments)})",
                file=sys.stderr,
            )
            professor_data = self.get_json(f"/api/departments/{department.department_id}/professors")
            for professor_payload in professor_data:
                professor_id = int(professor_payload["professor_id"])
                first_name = clean_text(professor_payload.get("first_name"))
                last_name = clean_text(professor_payload.get("last_name"))
                full_name = clean_text(f"{first_name} {last_name}")

                professor = professors_by_id.get(professor_id)
                if professor is None:
                    professor = Professor(
                        professor_id=professor_id,
                        first_name=first_name,
                        last_name=last_name,
                        full_name=full_name,
                        normalized_name=normalize_name(full_name),
                        nugget=professor_payload.get("nugget"),
                        status=professor_payload.get("status"),
                        uni=professor_payload.get("uni"),
                        departments={},
                    )
                    professors_by_id[professor_id] = professor

                professor.departments[department.department_id] = department

        return professors_by_id

    def fetch_professor_ratings(self, professor_id: int) -> tuple[RatingSummary, list[ProfessorReviewRating]]:
        first_page = self.get_json(f"/api/review/professor/{professor_id}", {"page": 1})
        number_of_reviews = int(first_page.get("number_of_reviews") or 0)
        page_count = math.ceil(number_of_reviews / REVIEWS_PER_PAGE) if number_of_reviews else 1
        reviews = list(first_page.get("reviews") or [])

        for page in range(2, page_count + 1):
            page_payload = self.get_json(f"/api/review/professor/{professor_id}", {"page": page})
            reviews.extend(page_payload.get("reviews") or [])

        ratings: list[int] = []
        rating_counts = {rating: 0 for rating in range(1, 6)}
        review_ratings: list[ProfessorReviewRating] = []
        agree_count = 0
        disagree_count = 0
        funny_count = 0
        latest_review_date: str | None = None

        for review in reviews:
            rating = review.get("rating")
            normalized_rating = rating if isinstance(rating, int) and 1 <= rating <= 5 else None
            if isinstance(rating, int) and 1 <= rating <= 5:
                ratings.append(rating)
                rating_counts[rating] += 1

            agree_count += int(review.get("agree_count") or 0)
            disagree_count += int(review.get("disagree_count") or 0)
            funny_count += int(review.get("funny_count") or 0)

            submission_date = review.get("submission_date")
            if isinstance(submission_date, str) and (latest_review_date is None or submission_date > latest_review_date):
                latest_review_date = submission_date

            review_id = review.get("review_id")
            if not isinstance(review_id, int):
                continue

            course_header = review.get("course_header") or {}
            review_ratings.append(
                ProfessorReviewRating(
                    review_id=review_id,
                    professor_id=professor_id,
                    course_id=course_header.get("course_id") if isinstance(course_header.get("course_id"), int) else None,
                    course_code=clean_text(course_header.get("course_code")) or None,
                    course_name=clean_text(course_header.get("course_name")) or None,
                    rating=normalized_rating,
                    agree_count=int(review.get("agree_count") or 0),
                    disagree_count=int(review.get("disagree_count") or 0),
                    funny_count=int(review.get("funny_count") or 0),
                    submission_date=submission_date if isinstance(submission_date, str) else None,
                )
            )

        avg_rating = round(sum(ratings) / len(ratings), 3) if ratings else None
        return (
            RatingSummary(
                professor_id=professor_id,
                number_of_reviews=number_of_reviews,
                rating_count=len(ratings),
                avg_rating=avg_rating,
                agree_count=agree_count,
                disagree_count=disagree_count,
                funny_count=funny_count,
                rating_1_count=rating_counts[1],
                rating_2_count=rating_counts[2],
                rating_3_count=rating_counts[3],
                rating_4_count=rating_counts[4],
                rating_5_count=rating_counts[5],
                latest_review_date=latest_review_date,
            ),
            review_ratings,
        )

    def get_json(self, path: str, params: dict[str, object] | None = None) -> object:
        url = f"{BASE_URL}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"

        for attempt in range(self.max_retries + 1):
            try:
                if self.delay_seconds > 0:
                    time.sleep(self.delay_seconds)
                response = self.session.get(url, timeout=self.timeout_seconds)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "application/json" not in content_type:
                    raise ValueError(f"Expected JSON from {url}, got {content_type}")
                return response.json()
            except (requests.RequestException, ValueError) as error:
                if attempt >= self.max_retries:
                    raise

                wait_seconds = retry_wait_seconds(error, attempt)
                print(f"CULPA request failed for {url}: {error}. Retrying in {wait_seconds:.1f}s.", file=sys.stderr)
                time.sleep(wait_seconds)

        raise RuntimeError(f"Unable to fetch {url}")


def load_course_professor_names(course_input: Path) -> dict[str, set[str]]:
    courses = json.loads(course_input.read_text(encoding="utf-8"))
    names_by_normalized_name: dict[str, set[str]] = defaultdict(set)

    for course in courses:
        prof_name = course.get("prof_name")
        if not isinstance(prof_name, str):
            continue
        for name in split_professor_names(prof_name):
            normalized_name = normalize_name(name)
            if normalized_name:
                names_by_normalized_name[normalized_name].add(name)

    return names_by_normalized_name


def retry_wait_seconds(error: Exception, attempt: int) -> float:
    response = getattr(error, "response", None)
    if response is not None and getattr(response, "status_code", None) == 429:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return 10.0 * (attempt + 1)

    return 1.0 * (2**attempt)


def split_professor_names(prof_name: str) -> list[str]:
    names: list[str] = []
    for comma_part in prof_name.split(","):
        for name in NAME_SPLIT_RE.split(comma_part):
            cleaned_name = clean_text(name)
            if cleaned_name and cleaned_name.lower() not in {"staff", "tba", "to be announced"}:
                names.append(cleaned_name)
    return names


def filter_professors_for_course_names(
    professors_by_id: dict[int, Professor],
    course_names_by_normalized_name: dict[str, set[str]],
) -> tuple[dict[int, Professor], dict[str, set[str]]]:
    professors_by_normalized_name: dict[str, list[Professor]] = defaultdict(list)
    for professor in professors_by_id.values():
        professors_by_normalized_name[professor.normalized_name].append(professor)

    matched_professors: dict[int, Professor] = {}
    unmatched_names: dict[str, set[str]] = {}

    for normalized_name, original_names in course_names_by_normalized_name.items():
        professor_matches = professors_by_normalized_name.get(normalized_name, [])
        if not professor_matches:
            unmatched_names[normalized_name] = original_names
            continue

        for professor in professor_matches:
            matched_professors[professor.professor_id] = professor

    return matched_professors, unmatched_names


def write_sqlite_database(
    output_db: Path,
    departments: list[Department],
    professors: dict[int, Professor],
    rating_summaries: dict[int, RatingSummary],
    review_ratings: list[ProfessorReviewRating],
    unmatched_names: dict[str, set[str]],
) -> None:
    initialize_sqlite_database(output_db, departments, unmatched_names, reset=True)
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(output_db) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        review_ratings_by_professor: dict[int, list[ProfessorReviewRating]] = defaultdict(list)
        for review_rating in review_ratings:
            review_ratings_by_professor[review_rating.professor_id].append(review_rating)

        for professor_id, professor in professors.items():
            write_professor_rating(
                connection,
                professor,
                rating_summaries[professor_id],
                review_ratings_by_professor[professor_id],
                scraped_at,
            )


def initialize_sqlite_database(
    output_db: Path,
    departments: list[Department],
    unmatched_names: dict[str, set[str]],
    reset: bool,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(output_db) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        if reset:
            connection.executescript(
                """
                DROP TABLE IF EXISTS unmatched_course_professors;
                DROP TABLE IF EXISTS professor_course_rating_summaries;
                DROP TABLE IF EXISTS professor_reviews;
                DROP TABLE IF EXISTS professor_departments;
                DROP TABLE IF EXISTS professors;
                DROP TABLE IF EXISTS departments;
                """
            )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS departments (
                department_id INTEGER PRIMARY KEY,
                department_code TEXT,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS professors (
                professor_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                full_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                uni TEXT,
                nugget INTEGER,
                status TEXT,
                number_of_reviews INTEGER NOT NULL,
                rating_count INTEGER NOT NULL,
                avg_rating REAL,
                agree_count INTEGER NOT NULL,
                disagree_count INTEGER NOT NULL,
                funny_count INTEGER NOT NULL,
                rating_1_count INTEGER NOT NULL,
                rating_2_count INTEGER NOT NULL,
                rating_3_count INTEGER NOT NULL,
                rating_4_count INTEGER NOT NULL,
                rating_5_count INTEGER NOT NULL,
                latest_review_date TEXT,
                scraped_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS professor_departments (
                professor_id INTEGER NOT NULL,
                department_id INTEGER NOT NULL,
                department_code TEXT,
                department_name TEXT NOT NULL,
                PRIMARY KEY (professor_id, department_id),
                FOREIGN KEY (professor_id) REFERENCES professors(professor_id),
                FOREIGN KEY (department_id) REFERENCES departments(department_id)
            );

            CREATE TABLE IF NOT EXISTS professor_reviews (
                review_id INTEGER PRIMARY KEY,
                professor_id INTEGER NOT NULL,
                course_id INTEGER,
                course_code TEXT,
                course_name TEXT,
                rating INTEGER,
                agree_count INTEGER NOT NULL,
                disagree_count INTEGER NOT NULL,
                funny_count INTEGER NOT NULL,
                submission_date TEXT,
                FOREIGN KEY (professor_id) REFERENCES professors(professor_id)
            );

            CREATE TABLE IF NOT EXISTS professor_course_rating_summaries (
                professor_id INTEGER NOT NULL,
                course_id INTEGER,
                course_code TEXT NOT NULL,
                course_name TEXT,
                review_count INTEGER NOT NULL,
                rating_count INTEGER NOT NULL,
                avg_rating REAL,
                PRIMARY KEY (professor_id, course_code),
                FOREIGN KEY (professor_id) REFERENCES professors(professor_id)
            );

            CREATE TABLE IF NOT EXISTS unmatched_course_professors (
                normalized_name TEXT PRIMARY KEY,
                names TEXT NOT NULL
            );
            """
        )

        connection.executemany(
            "INSERT OR REPLACE INTO departments (department_id, department_code, name) VALUES (?, ?, ?)",
            [(department.department_id, department.department_code, department.name) for department in departments],
        )

        connection.execute("DELETE FROM unmatched_course_professors")
        connection.executemany(
            "INSERT OR REPLACE INTO unmatched_course_professors (normalized_name, names) VALUES (?, ?)",
            [(normalized_name, json.dumps(sorted(names))) for normalized_name, names in unmatched_names.items()],
        )


def write_professor_rating(
    connection: sqlite3.Connection,
    professor: Professor,
    rating_summary: RatingSummary,
    review_ratings: list[ProfessorReviewRating],
    scraped_at: str,
) -> None:
    connection.execute("DELETE FROM professor_reviews WHERE professor_id = ?", (professor.professor_id,))
    connection.execute("DELETE FROM professor_course_rating_summaries WHERE professor_id = ?", (professor.professor_id,))
    connection.execute("DELETE FROM professor_departments WHERE professor_id = ?", (professor.professor_id,))

    connection.execute(
        """
        INSERT OR REPLACE INTO professors (
            professor_id,
            first_name,
            last_name,
            full_name,
            normalized_name,
            uni,
            nugget,
            status,
            number_of_reviews,
            rating_count,
            avg_rating,
            agree_count,
            disagree_count,
            funny_count,
            rating_1_count,
            rating_2_count,
            rating_3_count,
            rating_4_count,
            rating_5_count,
            latest_review_date,
            scraped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        professor_row(professor, rating_summary, scraped_at),
    )

    connection.executemany(
        """
        INSERT INTO professor_departments (professor_id, department_id, department_code, department_name)
        VALUES (?, ?, ?, ?)
        """,
        [
            (professor.professor_id, department.department_id, department.department_code, department.name)
            for department in professor.departments.values()
        ],
    )

    connection.executemany(
        """
        INSERT OR REPLACE INTO professor_reviews (
            review_id,
            professor_id,
            course_id,
            course_code,
            course_name,
            rating,
            agree_count,
            disagree_count,
            funny_count,
            submission_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [review_rating_row(review_rating) for review_rating in review_ratings],
    )

    connection.executemany(
        """
        INSERT OR REPLACE INTO professor_course_rating_summaries (
            professor_id,
            course_id,
            course_code,
            course_name,
            review_count,
            rating_count,
            avg_rating
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        course_rating_summary_rows(review_ratings),
    )


def completed_professor_ids(output_db: Path) -> set[int]:
    if not output_db.exists():
        return set()

    with sqlite3.connect(output_db) as connection:
        try:
            return {row[0] for row in connection.execute("SELECT professor_id FROM professors")}
        except sqlite3.OperationalError:
            return set()


def professor_row(professor: Professor, rating_summary: RatingSummary, scraped_at: str) -> tuple[object, ...]:
    return (
        professor.professor_id,
        professor.first_name,
        professor.last_name,
        professor.full_name,
        professor.normalized_name,
        professor.uni,
        professor.nugget,
        professor.status,
        rating_summary.number_of_reviews,
        rating_summary.rating_count,
        rating_summary.avg_rating,
        rating_summary.agree_count,
        rating_summary.disagree_count,
        rating_summary.funny_count,
        rating_summary.rating_1_count,
        rating_summary.rating_2_count,
        rating_summary.rating_3_count,
        rating_summary.rating_4_count,
        rating_summary.rating_5_count,
        rating_summary.latest_review_date,
        scraped_at,
    )


def review_rating_row(review_rating: ProfessorReviewRating) -> tuple[object, ...]:
    return (
        review_rating.review_id,
        review_rating.professor_id,
        review_rating.course_id,
        review_rating.course_code,
        review_rating.course_name,
        review_rating.rating,
        review_rating.agree_count,
        review_rating.disagree_count,
        review_rating.funny_count,
        review_rating.submission_date,
    )


def course_rating_summary_rows(review_ratings: list[ProfessorReviewRating]) -> list[tuple[object, ...]]:
    grouped_reviews: dict[tuple[int, str], list[ProfessorReviewRating]] = defaultdict(list)

    for review_rating in review_ratings:
        if not review_rating.course_code:
            continue
        grouped_reviews[(review_rating.professor_id, review_rating.course_code)].append(review_rating)

    rows: list[tuple[object, ...]] = []
    for (professor_id, course_code), grouped_review_ratings in sorted(grouped_reviews.items()):
        ratings = [review_rating.rating for review_rating in grouped_review_ratings if review_rating.rating is not None]
        course_ids = [review_rating.course_id for review_rating in grouped_review_ratings if review_rating.course_id is not None]
        course_names = [review_rating.course_name for review_rating in grouped_review_ratings if review_rating.course_name]
        rows.append(
            (
                professor_id,
                course_ids[0] if course_ids else None,
                course_code,
                course_names[0] if course_names else None,
                len(grouped_review_ratings),
                len(ratings),
                round(sum(ratings) / len(ratings), 3) if ratings else None,
            )
        )

    return rows


def build_json_summary(
    professors: dict[int, Professor],
    rating_summaries: dict[int, RatingSummary],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for professor in sorted(professors.values(), key=lambda item: (item.full_name, item.professor_id)):
        rating_summary = rating_summaries[professor.professor_id]
        rows.append(
            {
                "professor_id": professor.professor_id,
                "name": professor.full_name,
                "normalized_name": professor.normalized_name,
                "uni": professor.uni,
                "nugget": professor.nugget,
                "number_of_reviews": rating_summary.number_of_reviews,
                "rating_count": rating_summary.rating_count,
                "avg_rating": rating_summary.avg_rating,
                "agree_count": rating_summary.agree_count,
                "disagree_count": rating_summary.disagree_count,
                "funny_count": rating_summary.funny_count,
                "latest_review_date": rating_summary.latest_review_date,
                "departments": [department.name for department in sorted(professor.departments.values(), key=lambda item: item.name)],
            }
        )

    return rows


def write_json_summary(output_json: Path, rows: list[dict[str, object]], pretty: bool) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(rows, indent=2 if pretty else None, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_json_summary_from_database(output_db: Path, output_json: Path, pretty: bool) -> None:
    rows: list[dict[str, object]] = []
    with sqlite3.connect(output_db) as connection:
        connection.row_factory = sqlite3.Row
        professor_rows = connection.execute(
            """
            SELECT
                professor_id,
                full_name,
                normalized_name,
                uni,
                nugget,
                number_of_reviews,
                rating_count,
                avg_rating,
                agree_count,
                disagree_count,
                funny_count,
                latest_review_date
            FROM professors
            ORDER BY full_name, professor_id
            """
        ).fetchall()

        for professor_row_data in professor_rows:
            department_rows = connection.execute(
                """
                SELECT department_name
                FROM professor_departments
                WHERE professor_id = ?
                ORDER BY department_name
                """,
                (professor_row_data["professor_id"],),
            ).fetchall()
            rows.append(
                {
                    "professor_id": professor_row_data["professor_id"],
                    "name": professor_row_data["full_name"],
                    "normalized_name": professor_row_data["normalized_name"],
                    "uni": professor_row_data["uni"],
                    "nugget": professor_row_data["nugget"],
                    "number_of_reviews": professor_row_data["number_of_reviews"],
                    "rating_count": professor_row_data["rating_count"],
                    "avg_rating": professor_row_data["avg_rating"],
                    "agree_count": professor_row_data["agree_count"],
                    "disagree_count": professor_row_data["disagree_count"],
                    "funny_count": professor_row_data["funny_count"],
                    "latest_review_date": professor_row_data["latest_review_date"],
                    "departments": [row["department_name"] for row in department_rows],
                }
            )

    write_json_summary(output_json, rows, pretty)


def count_database_rows(output_db: Path, table_name: str) -> int:
    with sqlite3.connect(output_db) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return SPACE_RE.sub(" ", str(value).replace("\xa0", " ")).strip()


def normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned_name = re.sub(r"[^a-zA-Z0-9\s'-]", " ", ascii_name).lower()
    return SPACE_RE.sub(" ", cleaned_name).strip()


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape CULPA professor rating summaries without review comments.")
    parser.add_argument("--course-input", type=Path, help="Clean course JSON array used to limit ratings to listed professors.")
    parser.add_argument("--all-professors", action="store_true", help="Fetch rating summaries for all CULPA professors.")
    parser.add_argument("--output-db", type=Path, default=Path("backend/data/culpa_professor_ratings.sqlite"))
    parser.add_argument("--output-json", type=Path, default=Path("backend/data/culpa_professor_ratings.json"))
    parser.add_argument("--delay", type=float, default=0.03, help="Delay between CULPA API requests.")
    parser.add_argument("--retries", type=positive_int, default=3, help="Retry count for transient request failures.")
    parser.add_argument("--max-professors", type=positive_int, help="Limit rating fetches for smoke tests.")
    parser.add_argument("--workers", type=positive_int, default=1, help="Concurrent workers for fetching professor review pages.")
    parser.add_argument("--resume", action="store_true", help="Keep existing database rows and skip professors already written.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON summary output.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.all_professors and args.course_input is None:
        raise SystemExit("Pass --course-input to scrape course professor matches, or --all-professors to scrape all CULPA professors.")

    scraper = CulpaScraper(delay_seconds=args.delay, max_retries=args.retries)
    departments = scraper.fetch_departments()
    professors_by_id = scraper.fetch_professors_by_department(departments)
    unmatched_names: dict[str, set[str]] = {}

    if args.all_professors:
        target_professors = professors_by_id
    else:
        course_names_by_normalized_name = load_course_professor_names(args.course_input)
        target_professors, unmatched_names = filter_professors_for_course_names(
            professors_by_id,
            course_names_by_normalized_name,
        )
        print(
            f"Matched {len(target_professors)} CULPA professors for "
            f"{len(course_names_by_normalized_name)} normalized course professor names; "
            f"{len(unmatched_names)} names unmatched.",
            file=sys.stderr,
        )

    if args.max_professors is not None:
        target_professors = dict(list(target_professors.items())[: args.max_professors])
        print(f"Limiting scrape to {len(target_professors)} professors.", file=sys.stderr)

    target_professor_list = list(target_professors.values())
    initialize_sqlite_database(args.output_db, departments, unmatched_names, reset=not args.resume)
    completed_ids = completed_professor_ids(args.output_db) if args.resume else set()
    if completed_ids:
        target_professor_list = [professor for professor in target_professor_list if professor.professor_id not in completed_ids]
        print(
            f"Resuming scrape: skipping {len(completed_ids)} professors already stored; "
            f"{len(target_professor_list)} remain.",
            file=sys.stderr,
        )

    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(args.output_db) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for professor, rating_summary, professor_review_ratings in iter_rating_results(
            target_professor_list,
            delay_seconds=args.delay,
            max_retries=args.retries,
            workers=args.workers,
        ):
            write_professor_rating(connection, professor, rating_summary, professor_review_ratings, scraped_at)
            connection.commit()

    write_json_summary_from_database(args.output_db, args.output_json, args.pretty)
    professor_count = count_database_rows(args.output_db, "professors")
    print(
        f"Wrote {professor_count} professor rating summaries to {args.output_db} "
        f"and {args.output_json}; no review comments stored.",
        file=sys.stderr,
    )
    return 0


def iter_rating_results(
    professors: list[Professor],
    delay_seconds: float,
    max_retries: int,
    workers: int,
) -> Iterable[tuple[Professor, RatingSummary, list[ProfessorReviewRating]]]:
    if workers == 1:
        scraper = CulpaScraper(delay_seconds=delay_seconds, max_retries=max_retries)
        for index, professor in enumerate(professors, start=1):
            print(
                f"Fetching CULPA ratings for {professor.full_name} ({index}/{len(professors)})",
                file=sys.stderr,
            )
            rating_summary, professor_review_ratings = scraper.fetch_professor_ratings(professor.professor_id)
            yield professor, rating_summary, professor_review_ratings
        return

    def fetch_professor(professor: Professor) -> tuple[Professor, RatingSummary, list[ProfessorReviewRating]]:
        worker_scraper = CulpaScraper(delay_seconds=delay_seconds, max_retries=max_retries)
        rating_summary, professor_review_ratings = worker_scraper.fetch_professor_ratings(professor.professor_id)
        return professor, rating_summary, professor_review_ratings

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_professor, professor): professor for professor in professors}
        for index, future in enumerate(as_completed(futures), start=1):
            professor, rating_summary, professor_review_ratings = future.result()
            print(
                f"Fetched CULPA ratings for {professor.full_name} ({index}/{len(professors)})",
                file=sys.stderr,
            )
            yield professor, rating_summary, professor_review_ratings


if __name__ == "__main__":
    raise SystemExit(main())
