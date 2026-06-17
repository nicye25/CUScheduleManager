import './Dashboard.css'
import { useState, useRef } from 'react'
import { useCourses } from '@/hooks/useCourses'
import CourseCard from '@/components/CourseCard'
import ScheduleGrid from '@/components/ScheduleGrid'
import { useSchedule } from '@/context/ScheduleContext'
import GenerateButton from '@/components/GenerateButton'
import DashboardHeader from '@/components/DashboardHeader'

function SectionDivider({ label }) {
    return (
        <div
            className="dashboard__divider">
            {label}
        </div>
    )
}

function ResizeHandle({ onPointerDown }) {
    return (
        <div
            className="dashboard__resize-handle"
            onPointerDown={onPointerDown}
        />
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
    const [topPanelRatio, setTopPanelRatio] = useState(0.5)
    const sidebarRef = useRef(null)
    const isDraggingRef = useRef(false)

    const handleResizePointerDown = (e) => {
        if (!sidebarRef.current) return

        isDraggingRef.current = true
        e.currentTarget.setPointerCapture(e.pointerId)
        document.body.style.userSelect = 'none'
        document.body.style.cursor = 'row-resize'
    }

    const handleResizePointerMove = (e) => {
        if (!isDraggingRef.current || !sidebarRef.current) return

        const sidebarRect = sidebarRef.current.getBoundingClientRect()
        const relativeY = e.clientY - sidebarRect.top
        const newRatio = Math.max(0.2, Math.min(0.8, relativeY / sidebarRect.height))

        setTopPanelRatio(newRatio)
    }

    const handleResizePointerUp = () => {
        isDraggingRef.current = false
        document.body.style.userSelect = ''
        document.body.style.cursor = ''
    }

    return (
        <div className="dashboard__parent">
            <div
                className="dashboard__sidebar"
                ref={sidebarRef}
                onPointerMove={handleResizePointerMove}
                onPointerUp={handleResizePointerUp}
                onPointerLeave={handleResizePointerUp}
            >

                <div className="dashboard__panel" style={{ flex: topPanelRatio }}>
                    <div className="dashboard__divider">All Courses</div>
                    {/* <SectionDivider label="All Courses" /> */}
                    <CourseList grouped={grouped} />
                </div>

                <ResizeHandle onPointerDown={handleResizePointerDown} />

                <div className="dashboard__panel dashboard__panel--selected" style={{ flex: 1 - topPanelRatio }}>
                    <div className="dashboard__divider dashboard__divider--selected">Your Courses</div>
                    {/* <SectionDivider label="Your Courses" /> */}
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