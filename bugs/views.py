import os
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from teams.models import Membership, Team
from .forms import BugForm, BugUpdateForm, CommentForm
from .models import Attachment, Bug, BugEvent, Comment, Notification, STATUS

def notify(user, bug, text, actor):
    if user and user != actor:
        Notification.objects.create(user=user, bug=bug, text=text[:300])

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".txt", ".log"}
MAX_SIZE = 5 * 1024 * 1024

def save_attachments(request, bug):
    saved = 0
    for f in request.FILES.getlist("files"):
        if os.path.splitext(f.name)[1].lower() not in ALLOWED_EXT:
            messages.error(request, f"{f.name}: непідтримуваний тип файлу")
        elif f.size > MAX_SIZE:
            messages.error(request, f"{f.name}: більше 5 МБ")
        else:
            Attachment.objects.create(bug=bug, uploaded_by=request.user, file=f)
            saved += 1
    if saved:
        BugEvent.objects.create(bug=bug, actor=request.user, text=f"додав вкладень: {saved}")
    return saved

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
        BugEvent.objects.create(bug=bug, actor=request.user, text="створив баг" + (f" і призначив {bug.assignee.display_name}" if bug.assignee else ""))
        save_attachments(request, bug)
        steps = bug.steps if len(bug.steps) < 120 else bug.steps[:120] + "…"
        notify(bug.assignee, bug,
               f"{request.user.display_name} знайшов {bug.code} у вашій зоні ({bug.get_area_display()}). Дії: {steps}",
               request.user)
        return redirect(bug)
    return render(request, "bugs/form.html", {"form": form})

@login_required
def bug_detail(request, pk):
    bug = get_object_or_404(visible_bugs(request.user), pk=pk)
    form = BugUpdateForm(instance=bug)
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
    elif request.method == "POST" and "upload" in request.POST:
        save_attachments(request, bug)
        return redirect(bug)
    elif request.method == "POST":
        form = BugUpdateForm(request.POST, instance=bug)
        if form.is_valid():
            old_assignee, old_status = Bug.objects.values_list("assignee_id", "status").get(pk=pk)
            bug = form.save()
            if bug.assignee_id != old_assignee:
                BugEvent.objects.create(bug=bug, actor=request.user,
                    text=f"призначив відповідального: {bug.assignee.display_name if bug.assignee else '—'}")
                notify(bug.assignee, bug, f"Вам призначено {bug.code}: {bug.title}", request.user)
            if bug.status != old_status:
                BugEvent.objects.create(bug=bug, actor=request.user,
                    text=f"змінив статус на «{bug.get_status_display()}»")
                notify(bug.reporter, bug, f"Статус {bug.code} змінено на «{bug.get_status_display()}»", request.user)
            return redirect(bug)
    timeline = sorted(
        list(bug.comments.select_related("author")) + list(bug.events.select_related("actor")),
        key=lambda i: i.created_at)
    return render(request, "bugs/detail.html", {"bug": bug, "form": form, "cform": cform, "timeline": timeline})

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

@login_required
def attachment_file(request, pk):
    att = get_object_or_404(Attachment, pk=pk, bug__team__memberships__user=request.user)
    return FileResponse(att.file.open("rb"), as_attachment=not att.is_image, filename=att.filename)
