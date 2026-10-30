import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_profiles(apps, schema_editor):
    """Профілі для користувачів, які зареєструвалися ще до появи профілів."""
    User = apps.get_model("accounts", "User")
    Profile = apps.get_model("accounts", "Profile")
    existing = set(Profile.objects.values_list("user_id", flat=True))
    Profile.objects.bulk_create([Profile(user_id=pk) for pk in User.objects.values_list("pk", flat=True)
                                 if pk not in existing])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("avatar", models.ImageField(blank=True, upload_to="avatars/", verbose_name="Аватарка")),
                ("bio", models.CharField(blank=True, max_length=300, verbose_name="Про себе")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RunPython(create_profiles, migrations.RunPython.noop),
    ]
