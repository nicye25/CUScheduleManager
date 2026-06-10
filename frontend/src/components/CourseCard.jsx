import { useSchedule } from '@/context/ScheduleContext'
import './CourseCard.css'

// Old, for when each individual section was listed
// function DayTimeRow({ days, start_time, end_time }) {
//   const dayString = Array.isArray(days) ? days.join('') : days
//   return (
//     <div className="course-card__daytime">
//       <span className="course-card__daytime-dot" />
//       <span>{dayString}, {start_time}-{end_time}</span>
//     </div>
//   )
// }

// function ProfessorRow({ prof_name }) {
//   return (
//     <div className="course-card__professor">
//       <span>👤</span>
//       <span>{prof_name}</span>
//     </div>
//   )
// }

function SectionCountRow({ count }) {
  return (
    <div className="course-card__sections">
      <span className="course-card__sections-dot" />
      <span>{count} section{count !== 1 ? 's' : ''}</span>
    </div>
  )
}

function ProfessorRow({ professors }) {
  const uniqueProfessors = [...new Set(professors.filter(Boolean))]
  return (
    <div className="course-card__professor">
      <span>👤</span>
      <span>{uniqueProfessors.join(', ')}</span>
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

function CourseCard({ code, name, sections }) {
  const { addSection, removeSection, selectedSections } = useSchedule()
  const isSelected = sections.some(section =>
    selectedSections.some(s => s.code === code && s.section_id === section.section_id)
  )

  function handleAdd() {
    sections.forEach(section => addSection(code, section.section_id))
  }

  function handleRemove() {
    sections.forEach(section => removeSection(code, section.section_id))
  }

  const professors = sections.map(s => s.prof_name)

  return (
    <div className="course-card">
      <p className="course-card__code">{code}</p>
      <p className="course-card__name">{name}</p>
      <SectionCountRow count={sections.length} />
      <div className="course-card__bottom-row">
        <ProfessorRow professors={professors} />
        {isSelected
          ? <RemoveButton onClick={handleRemove} />
          : <AddButton onClick={handleAdd} />
        }
      </div>
    </div>
  )
}

export default CourseCard