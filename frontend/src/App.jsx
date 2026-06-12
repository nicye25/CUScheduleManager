import { useState } from 'react'
import Dashboard from '@/pages/Dashboard'
import { useCourses } from '@/hooks/useCourses'
import DashboardHeader from '@/components/DashboardHeader'

function App() {
  const [count, setCount] = useState(0)
  const { grouped, flat } = useCourses()

  return (
   <div>
    {/* <DashboardHeader /> */}
    <Dashboard />
   </div>
  )
}

export default App
