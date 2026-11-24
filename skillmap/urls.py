from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("skills/", views.skills_catalog, name="skills"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("resumes/new/", views.resume_add, name="resume_add"),
    path("resumes/<int:pk>/", views.resume_detail, name="resume_detail"),
    path("resumes/<int:pk>/delete/", views.resume_delete, name="resume_delete"),
    path("jobs/new/", views.job_add, name="job_add"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/delete/", views.job_delete, name="job_delete"),
    path("analyze/", views.analyze, name="analyze"),
    path("rank/<int:resume_id>/", views.rank, name="rank"),
    path("analyses/<int:pk>/", views.analysis_detail, name="analysis_detail"),
]
