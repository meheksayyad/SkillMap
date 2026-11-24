from django.conf import settings
from rest_framework import serializers

from .models import Analysis, JobDescription, Resume, Skill


class AnalyzeInputSerializer(serializers.Serializer):
    resume_text = serializers.CharField(max_length=settings.MAX_RESUME_CHARS, min_length=40)
    job_text = serializers.CharField(max_length=settings.MAX_JOB_CHARS, min_length=40)


class SkillSerializer(serializers.ModelSerializer):
    prerequisites = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")

    class Meta:
        model = Skill
        fields = ("id", "name", "category", "aliases", "prerequisites")


class AnalysisSerializer(serializers.ModelSerializer):
    resume_title = serializers.CharField(source="resume.title", read_only=True)
    job_title = serializers.CharField(source="job.title", read_only=True)

    class Meta:
        model = Analysis
        fields = ("id", "resume", "resume_title", "job", "job_title", "score", "label", "details", "created_at")
        read_only_fields = fields


class CreateAnalysisSerializer(serializers.Serializer):
    resume = serializers.IntegerField()
    job = serializers.IntegerField()
