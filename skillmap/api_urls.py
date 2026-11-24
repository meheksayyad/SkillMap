from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import api_views as v

urlpatterns = [
    path("token/", obtain_auth_token, name="api_token"),
    path("analyze/", v.QuickAnalyzeView.as_view(), name="api_analyze"),
    path("skills/", v.SkillListView.as_view(), name="api_skills"),
    path("analyses/", v.AnalysisListCreateView.as_view(), name="api_analyses"),
]
