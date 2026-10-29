import django.db.models.deletion
from django.db import migrations, models


def fill_search_text(apps, schema_editor):
    Bug = apps.get_model("bugs", "Bug")
    Comment = apps.get_model("bugs", "Comment")
    for b in Bug.objects.all():
        parts = [f"BUG-{b.pk:04d}", b.title, b.steps, b.expected, b.actual]
        parts += Comment.objects.filter(bug=b).values_list("text", flat=True)
        Bug.objects.filter(pk=b.pk).update(search_text="\n".join(parts).lower())


class Migration(migrations.Migration):

    dependencies = [
        ("bugs", "0003_alter_bugevent_options_alter_comment_options_and_more"),
        ("teams", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=30, verbose_name="Тег")),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tags", to="teams.team")),
            ],
            options={"ordering": ["name"], "unique_together": {("team", "name")}},
        ),
        migrations.AddField(
            model_name="bug",
            name="tags",
            field=models.ManyToManyField(blank=True, related_name="bugs", to="bugs.tag", verbose_name="Теги"),
        ),
        migrations.AddField(
            model_name="bug",
            name="search_text",
            field=models.TextField(blank=True, default="", editable=False),
        ),
        migrations.RunPython(fill_search_text, migrations.RunPython.noop),
    ]
