import { useCourses } from '@/hooks/useCourses'
import { useSchedule } from '@/context/ScheduleContext'
import CourseCard from '@/components/CourseCard'

function SectionDivider({ label }) {
  return (
    <div className="text-center text-sm font-semibold text-gray-600 border border-gray-200 rounded-full px-4 py-1 my-2">
      {label}
    </div>
  )
}

function CourseList({ grouped }) {
  return (
    <div className="flex flex-col gap-3">
      {Object.entries(grouped).map(([code, course]) =>
        course.sections.map((section) => (
          <CourseCard
            key={`${code}-${section.section_id}`}
            code={code}
            name={course.name}
            days={section.days}
            start_time={section.start_time}
            end_time={section.end_time}
            prof_name={section.prof_name}
            section_id={section.section_id}
          />
        ))
      )}
    </div>
  )
}

function SelectedList({ grouped, selectedSections }) {
  return (
    <div className="flex flex-col gap-3">
      {selectedSections.map(({ code, section_id }) => {
        const course = grouped[code]
        if (!course) return null
        const section = course.sections.find(s => s.section_id === section_id)
        if (!section) return null
        return (
          <CourseCard
            key={`selected-${code}-${section_id}`}
            code={code}
            name={course.name}
            days={section.days}
            start_time={section.start_time}
            end_time={section.end_time}
            prof_name={section.prof_name}
            section_id={section_id}
          />
        )
      })}
    </div>
  )
}

function Dashboard() {
  const { grouped } = useCourses()
  const { selectedSections } = useSchedule()

  return (
    <div className="flex flex-col gap-3 p-4">
      <CourseList grouped={grouped} />
      <SectionDivider label="Your Courses" />
      <SelectedList grouped={grouped} selectedSections={selectedSections} />
    </div>
  )
}

export default Dashboard