"""REST API (Django REST Framework). Token auth: send `Authorization: Token <key>`.

Public endpoints are throttled (see DEFAULT_THROTTLE_RATES in settings).
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Analysis, JobDescription, Resume, Skill
from .serializers import (
    AnalysisSerializer,
    AnalyzeInputSerializer,
    CreateAnalysisSerializer,
    SkillSerializer,
)


class QuickAnalyzeView(APIView):
    """POST /api/analyze/  {"resume_text": "...", "job_text": "..."}  -> match report.

    Public (no login) and not saved, so recruiters and scripts can try it instantly.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        data = AnalyzeInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = services.quick_check(data.validated_data["resume_text"], data.validated_data["job_text"])
        return Response(result)


class SkillListView(generics.ListAPIView):
    """GET /api/skills/?category=Backend  - the skill taxonomy (public)."""

    permission_classes = [AllowAny]
    serializer_class = SkillSerializer
    pagination_class = None  # ~100 small rows

    def get_queryset(self):
        qs = Skill.objects.prefetch_related("prerequisites")
        category = self.request.query_params.get("category")
        return qs.filter(category__iexact=category) if category else qs


class AnalysisListCreateView(generics.ListAPIView):
    """GET  /api/analyses/  - my saved analyses, best first
    POST /api/analyses/  {"resume": 1, "job": 2}  - analyze two of MY saved items
    """

    serializer_class = AnalysisSerializer

    def get_queryset(self):
        return Analysis.objects.filter(user=self.request.user).select_related("resume", "job")

    def post(self, request):
        data = CreateAnalysisSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        # get_object_or_404 with user=... => other people's ids look like they don't exist.
        resume = get_object_or_404(Resume, pk=data.validated_data["resume"], user=request.user)
        job = get_object_or_404(JobDescription, pk=data.validated_data["job"], user=request.user)
        analysis = services.run_analysis(request.user, resume, job)
        return Response(AnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)
