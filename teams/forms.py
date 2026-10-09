from django import forms
from django.contrib.auth import get_user_model
from .models import Team, Membership, AREAS

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
