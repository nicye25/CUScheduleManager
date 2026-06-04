import { useCourses } from '@/hooks/useCourses'
import Dashboard from '@/pages/Dashboard'
import { useState } from 'react'
import './App.css'

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
