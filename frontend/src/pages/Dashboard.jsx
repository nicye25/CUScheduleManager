import { useCourses } from '@/hooks/useCourses'
import CourseCard from '@/components/CourseCard'

function Dashboard() {
  const { grouped } = useCourses()

  return (
    <div>
      {Object.entries(grouped).map(([code, course]) => (
        <CourseCard key={code} code={code} {...course} />
      ))}
    </div>
  )
}
export default Dashboard