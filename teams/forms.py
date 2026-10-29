from django import forms
from django.contrib.auth import get_user_model
from .models import Team, Membership, TeamInvite, AREAS

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ("name", "description")

class AddMemberForm(forms.Form):
    username = forms.CharField(label="Логін користувача")
    area = forms.ChoiceField(label="За що відповідає", choices=AREAS)

    def clean_username(self):
        try:
            return get_user_model().objects.get(username=self.cleaned_data["username"])
        except get_user_model().DoesNotExist:
            raise forms.ValidationError("Такого користувача немає")

class MemberForm(forms.ModelForm):
    """Зміна зони й прав учасника. Які поля доступні — залежить від того, хто редагує."""
    class Meta:
        model = Membership
        fields = ("area", "can_close_bugs", "can_manage_members")

    def __init__(self, *args, actor_is_owner=False, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.is_owner:
            # у власника права завжди повні — міняти можна лише зону
            del self.fields["can_close_bugs"]
            del self.fields["can_manage_members"]
        elif not actor_is_owner:
            # право керувати складом видає тільки власник
            del self.fields["can_manage_members"]

class InviteForm(forms.ModelForm):
    ttl = forms.ChoiceField(
        label="Скільки діє", initial="7",
        choices=[("1", "1 день"), ("7", "7 днів"), ("30", "30 днів"), ("0", "Без обмеження")])
    max_uses = forms.IntegerField(
        label="Макс. кількість використань", required=False, min_value=1,
        help_text="Порожньо — без ліміту. 1 — одноразове посилання.")

    class Meta:
        model = TeamInvite
        fields = ("area", "max_uses")

    field_order = ["area", "ttl", "max_uses"]
