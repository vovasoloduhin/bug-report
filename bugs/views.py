from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from teams.models import Membership, Team
from .forms import BugForm, BugUpdateForm, CommentForm
from .models import Bug, Notification, STATUS

def notify(user, bug, text, actor):
    if user and user != actor:
        Notification.objects.create(user=user, bug=bug, text=text[:300])

def visible_bugs(user):
    return (Bug.objects.filter(team__memberships__user=user).distinct()
            .select_related("team", "reporter", "assignee"))

@login_required
def bug_list(request):
    bugs = visible_bugs(request.user)
    f = request.GET
    if f.get("team"): bugs = bugs.filter(team_id=f["team"])
    if f.get("status"): bugs = bugs.filter(status=f["status"])
    if f.get("scope") == "mine": bugs = bugs.filter(assignee=request.user)
    if f.get("scope") == "reported": bugs = bugs.filter(reporter=request.user)
    return render(request, "bugs/list.html", {
        "bugs": bugs, "f": f, "statuses": STATUS,
        "teams": Team.objects.filter(memberships__user=request.user).distinct(),
    })

@login_required
def bug_create(request):
    form = BugForm(request.POST or None, user=request.user)
    if form.is_valid():
        bug = form.save(commit=False)
        bug.reporter = request.user
        if not bug.assignee:
            m = Membership.objects.filter(team=bug.team, area=bug.area).first()
            bug.assignee = m.user if m else None
        bug.save()
        steps = bug.steps if len(bug.steps) < 120 else bug.steps[:120] + "…"
        notify(bug.assignee, bug,
               f"{request.user.display_name} знайшов {bug.code} у вашій зоні ({bug.get_area_display()}). Дії: {steps}",
               request.user)
        return redirect(bug)
    return render(request, "bugs/form.html", {"form": form})

@login_required
def bug_detail(request, pk):
    bug = get_object_or_404(visible_bugs(request.user), pk=pk)
    form = BugUpdateForm(request.POST or None, instance=bug)
    cform = CommentForm()
    if request.method == "POST" and "comment" in request.POST:
        cform = CommentForm(request.POST)
        if cform.is_valid():
            c = cform.save(commit=False)
            c.bug, c.author = bug, request.user
            c.save()
            for u in {bug.reporter, bug.assignee} - {None}:
                notify(u, bug, f"{request.user.display_name} прокоментував {bug.code}: {c.text[:100]}", request.user)
            return redirect(bug)
    elif request.method == "POST":
        form = BugUpdateForm(request.POST, instance=bug)
        if form.is_valid():
            old_assignee, old_status = Bug.objects.values_list("assignee_id", "status").distinct()
            if bug.assignee_id != old_assignee:
                notify(bug.assignee, bug, f"Вам призначено {bug.code}: {bug.title}", request.user)
            if bug.status != old_status:
                notify(bug.reporter, bug, f"Статус {bug.code} змінено на «{bug.get_status_display()}»", request.user)
            return redirect(bug)
        return render(request, "bugs/detail.html", {"bug": bug, "form": form})

@login_required
def suggest_assignee(request):
    m = Membership.objects.filter(team_id=request.GET.get("team"), area=request.GET.get("area"),
                                  team__memberships__user=request.user).first()
    return JsonResponse({"user_id": m.user_id if m else None})

@login_required
def notification_list(request):
    return render(request, "bugs/notifications.html", {"items": request.user.notifications.select_related("bug")})

@login_required
def notification_open(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    return redirect(n.bug)
