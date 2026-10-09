from django import forms
from django.contrib.auth import get_user_model
from teams.models import Team
from .models import Bug

User = get_user_model()

class BugForm(forms.ModelForm):
    class Meta:
        model = Bug
        fields = ("team", "title", "area", "severity", "steps", "expected", "actual", "assignee")
        widgets = {f: forms.Textarea(attrs={"rows": 4}) for f in ("steps", "expected", "actual")}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        teams = Team.objects.filter(memberships__user=user).distinct()
        self.fields["team"].queryset = teams
        self.fields["assignee"].queryset = User.objects.filter(memberships__team__in=teams).distinct()
        self.fields["assignee"].required = False
        self.fields["assignee"].empty_label = "Автоматично (за зоною відповідальності)"

    def clean(self):
        data = super().clean()
        team, who = data.get("team"), data.get("assignee")
        if team and who and not team.memberships.filter(user=who).exists():
            self.add_error("assignee", "Цей користувач не в обраній команді")
        return data

class BugUpdateForm(forms.ModelForm):
    class Meta:
        model = Bug
        fields = ("status", "assignee")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = User.objects.filter(memberships__team=self.instance.team)
