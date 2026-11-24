# SkillMap: Resume ↔ Job Matcher & Skill-Gap Analyzer

Paste or upload a resume and a job description. SkillMap finds the skills each one mentions,
scores the match, shows what you have and what's missing, and lists **what to learn next, in
an order where prerequisites come first**.

It is a Django web app plus a REST API. The matching is classical text processing
(regular expressions, term-frequency cosine similarity and a graph ordering). It uses **no
AI API and no machine learning**, so every number it shows can be traced and explained.

## Features

| Area | What it does |
|---|---|
| Quick check (no login) | Paste or upload a resume (PDF / DOCX / TXT) + a job description and get a full report. Nothing is saved. |
| Skill extraction | A ~90-skill taxonomy with aliases (`postgres` → PostgreSQL). Matching respects word boundaries, so `SQL` is not found inside `PostgreSQL` and `Java` is not found inside `JavaScript`. |
| Required vs nice-to-have | Reads headings such as "Requirements" / "Nice to have" / "is a plus" to decide which job skills are essential. |
| Score | 80% weighted skill coverage (required counts double) + 20% wording similarity (cosine over term frequencies). |
| Learning path | Missing skills plus the prerequisites you lack, ordered with a topological sort (Kahn's algorithm). |
| Resume health | 11 ATS-style checks on the resume itself: contact info, links, sections, length, action verbs, numbers, filler phrases. |
| Accounts | Save resumes and jobs, compare one resume against many jobs and get a **ranked list**; users only ever see their own data. |
| Admin | The skill taxonomy lives in the database. Add or edit skills and prerequisites in the Django admin, no code change. |
| REST API | Token auth, throttling, public analyze endpoint. |
| Tests | 98 tests (engine, file extraction, taxonomy data, services, web views, API). |

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate           # also loads the skill taxonomy
python manage.py seed_demo         # optional: demo user, sample resume, 3 sample jobs
python manage.py runserver
```

Open http://127.0.0.1:8000. Demo login (local demo only): `demo` / `demo12345`.
To use the admin site: `python manage.py createsuperuser`, then open `/admin/`.

### PostgreSQL instead of SQLite

```bash
export DB_NAME=skillmap DB_USER=postgres DB_PASSWORD=yourpass DB_HOST=localhost
python manage.py migrate
```

### Tests

```bash
python manage.py test
```

## REST API

```bash
# Public, no login. Throttled to 30 requests/minute per IP.
curl -X POST http://127.0.0.1:8000/api/analyze/ -H "Content-Type: application/json" \
     -d '{"resume_text": "...at least 40 chars...", "job_text": "...at least 40 chars..."}'

curl http://127.0.0.1:8000/api/skills/?category=Backend

# Logged-in endpoints
curl -X POST http://127.0.0.1:8000/api/token/ -d username=demo -d password=demo12345
curl http://127.0.0.1:8000/api/analyses/ -H "Authorization: Token <key>"
curl -X POST http://127.0.0.1:8000/api/analyses/ -H "Authorization: Token <key>" \
     -H "Content-Type: application/json" -d '{"resume": 1, "job": 2}'
```

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/analyze/` | none | One-off match report (not saved) |
| `GET /api/skills/?category=` | none | The skill taxonomy |
| `POST /api/token/` | none | Get a token |
| `GET /api/analyses/` | token | My saved analyses |
| `POST /api/analyses/` | token | Analyze one of my resumes against one of my jobs (404 for anyone else's ids) |

## Project layout

```
config/                         settings, root URLs
skillmap/
  engine.py                     THE CORE: skill finder, classifier, scoring, learning path, resume health
                                (pure Python, no Django imports)
  taxonomy.py                   starting skills, aliases and prerequisites
  extract.py                    PDF / DOCX / TXT -> text
  models.py                     Skill, Resume, JobDescription, Analysis
  services.py                   database <-> engine glue (views and API stay thin)
  views.py / forms.py / urls.py website
  api_views.py / serializers.py / api_urls.py   REST API
  migrations/0002_seed_taxonomy.py   loads the taxonomy on first migrate
  management/commands/          seed_demo, seed_skills
  tests.py                      98 tests
```

## How the score works (short version)

1. Find skills in the resume and in the job text.
2. Split the job's skills into **required** and **nice-to-have**.
3. `skill_score = (2 × required matched + 1 × nice-to-have matched) / (2 × required + 1 × nice-to-have)`
4. `text_score = min(1, cosine_similarity / 0.35)`
5. `score = 0.8 × skill_score + 0.2 × text_score`, shown as 0-100. 75+ is a "Strong match", 50-74 "Partial".

## Known limitations (read these before relying on a score)

- **Keyword matching only.** A skill is detected only if it is named. "Built REST endpoints" will
  not be read as REST APIs unless that phrase is in the taxonomy aliases.
- **No understanding of context.** "No experience with Docker" still counts as mentioning Docker.
- **"Python or Java" counts both as required.** The engine does not understand "or".
- **Classification is by headings and phrases.** A job description without headings treats every
  skill as required.
- **The weights are judgement calls.** 80/20, 2:1 and the 0.35 wording threshold were chosen by
  eye on sample data. They are not statistically calibrated, and the score is a guide, not a verdict.
- **The taxonomy is small (~90 skills)** and tech-focused. Add skills in the admin.
- **Scanned (image-only) PDFs** contain no text to extract.
- The public quick-check web form has size limits but no per-IP rate limit. Only the API is
  throttled. Add rate limiting (e.g. at the proxy) before exposing it widely.
- Uploaded files are never stored; only extracted text of saved resumes is kept. Delete a resume
  from its page to remove it.

## Deploy (Render / Railway / PythonAnywhere)

1. Push to GitHub and create a web service plus a PostgreSQL database.
2. Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
3. Start: `gunicorn config.wsgi`
4. Environment variables: `SECRET_KEY` (long random string), `DEBUG=0`,
   `ALLOWED_HOSTS=your-app.onrender.com`, `CSRF_TRUSTED_ORIGINS=https://your-app.onrender.com`,
   and `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
5. Optional: `python manage.py seed_demo` once for demo data, then change or delete the demo user's password.
