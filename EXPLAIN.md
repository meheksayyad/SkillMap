# Understand this project (read before any interview)

If SkillMap goes on your resume, you must be able to explain it. This is your study guide:
the ideas, where they live in the code, the honest weaknesses, and likely interview questions.
Run it, read `skillmap/engine.py` top to bottom (it's one file, about 400 lines), and break it
on purpose.

## 1. The 60-second pitch

> SkillMap compares a resume with a job description. It finds the skills each one mentions
> using a taxonomy with aliases and word-boundary matching, splits the job's skills into
> required and nice-to-have, and scores the match: 80% weighted skill coverage and 20% wording
> similarity using cosine similarity over term frequencies. It also builds a learning path by
> topologically sorting the missing skills so prerequisites come first, and runs ATS-style
> checks on the resume. It's a Django app with a REST API, 98 tests, and the engine is pure
> Python so it's easy to test. I deliberately used no AI API, so the scoring is fully explainable.

## 2. Where everything is

| Idea | Where |
|---|---|
| Finding skills with regex | `engine.Taxonomy` |
| Required vs nice-to-have | `engine.classify_job_skills` |
| Tokenizing, TF vectors, cosine | `engine.tokenize`, `tf_vector`, `cosine_similarity` |
| Score formula | `engine.analyze` (constants above it) |
| Learning path | `engine.learning_path` |
| Resume checks | `engine.resume_health` |
| PDF / DOCX reading | `extract.py` |
| Skills editable in admin | `models.Skill` + `services.load_taxonomy` |
| Taxonomy loaded on migrate | `migrations/0002_seed_taxonomy.py` |

## 3. The key ideas, in plain words

**Word-boundary matching.** Naively searching for "SQL" would also hit "PostgreSQL" and "NoSQL",
and "Java" would hit "JavaScript". The regex uses a lookbehind and lookahead
(`(?<![A-Za-z0-9+#.])` ... `(?![A-Za-z0-9+#])`) so a skill only matches when it isn't glued to
other letters, digits, `+`, `#` or `.`. The `.` in the lookbehind stops "js" matching inside
"Node.js". Terms are sorted longest-first so "spring boot" wins over "spring".

**Ambiguous names.** "Go", "C", "Excel", "Express" are also ordinary words ("excel in a team").
Their `match_name` flag is off, so only aliases like "golang" or "microsoft excel" match.

**Cosine similarity.** Turn each text into a vector of word weights, then measure the angle
between them: 1.0 = same wording, 0.0 = nothing shared. Weights use `1 + ln(count)` (sub-linear TF)
so repeating a word 10 times isn't 10x as important. It is TF only, not TF-IDF. I did not have a
background corpus to compute IDF from, and it's honest to say so.

**Required counts double.** `skill_score = (2R + P) / (2·total_required + total_preferred)`.
Missing a required skill hurts twice as much as missing a nice-to-have.

**Topological sort (Kahn's algorithm).** The taxonomy is a graph: Django needs Python, DRF needs
Django and REST APIs. For the missing skills I first collect any prerequisite you also lack
(transitively), then repeatedly take a skill whose prerequisites are all done. A min-heap breaks
ties (required gaps first, then prerequisites, then nice-to-haves, then alphabetical) so the
output is deterministic. If a cycle ever existed in the data, the leftover nodes are appended
rather than looping forever, and a test checks the shipped taxonomy has no cycles.

**Why the engine has no Django imports.** It's pure functions on plain data, so it's trivial to
unit test (`SimpleTestCase`, no database) and could be reused in a CLI or another framework.
`services.py` is the only glue between the database and the engine.

**Why the taxonomy is in the database.** Admins can add skills and aliases without a deploy.
The data migration seeds it so the app works right after `migrate`.

**Privacy and safety choices.** Uploaded files are not stored, only text. Every query for saved
data filters by `user=request.user`, so other people's ids return 404. Uploads are size-limited
and parsed defensively (corrupt PDFs give a clean error, not a crash). User text is rendered
through Django's auto-escaping (a test checks a `<script>` payload). The public API is throttled.

## 4. The honest weaknesses (say these before the interviewer finds them)

1. **Keyword matching, not understanding.** "Built REST endpoints" isn't read as REST APIs unless
   it's in the aliases. "No experience with Docker" still counts as Docker.
2. **"Python or Java" counts both as required** (there's a test documenting this).
3. **The constants are judgement calls.** 80/20, 2:1 weighting and the 0.35 cosine threshold were
   chosen by eye on sample data, not derived or validated against hiring outcomes.
   The score is a guide, not a prediction of whether you'd get an interview.
4. **Small taxonomy** (~90 skills), tech-focused.
5. **TF cosine, not TF-IDF**, so common-but-meaningless words aren't down-weighted beyond a
   stop-word list.
6. **No rate limit on the web quick-check form**, only on the API.

Naming these yourself is a strength. Interviewers trust people who know their project's limits.

## 5. Interview questions to practise

1. How does SkillMap decide which skills a resume has? Why not a plain `in` check?
2. What is cosine similarity? Why `1 + ln(count)` instead of the raw count?
3. Why does required weigh double? How would you tune the weights properly?
   *(Collect labelled resume/job pairs, measure agreement, and fit the weights.)*
4. Explain Kahn's algorithm. What happens with a cycle? How did you handle it?
5. Why keep the engine free of Django code?
6. What's a data migration and why use one for the taxonomy? Why is the reverse a no-op?
7. How do you stop one user from reading another's resume? *(Filter by user + 404.)*
8. What could go wrong with user-uploaded files? What did you do about it?
9. How would you add real semantic matching? *(Embeddings or an LLM, with cost, privacy and
   reproducibility trade-offs. Say why you chose not to.)*
10. What's the difference between `SimpleTestCase` and `TestCase`, and which did you use where?

## 6. Exercises (do these so it's truly yours)

1. Make "X or Y" count as ONE requirement satisfied by either (fix limitation 2) and add tests.
2. Add TF-IDF using all saved job descriptions as the corpus. Does ranking improve?
3. Add 20 skills for a field you know (e.g. data analysis) with aliases and prerequisites.
4. Add a "negation" rule so "no experience with Docker" isn't counted.
5. Add an export of the report as PDF or CSV.
6. Break it: remove the lookbehind from the regex and watch the finder tests fail. Restore it.
7. Add pagination to the ranking page and a delete button for analyses.

## 7. Be honest about how it was made

This project was generated with AI assistance. If asked, say so, and show you understand it
and have extended it (the exercises above). Never claim code you can't explain: interviewers
ask you to walk through a file and change something live.

## 8. Resume bullets you can use (only once they're true for you)

- Built a resume-to-job matching engine in Python/Django that extracts skills with a regex-based
  taxonomy, scores matches (weighted skill coverage + TF cosine similarity) and generates a
  prerequisite-ordered learning path using topological sort.
- Implemented PDF/DOCX/TXT resume parsing, ATS-style resume health checks and a ranked
  multi-job comparison view.
- Designed a token-authenticated, throttled REST API and wrote 98 unit/integration tests.
- Deployed at [your live link]; source at [your GitHub link].
