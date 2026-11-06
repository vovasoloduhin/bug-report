from django.urls import path
from . import api

urlpatterns = [
    path("me/", api.me, name="api_me"),
    path("teams/", api.teams, name="api_teams"),
    path("bugs/", api.bugs, name="api_bugs"),
    path("bugs/<int:pk>/", api.bug_detail, name="api_bug"),
    path("bugs/<int:pk>/comments/", api.comment, name="api_comment"),
    path("bugs/<int:pk>/status/", api.set_status, name="api_status"),
]
