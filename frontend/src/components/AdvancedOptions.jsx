import './AdvancedOptions.css'
import { useState } from 'react'
import { useSchedule } from '@/context/ScheduleContext'

function ChevronIcon({ open }) {
  return (
    <svg
      className={`advanced-options__chevron ${open ? 'advanced-options__chevron--open' : ''}`}
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
    >
      <path d="M3 5L7 9L11 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ToggleHeader({ open, onToggle }) {
  return (
    <button className="advanced-options__toggle" onClick={onToggle}>
      <span className="advanced-options__toggle-label">Advanced Options</span>
      <ChevronIcon open={open} />
    </button>
  )
}

function TimeField({ label, value, onChange, placeholder }) {
  return (
    <div className="advanced-options__field">
      <label className="advanced-options__label">{label}</label>
      <input
        className="advanced-options__input"
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

function CourseCountField({ value, onChange, max }) {
  return (
    <div className="advanced-options__field">
      <label className="advanced-options__label">Exact number of courses</label>
      <input
        className="advanced-options__input"
        type="number"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="All selected"
        min={1}
        max={max}
      />
    </div>
  )
}

function AdvancedOptions() {
  const [open, setOpen] = useState(false)
  const {
    requirements,
    setRequirements,
    targetCourseCount,
    setTargetCourseCount,
    selectedSections
  } = useSchedule()

  const selectedCourseCount = [...new Set(selectedSections.map(s => s.code))].length

  function handleBeforeChange(value) {
    setRequirements(prev => ({ ...prev, no_class_before: value }))
  }

  function handleAfterChange(value) {
    setRequirements(prev => ({ ...prev, no_class_after: value }))
  }

  return (
    <div className="advanced-options">
      <ToggleHeader open={open} onToggle={() => setOpen(prev => !prev)} />

      {open && (
        <div className="advanced-options__panel">
          <TimeField
            label="No class before"
            value={requirements.no_class_before}
            onChange={handleBeforeChange}
            placeholder="e.g. 10am"
          />
          <TimeField
            label="No class after"
            value={requirements.no_class_after}
            onChange={handleAfterChange}
            placeholder="e.g. 6pm"
          />
          <CourseCountField
            value={targetCourseCount}
            onChange={setTargetCourseCount}
            max={selectedCourseCount}
          />
        </div>
      )}
    </div>
  )
}

export default AdvancedOptions