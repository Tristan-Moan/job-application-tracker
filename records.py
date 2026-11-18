"""Trusted table definitions used by the forms, validation and SQL builders."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "text"
    limit: int = 0
    required: bool = False
    choices: tuple = ()


TYPES = ("Full-time", "Part-time", "Contract", "Internship")
STAGES = ("Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn")
COMPANY = Field("company_id", "Company", "companies", required=True)
FIELDS = {
    "companies": (
        Field("company_name", "Company name", limit=100, required=True),
        Field("industry", "Industry", limit=50), Field("website", "Website", "url", 200),
        Field("city", "City", limit=50), Field("state", "State or region", limit=50),
        Field("notes", "Notes", "textarea"),
    ),
    "jobs": (
        Field("job_title", "Job title", limit=100, required=True), COMPANY,
        Field("job_type", "Job type", "select", choices=TYPES),
        Field("salary_min", "Minimum annual salary ($)", "number"),
        Field("salary_max", "Maximum annual salary ($)", "number"),
        Field("job_url", "Job posting URL", "url", 300),
        Field("date_posted", "Date posted", "date"),
        Field("requirements", "Required skills", "skills"),
    ),
    "applications": (
        Field("job_id", "Job", "jobs", required=True),
        Field("application_date", "Application date", "date", required=True),
        Field("status", "Status", "select", required=True, choices=STAGES),
        Field("resume_version", "Resume version", limit=50),
        Field("cover_letter_sent", "Cover letter sent", "checkbox"),
        Field("interview_data", "Interview details", "json"),
    ),
    "contacts": (
        Field("contact_name", "Contact name", limit=100, required=True), COMPANY,
        Field("title", "Position", limit=100), Field("email", "Email", "email", 100),
        Field("phone", "Phone", "tel", 20), Field("linkedin_url", "LinkedIn URL", "url", 200),
        Field("notes", "Notes", "textarea"),
    ),
}
SINGULAR = dict(companies="company", jobs="job", applications="application", contacts="contact")
COLUMNS = {
    "companies": ("company_name", "industry", "city", "state"),
    "jobs": ("job_title", "company_name", "job_type", "date_posted"),
    "applications": ("job_title", "company_name", "application_date", "status"),
    "contacts": ("contact_name", "company_name", "title", "email"),
}
# Only these hardcoded identifiers are interpolated. User values use parameters.
SELECT = {
    "companies": "SELECT companies.* FROM companies",
    "jobs": "SELECT jobs.*, company_name FROM jobs JOIN companies USING (company_id)",
    "applications": """SELECT applications.*, job_title, company_name FROM applications
                       JOIN jobs USING (job_id) JOIN companies USING (company_id)""",
    "contacts": "SELECT contacts.*, company_name FROM contacts JOIN companies USING (company_id)",
}
LABELS = {f.key: f.label for fields in FIELDS.values() for f in fields}
LABELS.update(company_name="Company", job_title="Job title")
