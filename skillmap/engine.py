"""SkillMap matching engine.

Pure Python: NO Django imports. That makes it fast to test and easy to explain.
Everything here is classical text processing (regular expressions, counting,
cosine similarity, a graph ordering). There is no machine learning and no AI API.

Pipeline for one resume + one job description:

    1. Taxonomy.find()        -> which known skills does each text mention?
    2. classify_job_skills()  -> which of the job's skills are required vs nice-to-have?
    3. cosine_similarity()    -> how similar is the wording overall?
    4. analyze()              -> combine into one score and a gap report
    5. learning_path()        -> order the missing skills so prerequisites come first
    6. resume_health()        -> separate, ATS-style checks of the resume itself
"""

from __future__ import annotations

import heapq
import math
import re
from collections import Counter
from dataclasses import dataclass, field


# =========================================================== 1. skill finder
@dataclass(frozen=True)
class SkillDef:
    """One skill in the taxonomy (plain data, independent of the database)."""

    name: str
    category: str = ""
    aliases: tuple = ()
    prerequisites: tuple = ()
    # False for names that are also ordinary words ("Go", "C", "Excel"): the bare name is
    # then NOT matched, only its aliases ("golang", "microsoft excel").
    match_name: bool = True


# A skill name only counts as a match when it is NOT glued to other letters,
# digits, '+', '#' or '.', so "SQL" does not match inside "PostgreSQL"/"NoSQL",
# "Java" does not match inside "JavaScript", and "js" does not match inside "Node.js".
_BEFORE = r"(?<![A-Za-z0-9+#.])"
_AFTER = r"(?![A-Za-z0-9+#])"


class Taxonomy:
    """A set of skills plus a compiled regex that finds them in free text."""

    def __init__(self, skills):
        self.skills: dict[str, SkillDef] = {s.name: s for s in skills}
        self._lookup: dict[str, str] = {}
        for skill in self.skills.values():
            terms = (skill.name, *skill.aliases) if skill.match_name else skill.aliases
            for term in terms:
                self._lookup.setdefault(term.lower(), skill.name)
        # Longest terms first so "spring boot" wins over "spring".
        terms = sorted(self._lookup, key=len, reverse=True)
        self._regex = (
            re.compile(
                _BEFORE + "(" + "|".join(re.escape(t) for t in terms) + ")" + _AFTER,
                re.IGNORECASE,
            )
            if terms
            else None
        )

    def find(self, text: str) -> set[str]:
        """Return the canonical names of all skills mentioned in `text`."""
        if not self._regex or not text:
            return set()
        return {self._lookup[m.group(1).lower()] for m in self._regex.finditer(text)}

    def category_of(self, name: str) -> str:
        skill = self.skills.get(name)
        return skill.category if skill else ""


# ============================================ 2. required vs nice-to-have
_PREFERRED = re.compile(
    r"\b(preferred|nice[- ]to[- ]have|good[- ]to[- ]have|bonus|a plus|is a plus|"
    r"desirable|optional|advantage|added advantage)\b",
    re.IGNORECASE,
)
_REQUIRED = re.compile(
    r"\b(required|requirements?|must[- ]have|qualifications?|responsibilities|"
    r"you will|what you.ll need|mandatory|essential)\b",
    re.IGNORECASE,
)


def classify_job_skills(taxonomy: Taxonomy, job_text: str) -> tuple[set[str], set[str]]:
    """Split a job description's skills into (required, preferred).

    Walks the text line by line, remembering the current "mode":
      * a line with only "preferred"-style words ("nice to have", "bonus", "is a plus")
        switches to preferred mode;
      * a line with only "required"-style words ("requirements", "must have") switches
        back to required mode;
      * a line with both, or neither, keeps the current mode.
    Everything starts in required mode, and a skill found in both lists stays required.
    """
    mode = "required"
    required: set[str] = set()
    preferred: set[str] = set()
    for line in job_text.splitlines():
        line = line.strip()
        if not line:
            continue
        is_pref = bool(_PREFERRED.search(line))
        is_req = bool(_REQUIRED.search(line))
        if is_pref and not is_req:
            mode = "preferred"
        elif is_req and not is_pref:
            mode = "required"
        found = taxonomy.find(line)
        (preferred if mode == "preferred" else required).update(found)
    return required, preferred - required


# =============================================== 3. text similarity (cosine)
STOPWORDS = frozenset(
    """a about above after again all also am an and any are as at be because been before
    being below between both but by can could did do does doing down during each few for
    from further had has have having he her here hers him his how i if in into is it its
    just me more most my no nor not of off on once only or other our out over own same she
    should so some such than that the their them then there these they this those through
    to too under until up us very was we were what when where which while who whom why will
    with would you your yours etc eg ie using use used work working experience years year
    strong good ability able team role looking join candidate company""".split()
)
_TOKEN = re.compile(r"[a-z][a-z0-9+#.]*[a-z0-9+#]|[a-z]")


def tokenize(text: str) -> list[str]:
    """Lower-case words, keeping things like 'c++' and 'node.js', minus stopwords."""
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 1 and t not in STOPWORDS]


def tf_vector(tokens: list[str]) -> dict[str, float]:
    """Sub-linear term frequency: 1 + ln(count). Repeating a word 10x isn't 10x as important."""
    return {t: 1.0 + math.log(c) for t, c in Counter(tokens).items()}


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """cos(angle) between two sparse vectors: 1.0 = same wording, 0.0 = nothing shared."""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    dot = sum(w * b.get(t, 0.0) for t, w in a.items())
    norm = math.sqrt(sum(w * w for w in a.values())) * math.sqrt(sum(w * w for w in b.values()))
    return dot / norm if norm else 0.0


# ============================================================== 5. learning path
@dataclass
class LearningStep:
    skill: str
    category: str
    kind: str  # "required" | "preferred" | "prerequisite"
    needed_for: list = field(default_factory=list)


def learning_path(
    taxonomy: Taxonomy,
    missing_required: set[str],
    missing_preferred: set[str],
    have: set[str],
) -> list[LearningStep]:
    """Order the skills to learn so every prerequisite comes before what depends on it.

    1. Collect the missing skills plus (transitively) any prerequisite you don't have.
    2. Topological sort (Kahn's algorithm) over that small graph.
    3. Among skills that are ready at the same time, pick required gaps first, then
       prerequisites, then nice-to-haves, then alphabetical (so output is deterministic).
    """
    wanted = {s for s in (missing_required | missing_preferred) if s in taxonomy.skills}
    needed: set[str] = set()
    stack = list(wanted)
    while stack:
        name = stack.pop()
        if name in needed or name in have or name not in taxonomy.skills:
            continue
        needed.add(name)
        stack.extend(taxonomy.skills[name].prerequisites)

    # edges: prerequisite -> skill that depends on it (only inside `needed`)
    deps_left = {n: 0 for n in needed}
    unlocks: dict[str, list[str]] = {n: [] for n in needed}
    for n in needed:
        for p in taxonomy.skills[n].prerequisites:
            if p in needed:
                deps_left[n] += 1
                unlocks[p].append(n)

    def rank(n: str) -> tuple:
        if n in missing_required:
            return (0, n)
        if n in missing_preferred:
            return (2, n)
        return (1, n)  # pure prerequisite

    heap = [rank(n) for n, d in deps_left.items() if d == 0]
    heapq.heapify(heap)
    order: list[str] = []
    while heap:
        _, name = heapq.heappop(heap)
        order.append(name)
        for nxt in unlocks[name]:
            deps_left[nxt] -= 1
            if deps_left[nxt] == 0:
                heapq.heappush(heap, rank(nxt))
    # Safety net: a cycle in the taxonomy would leave nodes behind. Append them anyway.
    order.extend(sorted(n for n in needed if n not in order))

    steps = []
    for name in order:
        if name in missing_required:
            kind = "required"
        elif name in missing_preferred:
            kind = "preferred"
        else:
            kind = "prerequisite"
        steps.append(
            LearningStep(
                skill=name,
                category=taxonomy.category_of(name),
                kind=kind,
                needed_for=sorted(u for u in unlocks[name] if u in needed),
            )
        )
    return steps


# ================================================================ 4. analysis
# Required skills count double; nice-to-haves count once.
REQUIRED_WEIGHT = 2
PREFERRED_WEIGHT = 1
# Final score = 80% skill coverage + 20% wording similarity.
SKILL_SHARE = 0.8
TEXT_SHARE = 0.2
# A raw cosine of 0.35 or more is treated as "full marks" for wording. Raw cosine between
# two different documents is rarely high, so we rescale. The 0.35 is a judgement call
# chosen by eye on sample data, not a statistically derived number.
TEXT_FULL_MARKS = 0.35


@dataclass
class MatchResult:
    score: int
    label: str
    skill_score: float | None
    text_score: float
    matched_required: list
    missing_required: list
    matched_preferred: list
    missing_preferred: list
    extra_skills: list
    resume_skills: list
    job_skills_found: int
    learning_path: list

    def as_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)


def label_for(score: int) -> str:
    if score >= 75:
        return "Strong match"
    if score >= 50:
        return "Partial match"
    return "Weak match"


def analyze(taxonomy: Taxonomy, resume_text: str, job_text: str) -> MatchResult:
    resume_skills = taxonomy.find(resume_text)
    required, preferred = classify_job_skills(taxonomy, job_text)

    matched_req = required & resume_skills
    missing_req = required - resume_skills
    matched_pref = preferred & resume_skills
    missing_pref = preferred - resume_skills
    extra = resume_skills - required - preferred

    possible = REQUIRED_WEIGHT * len(required) + PREFERRED_WEIGHT * len(preferred)
    earned = REQUIRED_WEIGHT * len(matched_req) + PREFERRED_WEIGHT * len(matched_pref)
    skill_score = earned / possible if possible else None

    cosine = cosine_similarity(tf_vector(tokenize(resume_text)), tf_vector(tokenize(job_text)))
    text_score = min(1.0, cosine / TEXT_FULL_MARKS)

    if skill_score is None:
        # The job text mentions no skills we know: fall back to wording similarity alone.
        final = text_score
    else:
        final = SKILL_SHARE * skill_score + TEXT_SHARE * text_score
    score = max(0, min(100, round(final * 100)))

    path = learning_path(taxonomy, missing_req, missing_pref, resume_skills)
    return MatchResult(
        score=score,
        label=label_for(score),
        skill_score=None if skill_score is None else round(skill_score, 3),
        text_score=round(text_score, 3),
        matched_required=sorted(matched_req),
        missing_required=sorted(missing_req),
        matched_preferred=sorted(matched_pref),
        missing_preferred=sorted(missing_pref),
        extra_skills=sorted(extra),
        resume_skills=sorted(resume_skills),
        job_skills_found=len(required) + len(preferred),
        learning_path=[s.__dict__ for s in path],
    )


# ========================================================== 6. resume health
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
_BULLET = re.compile(r"^\s*(?:[-•‣▪●◦*]|\d+[.)])\s+")
_HEADINGS = {
    "education": {"education", "academic qualifications", "academics"},
    "skills": {"skills", "technical skills", "key skills", "core skills", "skill set"},
    "projects": {
        "projects", "project", "academic projects", "personal projects", "key projects",
        "experience", "work experience", "professional experience", "internship",
        "internships", "training",
    },
}
_ACTION_VERBS = frozenset(
    """built developed designed implemented created optimized optimised deployed integrated
    led automated wrote tested configured improved reduced analyzed analysed engineered
    architected launched migrated refactored debugged maintained delivered documented
    modeled modelled established streamlined""".split()
)
# A number that measures something: "40%", "3x", or a number followed (within up to two
# words) by a countable thing, e.g. "3 tables", "12 unit tests", "5 REST endpoints".
# A bare "9.00" (CGPA) or a year does not count.
_METRIC = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:%|\+|x\b|k\b)"
    r"|\b\d+(?:\.\d+)?(?:\s+[A-Za-z-]+){0,2}\s+"
    r"(?:ms\b|seconds?\b|users?\b|tests?\b|tables?\b|endpoints?\b|apis?\b|features?\b|"
    r"modules?\b|pages?\b|records?\b|requests?\b|queries\b|models?\b|screens?\b)",
    re.IGNORECASE,
)
_WEAK_PHRASES = (
    "hard working", "hardworking", "quick learner", "fast learner", "team player",
    "willingness to learn", "responsible for", "self-motivated", "passionate about",
)


def _statement_lines(text: str) -> list[str]:
    """Lines that look like sentences/bullets (5+ words), with the bullet mark removed."""
    out = []
    for raw in text.splitlines():
        line = _BULLET.sub("", raw).strip()
        if len(line.split()) >= 5:
            out.append(line)
    return out


def _has_heading(text: str, words: set[str]) -> bool:
    for raw in text.splitlines():
        line = raw.strip().strip(":").strip().lower()
        if 0 < len(line) <= 40 and line in words:
            return True
    return False


def resume_health(text: str) -> dict:
    """ATS-style checks of the resume on its own (independent of any job)."""
    lower = text.lower()
    lines = _statement_lines(text)
    word_count = len(text.split())
    phone = _PHONE.search(text)
    phone_ok = bool(phone) and sum(c.isdigit() for c in phone.group(0)) >= 10
    verb_lines = [ln for ln in lines if ln.split()[0].lower().strip(".,:;") in _ACTION_VERBS]
    metric_lines = [ln for ln in lines if _METRIC.search(ln)]
    weak = [p for p in _WEAK_PHRASES if p in lower]

    checks = [
        ("email", "Email address present", bool(_EMAIL.search(text)),
         "Add a professional email address near the top."),
        ("phone", "Phone number present", phone_ok,
         "Add a phone number recruiters can call."),
        ("github", "GitHub link present", "github.com" in lower,
         "Add your GitHub profile or project links: it lets recruiters verify your claims."),
        ("linkedin", "LinkedIn link present", "linkedin.com" in lower,
         "Add your LinkedIn profile URL."),
        ("education", "Education section", _has_heading(text, _HEADINGS["education"]),
         "Add a clearly labelled Education section."),
        ("skills", "Skills section", _has_heading(text, _HEADINGS["skills"]),
         "Add a clearly labelled Skills section; applicant tracking systems look for it."),
        ("projects", "Projects or Experience section", _has_heading(text, _HEADINGS["projects"]),
         "Add a Projects (or Experience) section."),
        ("length", "Sensible length (150-900 words)", 150 <= word_count <= 900,
         f"Your resume has {word_count} words. Aim for one page, roughly 300-600 words."),
        ("action_verbs", "Bullets start with action verbs (3+)", len(verb_lines) >= 3,
         "Start bullets with verbs like Built, Implemented, Designed, Optimized."),
        ("metrics", "Numbers that show scale or impact (2+)", len(metric_lines) >= 2,
         "Add numbers: tests written, tables designed, users, speed-ups, endpoints built."),
        ("weak_phrases", "No filler phrases", not weak,
         "Remove filler such as: " + ", ".join(weak) + "." if weak else ""),
    ]
    items = [{"id": i, "label": l, "passed": bool(p), "tip": "" if p else t} for i, l, p, t in checks]
    passed = sum(1 for it in items if it["passed"])
    return {
        "score": round(100 * passed / len(items)),
        "passed": passed,
        "total": len(items),
        "word_count": word_count,
        "checks": items,
    }
