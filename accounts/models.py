import hashlib
import os
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone


class User(AbstractUser):
    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initial(self):
        return self.display_name[:1].upper()

    @property
    def avatar_url(self):
        """Адреса аватарки або "" (тоді шаблон показує першу літеру імені)."""
        try:
            return self.profile.avatar_url
        except Profile.DoesNotExist:
            return ""


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField("Аватарка", upload_to="avatars/", blank=True)
    bio = models.CharField("Про себе", max_length=300, blank=True)

    def __str__(self):
        return f"Профіль {self.user}"

    @property
    def avatar_url(self):
        if not self.avatar:
            return ""
        # ?v=<випадкове ім'я файлу>: після заміни аватарки браузер не покаже стару з кешу
        version = os.path.splitext(os.path.basename(self.avatar.name))[0]
        return f"{reverse('avatar', args=[self.user_id])}?v={version}"


class ApiToken(models.Model):
    """Персональний токен для API/MCP. У базі лише SHA-256 хеш: сам токен видно один раз при створенні."""
    SCOPES = [("read", "Лише читання"), ("write", "Читання й запис")]
    MAX_ACTIVE = 10

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField("Назва", max_length=60)
    prefix = models.CharField(max_length=12, editable=False)
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    scope = models.CharField("Доступ", max_length=5, choices=SCOPES, default="read")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def _hash(raw):
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def issue(cls, user, name, scope="read", days=90):
        raw = "bt_" + secrets.token_urlsafe(32)
        obj = cls.objects.create(
            user=user, name=name, scope=scope, prefix=raw[:10], key_hash=cls._hash(raw),
            expires_at=timezone.now() + timedelta(days=days) if days else None)
        return obj, raw

    @classmethod
    def authenticate(cls, raw):
        if not raw.startswith("bt_") or len(raw) > 200:
            return None
        tok = cls.objects.select_related("user").filter(key_hash=cls._hash(raw)).first()
        if not tok or not tok.is_active or not tok.user.is_active:
            return None
        now = timezone.now()
        if not tok.last_used_at or now - tok.last_used_at > timedelta(minutes=1):
            cls.objects.filter(pk=tok.pk).update(last_used_at=now)
        return tok

    @property
    def is_active(self):
        return not self.revoked_at and not (self.expires_at and self.expires_at <= timezone.now())

    @property
    def status_label(self):
        if self.revoked_at:
            return "Відкликано"
        return "Прострочено" if not self.is_active else "Активний"

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"
