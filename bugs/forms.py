from django import forms
from django.contrib.auth import get_user_model
from teams.models import Team
from .models import Bug, Comment, STATUS
from .tags import parse_tags

User = get_user_model()

# Ці статуси може ставити (і знімати) лише той, хто має право закривати баги
RESTRICTED_STATUSES = ("closed", "wontfix")

class BugForm(forms.ModelForm):
    tags = forms.CharField(label="Теги", required=False, max_length=300,
                           help_text="Через кому, напр.: оплата, мобільна версія")

    class Meta:
        model = Bug
        fields = ("team", "title", "area", "severity", "steps", "expected", "actual", "assignee")
        widgets = {f: forms.Textarea(attrs={"rows": 4}) for f in ("steps", "expected", "actual")}

    field_order = ["team", "title", "area", "severity", "tags", "steps", "expected", "actual", "assignee"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        teams = Team.objects.filter(memberships__user=user).distinct()
        self.fields["team"].queryset = teams
        self.fields["assignee"].queryset = User.objects.filter(memberships__team__in=teams).distinct()
        self.fields["assignee"].required = False
        self.fields["assignee"].empty_label = "Автоматично (за зоною відповідальності)"

    def clean_tags(self):
        return parse_tags(self.cleaned_data["tags"])

    def clean(self):
        data = super().clean()
        team, who = data.get("team"), data.get("assignee")
        if team and who and not team.memberships.filter(user=who).exists():
            self.add_error("assignee", "Цей користувач не в обраній команді")
        return data

class BugUpdateForm(forms.ModelForm):
    tags = forms.CharField(label="Теги", required=False, max_length=300, help_text="Через кому")

    class Meta:
        model = Bug
        fields = ("status", "assignee")

    def __init__(self, *args, can_close=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = User.objects.filter(memberships__team=self.instance.team)
        self.fields["tags"].initial = ", ".join(t.name for t in self.instance.tags.all())
        if not can_close:
            if self.instance.status in RESTRICTED_STATUSES:
                self.fields["status"].disabled = True
            else:
                self.fields["status"].choices = [(v, l) for v, l in STATUS if v not in RESTRICTED_STATUSES]
            self.fields["status"].help_text = "Закривати баги може лише той, кому команда дала це право"

    def clean_tags(self):
        return parse_tags(self.cleaned_data["tags"])

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("text",)
        labels = {"text": ""}
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": "Напишіть коментар..."})}
