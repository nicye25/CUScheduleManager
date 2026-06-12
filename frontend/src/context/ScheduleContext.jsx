import { createContext, useContext, useState } from 'react'
import { generateSchedule } from '@/services/scheduleService'

const ScheduleContext = createContext(null)

export function ScheduleProvider({ children }) {
  const [selectedSections, setSelectedSections] = useState([])
  const [requirements, setRequirements] = useState({ no_class_before: '', no_class_after: '' })
  const [combinations, setCombinations] = useState([])
  const [activeCombinationIndex, setActiveCombinationIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

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
      const result = await generateSchedule(courseNumbers, requirements)
      setCombinations(result.combinations)
      setActiveCombinationIndex(0)
      console.log('Schedule result:', result)  // inspect full response
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