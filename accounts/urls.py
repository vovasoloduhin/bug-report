from django.urls import path, include
from . import views
urlpatterns = [
    path("register/", views.register, name="register"),
    path("profile/", views.my_profile, name="my_profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("profile/<int:pk>/", views.profile, name="profile"),
    path("avatar/<int:pk>/", views.avatar, name="avatar"),
    path("tokens/", views.tokens, name="tokens"),
    path("tokens/<int:pk>/revoke/", views.token_revoke, name="token_revoke"),
    path("", include("django.contrib.auth.urls")),
]
