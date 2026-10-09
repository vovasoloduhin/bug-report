from django.conf import settings
from django.db import models
from django.urls import reverse
from teams.models import Team, AREAS

SEVERITY = [("low", "Низька"), ("medium", "Середня"), ("high", "Висока"), ("critical", "Критична")]
STATUS = [("new", "Новий"), ("in_progress", "У роботі"), ("fixed", "Виправлено"),
          ("closed", "Закрито"), ("wontfix", "Не буде виправлено")]

class Bug(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="bugs", verbose_name="Команда")
    title = models.CharField("Короткий опис", max_length=200)
    area = models.CharField("Де баг", max_length=20, choices=AREAS)
    severity = models.CharField("Важливість", max_length=10, choices=SEVERITY, default="medium")
    status = models.CharField("Статус", max_length=12, choices=STATUS, default="new")
    steps = models.TextField("Кроки відтворення")
    expected = models.TextField("Очікуваний результат", blank=True)
    actual = models.TextField("Фактичний результат", blank=True)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_bugs")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="assigned_bugs", verbose_name="Відповідальний")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def code(self):
        return f"BUG-{self.pk:04d}"

    def get_absolute_url(self):
        return reverse("bug_detail", args=[self.pk])

    def __str__(self):
        return f"{self.code} {self.title}"

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    bug = models.ForeignKey(Bug, on_delete=models.CASCADE)
    text = models.CharField(max_length=300)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
