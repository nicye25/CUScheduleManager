# Schedule Planner Backend

Initial backend work is focused on scraping Columbia College course and section data from the public Bulletin pages.

## Columbia College Bulletin Scraper

The scraper starts at:

```text
https://bulletin.columbia.edu/columbia-college/departments-instruction/
```

It avoids Bulletin search paths because `robots.txt` disallows `/search/` routes. Instead, it follows the department and program pages linked from the seed page and parses CourseLeaf `div.courseblock` entries in each Courses tab.

Captured fields include:

- department name, slug, and source URL
- course code, subject, catalog number, title, and credits
- description, prerequisites, and corequisites when available
- scheduled sections embedded in the Bulletin, including term, section/call number, meeting time, location, instructor, points, and enrollment

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

## Run a Smoke Test

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin --department computer-science --output backend/data/sample_courses.json --pretty
```

## Run the Full Columbia College Crawl

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin --output backend/data/columbia_college_courses.json --pretty
```

## Run a Flattened Fall 2026 Section Export

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin --term "Fall 2026" --flat-sections --clean --output backend/data/fall_2026_courses_flat.json --pretty
```

For the Columbia Engineering/SEAS Bulletin:

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin --seed-url https://bulletin.columbia.edu/columbia-engineering/academic-departments-programs/ --term "Fall 2026" --flat-sections --clean --output backend/data/seas_fall_2026_courses_flat.json --pretty
```

Merge the Columbia College and SEAS clean exports into one deduplicated Fall 2026 file:

```bash
.venv/bin/python backend/scripts/merge_clean_course_exports.py backend/data/fall_2026_courses_flat.json backend/data/seas_fall_2026_courses_flat.json --output backend/data/fall_2026_all_courses_flat.json --pretty
```

The clean flattened export writes one top-level JSON array item per scheduled section/call number. Each item contains `course_id`, `course_code`, `name`, `section`, `credit_hrs`, `location`, `prof_name`, `department`, and `call number`. Scheduled entries also include `days`, `start_time`, and `end_time`; unscheduled/TBA entries omit those time fields.

Run without `--clean` if you need the detailed flattened output with scrape metadata and cross-listing details.

If the same call number appears through multiple department pages, the exporter keeps one top-level entry and records those catalog appearances in `catalog_course_refs`.

The full crawl requests each department page once and waits briefly between department requests by default.

The scraper also retries transient request failures with exponential backoff. You can adjust the request delay or retry count with `--delay` and `--retries`.

## CULPA Professor Ratings

The CULPA scraper uses public JSON endpoints and stores rating summaries only. It does not store review comments.

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.culpa --course-input backend/data/fall_2026_all_courses_flat.json --output-db backend/data/culpa_professor_ratings.sqlite --output-json backend/data/culpa_professor_ratings.json --pretty
```

The SQLite database contains `professors`, `departments`, `professor_departments`, and `unmatched_course_professors` tables.

Note: the Bulletin data is useful for catalog courses and the embedded section snapshots it exposes. If we later need authoritative live registration state, the next scraper should target Columbia's Directory of Classes or Vergil APIs separately.
