from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import ApiToken, Profile, User

admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "bio")
    search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "prefix", "scope", "created_at", "last_used_at", "revoked_at")
    readonly_fields = ("prefix", "key_hash", "created_at", "last_used_at")
