"""The starting skill taxonomy.

Each entry is (name, category, aliases, prerequisites).
  * aliases: other spellings the text matcher should treat as the same skill
  * prerequisites: skills best learned first (drives the learning-path order)

This is loaded into the database by the data migration and by `manage.py seed_skills`,
and then edited from the Django admin. Keep the graph acyclic (a test checks this).

Known limits, on purpose: names that are also ordinary words ("C", "Go", "Swift", "Excel",
"Express") are listed in NAME_NOT_MATCHED, so only their aliases ("C programming", "Golang",
"Microsoft Excel") count. Skills like "R" are left out entirely. Matching is keyword-based,
so a skill you only *describe* without naming it will not be detected.
"""

# Skills whose bare name is too ambiguous to match; only their aliases are used.
NAME_NOT_MATCHED = {"C", "Go", "Swift", "Excel", "Express"}

LANG = "Language"
BACKEND = "Backend"
FRONTEND = "Frontend"
DB = "Database"
DEVOPS = "DevOps & Cloud"
TESTING = "Testing"
CS = "CS fundamentals"
DATA = "Data & AI"
TOOLS = "Tools & process"

TAXONOMY = [
    # ----------------------------------------------------------- languages
    ("Python", LANG, ("python3",), ()),
    ("JavaScript", LANG, ("ecmascript", "es6"), ()),
    ("TypeScript", LANG, (), ("JavaScript",)),
    ("Java", LANG, ("core java",), ("OOP",)),
    ("C++", LANG, ("cpp",), ("OOP",)),
    ("C#", LANG, ("csharp", "c sharp"), ("OOP",)),
    ("C", LANG, ("c programming", "c language"), ()),
    ("Go", LANG, ("golang", "go language", "go programming"), ()),
    ("Rust", LANG, (), ()),
    ("PHP", LANG, (), ()),
    ("Ruby", LANG, (), ()),
    ("Kotlin", LANG, (), ("Java",)),
    ("Swift", LANG, ("swiftui", "swift programming"), ()),
    ("SQL", LANG, ("sql queries", "structured query language"), ()),
    ("Bash", LANG, ("shell scripting", "shell script", "bash scripting"), ("Linux",)),
    # ----------------------------------------------------------- frontend
    ("HTML", FRONTEND, ("html5",), ()),
    ("CSS", FRONTEND, ("css3",), ("HTML",)),
    ("Responsive Design", FRONTEND, ("responsive web design", "mobile-first", "mobile first"), ("CSS",)),
    ("Bootstrap", FRONTEND, (), ("CSS",)),
    ("Tailwind CSS", FRONTEND, ("tailwind", "tailwindcss"), ("CSS",)),
    ("jQuery", FRONTEND, (), ("JavaScript",)),
    ("React", FRONTEND, ("reactjs", "react.js"), ("JavaScript", "HTML", "CSS")),
    ("Next.js", FRONTEND, ("nextjs",), ("React",)),
    ("Angular", FRONTEND, ("angularjs",), ("TypeScript",)),
    ("Vue", FRONTEND, ("vue.js", "vuejs"), ("JavaScript",)),
    # ------------------------------------------------------------ backend
    ("Django", BACKEND, (), ("Python",)),
    ("Django REST Framework", BACKEND, ("drf", "django rest"), ("Django", "REST APIs")),
    ("Flask", BACKEND, (), ("Python",)),
    ("FastAPI", BACKEND, (), ("Python", "REST APIs")),
    ("Node.js", BACKEND, ("nodejs", "node js"), ("JavaScript",)),
    ("Express", BACKEND, ("express.js", "expressjs"), ("Node.js",)),
    ("Spring Boot", BACKEND, ("spring", "spring framework"), ("Java",)),
    (".NET", BACKEND, ("dotnet", "asp.net", ".net core"), ("C#",)),
    ("Laravel", BACKEND, (), ("PHP",)),
    ("Ruby on Rails", BACKEND, ("rails",), ("Ruby",)),
    ("REST APIs", BACKEND, ("restful", "rest api", "restful apis", "restful api", "web services"), ()),
    ("GraphQL", BACKEND, (), ("REST APIs",)),
    ("WebSockets", BACKEND, ("websocket", "web sockets"), ()),
    ("Microservices", BACKEND, ("microservice", "micro-services"), ("REST APIs", "Docker")),
    ("Authentication", BACKEND, ("authorization", "oauth", "oauth2", "jwt", "authentication and authorization", "user authentication", "role-based access"), ()),
    ("Celery", BACKEND, (), ("Python",)),
    ("Message Queues", BACKEND, ("message queue", "rabbitmq", "kafka", "task queue", "task queues"), ()),
    ("Caching", BACKEND, ("cache", "memcached"), ()),
    # ---------------------------------------------------------- databases
    ("PostgreSQL", DB, ("postgres", "psql"), ("SQL",)),
    ("MySQL", DB, ("mariadb",), ("SQL",)),
    ("SQLite", DB, (), ("SQL",)),
    ("MongoDB", DB, ("mongo", "mongoose"), ("NoSQL",)),
    ("NoSQL", DB, (), ()),
    ("Redis", DB, (), ("Caching",)),
    ("Elasticsearch", DB, ("elastic search", "opensearch"), ()),
    ("Database Design", DB, ("schema design", "normalization", "normalisation", "data modeling", "data modelling", "er diagram", "er diagrams", "relational database design", "database schema"), ("SQL",)),
    ("ORM", DB, ("django orm", "sqlalchemy", "hibernate", "object-relational mapping", "prisma"), ("SQL",)),
    # ------------------------------------------------------ devops & cloud
    ("Linux", DEVOPS, ("ubuntu", "unix"), ()),
    ("Git", TOOLS, ("version control", "git flow"), ()),
    ("GitHub", TOOLS, ("gitlab", "bitbucket", "pull requests", "pull request"), ("Git",)),
    ("Docker", DEVOPS, ("containerization", "containers", "dockerfile", "docker compose"), ("Linux",)),
    ("Kubernetes", DEVOPS, ("k8s",), ("Docker",)),
    ("CI/CD", DEVOPS, ("cicd", "github actions", "jenkins", "gitlab ci", "continuous integration", "continuous deployment"), ("Git",)),
    ("AWS", DEVOPS, ("amazon web services", "ec2", "s3"), ("Linux",)),
    ("Azure", DEVOPS, ("microsoft azure",), ()),
    ("GCP", DEVOPS, ("google cloud", "google cloud platform"), ()),
    ("Terraform", DEVOPS, ("infrastructure as code",), ("Linux",)),
    ("Nginx", DEVOPS, (), ("Linux",)),
    ("Deployment", DEVOPS, ("deploy", "deployed", "deploying", "hosting", "heroku"), ()),
    # ------------------------------------------------------------ testing
    ("Testing", TESTING, ("unit testing", "unit tests", "unit test", "automated testing", "tdd", "test-driven development", "pytest", "unittest", "junit", "jest", "test cases"), ()),
    ("Selenium", TESTING, (), ("Python",)),
    ("Postman", TESTING, ("api testing",), ("REST APIs",)),
    # ------------------------------------------------- CS fundamentals
    ("OOP", CS, ("object-oriented programming", "object oriented programming", "object-oriented design", "object oriented design", "oops"), ()),
    ("Data Structures & Algorithms", CS, ("data structures", "algorithms", "dsa", "data structures and algorithms"), ()),
    ("Design Patterns", CS, ("design pattern", "solid principles"), ("OOP",)),
    ("System Design", CS, ("high-level design", "low-level design"), ("REST APIs", "Database Design", "Caching")),
    ("Concurrency", CS, ("multithreading", "multi-threading", "multiprocessing", "asyncio", "async programming", "threading", "race conditions", "race condition"), ()),
    ("Web Security", CS, ("owasp", "sql injection", "xss", "csrf", "secure coding", "application security"), ("Authentication",)),
    ("Web Scraping", CS, ("beautifulsoup", "scrapy", "web crawling", "scraping"), ("Python", "HTML")),
    # ---------------------------------------------------------- data & AI
    ("NumPy", DATA, (), ("Python",)),
    ("Pandas", DATA, (), ("Python",)),
    ("Data Analysis", DATA, ("data analytics", "exploratory data analysis", "eda"), ("SQL",)),
    ("Data Visualization", DATA, ("data visualisation", "matplotlib", "seaborn", "plotly"), ("Data Analysis",)),
    ("Excel", DATA, ("ms excel", "microsoft excel", "advanced excel", "pivot tables", "excel spreadsheets"), ()),
    ("Power BI", DATA, ("powerbi",), ("Data Analysis",)),
    ("Tableau", DATA, (), ("Data Analysis",)),
    ("Machine Learning", DATA, ("ml", "machine-learning"), ("Python", "NumPy", "Pandas")),
    ("scikit-learn", DATA, ("sklearn", "scikit learn"), ("Machine Learning",)),
    ("TensorFlow", DATA, ("keras",), ("Machine Learning",)),
    ("PyTorch", DATA, (), ("Machine Learning",)),
    ("NLP", DATA, ("natural language processing",), ("Machine Learning",)),
    ("Generative AI", DATA, ("genai", "gen ai", "llm", "llms", "large language models", "prompt engineering", "chatgpt", "ai content creation"), ()),
    # ------------------------------------------------------ tools & process
    ("Agile", TOOLS, ("scrum", "kanban", "sprint planning"), ()),
    ("Jira", TOOLS, (), ("Agile",)),
    ("Figma", TOOLS, (), ()),
    ("Technical Documentation", TOOLS, ("documentation", "technical writing", "uml"), ()),
]
