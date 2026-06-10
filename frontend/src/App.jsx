import { useState } from 'react'
import Dashboard from '@/pages/Dashboard'
import { useCourses } from '@/hooks/useCourses'
import ScheduleGrid from '@/components/ScheduleGrid'

function App() {
  const [count, setCount] = useState(0)
  const { grouped, flat } = useCourses()

  return (
   <div>
    <Dashboard />
   </div>
  )
}

export default App
