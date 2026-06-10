# Schedule Planner Backend

This backend currently has two jobs:

- Serve a Flask API and browser visualizer for testing schedule combinations.
- Build the Columbia Fall 2026 course dataset from Bulletin pages.

## 1. Flask Server And Visualizer Test

Use this section if you just want to run the backend and test schedules locally.

### Setup

From the project root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

### Start The Server

From the project root:

```bash
PYTHONPATH=backend .venv/bin/python -m app
```

Or, if your virtual environment is already active and you are inside `backend/`:

```bash
python -m app
```

The server runs at:

```text
http://127.0.0.1:5001
```

Health checks:

```bash
curl http://127.0.0.1:5001/health
curl http://127.0.0.1:5001/api/health
```

### Open The Visualizer

Open this URL in your browser:

```text
http://127.0.0.1:5001/api/schedules/visualizer
```

The visualizer is a test UI for the real API endpoint. It calls `POST /api/schedules/combinations` from browser JavaScript, then renders the returned combinations as schedule blocks.

In the visualizer, enter exact course codes from the JSON data, one per line:

```text
AFAS UN1001
AMST UN3930
ANTH UN1002
```

Optional inputs:

- `Take exactly`: choose exactly Y courses from the X course codes entered.
- `No class before`: filter out sections starting before a time such as `10am`.
- `No class after`: filter out sections ending after a time such as `5pm`.

Every visualized combination uses the same standard time table so schedules are easy to compare. Unscheduled/TBA sections are included and treated as non-conflicting.

### Use The JSON API Directly

Generate non-conflicting schedule combinations:

```bash
curl -X POST http://127.0.0.1:5001/api/schedules/combinations \
  -H "Content-Type: application/json" \
  -d '{"course_numbers":["AFAS UN1001","AMST UN3930","ANTH UN1002"],"target_course_count":2,"requirements":{"no_class_before":"10am","no_class_after":"5pm"},"limit":3,"include_ascii":true}'
```

Request fields:

- `course_numbers`: exact course codes to consider, maximum 10.
- `target_course_count`: optional; choose exactly this many courses from the requested list. If omitted, all requested courses are used.
- `requirements.no_class_before`: optional time string such as `10am` or `10:30am`.
- `requirements.no_class_after`: optional time string such as `5pm` or `5:30pm`.
- `limit`: optional; limits how many combinations are returned, while still counting all valid combinations.
- `include_ascii`: optional; includes a compact text preview.

Response summary fields:

- `total_valid_combinations`
- `returned_combinations`
- `target_course_count`
- `requirements`
- `missing_course_numbers`
- `combinations`

Each returned section is intentionally compact:

```json
{
  "course_code": "AFAS UN1001",
  "section": "001",
  "days": ["M", "W"],
  "start_time": "2:40pm",
  "end_time": "3:55pm",
  "call_number": "12140"
}
```

### Preview In The Terminal

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/preview_schedule_combinations.py \
  "AFAS UN1001" "AMST UN3930" "ANTH UN1002" --take-exactly 2 --limit 3
```

## 2. Course Data And Scraper

The current app data file is:

```text
backend/data/fall_2026_all_courses_flat.json
```

This is the only generated course data file we keep in the repo right now. It is a merged Columbia College + SEAS Fall 2026 export.

### Clean Scraper Approach

The Bulletin scraper now writes the app's final JSON shape directly. Earlier versions scraped richer nested course data and then flattened it later. We removed that extra step because the app only needs one row per scheduled section/call number.

Each top-level JSON item is one section/call number and contains:

- `course_id`
- `course_code`
- `name`
- `section`
- `credit_hrs`
- `location`
- `prof_name`
- `department`
- `call number`
- `days`, `start_time`, and `end_time` only when the Bulletin row has a scheduled meeting time

There is no nested course wrapper and no legacy combined `time` field. Unscheduled/TBA rows simply omit the meeting-time fields.

### Columbia College Bulletin Scraper

The Columbia College seed URL is:

```text
https://bulletin.columbia.edu/columbia-college/departments-instruction/
```

The scraper avoids Bulletin `/search/` paths because `robots.txt` disallows them. Instead, it follows department/program links from the seed page and parses CourseLeaf `div.courseblock` entries and schedule tables on department pages.

Run a small smoke test:

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin \
  --department computer-science \
  --output backend/data/sample_courses.json \
  --pretty
```

Run a Fall 2026 Columbia College export:

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin \
  --term "Fall 2026" \
  --output backend/data/fall_2026_courses_flat.json \
  --pretty
```

### SEAS Export

Use the same scraper with the SEAS seed URL:

```bash
PYTHONPATH=backend .venv/bin/python -m scraper.columbia_bulletin \
  --seed-url https://bulletin.columbia.edu/columbia-engineering/academic-departments-programs/ \
  --term "Fall 2026" \
  --output backend/data/seas_fall_2026_courses_flat.json \
  --pretty
```

### Merge College And SEAS

Merge the clean exports into the single app data file:

```bash
.venv/bin/python backend/scripts/merge_clean_course_exports.py \
  backend/data/fall_2026_courses_flat.json \
  backend/data/seas_fall_2026_courses_flat.json \
  --output backend/data/fall_2026_all_courses_flat.json \
  --pretty
```

The merge script deduplicates by `call number` and renumbers `course_id` sequentially. If the same call number appears through multiple department pages, the first row is kept and later duplicates are skipped.

### Scraper Notes

- The full crawl requests each department page once and waits briefly between requests by default.
- Transient request failures are retried with exponential backoff.
- You can adjust crawl behavior with `--delay` and `--retries`.

Note: Bulletin data is useful for catalog courses and the embedded section snapshots it exposes. If we later need authoritative live registration state, the next scraper should target Columbia's Directory of Classes or Vergil APIs separately.