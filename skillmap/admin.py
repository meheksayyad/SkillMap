from django.contrib import admin

from .models import Analysis, JobDescription, Resume, Skill


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "match_name")
    list_filter = ("category", "match_name")
    search_fields = ("name",)
    filter_horizontal = ("prerequisites",)


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "source_filename", "created_at")
    search_fields = ("title", "user__username")


@admin.register(JobDescription)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "user", "created_at")
    search_fields = ("title", "company")


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ("resume", "job", "score", "label", "created_at")
    list_filter = ("label",)
