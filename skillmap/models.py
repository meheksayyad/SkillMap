from django.conf import settings
from django.db import models
from django.db.models import Q


class Skill(models.Model):
    """One entry in the skill taxonomy. Editable from the Django admin."""

    name = models.CharField(max_length=60, unique=True)
    category = models.CharField(max_length=40, blank=True)
    aliases = models.JSONField(default=list, blank=True, help_text="Other spellings, as a JSON list")
    prerequisites = models.ManyToManyField(
        "self", symmetrical=False, related_name="unlocks", blank=True
    )
    match_name = models.BooleanField(
        default=True,
        help_text="Untick if the name is also an ordinary word (e.g. 'Go'); only aliases will match.",
    )

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class Resume(models.Model):
    """A resume's extracted TEXT. The uploaded file itself is not kept."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resumes"
    )
    title = models.CharField(max_length=80)
    text = models.TextField()
    source_filename = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.user.get_username()})"


class JobDescription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_descriptions"
    )
    title = models.CharField(max_length=120)
    company = models.CharField(max_length=120, blank=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} @ {self.company or 'n/a'}"


class Analysis(models.Model):
    """The saved result of matching one resume against one job description.

    `details` holds the full engine output (matched/missing skills, learning path...).
    `score` and `label` are copied into real columns so we can sort and filter in SQL.
    Re-running the same resume+job pair replaces the old row.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="analyses"
    )
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="analyses")
    job = models.ForeignKey(JobDescription, on_delete=models.CASCADE, related_name="analyses")
    score = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=20)
    details = models.JSONField()
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score", "-created_at"]
        verbose_name_plural = "analyses"
        constraints = [
            models.UniqueConstraint(fields=["resume", "job"], name="one_analysis_per_resume_job"),
            models.CheckConstraint(
                condition=Q(score__gte=0) & Q(score__lte=100), name="analysis_score_0_to_100"
            ),
        ]

    def __str__(self):
        return f"{self.resume.title} vs {self.job.title}: {self.score}"
