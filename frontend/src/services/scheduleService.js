const BASE = import.meta.env.VITE_API_BASE_URL

export async function generateSchedule(courseNumbers, requirements = {}, targetCourseCount) {
  const response = await fetch(`${BASE}/api/schedules/combinations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      course_numbers: courseNumbers,
      requirements,
      target_course_count: targetCourseCount || null
    })
  })

  if (!response.ok) {
    const error = await response.json()
    console.log(error)
    throw new Error(error.message || 'Failed to generate schedule')
  }
  return response.json()
}