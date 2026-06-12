export function groupByCode(sections) {
    return sections.reduce((acc, section) => {
        const key = section.course_code
        if (!acc[key]) {
            acc[key] = {
                name: section.name,
                // prof_name: section.prof_name,
                credit_hrs: section.credit_hrs,
                department: section.department,
                sections: []
            }
        }
        acc[key].sections.push({
            section_id: section.section,
            course_id: section.course_id,
            call_number: section["call number"],
            prof_name: section.prof_name,
            days: section.days,
            start_time: section.start_time,
            end_time: section.end_time,
            location: section.location
        })

        return acc
    }, {})
}