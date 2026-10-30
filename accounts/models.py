import os
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse


class User(AbstractUser):
    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initial(self):
        return self.display_name[:1].upper()

    @property
    def avatar_url(self):
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
        version = os.path.splitext(os.path.basename(self.avatar.name))[0]
        return f"{reverse('avatar', args=[self.user_id])}?v={version}"
