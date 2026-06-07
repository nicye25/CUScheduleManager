import { useSchedule } from '@/context/ScheduleContext'
import './CourseCard.css'

function DayTimeRow({ days, start_time, end_time }) {
  const dayString = Array.isArray(days) ? days.join('') : days
  return (
    <div className="course-card__daytime">
      <span className="course-card__daytime-dot" />
      <span>{dayString}, {start_time}-{end_time}</span>
    </div>
  )
}

function ProfessorRow({ prof_name }) {
  return (
    <div className="course-card__professor">
      <span>👤</span>
      <span>{prof_name}</span>
    </div>
  )
}

function AddButton({ onClick }) {
  return (
    <button onClick={onClick} className="course-card__btn course-card__btn--add">
      Add
    </button>
  )
}

function RemoveButton({ onClick }) {
  return (
    <button onClick={onClick} className="course-card__btn course-card__btn--remove">
      Remove
    </button>
  )
}

function CourseCard({ code, name, days, start_time, end_time, prof_name, section_id }) {
  const { addSection, removeSection, selectedSections } = useSchedule()
  const isSelected = selectedSections.some(s => s.code === code && s.section_id === section_id)

  return (
    <div className="course-card">
      <p className="course-card__code">{code}</p>
      <p className="course-card__name">{name}</p>
      <DayTimeRow days={days} start_time={start_time} end_time={end_time} />
      <div className="course-card__bottom-row">
        <ProfessorRow prof_name={prof_name} />
        {isSelected
          ? <RemoveButton onClick={() => removeSection(code, section_id)} />
          : <AddButton onClick={() => addSection(code, section_id)} />
        }
      </div>
    </div>
  )
}

export default CourseCard