"""Glue between the database and the pure engine in engine.py.

Views and API endpoints call these functions and stay thin.
"""

from django.db import transaction

from . import engine
from .models import Analysis, Skill
from .taxonomy import NAME_NOT_MATCHED, TAXONOMY


# ------------------------------------------------------------ taxonomy
def seed_skills(skill_model=Skill):
    """Create/refresh the starting taxonomy. Safe to run repeatedly.

    `skill_model` is a parameter so the data migration can pass in its "historical" model.
    Only touches skills listed in TAXONOMY; skills you added yourself are left alone.
    """
    created = {}
    for name, category, aliases, _prereqs in TAXONOMY:
        obj, _ = skill_model.objects.update_or_create(
            name=name,
            defaults={
                "category": category,
                "aliases": list(aliases),
                "match_name": name not in NAME_NOT_MATCHED,
            },
        )
        created[name] = obj
    for name, _category, _aliases, prereqs in TAXONOMY:
        created[name].prerequisites.set([created[p] for p in prereqs])
    return len(created)


def load_taxonomy() -> engine.Taxonomy:
    """Build the engine's Taxonomy from the database (about 100 rows, so it's cheap)."""
    skills = Skill.objects.prefetch_related("prerequisites")
    return engine.Taxonomy(
        engine.SkillDef(
            name=s.name,
            category=s.category,
            aliases=tuple(s.aliases or ()),
            prerequisites=tuple(p.name for p in s.prerequisites.all()),
            match_name=s.match_name,
        )
        for s in skills
    )


# ------------------------------------------------------------- analysis
def quick_check(resume_text: str, job_text: str) -> dict:
    """One-off analysis that is NOT saved (used by the public home page and the API)."""
    result = engine.analyze(load_taxonomy(), resume_text, job_text).as_dict()
    result["resume_health"] = engine.resume_health(resume_text)
    return result


@transaction.atomic
def run_analysis(user, resume, job) -> Analysis:
    """Match a saved resume against a saved job and store (or replace) the result."""
    result = engine.analyze(load_taxonomy(), resume.text, job.text)
    analysis, _ = Analysis.objects.update_or_create(
        resume=resume,
        job=job,
        defaults={
            "user": user,
            "score": result.score,
            "label": result.label,
            "details": result.as_dict(),
        },
    )
    return analysis


def run_many(user, resume, jobs) -> list:
    """Analyze one resume against several jobs; returns analyses best-first."""
    tax = load_taxonomy()
    out = []
    with transaction.atomic():
        for job in jobs:
            result = engine.analyze(tax, resume.text, job.text)
            analysis, _ = Analysis.objects.update_or_create(
                resume=resume,
                job=job,
                defaults={
                    "user": user,
                    "score": result.score,
                    "label": result.label,
                    "details": result.as_dict(),
                },
            )
            out.append(analysis)
    return sorted(out, key=lambda a: -a.score)


def skills_by_category(taxonomy: engine.Taxonomy, names) -> list:
    """[('Backend', ['Django', ...]), ...] sorted, for display."""
    groups = {}
    for name in names:
        groups.setdefault(taxonomy.category_of(name) or "Other", []).append(name)
    return [(cat, sorted(items)) for cat, items in sorted(groups.items())]
