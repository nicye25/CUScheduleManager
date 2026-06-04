function CourseCard({ code, name, department, credit_hrs, sections }) {
  return (
    <div>
      <h3>{code} — {name}</h3>
      <p>{department} | {credit_hrs} credits</p>
      <p>{sections.length} section(s)</p>
    </div>
  )
}
export default CourseCard