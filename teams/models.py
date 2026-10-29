import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

AREAS = [
    ("ui_ux", "UI/UX"), ("frontend", "Frontend"), ("backend", "Backend"),
    ("database", "База даних"), ("devops", "DevOps"), ("qa", "QA"), ("other", "Інше"),
]


def generate_token():
    return secrets.token_urlsafe(24)


class Team(models.Model):
    name = models.CharField("Назва", max_length=100)
    description = models.TextField("Опис", blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_teams")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    area = models.CharField("Відповідальність", max_length=20, choices=AREAS)
    can_close_bugs = models.BooleanField("Може закривати баги", default=False)
    can_manage_members = models.BooleanField("Може керувати складом команди", default=False)

    class Meta:
        unique_together = ("team", "user")

    @property
    def is_owner(self):
        return self.team.owner_id == self.user_id

    # Власник завжди має всі права, решта — за прапорцями.
    @property
    def perm_close(self):
        return self.is_owner or self.can_close_bugs

    @property
    def perm_manage(self):
        return self.is_owner or self.can_manage_members

    def __str__(self):
        return f"{self.user} · {self.get_area_display()} ({self.team})"


class TeamInvite(models.Model):
    """Запрошення в команду за посиланням."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="invites")
    token = models.CharField(max_length=64, unique=True, default=generate_token, editable=False)
    area = models.CharField("Зона нового учасника", max_length=20, choices=AREAS, default="other")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField("Макс. кількість використань", null=True, blank=True)
    uses = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        if self.max_uses is not None and self.uses >= self.max_uses:
            return False
        return True

    def __str__(self):
        return f"Запрошення в {self.team} ({self.token[:6]}…)"
