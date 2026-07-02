import { useSchedule } from '@/context/ScheduleContext'
import './ScheduleGrid.css'

// ─── Configuration ────────────────────────────────────────────────────────────
// Edit these to change grid range and slot size
const GRID_START_HOUR = 8        // 8 AM
const GRID_END_HOUR   = 22       // 10 PM
const SLOT_HEIGHT_PX  = 60       // pixels per hour

const DAYS = ['Mon', 'Tue', 'Wed', 'Thurs', 'Fri']

// One color per course — add more if needed
const COURSE_COLORS = [
  { bg: '#DBEAFE', border: '#3B82F6', text: '#1E40AF' }, // blue
  { bg: '#D1FAE5', border: '#10B981', text: '#065F46' }, // green
  { bg: '#FEE2E2', border: '#F87171', text: '#991B1B' }, // red
  { bg: '#FEF3C7', border: '#F59E0B', text: '#92400E' }, // yellow
  { bg: '#EDE9FE', border: '#8B5CF6', text: '#4C1D95' }, // purple
  { bg: '#FFEDD5', border: '#FB923C', text: '#9A3412' }, // orange
  { bg: '#FCE7F3', border: '#EC4899', text: '#9D174D' }, // pink
  { bg: '#CFFAFE', border: '#06B6D4', text: '#164E63' }, // cyan
]

// ─── Helpers ──────────────────────────────────────────────────────────────────

// "4:10pm" → minutes since midnight
function parseTimeToMinutes(timeStr) {
  if (!timeStr) return null
  const match = timeStr.replace(' ', '').toLowerCase().match(/^(\d{1,2})(?::(\d{2}))?(am|pm)$/)
  if (!match) return null
  let hour = parseInt(match[1])
  const minute = parseInt(match[2] || '0')
  const period = match[3]
  if (hour === 12) hour = 0
  if (period === 'pm') hour += 12
  return hour * 60 + minute
}

// minutes since midnight → px offset from grid top
function minutesToPx(minutes) {
  return ((minutes - GRID_START_HOUR * 60) / 60) * SLOT_HEIGHT_PX
}

// normalize day abbreviations to match DAYS array
function normalizeDay(day) {
  const map = {
    'm': 'Mon', 'mon': 'Mon', 'monday': 'Mon',
    't': 'Tue', 'tu': 'Tue', 'tue': 'Tue', 'tues': 'Tue', 'tuesday': 'Tue',
    'w': 'Wed', 'wed': 'Wed', 'wednesday': 'Wed',
    'th': 'Thurs', 'thu': 'Thurs', 'thur': 'Thurs', 'thurs': 'Thurs', 'thursday': 'Thurs', 'r': 'Thurs',
    'f': 'Fri', 'fri': 'Fri', 'friday': 'Fri',
  }
  return map[day.toLowerCase()] ?? null
}

// assign a stable color index per course code
function buildColorMap(sections) {
  const codes = [...new Set(sections.map(s => s.course_code))]
  return Object.fromEntries(codes.map((code, i) => [code, COURSE_COLORS[i % COURSE_COLORS.length]]))
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function TimeLabels() {
  const hours = []
  for (let h = GRID_START_HOUR; h <= GRID_END_HOUR; h++) {
    const label = h === 12 ? '12 PM' : h < 12 ? `${h} AM` : `${h - 12} PM`
    hours.push(
      <div
        key={h}
        className="schedule-grid__time-label"
        style={{ top: (h - GRID_START_HOUR) * SLOT_HEIGHT_PX }}
      >
        {label}
      </div>
    )
  }
  return <div className="schedule-grid__time-col">{hours}</div>
}

function HourLines() {
  const lines = []
  for (let h = GRID_START_HOUR; h <= GRID_END_HOUR; h++) {
    lines.push(
      <div
        key={h}
        className="schedule-grid__hour-line"
        style={{ top: (h - GRID_START_HOUR) * SLOT_HEIGHT_PX }}
      />
    )
  }
  return <>{lines}</>
}

function CourseBlock({ section, color }) {
  const startMin = parseTimeToMinutes(section.start_time)
  const endMin   = parseTimeToMinutes(section.end_time)
  if (startMin === null || endMin === null) return null

  const top    = minutesToPx(startMin)
  const height = minutesToPx(endMin) - top

  // format time for display e.g. "4:10–5:25pm"
  const timeLabel = `${section.start_time}–${section.end_time}`

  return (
    <div
      className="schedule-grid__block"
      style={{
        top,
        height,
        backgroundColor: color.bg,
        borderLeft: `3px solid ${color.border}`,
        color: color.text,
      }}
    >
      <span className="schedule-grid__block-code">{section.course_code}</span>
      <span className="schedule-grid__block-time">{timeLabel}</span>
      {section.section && (
        <span className="schedule-grid__block-section">§{section.section}</span>
      )}
      {section.prof_name && (
        <span className="schedule-grid__block-prof">👤 {section.prof_name}</span>
      )}
      {section.location && (
        <span className="schedule-grid__block-location">📍 {section.location}</span>
      )}
    </div>
  )
}

function DayColumn({ day, sections, colorMap }) {
  const daySections = sections.filter(s =>
    (s.days ?? []).some(d => normalizeDay(d) === day)
  )

  return (
    <div className="schedule-grid__day-col">
      <HourLines />
      {daySections.map((section, i) => (
        <CourseBlock
          key={`${section.course_code}-${section.section}-${i}`}
          section={section}
          color={colorMap[section.course_code] ?? COURSE_COLORS[0]}
        />
      ))}
    </div>
  )
}

function CombinationNav({ index, total, onPrev, onNext, requested, exact, requirements }) {
  const hasBefore = requirements.no_class_before
  const hasAfter = requirements.no_class_after
  const hasTimePref = hasBefore || hasAfter

  return (
    <div className="schedule-grid__nav">
      <span className="schedule-grid__nav-label">
        Schedule {index + 1} of {total}
      </span>
      <div className="schedule-grid__nav-reqs">
        <span className="schedule-grid__nav-exact">
          Taking {exact} of {requested} classes
        </span>
        {hasTimePref && (
          <span className="schedule-grid__nav-times">
            {hasBefore && <span>After {requirements.no_class_before}</span>}
            {hasAfter && <span> & before {requirements.no_class_after}</span>}
          </span>
        )}
      </div>
      <div className="schedule-grid__nav-btns">
        <button
          className="schedule-grid__nav-btn"
          onClick={onPrev}
          disabled={index === 0}
          aria-label="Previous schedule"
        >
          ‹
        </button>
        <button
          className="schedule-grid__nav-btn"
          onClick={onNext}
          disabled={index === total - 1}
          aria-label="Next schedule"
        >
          ›
        </button>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="schedule-grid__empty">
      <p>Add courses and generate a schedule to see results here.</p>
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

function ScheduleGrid() {
  const { combinations, activeCombinationIndex, setActiveCombinationIndex, activeTargetCourseCount,
    activeRequirements, activeRequestedCourseCount} = useSchedule()

  const hasCombinations = combinations.length > 0
  const activeCombination = hasCombinations ? combinations[activeCombinationIndex] : null
  const sections = activeCombination?.sections ?? []
  const colorMap = buildColorMap(sections)

  const totalHeight = (GRID_END_HOUR - GRID_START_HOUR) * SLOT_HEIGHT_PX

  return (
    <div className="schedule-grid">

      {/* Day headers */}
      <div className="schedule-grid__header">
        <div className="schedule-grid__header-offset" /> {/* aligns with time col */}
        {DAYS.map(day => (
          <div key={day} className="schedule-grid__header-day">{day}</div>
        ))}
      </div>

      {/* Grid body */}
      <div className="schedule-grid__body">
        <TimeLabels />
        <div className="schedule-grid__columns" style={{ height: totalHeight }}>
          {DAYS.map(day => (
            <DayColumn key={day} day={day} sections={sections} colorMap={colorMap} />
          ))}
        </div>

        {!hasCombinations && <EmptyState />}
      </div>
      
      {/* Navigation */}
      {hasCombinations && (
        <CombinationNav
          index={activeCombinationIndex}
          total={combinations.length}
          onPrev={() => setActiveCombinationIndex(i => Math.max(0, i - 1))}
          onNext={() => setActiveCombinationIndex(i => Math.min(combinations.length - 1, i + 1))}
          requested={activeRequestedCourseCount}
          exact={activeTargetCourseCount}
          requirements={activeRequirements}
        />
      )}

    </div>
  )
}

export default ScheduleGrid
