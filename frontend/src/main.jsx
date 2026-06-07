import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ScheduleProvider } from '@/context/ScheduleContext'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ScheduleProvider>
      <App />
    </ScheduleProvider>
  </StrictMode>
)