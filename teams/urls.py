from django.urls import path
from . import views
urlpatterns = [
    path("", views.team_list, name="team_list"),
    path("new/", views.team_create, name="team_create"),
    path("join/<str:token>/", views.team_join, name="team_join"),
    path("<int:pk>/", views.team_detail, name="team_detail"),
    path("<int:pk>/add-member/", views.add_member, name="add_member"),
    path("<int:pk>/invites/new/", views.invite_create, name="invite_create"),
    path("<int:pk>/invites/<int:invite_pk>/revoke/", views.invite_revoke, name="invite_revoke"),
    path("<int:pk>/members/<int:member_pk>/update/", views.member_update, name="member_update"),
    path("<int:pk>/members/<int:member_pk>/remove/", views.member_remove, name="member_remove"),
]
