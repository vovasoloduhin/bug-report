from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from bugs.models import Bug
from .forms import TeamForm, AddMemberForm
from .models import Team, Membership

@login_required
def team_list(request):
    teams = Team.objects.filter(memberships__user=request.user).distinct()
    return render(request, "teams/list.html", {"teams": teams})

@login_required
def team_create(request):
    form = TeamForm(request.POST or None)
    if form.is_valid():
        team = form.save(commit=False)
        team.owner = request.user
        team.save()
        Membership.objects.create(team=team, user=request.user, area="other")
        return redirect("team_detail", pk=team.pk)
    return render(request, "teams/form.html", {"form": form})

@login_required
def team_detail(request, pk):
    team = get_object_or_404(Team, pk=pk, memberships__user=request.user)
    rows = []
    for m in team.memberships.select_related("user"):
        rows.append({
            "m": m,
            "found": Bug.objects.filter(team=team, reporter=m.user).count(),
            "open": Bug.objects.filter(team=team, assignee=m.user).exclude(status__in=["fixed", "closed"]).count(),
        })
    return render(request, "teams/detail.html", {
        "team": team, "rows": rows, "form": AddMemberForm(),
        "is_owner": team.owner_id == request.user.id,
    })

@login_required
@require_POST
def add_member(request, pk):
    team = get_object_or_404(Team, pk=pk, owner=request.user)
    form = AddMemberForm(request.POST)
    if form.is_valid():
        _, created = Membership.objects.update_or_create(
            team=team, user=form.cleaned_data["username"],
            defaults={"area": form.cleaned_data["area"]})
        messages.success(request, "Учасника додано" if created else "Відповідальність оновлено")
    else:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("team_detail", pk=pk)
