import rawData from '@/data/fall_2026_all_courses_flat.json'
import { groupByCode } from '@/utils/transformCourses'

export function useCourses() {
    const grouped = groupByCode(rawData)
    const flat = rawData

    return {grouped, flat}
}