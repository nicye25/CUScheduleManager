from __future__ import annotations

from flask import Blueprint, jsonify, render_template_string, request

from app.services.ascii_schedule import format_combinations_ascii
from app.services.course_catalog import load_course_rows
from app.services.schedule_generator import (
    MAX_COURSES,
    ScheduleGenerationError,
    generate_schedule_combinations,
)


schedules_bp = Blueprint("schedules", __name__, url_prefix="/api")


@schedules_bp.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@schedules_bp.post("/schedules/combinations")
def schedule_combinations():
    payload = request.get_json(silent=True) or {}
    course_numbers = payload.get("course_numbers", payload.get("course_codes"))
    limit = payload.get("limit")
    include_ascii = bool(payload.get("include_ascii", False))
    requirements = extract_requirements(payload)
    target_course_count = extract_target_course_count(payload)

    try:
        validated_course_numbers = validate_course_numbers(course_numbers)
        validated_limit = validate_limit(limit)
        result = generate_schedule_combinations(
            validated_course_numbers,
            load_course_rows(),
            limit=validated_limit,
            requirements=requirements,
            target_course_count=target_course_count,
        )
    except (ScheduleGenerationError, ValueError) as error:
        return jsonify({"error": str(error)}), 400

    if include_ascii:
        result["ascii"] = format_combinations_ascii(result["combinations"])

    return jsonify(result), 200


@schedules_bp.get("/schedules/visualizer")
def schedule_visualizer():
    return render_template_string(VISUALIZER_TEMPLATE)


def validate_course_numbers(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Request body must include course_numbers as a list of course codes.")

    course_numbers = []
    for course_number in value:
        if not isinstance(course_number, str) or not course_number.strip():
            raise ValueError("Each course number must be a non-empty string.")
        course_numbers.append(course_number)

    if len(course_numbers) > MAX_COURSES:
        raise ValueError(f"A maximum of {MAX_COURSES} courses can be selected.")

    return course_numbers


def validate_limit(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError("limit must be an integer when provided.")
    if value < 1:
        raise ValueError("limit must be at least 1.")
    return value


def extract_requirements(payload: dict[str, object]) -> object:
    requirements = payload.get("requirements")
    if requirements is not None:
        return requirements
    return {
        "no_class_before": payload.get("no_class_before"),
        "no_class_after": payload.get("no_class_after"),
    }


def extract_target_course_count(payload: dict[str, object]) -> object:
    for field_name in ("target_course_count", "take_exactly", "exact_course_count"):
        if field_name in payload:
            return payload[field_name]
    return None


VISUALIZER_TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SchedulePlanner Visualizer</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            background: #f5f6f8;
            color: #1f2933;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        main {
            width: min(1180px, calc(100vw - 32px));
            margin: 24px auto 48px;
        }
        h1 {
            margin: 0 0 18px;
            font-size: 24px;
            font-weight: 720;
            letter-spacing: 0;
        }
        form {
            display: grid;
            grid-template-columns: minmax(280px, 1fr) 120px 150px 150px 140px;
            align-items: end;
            gap: 12px;
            padding: 16px;
            background: #ffffff;
            border: 1px solid #d9dee7;
            border-radius: 8px;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
        }
        label {
            display: grid;
            gap: 6px;
            font-size: 13px;
            font-weight: 680;
            color: #344054;
        }
        textarea,
        input {
            width: 100%;
            border: 1px solid #c9d2df;
            border-radius: 6px;
            color: #111827;
            font: inherit;
            font-size: 14px;
            background: #ffffff;
        }
        textarea {
            min-height: 82px;
            padding: 10px 12px;
            resize: vertical;
            line-height: 1.45;
        }
        input { height: 40px; padding: 0 10px; }
        button {
            height: 40px;
            border: 0;
            border-radius: 6px;
            background: #1f6feb;
            color: #ffffff;
            font: inherit;
            font-weight: 720;
            cursor: pointer;
        }
        button:hover { background: #175bc2; }
        .summary,
        .alert,
        .empty {
            margin-top: 16px;
            padding: 12px 14px;
            border-radius: 8px;
            border: 1px solid #d9dee7;
            background: #ffffff;
        }
        .alert {
            border-color: #f3b8b8;
            background: #fff7f7;
            color: #9f1d1d;
        }
        .summary {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
            color: #475467;
        }
        .summary strong { color: #111827; }
        .api-note {
            margin-top: 10px;
            color: #667085;
            font-size: 13px;
        }
        .combination {
            margin-top: 18px;
            background: #ffffff;
            border: 1px solid #d9dee7;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
        }
        .combination header {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: center;
            padding: 12px 14px;
            border-bottom: 1px solid #e5e9f0;
            background: #fbfcfe;
        }
        h2 { margin: 0; font-size: 16px; letter-spacing: 0; }
        .calendar-header {
            display: grid;
            grid-template-columns: 72px repeat(5, minmax(120px, 1fr));
            border-bottom: 1px solid #e5e9f0;
            background: #f8fafc;
        }
        .calendar-header div {
            min-height: 38px;
            display: grid;
            place-items: center;
            border-left: 1px solid #e5e9f0;
            color: #475467;
            font-size: 13px;
            font-weight: 720;
        }
        .calendar-header div:first-child { border-left: 0; }
        .calendar-body {
            display: grid;
            grid-template-columns: 72px 1fr;
            min-height: 620px;
        }
        .time-rail,
        .days-area { position: relative; }
        .time-rail {
            border-right: 1px solid #e5e9f0;
            background: #fbfcfe;
        }
        .time-mark {
            position: absolute;
            right: 8px;
            transform: translateY(-50%);
            color: #667085;
            font-size: 12px;
            white-space: nowrap;
        }
        .days-area {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            background: #ffffff;
        }
        .day-column { border-left: 1px solid #eef1f5; }
        .day-column:first-child { border-left: 0; }
        .hour-line {
            position: absolute;
            left: 0;
            right: 0;
            height: 1px;
            background: #eef1f5;
            pointer-events: none;
        }
        .course-block {
            position: absolute;
            left: calc(var(--day) * 20% + 6px);
            top: var(--top);
            width: calc(20% - 12px);
            height: var(--height);
            min-height: 54px;
            padding: 8px;
            border-left: 4px solid var(--color);
            border-radius: 7px;
            background: color-mix(in srgb, var(--color) 12%, #ffffff);
            box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color) 24%, #ffffff);
            overflow: hidden;
            color: #172033;
        }
        .course-block strong,
        .course-block span,
        .course-block small {
            display: block;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .course-block strong { font-size: 13px; }
        .course-block span { margin-top: 2px; font-size: 12px; }
        .course-block small { margin-top: 2px; color: #475467; font-size: 11px; }
        .tba {
            padding: 12px 14px;
            border-top: 1px solid #e5e9f0;
            background: #fbfcfe;
            color: #475467;
            font-size: 13px;
        }
        .tba span { display: inline-block; margin: 4px 10px 0 0; }
        @media (max-width: 780px) {
            main { width: min(100vw - 20px, 1180px); margin-top: 14px; }
            form { grid-template-columns: 1fr; }
            .calendar-header { grid-template-columns: 58px repeat(5, minmax(86px, 1fr)); }
            .calendar-body { grid-template-columns: 58px 1fr; min-width: 560px; }
            .combination { overflow-x: auto; }
            .time-mark { font-size: 11px; right: 5px; }
        }
    </style>
</head>
<body>
    <main>
        <h1>SchedulePlanner</h1>
        <form id="schedule-form">
            <label>
                Course codes
                <textarea id="course-codes" spellcheck="false">AFAS UN1001
AMST UN3930</textarea>
            </label>
            <label>
                Take exactly
                <input id="target-course-count" type="number" min="1" max="10" placeholder="all">
            </label>
            <label>
                No class before
                <input id="no-class-before" type="text" placeholder="10am">
            </label>
            <label>
                No class after
                <input id="no-class-after" type="text" placeholder="5pm">
            </label>
            <button type="submit">Generate</button>
        </form>
        <div class="api-note">This page calls POST /api/schedules/combinations and renders that response.</div>

        <div id="message"><div class="summary">Loading sample schedules...</div></div>
        <div id="results"></div>
        <noscript>
            <div class="alert">JavaScript is required because this page tests the real POST /api/schedules/combinations endpoint from the browser.</div>
        </noscript>
    </main>
    <script>
        const dayColumns = [
            ["M", "Mon"],
            ["T", "Tue"],
            ["W", "Wed"],
            ["Th", "Thu"],
            ["F", "Fri"],
        ];
        const dayIndex = new Map(dayColumns.map(([day], index) => [day, index]));
        const courseColors = ["#2f6fed", "#0f8f76", "#c45a10", "#7a4cc2", "#b5365b", "#2d7d2d", "#7a5f11", "#1f7899"];
        const standardViewStart = 8 * 60;
        const standardViewEnd = 22 * 60;

        const form = document.querySelector("#schedule-form");
        const courseCodesInput = document.querySelector("#course-codes");
        const targetCourseCountInput = document.querySelector("#target-course-count");
        const noClassBeforeInput = document.querySelector("#no-class-before");
        const noClassAfterInput = document.querySelector("#no-class-after");
        const message = document.querySelector("#message");
        const results = document.querySelector("#results");

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const courseNumbers = parseCourseCodes(courseCodesInput.value);
            if (courseNumbers.length === 0) {
                renderMessage("Enter at least one course code.", "alert");
                results.replaceChildren();
                return;
            }

            renderMessage("Generating schedules...", "summary");
            results.replaceChildren();

            try {
                const requestBody = { course_numbers: courseNumbers };
                const targetCourseCount = parseTargetCourseCount();
                if (targetCourseCount !== null) {
                    requestBody.target_course_count = targetCourseCount;
                }
                const requirements = buildRequirements();
                if (Object.keys(requirements).length > 0) {
                    requestBody.requirements = requirements;
                }
                const response = await fetch("/api/schedules/combinations", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(requestBody),
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || "Could not generate schedules.");
                }
                renderResult(data);
            } catch (error) {
                renderMessage(error.message, "alert");
            }
        });

        form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

        function parseCourseCodes(value) {
            return value
                .split(/[\n,;]+/)
                .map((courseCode) => courseCode.trim())
                .filter(Boolean);
        }

        function buildRequirements() {
            const requirements = {};
            const noClassBefore = noClassBeforeInput.value.trim();
            const noClassAfter = noClassAfterInput.value.trim();
            if (noClassBefore) {
                requirements.no_class_before = noClassBefore;
            }
            if (noClassAfter) {
                requirements.no_class_after = noClassAfter;
            }
            return requirements;
        }

        function parseTargetCourseCount() {
            const value = targetCourseCountInput.value.trim();
            if (!value) {
                return null;
            }
            return Number(value);
        }

        function renderResult(data) {
            const missingCourses = Array.isArray(data.missing_course_numbers) ? data.missing_course_numbers : [];
            const summary = document.createElement("div");
            summary.className = "summary";
            summary.append(makeSummaryItem(data.total_valid_combinations || 0, "valid combinations"));
            summary.append(makeSummaryItem((data.combinations || []).length, "rendered"));
            if (data.target_course_count) {
                const targetItem = document.createElement("span");
                targetItem.innerHTML = `<strong>Taking:</strong> ${data.target_course_count} of ${data.matched_course_count}`;
                summary.append(targetItem);
            }
            const requirementText = formatRequirements(data.requirements || {});
            if (requirementText) {
                const requirementItem = document.createElement("span");
                requirementItem.innerHTML = `<strong>Requirements:</strong> ${requirementText}`;
                summary.append(requirementItem);
            }
            if (missingCourses.length > 0) {
                const missing = document.createElement("span");
                missing.innerHTML = `<strong>Missing:</strong> ${missingCourses.join(", ")}`;
                summary.append(missing);
            }
            message.replaceChildren(summary);

            if (!Array.isArray(data.combinations) || data.combinations.length === 0) {
                renderEmpty("No schedules to display.");
                return;
            }

            const fragment = document.createDocumentFragment();
            const scheduleRange = buildScheduleRange(data.combinations);
            data.combinations.forEach((combination) => {
                fragment.append(renderCombination(combination, scheduleRange));
            });
            results.replaceChildren(fragment);
        }

        function makeSummaryItem(value, label) {
            const item = document.createElement("span");
            item.innerHTML = `<strong>${value}</strong> ${label}`;
            return item;
        }

        function formatRequirements(requirements) {
            const parts = [];
            if (requirements.no_class_before) {
                parts.push(`no class before ${requirements.no_class_before}`);
            }
            if (requirements.no_class_after) {
                parts.push(`no class after ${requirements.no_class_after}`);
            }
            return parts.join(", ");
        }

        function renderCombination(combination, scheduleRange) {
            const schedule = buildVisualSchedule(combination, scheduleRange);
            const article = document.createElement("article");
            article.className = "combination";

            const header = document.createElement("header");
            const title = document.createElement("h2");
            title.textContent = `Combination ${schedule.combinationId}`;
            header.append(title);
            article.append(header);
            article.append(renderCalendarHeader());

            const calendarBody = document.createElement("div");
            calendarBody.className = "calendar-body";

            const timeRail = document.createElement("div");
            timeRail.className = "time-rail";
            schedule.timeMarks.forEach((mark) => {
                const timeMark = document.createElement("div");
                timeMark.className = "time-mark";
                timeMark.style.top = `${mark.top}%`;
                timeMark.textContent = mark.label;
                timeRail.append(timeMark);
            });

            const daysArea = document.createElement("div");
            daysArea.className = "days-area";
            dayColumns.forEach(() => {
                const column = document.createElement("div");
                column.className = "day-column";
                daysArea.append(column);
            });
            schedule.timeMarks.forEach((mark) => {
                const line = document.createElement("div");
                line.className = "hour-line";
                line.style.top = `${mark.top}%`;
                daysArea.append(line);
            });
            schedule.blocks.forEach((block) => daysArea.append(renderCourseBlock(block)));

            calendarBody.append(timeRail, daysArea);
            article.append(calendarBody);

            if (schedule.unscheduled.length > 0) {
                article.append(renderUnscheduled(schedule.unscheduled));
            }
            return article;
        }

        function renderCalendarHeader() {
            const header = document.createElement("div");
            header.className = "calendar-header";
            const timeCell = document.createElement("div");
            timeCell.textContent = "Time";
            header.append(timeCell);
            dayColumns.forEach(([, label]) => {
                const day = document.createElement("div");
                day.textContent = label;
                header.append(day);
            });
            return header;
        }

        function renderCourseBlock(block) {
            const element = document.createElement("div");
            element.className = "course-block";
            element.style.setProperty("--day", block.dayIndex);
            element.style.setProperty("--top", `${block.top}%`);
            element.style.setProperty("--height", `${block.height}%`);
            element.style.setProperty("--color", block.color);

            const title = document.createElement("strong");
            title.textContent = `${block.courseCode} ${block.section || ""}`.trim();
            const time = document.createElement("span");
            time.textContent = `${block.startTime}-${block.endTime}`;
            const details = document.createElement("small");
            details.textContent = `${block.daysText}${block.callNumber ? ` | call ${block.callNumber}` : ""}`;
            element.append(title, time, details);
            return element;
        }

        function renderUnscheduled(sections) {
            const element = document.createElement("div");
            element.className = "tba";
            element.append("TBA: ");
            sections.forEach((section) => {
                const item = document.createElement("span");
                item.textContent = `${section.course_code || "Unknown"} ${section.section || ""}`.trim();
                element.append(item);
            });
            return element;
        }

        function buildVisualSchedule(combination, scheduleRange) {
            const sections = Array.isArray(combination.sections) ? combination.sections : [];
            const blocks = [];
            const unscheduled = [];
            sections.forEach((section) => {
                const sectionBlocks = buildSectionBlocks(section);
                if (sectionBlocks.length === 0) {
                    unscheduled.push(section);
                } else {
                    blocks.push(...sectionBlocks);
                }
            });

            const viewStart = scheduleRange.viewStart;
            const viewEnd = scheduleRange.viewEnd;

            const visibleMinutes = viewEnd - viewStart;
            blocks.forEach((block) => {
                block.top = percentage(block.startMinutes - viewStart, visibleMinutes);
                block.height = percentage(block.endMinutes - block.startMinutes, visibleMinutes);
            });

            return {
                combinationId: combination.combination_id,
                timeMarks: buildTimeMarks(viewStart, viewEnd),
                blocks,
                unscheduled,
            };
        }

        function buildScheduleRange(combinations) {
            let viewStart = standardViewStart;
            let viewEnd = standardViewEnd;
            if (!Array.isArray(combinations)) {
                return { viewStart, viewEnd };
            }

            combinations.forEach((combination) => {
                const sections = Array.isArray(combination.sections) ? combination.sections : [];
                sections.forEach((section) => {
                    const startMinutes = parseTimeToMinutes(section.start_time);
                    const endMinutes = parseTimeToMinutes(section.end_time);
                    if (startMinutes === null || endMinutes === null || startMinutes >= endMinutes) {
                        return;
                    }
                    viewStart = Math.min(viewStart, Math.floor(startMinutes / 60) * 60);
                    viewEnd = Math.max(viewEnd, Math.ceil(endMinutes / 60) * 60);
                });
            });

            if (viewEnd <= viewStart) {
                viewEnd = viewStart + 60;
            }
            return { viewStart, viewEnd };
        }

        function buildSectionBlocks(section) {
            if (!Array.isArray(section.days) || !section.start_time || !section.end_time) {
                return [];
            }
            const startMinutes = parseTimeToMinutes(section.start_time);
            const endMinutes = parseTimeToMinutes(section.end_time);
            if (startMinutes === null || endMinutes === null || startMinutes >= endMinutes) {
                return [];
            }

            return section.days
                .map(normalizeDay)
                .filter((day) => dayIndex.has(day))
                .map((day) => ({
                    dayIndex: dayIndex.get(day),
                    courseCode: section.course_code,
                    section: section.section,
                    daysText: section.days.join("/"),
                    startTime: section.start_time,
                    endTime: section.end_time,
                    startMinutes,
                    endMinutes,
                    callNumber: section.call_number,
                    color: courseColor(section.course_code || ""),
                }));
        }

        function buildTimeMarks(viewStart, viewEnd) {
            const marks = [];
            const visibleMinutes = viewEnd - viewStart;
            for (let minutes = viewStart; minutes <= viewEnd; minutes += 60) {
                marks.push({
                    label: formatMinutes(minutes),
                    top: percentage(minutes - viewStart, visibleMinutes),
                });
            }
            return marks;
        }

        function parseTimeToMinutes(timeText) {
            const match = String(timeText).replace(/\s+/g, "").toLowerCase().match(/^(\d{1,2}):(\d{2})(am|pm)$/);
            if (!match) {
                return null;
            }
            let hour = Number(match[1]);
            const minute = Number(match[2]);
            const period = match[3];
            if (hour === 12) {
                hour = 0;
            }
            if (period === "pm") {
                hour += 12;
            }
            return hour * 60 + minute;
        }

        function normalizeDay(day) {
            const trimmed = String(day).trim();
            if (trimmed.toLowerCase() === "th" || trimmed.toUpperCase() === "R") {
                return "Th";
            }
            return trimmed;
        }

        function percentage(value, total) {
            return Math.round((value / total) * 10000) / 100;
        }

        function formatMinutes(minutes) {
            const hour = Math.floor(minutes / 60);
            const minute = minutes % 60;
            const period = hour < 12 ? "am" : "pm";
            const displayHour = hour % 12 || 12;
            return `${displayHour}:${String(minute).padStart(2, "0")}${period}`;
        }

        function courseColor(courseCode) {
            const index = [...courseCode].reduce((sum, character) => sum + character.charCodeAt(0), 0) % courseColors.length;
            return courseColors[index];
        }

        function renderMessage(text, className) {
            const element = document.createElement("div");
            element.className = className;
            element.textContent = text;
            message.replaceChildren(element);
        }

        function renderEmpty(text) {
            const element = document.createElement("div");
            element.className = "empty";
            element.textContent = text;
            results.replaceChildren(element);
        }
    </script>
</body>
</html>
"""
