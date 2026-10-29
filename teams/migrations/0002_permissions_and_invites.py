import django.db.models.deletion
import teams.models
from django.conf import settings
from django.db import migrations, models


def grant_owner_rights(apps, schema_editor):
    """Власники вже існуючих команд отримують явні права (на випадок перегляду в адмінці)."""
    Membership = apps.get_model("teams", "Membership")
    for m in Membership.objects.select_related("team"):
        if m.team.owner_id == m.user_id:
            m.can_close_bugs = True
            m.can_manage_members = True
            m.save(update_fields=["can_close_bugs", "can_manage_members"])


class Migration(migrations.Migration):

    dependencies = [
        ("teams", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="can_close_bugs",
            field=models.BooleanField(default=False, verbose_name="Може закривати баги"),
        ),
        migrations.AddField(
            model_name="membership",
            name="can_manage_members",
            field=models.BooleanField(default=False, verbose_name="Може керувати складом команди"),
        ),
        migrations.CreateModel(
            name="TeamInvite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(default=teams.models.generate_token, editable=False, max_length=64, unique=True)),
                ("area", models.CharField(choices=[("ui_ux", "UI/UX"), ("frontend", "Frontend"), ("backend", "Backend"), ("database", "База даних"), ("devops", "DevOps"), ("qa", "QA"), ("other", "Інше")], default="other", max_length=20, verbose_name="Зона нового учасника")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("max_uses", models.PositiveIntegerField(blank=True, null=True, verbose_name="Макс. кількість використань")),
                ("uses", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invites", to="teams.team")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.RunPython(grant_owner_rights, migrations.RunPython.noop),
    ]
