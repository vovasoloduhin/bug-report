from django.urls import path
from . import views
urlpatterns = [
    path("", views.bug_list, name="bug_list"),
    path("bugs/new/", views.bug_create, name="bug_create"),
    path("bugs/suggest/", views.suggest_assignee, name="suggest_assignee"),
    path("bugs/<int:pk>/", views.bug_detail, name="bug_detail"),
    path("notifications/", views.notification_list, name="notifications"),
    path("notifications/<int:pk>/open/", views.notification_open, name="notification_open"),
]
