# Schedule Planner Backend

The backend has two pieces right now: a Flask JSON API for schedule combinations and scrapers for building the Columbia course dataset.

## Columbia College Bulletin Scraper

The scraper starts at:

```text
https://bulletin.columbia.edu/columbia-college/departments-instruction/
```

It avoids Bulletin search paths because `robots.txt` disallows `/search/` routes. Instead, it follows the department and program pages linked from the seed page and parses CourseLeaf `div.courseblock` entries in each Courses tab.

The scraper writes the schedule-planner JSON shape directly. Each top-level array item is one scheduled section/call number and contains:

- `course_id`
- `course_code`
- `name`
- `section`
- `credit_hrs`
- `location`
- `prof_name`
- `department`
- `call number`
- `days`, `start_time`, and `end_time` when the Bulletin row has a scheduled meeting time

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

## Run the Flask API

```bash
PYTHONPATH=backend .venv/bin/python -m app
```

The root URL also returns a small API index:

```bash
curl http://127.0.0.1:5001/
```

Health check:

```bash
curl http://127.0.0.1:5001/health
curl http://127.0.0.1:5001/api/health
```

Generate non-conflicting schedule combinations for up to 10 course numbers:

```bash
curl -X POST http://127.0.0.1:5001/api/schedules/combinations \
	-H "Content-Type: application/json" \
	-d '{"course_numbers":["COMS W3137","COMS W3157"],"limit":3,"include_ascii":true}'
```

The endpoint returns `total_valid_combinations` for all possible valid schedules and only includes the first `limit` combinations in the response when `limit` is provided. Each returned section is compact: `course_code`, `section`, `days`, `start_time`, `end_time`, and `call_number`.

Open the browser test UI:

```text
http://127.0.0.1:5001/api/schedules/visualizer
```

It uses exact course codes, calls `POST /api/schedules/combinations` from the browser, and renders every returned combination as a day/time schedule with blocks.

## Preview Schedules in the Terminal

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/preview_schedule_combinations.py "COMS W3137" "COMS W3157" --limit 3
```

Unscheduled/TBA sections are included in combinations and treated as non-conflicting for now.

## Run a Smoke Test

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin --department computer-science --output backend/data/sample_courses.json --pretty
```

## Run the Full Columbia College Crawl

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin --output backend/data/columbia_college_courses.json --pretty
```

## Run a Fall 2026 Section Export

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin --term "Fall 2026" --output backend/data/fall_2026_courses_flat.json --pretty
```

For the Columbia Engineering/SEAS Bulletin:

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin --seed-url https://bulletin.columbia.edu/columbia-engineering/academic-departments-programs/ --term "Fall 2026" --output backend/data/seas_fall_2026_courses_flat.json --pretty
```

Merge the Columbia College and SEAS clean exports into one deduplicated Fall 2026 file:

```bash
.venv/bin/python backend/scripts/merge_clean_course_exports.py backend/data/fall_2026_courses_flat.json backend/data/seas_fall_2026_courses_flat.json --output backend/data/fall_2026_all_courses_flat.json --pretty
```

If the same call number appears through multiple department pages, the scraper keeps the first row and skips the duplicate. The old `--flat-sections` and `--clean` flags are still accepted for backwards compatibility, but clean rows are now always written directly.

The full crawl requests each department page once and waits briefly between department requests by default.

The scraper also retries transient request failures with exponential backoff. You can adjust the request delay or retry count with `--delay` and `--retries`.

## CULPA Professor Ratings

The CULPA scraper uses public JSON endpoints and stores rating summaries only. It does not store review comments.

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.culpa --course-input backend/data/fall_2026_all_courses_flat.json --output-db backend/data/culpa_professor_ratings.sqlite --output-json backend/data/culpa_professor_ratings.json --pretty
```

The SQLite database contains `professors`, `departments`, `professor_departments`, `professor_reviews`, `professor_course_rating_summaries`, and `unmatched_course_professors` tables. The `professor_reviews` table stores ratings and review metadata only, not review text.

Note: the Bulletin data is useful for catalog courses and the embedded section snapshots it exposes. If we later need authoritative live registration state, the next scraper should target Columbia's Directory of Classes or Vergil APIs separately.
