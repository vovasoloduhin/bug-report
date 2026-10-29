from django.urls import path
from . import views
urlpatterns = [
    path("", views.bug_list, name="bug_list"),
    path("bugs/new/", views.bug_create, name="bug_create"),
    path("bugs/suggest/", views.suggest_assignee, name="suggest_assignee"),
    path("bugs/tags/", views.tag_suggest, name="tag_suggest"),
    path("bugs/panel/", views.bug_panel, name="bug_panel"),
    path("bugs/<int:pk>/", views.bug_detail, name="bug_detail"),
    path("bugs/<int:pk>/delete/", views.bug_delete, name="bug_delete"),
    path("attachments/<int:pk>/", views.attachment_file, name="attachment"),
    path("notifications/", views.notification_list, name="notifications"),
    path("notifications/poll/", views.notifications_poll, name="notifications_poll"),
    path("notifications/<int:pk>/open/", views.notification_open, name="notification_open"),
]
