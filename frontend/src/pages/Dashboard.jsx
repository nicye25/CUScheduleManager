import { useCourses } from '@/hooks/useCourses'
import { useSchedule } from '@/context/ScheduleContext'
import CourseCard from '@/components/CourseCard'
import GenerateButton from '@/components/GenerateButton'
import './Dashboard.css'

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
        <div className="dashboard__scroll-section">
            {selectedSections.length === 0
                ? <p className="dashboard__empty">No courses added yet.</p>
                : selectedSections.map(({ code, section_id }) => {
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

            {combinations.length > 0 && (
                <pre className="dashboard__debug">
                    {JSON.stringify(combinations[0], null, 2)}
                </pre>
            )}

        </div>
    )
}

export default Dashboard