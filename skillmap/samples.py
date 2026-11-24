"""Fictional sample data used by `seed_demo` and by the tests. Not a real person or company."""

SAMPLE_RESUME = """ASHA KULKARNI
Pune, Maharashtra | 9000000000 | asha.demo@example.com
github.com/asha-demo | linkedin.com/in/asha-demo

SUMMARY
Python/Django developer and B.Sc. Computer Science graduate who built a job portal with user
authentication, resume uploads and an admin panel using Django and PostgreSQL.
Seeking an entry-level Python backend developer role.

EDUCATION
B.Sc. Computer Science, Example College, Pune | 2023-2026 | CGPA 8.9

TECHNICAL SKILLS
Languages: Python, SQL
Framework: Django (ORM, Admin)
Database: PostgreSQL, relational design and normalization
Frontend: HTML, CSS
Tools: Git, VS Code

PROJECTS
Job Portal (academic project)
- Designed a normalized PostgreSQL schema with 3 tables linked by foreign keys.
- Built registration, login and profile management with resume upload.
- Implemented keyword job search and an application tracking dashboard.
- Wrote 12 unit tests covering models and views.
- Configured Django Admin for managing job postings and reviewing applications.

CERTIFICATIONS
Full Stack Web Development, Grade A

STRENGTHS
Quick learner and team player. Responsible for writing clean, readable code in every project.
"""

SAMPLE_JOBS = [
    {
        "title": "Junior Python Developer",
        "company": "Example Tech Pvt Ltd (fictional)",
        "text": """Junior Python Developer

Requirements
- Python and the Django framework
- SQL and PostgreSQL
- Building REST APIs
- Git and pull requests

Nice to have
- Docker
- Unit testing with pytest
- Basic AWS knowledge
""",
    },
    {
        "title": "Backend Engineer",
        "company": "Sample Cloud Co (fictional)",
        "text": """Backend Engineer

Responsibilities
Design and ship backend services, own deployment and monitoring.

Must have
- Python or Java
- REST APIs and microservices
- PostgreSQL and Redis
- Docker and CI/CD pipelines
- Automated testing

Bonus points
- Kubernetes
- Message queues such as Kafka
""",
    },
    {
        "title": "Full Stack Developer",
        "company": "Demo Apps Ltd (fictional)",
        "text": """Full Stack Developer

Requirements
- JavaScript, React and HTML/CSS
- Node.js and Express
- MongoDB

Preferred
- TypeScript
- Responsive design
""",
    },
]
