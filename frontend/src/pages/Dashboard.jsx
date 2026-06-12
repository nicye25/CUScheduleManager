import './Dashboard.css'
import { useCourses } from '@/hooks/useCourses'
import CourseCard from '@/components/CourseCard'
import ScheduleGrid from '@/components/ScheduleGrid'
import { useSchedule } from '@/context/ScheduleContext'
import GenerateButton from '@/components/GenerateButton'

function SectionDivider({ label }) {
    return (
        <div className="dashboard__divider">
            {label}
        </div>
    )
}

function CourseList({ grouped }) {
    return (
        <div className="dashboard__scroll-section">
            {Object.entries(grouped).map(([code, course]) => (
                <CourseCard
                    key={code}
                    code={code}
                    name={course.name}
                    sections={course.sections}
                />
            ))}
        </div>
    )
}

function SelectedList({ grouped, selectedSections }) {
    const selectedCodes = [...new Set(selectedSections.map(s => s.code))]

    return (
        <div className="dashboard__scroll-section">
            {selectedCodes.length === 0
                ? <p className="dashboard__empty">No courses added yet.</p>
                : selectedCodes.map(code => {
                    const course = grouped[code]
                    if (!course) return null
                    return (
                        <CourseCard
                            key={`selected-${code}`}
                            code={code}
                            name={course.name}
                            sections={course.sections}
                        />
                    )
                })
            }
        </div>
    )
}


function Dashboard() {
    const { grouped } = useCourses()
    const { selectedSections, handleGenerate, loading, error, combinations } = useSchedule()
    // const { selectedSections } = useSchedule()

    return (
        <div className="dashboard__parent">
            <div className="dashboard__sidebar">

                <div className="dashboard__panel">
                    <SectionDivider label="All Courses" />
                    <CourseList grouped={grouped} />
                </div>

                <div className="dashboard__panel">
                    <SectionDivider label="Your Courses" />
                    <SelectedList grouped={grouped} selectedSections={selectedSections} />
                </div>

                <div className="dashboard__footer">
                    {error && <p className="dashboard__error">{error}</p>}
                    <GenerateButton
                        onClick={handleGenerate}
                        loading={loading}
                        disabled={selectedSections.length === 0}
                    />
                </div>

                {/* {combinations.length > 0 && (
                <pre className="dashboard__debug">
                    {JSON.stringify(combinations[0], null, 2)}
                </pre>
            )} */}
            </div>
            <main className="dashboard__main">
                <ScheduleGrid />
            </main>
        </div>

    )
}

export default Dashboard