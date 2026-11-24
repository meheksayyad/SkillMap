from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import engine, services
from .forms import AnalyzeForm, JobForm, QuickCheckForm, ResumeForm, SignUpForm
from .models import Analysis, JobDescription, Resume, Skill


# ------------------------------------------------------------------ public
def home(request):
    """Public quick check: paste or upload a resume + a job description. Nothing is saved."""
    form = QuickCheckForm(request.POST or None, request.FILES or None)
    result = None
    if request.method == "POST" and form.is_valid():
        result = services.quick_check(form.cleaned_data["resume_text"], form.cleaned_data["job_text"])
    return render(request, "skillmap/home.html", {"form": form, "result": result})


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to SkillMap! Add a resume to get started.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def skills_catalog(request):
    skills = Skill.objects.prefetch_related("prerequisites").order_by("category", "name")
    groups = {}
    for s in skills:
        groups.setdefault(s.category or "Other", []).append(s)
    return render(request, "skillmap/skills.html", {"groups": sorted(groups.items()), "total": len(skills)})


# --------------------------------------------------------------- dashboard
@login_required
def dashboard(request):
    return render(
        request,
        "skillmap/dashboard.html",
        {
            "resumes": Resume.objects.filter(user=request.user),
            "jobs": JobDescription.objects.filter(user=request.user),
            "recent": Analysis.objects.filter(user=request.user)
            .select_related("resume", "job")
            .order_by("-created_at")[:6],
        },
    )


# ----------------------------------------------------------------- resumes
@login_required
def resume_add(request):
    form = ResumeForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        resume = form.save()
        messages.success(request, "Resume saved.")
        return redirect("resume_detail", pk=resume.pk)
    return render(request, "skillmap/resume_form.html", {"form": form})


@login_required
def resume_detail(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    taxonomy = services.load_taxonomy()
    return render(
        request,
        "skillmap/resume_detail.html",
        {
            "resume": resume,
            "skill_groups": services.skills_by_category(taxonomy, taxonomy.find(resume.text)),
            "health": engine.resume_health(resume.text),
            "analyses": resume.analyses.select_related("job"),
        },
    )


@login_required
@require_POST
def resume_delete(request, pk):
    get_object_or_404(Resume, pk=pk, user=request.user).delete()
    messages.success(request, "Resume deleted.")
    return redirect("dashboard")


# -------------------------------------------------------------------- jobs
@login_required
def job_add(request):
    form = JobForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.user = request.user
        job.save()
        messages.success(request, "Job description saved.")
        return redirect("job_detail", pk=job.pk)
    return render(request, "skillmap/job_form.html", {"form": form})


@login_required
def job_detail(request, pk):
    job = get_object_or_404(JobDescription, pk=pk, user=request.user)
    taxonomy = services.load_taxonomy()
    required, preferred = engine.classify_job_skills(taxonomy, job.text)
    return render(
        request,
        "skillmap/job_detail.html",
        {
            "job": job,
            "required": sorted(required),
            "preferred": sorted(preferred),
            "analyses": job.analyses.select_related("resume"),
        },
    )


@login_required
@require_POST
def job_delete(request, pk):
    get_object_or_404(JobDescription, pk=pk, user=request.user).delete()
    messages.success(request, "Job description deleted.")
    return redirect("dashboard")


# ---------------------------------------------------------------- analysis
@login_required
def analyze(request):
    has_data = (
        Resume.objects.filter(user=request.user).exists()
        and JobDescription.objects.filter(user=request.user).exists()
    )
    if not has_data:
        messages.info(request, "Add at least one resume and one job description first.")
        return redirect("dashboard")

    initial = {}
    if request.GET.get("resume", "").isdigit():
        initial["resume"] = int(request.GET["resume"])
    job_ids = [int(j) for j in request.GET.getlist("job") if j.isdigit()]
    if job_ids:
        initial["jobs"] = job_ids

    form = AnalyzeForm(request.user, request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        resume = form.cleaned_data["resume"]
        results = services.run_many(request.user, resume, form.cleaned_data["jobs"])
        if len(results) == 1:
            return redirect("analysis_detail", pk=results[0].pk)
        return redirect("rank", resume_id=resume.pk)
    return render(request, "skillmap/analyze.html", {"form": form})


@login_required
def rank(request, resume_id):
    resume = get_object_or_404(Resume, pk=resume_id, user=request.user)
    analyses = resume.analyses.select_related("job").order_by("-score", "job__title")
    return render(request, "skillmap/rank.html", {"resume": resume, "analyses": analyses})


@login_required
def analysis_detail(request, pk):
    analysis = get_object_or_404(
        Analysis.objects.select_related("resume", "job"), pk=pk, user=request.user
    )
    return render(
        request,
        "skillmap/analysis_detail.html",
        {
            "analysis": analysis,
            "result": analysis.details,
            "health": engine.resume_health(analysis.resume.text),
        },
    )
