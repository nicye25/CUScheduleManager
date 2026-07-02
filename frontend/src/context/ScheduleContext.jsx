import { createContext, useContext, useState } from 'react'
import { generateSchedule } from '@/services/scheduleService'

const ScheduleContext = createContext(null)

export function ScheduleProvider({ children }) {
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [combinations, setCombinations] = useState([])
  const [selectedSections, setSelectedSections] = useState([])
  const [targetCourseCount, setTargetCourseCount] = useState('')
  const [activeCombinationIndex, setActiveCombinationIndex] = useState(0)
  const [requirements, setRequirements] = useState({ no_class_before: '', no_class_after: '' })

  const [activeRequirements, setActiveRequirements] = useState({})
  const [activeTargetCourseCount, setActiveTargetCourseCount] = useState(0)
  const [activeRequestedCourseCount, setActiveRequestedCourseCount] = useState(0)

  function addSection(code, section_id) {
    const alreadyAdded = selectedSections.some(s => s.code === code && s.section_id === section_id)
    if (alreadyAdded) return
    setSelectedSections(prev => [...prev, { code, section_id }])
  }

  function removeSection(code, section_id) {
    setSelectedSections(prev =>
      prev.filter(s => !(s.code === code && s.section_id === section_id))
    )
  }

  // extract unique course codes from selected sections
  function getSelectedCourseCodes() {
    return [...new Set(selectedSections.map(s => s.code))]
  }

  async function handleGenerate() {
    const courseNumbers = getSelectedCourseCodes()
    if (courseNumbers.length === 0) return

    setLoading(true)
    setError(null)
    setCombinations([])

    try {
      const result = await generateSchedule(courseNumbers, requirements, Number(targetCourseCount) || null)
      // console.log(Number(targetCourseCount))
      setActiveTargetCourseCount(result.target_course_count)
      setActiveRequirements(result.requirements)
      setActiveRequestedCourseCount(result.requested_course_count)
      // console.log(result.target_course_count)
      // console.log(result.requirements)
      setCombinations(result.combinations)
      setActiveCombinationIndex(0)
      // console.log('Schedule result:', result)  // inspect full response
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setSelectedSections([])
    setCombinations([])
    setActiveCombinationIndex(0)
    setRequirements({ no_class_before: '', no_class_after: '' })
    setTargetCourseCount('')
    setActiveTargetCourseCount(0)
    setActiveRequestedCourseCount(0)
    setActiveRequirements({ no_class_before: '', no_class_after: '' })
    setError(null)
  }

  return (
    <ScheduleContext.Provider value={{
      selectedSections,
      requirements,
      setRequirements,
      combinations,
      setCombinations,
      activeCombinationIndex,
      setActiveCombinationIndex,
      targetCourseCount,
      setTargetCourseCount,
      activeTargetCourseCount,
      activeRequirements,
      activeRequestedCourseCount,
      loading,
      error,
      addSection,
      removeSection,
      handleGenerate,
      reset
    }}>
      {children}
    </ScheduleContext.Provider>
  )
}

export function useSchedule() {
  const context = useContext(ScheduleContext)
  if (!context) throw new Error('useSchedule must be used within a ScheduleProvider')
  return context
}