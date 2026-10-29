from django.conf import settings
from django.db import models
from django.urls import reverse
from teams.models import Team, AREAS

SEVERITY = [("low", "Низька"), ("medium", "Середня"), ("high", "Висока"), ("critical", "Критична")]
STATUS = [("new", "Новий"), ("in_progress", "У роботі"), ("fixed", "Виправлено"),
          ("closed", "Закрито"), ("wontfix", "Не буде виправлено")]

class Tag(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField("Тег", max_length=30)

    class Meta:
        unique_together = ("team", "name")
        ordering = ["name"]

    def __str__(self):
        return f"#{self.name}"

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
    tags = models.ManyToManyField(Tag, blank=True, related_name="bugs", verbose_name="Теги")
    # Усе, по чому шукаємо, у нижньому регістрі. SQLite порівнює без урахування регістру
    # лише ASCII, тому для кирилиці `icontains` не працює — шукаємо по заздалегідь «опущеному» тексту.
    search_text = models.TextField(blank=True, default="", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def rebuild_search_text(self):
        parts = [self.code, self.title, self.steps, self.expected, self.actual]
        parts += self.tags.values_list("name", flat=True)
        parts += self.comments.values_list("text", flat=True)
        Bug.objects.filter(pk=self.pk).update(search_text="\n".join(parts).lower())

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

class Comment(models.Model):
    bug = models.ForeignKey(Bug, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField("Коментар")
    created_at = models.DateTimeField(auto_now_add=True)
    kind = "comment"

    class Meta:
        ordering = ["created_at"]

class BugEvent(models.Model):
    """Запис в історії змін: створення, зміна статусу, зміна відповідального."""
    bug = models.ForeignKey(Bug, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    kind = "event"

    class Meta:
        ordering = ["created_at"]

class Attachment(models.Model):
    bug = models.ForeignKey(Bug, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    file = models.FileField(upload_to="attachments/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def filename(self):
        return self.file.name.rsplit("/", 1)[-1]

    @property
    def is_image(self):
        return self.filename.lower().rsplit(".", 1)[-1] in ("png", "jpg", "jpeg", "gif", "webp")
