import secrets
from io import BytesIO

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .models import Profile, User

AVATAR_MAX_BYTES = 5 * 1024 * 1024
AVATAR_MAX_PIXELS = 40_000_000
AVATAR_SIZE = 256
AVATAR_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")


def process_avatar(upload):
    upload.seek(0)
    img = ImageOps.exif_transpose(Image.open(upload)).convert("RGBA")
    img = ImageOps.fit(img, (AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, "WEBP", quality=88)
    return ContentFile(buf.getvalue())


class ProfileForm(forms.ModelForm):
    avatar = forms.ImageField(
        label="Аватарка", required=False,
        widget=forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp,image/gif"}),
        help_text="PNG, JPG, WEBP або GIF до 5 МБ. Зображення буде обрізано до квадрата.")
    remove_avatar = forms.BooleanField(label="Видалити поточну аватарку", required=False)

    class Meta:
        model = Profile
        fields = ("bio",)
        widgets = {"bio": forms.Textarea(attrs={"rows": 3, "maxlength": 300,
                                               "placeholder": "Кілька слів про себе, наприклад: що тестуєте чи за що відповідаєте"})}

    def clean_avatar(self):
        f = self.cleaned_data.get("avatar")
        if not f:
            return f
        if f.size > AVATAR_MAX_BYTES:
            raise forms.ValidationError("Файл більший за 5 МБ.")
        img = f.image
        if img.format not in AVATAR_FORMATS:
            raise forms.ValidationError("Підтримуються лише PNG, JPG, WEBP і GIF.")
        if img.width * img.height > AVATAR_MAX_PIXELS:
            raise forms.ValidationError("Зображення має завелику роздільну здатність.")
        return f

    def save(self, commit=True):
        profile = super().save(commit=False)
        new = self.cleaned_data.get("avatar")
        old_name = profile.avatar.name if profile.avatar else ""
        replaced = False
        if new:
            name = f"{profile.user_id}_{secrets.token_hex(8)}.webp"
            profile.avatar.save(name, process_avatar(new), save=False)
            replaced = True
        elif self.cleaned_data.get("remove_avatar") and old_name:
            profile.avatar = ""
            replaced = True
        if commit:
            profile.save()
            if replaced and old_name:
                try:
                    profile.avatar.storage.delete(old_name)
                except OSError:
                    pass
        return profile
