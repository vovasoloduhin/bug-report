from django.conf import settings
from django.db import models

AREAS = [
    ("ui_ux", "UI/UX"), ("frontend", "Frontend"), ("backend", "Backend"),
    ("database", "База даних"), ("devops", "DevOps"), ("qa", "QA"), ("other", "Інше"),
]

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

    class Meta:
        unique_together = ("team", "user")

    def __str__(self):
        return f"{self.user} · {self.get_area_display()} ({self.team})"
