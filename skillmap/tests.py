import io

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from . import engine, extract, services
from .engine import SkillDef, Taxonomy
from .models import Analysis, JobDescription, Resume, Skill
from .samples import SAMPLE_JOBS, SAMPLE_RESUME
from .taxonomy import NAME_NOT_MATCHED, TAXONOMY

User = get_user_model()


def small_taxonomy():
    return Taxonomy(
        [
            SkillDef("Python", "Language"),
            SkillDef("Django", "Backend", (), ("Python",)),
            SkillDef("Django REST Framework", "Backend", ("drf",), ("Django", "REST APIs")),
            SkillDef("REST APIs", "Backend", ("restful",)),
            SkillDef("SQL", "Language"),
            SkillDef("PostgreSQL", "Database", ("postgres",), ("SQL",)),
            SkillDef("Java", "Language"),
            SkillDef("JavaScript", "Language", ("javascript",)),
            SkillDef("Node.js", "Backend", ("nodejs",), ("JavaScript",)),
            SkillDef("C++", "Language", ("cpp",)),
            SkillDef("C#", "Language"),
            SkillDef("Go", "Language", ("golang",), (), False),
            SkillDef("Spring", "Backend", ()),
            SkillDef("Spring Boot", "Backend", (), ("Java",)),
            SkillDef("Docker", "DevOps"),
            SkillDef("AWS", "DevOps"),
            SkillDef("Testing", "Testing", ("pytest", "unit tests")),
            SkillDef("NoSQL", "Database"),
        ]
    )


# ============================================================ engine: finder
class SkillFinderTests(SimpleTestCase):
    def setUp(self):
        self.tax = small_taxonomy()

    def test_sql_not_found_inside_postgresql_or_nosql(self):
        self.assertEqual(self.tax.find("PostgreSQL"), {"PostgreSQL"})
        self.assertEqual(self.tax.find("NoSQL"), {"NoSQL"})

    def test_java_not_found_inside_javascript(self):
        self.assertEqual(self.tax.find("I write JavaScript daily"), {"JavaScript"})

    def test_matching_is_case_insensitive(self):
        self.assertEqual(self.tax.find("PYTHON and django"), {"Python", "Django"})

    def test_aliases_map_to_canonical_name(self):
        self.assertEqual(self.tax.find("We use postgres and nodejs"), {"PostgreSQL", "Node.js"})

    def test_special_characters_in_names(self):
        self.assertEqual(self.tax.find("C++, C# and cpp"), {"C++", "C#"})

    def test_skill_at_end_of_sentence_and_in_lists(self):
        self.assertEqual(self.tax.find("I know Python. Also Django, and SQL."), {"Python", "Django", "SQL"})
        self.assertEqual(self.tax.find("Python/Django/SQL"), {"Python", "Django", "SQL"})

    def test_glued_to_other_letters_is_ignored(self):
        self.assertEqual(self.tax.find("Pythonic code, Djangoesque"), set())

    def test_node_js_does_not_also_match_a_bare_js_skill(self):
        self.assertEqual(self.tax.find("Node.js"), {"Node.js"})

    def test_ambiguous_bare_name_not_matched_but_alias_is(self):
        self.assertEqual(self.tax.find("Let's go and express ourselves"), set())
        self.assertEqual(self.tax.find("Golang services"), {"Go"})

    def test_longest_alias_wins(self):
        self.assertEqual(self.tax.find("Spring Boot"), {"Spring Boot"})
        self.assertEqual(self.tax.find("Spring"), {"Spring"})

    def test_empty_inputs(self):
        self.assertEqual(self.tax.find(""), set())
        self.assertEqual(Taxonomy([]).find("Python"), set())


# ===================================================== engine: classification
class ClassificationTests(SimpleTestCase):
    def setUp(self):
        self.tax = small_taxonomy()

    def test_headings_switch_mode(self):
        jd = "Requirements\n- Python\n- Django\nNice to have\n- Docker\n- AWS\n"
        req, pref = engine.classify_job_skills(self.tax, jd)
        self.assertEqual(req, {"Python", "Django"})
        self.assertEqual(pref, {"Docker", "AWS"})

    def test_everything_required_when_no_markers(self):
        req, pref = engine.classify_job_skills(self.tax, "We need Python and Docker.")
        self.assertEqual(req, {"Python", "Docker"})
        self.assertEqual(pref, set())

    def test_inline_plus_marks_that_line_preferred(self):
        req, pref = engine.classify_job_skills(self.tax, "Requirements\nPython\nDocker is a plus\n")
        self.assertIn("Python", req)
        self.assertIn("Docker", pref)

    def test_requirements_heading_switches_back(self):
        jd = "Nice to have\nDocker\nRequirements\nPython\n"
        req, pref = engine.classify_job_skills(self.tax, jd)
        self.assertEqual(req, {"Python"})
        self.assertEqual(pref, {"Docker"})

    def test_skill_in_both_sections_stays_required(self):
        jd = "Requirements\nPython\nNice to have\nPython, Docker\n"
        req, pref = engine.classify_job_skills(self.tax, jd)
        self.assertEqual(req, {"Python"})
        self.assertEqual(pref, {"Docker"})

    def test_line_with_both_markers_keeps_current_mode(self):
        req, pref = engine.classify_job_skills(self.tax, "Must have Python; Docker is a plus\n")
        self.assertEqual(req, {"Python", "Docker"})
        self.assertEqual(pref, set())


# ==================================================== engine: text similarity
class SimilarityTests(SimpleTestCase):
    def test_tokenize_keeps_special_tokens_and_drops_stopwords(self):
        tokens = engine.tokenize("We are using Node.js and C++ with the team.")
        self.assertIn("node.js", tokens)
        self.assertIn("c++", tokens)
        self.assertNotIn("the", tokens)
        self.assertNotIn("are", tokens)

    def test_identical_text_has_cosine_one(self):
        v = engine.tf_vector(engine.tokenize("python django postgresql api"))
        self.assertAlmostEqual(engine.cosine_similarity(v, v), 1.0)

    def test_disjoint_text_has_cosine_zero(self):
        a = engine.tf_vector(engine.tokenize("python django"))
        b = engine.tf_vector(engine.tokenize("welding carpentry"))
        self.assertEqual(engine.cosine_similarity(a, b), 0.0)

    def test_empty_vectors_are_zero(self):
        self.assertEqual(engine.cosine_similarity({}, {"a": 1.0}), 0.0)

    def test_repetition_has_diminishing_effect(self):
        once = engine.tf_vector(["python"])["python"]
        ten = engine.tf_vector(["python"] * 10)["python"]
        self.assertLess(ten, 10 * once)

    def test_cosine_is_symmetric(self):
        a = engine.tf_vector(engine.tokenize("python django api"))
        b = engine.tf_vector(engine.tokenize("django api docker"))
        self.assertAlmostEqual(engine.cosine_similarity(a, b), engine.cosine_similarity(b, a))


# ============================================================ engine: analyze
class AnalyzeTests(SimpleTestCase):
    def setUp(self):
        self.tax = small_taxonomy()

    def test_full_match_scores_high(self):
        jd = "Requirements\nPython, Django, SQL\n"
        r = engine.analyze(self.tax, "Python Django SQL developer", jd)
        self.assertEqual(r.skill_score, 1.0)
        self.assertEqual(r.missing_required, [])
        self.assertGreaterEqual(r.score, 80)
        self.assertEqual(r.label, "Strong match")

    def test_no_overlap_scores_zero(self):
        r = engine.analyze(self.tax, "Carpenter with ten years of woodworking", "Requirements\nPython, Django\n")
        self.assertEqual(r.score, 0)
        self.assertEqual(r.label, "Weak match")
        self.assertEqual(r.missing_required, ["Django", "Python"])

    def test_required_skills_weigh_double(self):
        jd = "Requirements\nPython\nNice to have\nDocker\n"
        have_req = engine.analyze(self.tax, "Python", jd)
        have_pref = engine.analyze(self.tax, "Docker", jd)
        self.assertAlmostEqual(have_req.skill_score, 2 / 3, places=3)
        self.assertAlmostEqual(have_pref.skill_score, 1 / 3, places=3)

    def test_extra_skills_are_reported_not_penalised(self):
        r = engine.analyze(self.tax, "Python Docker AWS", "Requirements\nPython\n")
        self.assertEqual(r.extra_skills, ["AWS", "Docker"])
        self.assertEqual(r.skill_score, 1.0)

    def test_job_without_known_skills_uses_text_only(self):
        r = engine.analyze(self.tax, "friendly cashier retail", "friendly cashier wanted for retail store")
        self.assertIsNone(r.skill_score)
        self.assertEqual(r.job_skills_found, 0)
        self.assertGreater(r.score, 0)

    def test_score_is_clamped_0_to_100(self):
        r = engine.analyze(self.tax, "Python " * 500, "Requirements\nPython\n")
        self.assertTrue(0 <= r.score <= 100)

    def test_labels(self):
        self.assertEqual(engine.label_for(75), "Strong match")
        self.assertEqual(engine.label_for(74), "Partial match")
        self.assertEqual(engine.label_for(50), "Partial match")
        self.assertEqual(engine.label_for(49), "Weak match")

    def test_result_as_dict_is_plain_data(self):
        d = engine.analyze(self.tax, "Python", "Requirements\nPython, Docker\n").as_dict()
        self.assertIsInstance(d["learning_path"], list)
        self.assertIsInstance(d["learning_path"][0], dict)


# ======================================================= engine: learning path
class LearningPathTests(SimpleTestCase):
    def setUp(self):
        self.tax = small_taxonomy()

    def names(self, steps):
        return [s.skill for s in steps]

    def test_prerequisites_come_first(self):
        steps = engine.learning_path(self.tax, {"Django"}, set(), have=set())
        self.assertEqual(self.names(steps), ["Python", "Django"])
        self.assertEqual(steps[0].kind, "prerequisite")
        self.assertEqual(steps[1].kind, "required")
        self.assertEqual(steps[0].needed_for, ["Django"])

    def test_known_prerequisites_are_skipped(self):
        steps = engine.learning_path(self.tax, {"Django"}, set(), have={"Python"})
        self.assertEqual(self.names(steps), ["Django"])

    def test_transitive_chain(self):
        steps = engine.learning_path(self.tax, {"Django REST Framework"}, set(), have=set())
        order = self.names(steps)
        self.assertEqual(set(order), {"Python", "Django", "REST APIs", "Django REST Framework"})
        self.assertLess(order.index("Python"), order.index("Django"))
        self.assertLess(order.index("Django"), order.index("Django REST Framework"))
        self.assertLess(order.index("REST APIs"), order.index("Django REST Framework"))

    def test_required_before_preferred_when_independent(self):
        steps = engine.learning_path(self.tax, {"Docker"}, {"AWS"}, have=set())
        self.assertEqual(self.names(steps), ["Docker", "AWS"])

    def test_nothing_missing_gives_empty_path(self):
        self.assertEqual(engine.learning_path(self.tax, set(), set(), have={"Python"}), [])

    def test_unknown_skill_names_are_ignored(self):
        self.assertEqual(engine.learning_path(self.tax, {"Underwater Basket Weaving"}, set(), set()), [])

    def test_cycle_in_taxonomy_does_not_hang(self):
        cyc = Taxonomy([SkillDef("A", "", (), ("B",)), SkillDef("B", "", (), ("A",))])
        steps = engine.learning_path(cyc, {"A"}, set(), have=set())
        self.assertEqual(sorted(s.skill for s in steps), ["A", "B"])


# ============================================================ engine: health
class ResumeHealthTests(SimpleTestCase):
    def check(self, health, check_id):
        return next(c for c in health["checks"] if c["id"] == check_id)["passed"]

    def test_sample_resume_results(self):
        h = engine.resume_health(SAMPLE_RESUME)
        for ok in ("email", "phone", "github", "linkedin", "education", "skills", "projects",
                   "action_verbs", "metrics"):
            self.assertTrue(self.check(h, ok), ok)
        # The sample deliberately contains filler phrases.
        self.assertFalse(self.check(h, "weak_phrases"))
        self.assertEqual(h["total"], 11)
        self.assertTrue(0 <= h["score"] <= 100)

    def test_empty_resume_fails_most_checks(self):
        h = engine.resume_health("hello")
        self.assertLess(h["score"], 20)

    def test_short_phone_number_not_accepted(self):
        self.assertFalse(self.check(engine.resume_health("call 12345"), "phone"))

    def test_metrics_need_a_unit(self):
        text = "- Built a thing that is very good and nice\n- Improved a thing in a good way overall\n"
        self.assertFalse(self.check(engine.resume_health(text), "metrics"))
        text2 = "- Cut page load time by 40% on the main dashboard\n- Wrote 25 tests for the booking module\n"
        self.assertTrue(self.check(engine.resume_health(text2), "metrics"))

    def test_weak_phrase_is_named_in_tip(self):
        h = engine.resume_health("I am a hard working person")
        tip = next(c for c in h["checks"] if c["id"] == "weak_phrases")["tip"]
        self.assertIn("hard working", tip)

    def test_cgpa_is_not_counted_as_a_metric(self):
        text = "- Completed B.Sc. Computer Science with CGPA 9.00 at the university\n"
        self.assertFalse(self.check(engine.resume_health(text), "metrics"))


# ================================================================= extraction
def make_pdf(text: str) -> bytes:
    """Build a tiny valid one-page PDF containing `text` (no parentheses allowed)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def make_docx(paragraphs) -> bytes:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class ExtractTests(SimpleTestCase):
    def test_txt(self):
        text = extract.extract_text("cv.txt", b"Python Django developer with PostgreSQL experience")
        self.assertIn("Django", text)

    def test_docx(self):
        data = make_docx(["Python developer", "Skills: Django, PostgreSQL, Git"])
        text = extract.extract_text("cv.docx", data)
        self.assertIn("PostgreSQL", text)

    def test_pdf(self):
        text = extract.extract_text("cv.pdf", make_pdf("Python Django PostgreSQL developer resume"))
        self.assertIn("Django", text)

    def test_unsupported_extension(self):
        with self.assertRaises(extract.ExtractError):
            extract.extract_text("cv.exe", b"MZ" * 50)

    def test_too_large(self):
        with self.assertRaises(extract.ExtractError):
            extract.extract_text("cv.txt", b"a" * (extract.MAX_BYTES + 1))

    def test_nearly_empty_file(self):
        with self.assertRaises(extract.ExtractError):
            extract.extract_text("cv.txt", b"hi")

    def test_corrupt_pdf_is_a_clean_error(self):
        with self.assertRaises(extract.ExtractError):
            extract.extract_text("cv.pdf", b"this is not a pdf at all" * 5)

    def test_corrupt_docx_is_a_clean_error(self):
        with self.assertRaises(extract.ExtractError):
            extract.extract_text("cv.docx", b"not a zip file" * 5)

    def test_long_text_is_truncated(self):
        big = ("python " * 10000).encode()
        self.assertLessEqual(len(extract.extract_text("cv.txt", big)), extract.MAX_CHARS)


# ================================================================= taxonomy data
class TaxonomyDataTests(TestCase):
    def test_migration_loaded_the_taxonomy(self):
        self.assertEqual(Skill.objects.count(), len(TAXONOMY))

    def test_prerequisite_names_exist(self):
        names = {t[0] for t in TAXONOMY}
        for name, _c, _a, prereqs in TAXONOMY:
            for p in prereqs:
                self.assertIn(p, names, f"{name} lists unknown prerequisite {p}")

    def test_taxonomy_has_no_cycles(self):
        tax = services.load_taxonomy()
        state = {}

        def visit(n, trail):
            if state.get(n) == 2:
                return
            self.assertNotEqual(state.get(n), 1, f"cycle: {' -> '.join(trail + [n])}")
            state[n] = 1
            for p in tax.skills[n].prerequisites:
                visit(p, trail + [n])
            state[n] = 2

        for n in tax.skills:
            visit(n, [])

    def test_no_alias_belongs_to_two_skills(self):
        seen = {}
        for name, _c, aliases, _p in TAXONOMY:
            terms = [a.lower() for a in aliases]
            if name not in NAME_NOT_MATCHED:
                terms.append(name.lower())
            for t in terms:
                self.assertNotIn(t, seen, f"'{t}' is used by both {seen.get(t)} and {name}")
                seen[t] = name

    def test_name_not_matched_entries_exist_and_have_aliases(self):
        by_name = {t[0]: t for t in TAXONOMY}
        for n in NAME_NOT_MATCHED:
            self.assertIn(n, by_name)
            self.assertTrue(by_name[n][2], f"{n} needs at least one alias")

    def test_seed_is_idempotent(self):
        before = Skill.objects.count()
        services.seed_skills()
        self.assertEqual(Skill.objects.count(), before)

    def test_loaded_taxonomy_knows_django_needs_python(self):
        tax = services.load_taxonomy()
        self.assertIn("Python", tax.skills["Django"].prerequisites)

    def test_real_taxonomy_end_to_end_on_sample(self):
        tax = services.load_taxonomy()
        found = tax.find(SAMPLE_RESUME)
        for expected in ("Python", "Django", "PostgreSQL", "SQL", "Git", "HTML", "CSS", "Testing",
                         "Database Design"):
            self.assertIn(expected, found)
        self.assertNotIn("Java", found)
        self.assertNotIn("JavaScript", found)


# ================================================================== services
class ServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u1", password="pass12345")
        self.resume = Resume.objects.create(user=self.user, title="r", text=SAMPLE_RESUME)
        self.jobs = [
            JobDescription.objects.create(user=self.user, title=j["title"], text=j["text"])
            for j in SAMPLE_JOBS
        ]

    def test_quick_check_includes_health_and_saves_nothing(self):
        out = services.quick_check(SAMPLE_RESUME, SAMPLE_JOBS[0]["text"])
        self.assertIn("score", out)
        self.assertIn("resume_health", out)
        self.assertEqual(Analysis.objects.count(), 0)

    def test_run_analysis_creates_then_replaces(self):
        a1 = services.run_analysis(self.user, self.resume, self.jobs[0])
        a2 = services.run_analysis(self.user, self.resume, self.jobs[0])
        self.assertEqual(a1.pk, a2.pk)
        self.assertEqual(Analysis.objects.count(), 1)

    def test_run_many_is_sorted_best_first(self):
        results = services.run_many(self.user, self.resume, self.jobs)
        scores = [a.score for a in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(len(results), 3)

    def test_sample_ranking_makes_sense(self):
        """A Python/Django resume must rank the Django job first, well ahead of the others."""
        results = services.run_many(self.user, self.resume, self.jobs)
        self.assertEqual(results[0].job.title, "Junior Python Developer")
        self.assertGreaterEqual(results[0].score, 75)
        for other in results[1:]:
            self.assertLess(other.score, 50)
            self.assertGreater(results[0].score - other.score, 25)

    def test_or_alternatives_are_a_known_limitation(self):
        """'Python or Java' makes BOTH required: the engine does not understand 'or'."""
        a = services.run_analysis(self.user, self.resume, self.jobs[1])
        self.assertIn("Java", a.details["missing_required"])

    def test_sample_gap_report(self):
        a = services.run_analysis(self.user, self.resume, self.jobs[0])
        d = a.details
        self.assertIn("Django", d["matched_required"])
        self.assertIn("REST APIs", d["missing_required"])
        self.assertIn("Docker", d["missing_preferred"])
        # Docker needs Linux first, and it must appear before Docker in the learning path.
        order = [s["skill"] for s in d["learning_path"]]
        self.assertLess(order.index("Linux"), order.index("Docker"))

    def test_skills_by_category_groups_and_sorts(self):
        tax = services.load_taxonomy()
        groups = services.skills_by_category(tax, ["Python", "Django", "SQL"])
        self.assertEqual(dict(groups)["Language"], ["Python", "SQL"])


# ===================================================================== web UI
class WebTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.bob = User.objects.create_user("bob", password="pass12345")
        self.job_text = SAMPLE_JOBS[0]["text"]

    def login(self, name="alice"):
        self.client.login(username=name, password="pass12345")

    def make_resume(self, user, title="cv"):
        return Resume.objects.create(user=user, title=title, text=SAMPLE_RESUME)

    def make_job(self, user, i=0):
        j = SAMPLE_JOBS[i]
        return JobDescription.objects.create(user=user, title=j["title"], text=j["text"])

    # ---- public quick check
    def test_home_page_loads(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_quick_check_with_pasted_text_shows_result_and_saves_nothing(self):
        r = self.client.post(reverse("home"), {"resume_text": SAMPLE_RESUME, "job_text": self.job_text})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Suggested learning order")
        self.assertContains(r, "Resume health")
        self.assertEqual(Resume.objects.count(), 0)
        self.assertEqual(Analysis.objects.count(), 0)

    def test_quick_check_with_uploaded_docx(self):
        upload = SimpleUploadedFile("cv.docx", make_docx(SAMPLE_RESUME.splitlines()))
        r = self.client.post(reverse("home"), {"resume_file": upload, "job_text": self.job_text})
        self.assertContains(r, "Resume health")

    def test_quick_check_with_uploaded_pdf(self):
        upload = SimpleUploadedFile("cv.pdf", make_pdf("Python Django PostgreSQL SQL Git developer resume"))
        r = self.client.post(reverse("home"), {"resume_file": upload, "job_text": self.job_text})
        self.assertContains(r, "Required skills you have")

    def test_quick_check_rejects_unsupported_file(self):
        upload = SimpleUploadedFile("cv.exe", b"MZ" * 100)
        r = self.client.post(reverse("home"), {"resume_file": upload, "job_text": self.job_text})
        self.assertContains(r, "Please upload a .pdf, .docx or .txt")
        self.assertNotContains(r, "Suggested learning order")

    def test_quick_check_requires_resume_and_job(self):
        r = self.client.post(reverse("home"), {"resume_text": "", "job_text": self.job_text})
        self.assertContains(r, "Paste your resume")
        r = self.client.post(reverse("home"), {"resume_text": SAMPLE_RESUME, "job_text": "short"})
        self.assertNotContains(r, "Suggested learning order")

    def test_user_text_is_html_escaped_in_results(self):
        evil = "<script>alert(1)</script> Python developer with Django skills and more words here"
        r = self.client.post(reverse("home"), {"resume_text": evil, "job_text": self.job_text})
        self.assertNotContains(r, "<script>alert(1)</script>")

    def test_public_pages(self):
        self.assertEqual(self.client.get(reverse("skills")).status_code, 200)
        self.assertEqual(self.client.get(reverse("signup")).status_code, 200)
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)

    # ---- auth
    def test_private_pages_require_login(self):
        for name, args in [("dashboard", []), ("resume_add", []), ("job_add", []), ("analyze", [])]:
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn("/accounts/login/", r["Location"])

    def test_signup_logs_user_in(self):
        r = self.client.post(
            reverse("signup"),
            {"username": "newbie", "password1": "a-Strong-pass-123", "password2": "a-Strong-pass-123"},
        )
        self.assertRedirects(r, reverse("dashboard"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    # ---- resumes & jobs
    def test_add_resume_by_pasting(self):
        self.login()
        r = self.client.post(reverse("resume_add"), {"title": "My CV", "text": SAMPLE_RESUME})
        resume = Resume.objects.get(user=self.alice)
        self.assertRedirects(r, reverse("resume_detail", args=[resume.pk]))
        self.assertContains(self.client.get(reverse("resume_detail", args=[resume.pk])), "Skills detected")

    def test_add_resume_by_upload_keeps_text_not_file(self):
        self.login()
        upload = SimpleUploadedFile("cv.txt", SAMPLE_RESUME.encode())
        self.client.post(reverse("resume_add"), {"title": "From file", "file": upload})
        resume = Resume.objects.get(user=self.alice)
        self.assertEqual(resume.source_filename, "cv.txt")
        self.assertIn("Django", resume.text)

    def test_resume_limit_enforced(self):
        self.login()
        with override_settings(MAX_RESUMES_PER_USER=1):
            self.make_resume(self.alice)
            r = self.client.post(reverse("resume_add"), {"title": "Second", "text": SAMPLE_RESUME})
            self.assertContains(r, "at most 1 resumes")
            self.assertEqual(Resume.objects.filter(user=self.alice).count(), 1)

    def test_add_job_and_detail_lists_skills(self):
        self.login()
        self.client.post(reverse("job_add"), {"title": "Dev", "company": "X", "text": self.job_text})
        job = JobDescription.objects.get(user=self.alice)
        r = self.client.get(reverse("job_detail", args=[job.pk]))
        self.assertContains(r, "Required skills found")
        self.assertContains(r, "Docker")

    def test_cannot_open_other_users_items(self):
        resume, job = self.make_resume(self.bob), self.make_job(self.bob)
        analysis = services.run_analysis(self.bob, resume, job)
        self.login("alice")
        for name, pk in [("resume_detail", resume.pk), ("job_detail", job.pk),
                         ("analysis_detail", analysis.pk), ("rank", resume.pk)]:
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 404, name)

    def test_delete_requires_post_and_ownership(self):
        resume = self.make_resume(self.bob)
        self.login("alice")
        self.assertEqual(self.client.get(reverse("resume_delete", args=[resume.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse("resume_delete", args=[resume.pk])).status_code, 404)
        self.assertTrue(Resume.objects.filter(pk=resume.pk).exists())

    def test_owner_can_delete_and_analyses_cascade(self):
        resume, job = self.make_resume(self.alice), self.make_job(self.alice)
        services.run_analysis(self.alice, resume, job)
        self.login()
        self.client.post(reverse("resume_delete", args=[resume.pk]))
        self.assertFalse(Resume.objects.exists())
        self.assertFalse(Analysis.objects.exists())

    # ---- analysis flow
    def test_analyze_needs_data_first(self):
        self.login()
        r = self.client.get(reverse("analyze"))
        self.assertRedirects(r, reverse("dashboard"))

    def test_analyze_one_job_goes_to_detail(self):
        resume, job = self.make_resume(self.alice), self.make_job(self.alice)
        self.login()
        r = self.client.post(reverse("analyze"), {"resume": resume.pk, "jobs": [job.pk]})
        analysis = Analysis.objects.get()
        self.assertRedirects(r, reverse("analysis_detail", args=[analysis.pk]))
        self.assertContains(self.client.get(reverse("analysis_detail", args=[analysis.pk])), "Resume health")

    def test_analyze_many_jobs_goes_to_ranking(self):
        resume = self.make_resume(self.alice)
        jobs = [self.make_job(self.alice, i) for i in range(3)]
        self.login()
        r = self.client.post(reverse("analyze"), {"resume": resume.pk, "jobs": [j.pk for j in jobs]})
        self.assertRedirects(r, reverse("rank", args=[resume.pk]))
        page = self.client.get(reverse("rank", args=[resume.pk]))
        self.assertContains(page, "Best-fit jobs")
        self.assertEqual(Analysis.objects.count(), 3)

    def test_cannot_analyze_with_someone_elses_resume(self):
        self.make_resume(self.alice, "mine")  # so the page doesn't bounce her to the dashboard
        bobs_resume = self.make_resume(self.bob)
        my_job = self.make_job(self.alice)
        self.login("alice")
        r = self.client.post(reverse("analyze"), {"resume": bobs_resume.pk, "jobs": [my_job.pk]})
        self.assertEqual(r.status_code, 200)  # form re-rendered with an error
        self.assertContains(r, "Select a valid choice")
        self.assertEqual(Analysis.objects.count(), 0)


# ====================================================================== API
class ApiTests(TestCase):
    def setUp(self):
        cache.clear()  # the throttle counters live in the cache
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.bob = User.objects.create_user("bob", password="pass12345")
        self.resume = Resume.objects.create(user=self.alice, title="cv", text=SAMPLE_RESUME)
        self.job = JobDescription.objects.create(
            user=self.alice, title=SAMPLE_JOBS[0]["title"], text=SAMPLE_JOBS[0]["text"]
        )
        self.anon = APIClient()
        self.alice_api = self.client_for(self.alice)
        self.bob_api = self.client_for(self.bob)

    @staticmethod
    def client_for(user):
        token, _ = Token.objects.get_or_create(user=user)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return c

    def test_analyze_is_public_and_returns_report(self):
        r = self.anon.post(
            "/api/analyze/",
            {"resume_text": SAMPLE_RESUME, "job_text": SAMPLE_JOBS[0]["text"]},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("Django", body["matched_required"])
        self.assertIn("resume_health", body)
        self.assertEqual(Analysis.objects.count(), 0)

    def test_analyze_validates_input(self):
        r = self.anon.post("/api/analyze/", {"resume_text": "short", "job_text": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.anon.post("/api/analyze/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_analyze_rejects_oversized_input(self):
        r = self.anon.post(
            "/api/analyze/",
            {"resume_text": "python " * 10000, "job_text": SAMPLE_JOBS[0]["text"]},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_anonymous_requests_are_throttled(self):
        payload = {"resume_text": SAMPLE_RESUME, "job_text": SAMPLE_JOBS[0]["text"]}
        codes = [self.anon.post("/api/analyze/", payload, format="json").status_code for _ in range(35)]
        self.assertIn(429, codes)
        self.assertEqual(codes[0], 200)

    def test_skills_list_public_and_filterable(self):
        r = self.anon.get("/api/skills/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), len(TAXONOMY))
        r = self.anon.get("/api/skills/?category=Database")
        names = {s["name"] for s in r.json()}
        self.assertIn("PostgreSQL", names)
        self.assertNotIn("Python", names)
        django = next(s for s in self.anon.get("/api/skills/").json() if s["name"] == "Django")
        self.assertEqual(django["prerequisites"], ["Python"])

    def test_analyses_require_authentication(self):
        self.assertEqual(self.anon.get("/api/analyses/").status_code, 401)
        self.assertEqual(self.anon.post("/api/analyses/", {"resume": 1, "job": 1}, format="json").status_code, 401)

    def test_token_endpoint(self):
        r = APIClient().post("/api/token/", {"username": "alice", "password": "pass12345"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.json())
        self.assertEqual(APIClient().post("/api/token/", {"username": "alice", "password": "wrong"}).status_code, 400)

    def test_create_and_list_analysis(self):
        r = self.alice_api.post("/api/analyses/", {"resume": self.resume.pk, "job": self.job.pk}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertGreater(r.json()["score"], 0)
        listed = self.alice_api.get("/api/analyses/").json()
        self.assertEqual(listed["count"], 1)
        self.assertEqual(self.bob_api.get("/api/analyses/").json()["count"], 0)

    def test_other_users_ids_look_nonexistent(self):
        r = self.bob_api.post("/api/analyses/", {"resume": self.resume.pk, "job": self.job.pk}, format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Analysis.objects.count(), 0)
