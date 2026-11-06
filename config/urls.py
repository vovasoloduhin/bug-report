from django.contrib import admin
from django.urls import path, include
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("teams/", include("teams.urls")),
    path("api/v1/", include("bugs.api_urls")),
    path("", include("bugs.urls")),
]
