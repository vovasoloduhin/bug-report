import os
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, When
from django.http import FileResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from teams.models import Membership, Team
from .forms import BugForm, BugUpdateForm, CommentForm
from .models import Attachment, Bug, BugEvent, Comment, Notification, STATUS, Tag
from .tags import set_tags

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

OPEN_STATUSES = ("new", "in_progress")

def is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"

def can_delete_bug(user, bug, member):
    """Видаляти баг може його автор, власник команди або той, кому дали право закривати баги."""
    return bug.reporter_id == user.id or member.perm_close

def panel_context(user):
    """Дані для правої панелі: зведення, «мої» баги й остання активність (лише з команд користувача)."""
    base = Bug.objects.filter(team__memberships__user=user)
    by_status = dict(base.order_by().values_list("status").annotate(n=Count("pk")))
    open_n = sum(by_status.get(k, 0) for k in OPEN_STATUSES)
    mine_qs = base.filter(assignee=user, status__in=OPEN_STATUSES)
    mine = (mine_qs.select_related("team")
            .annotate(rank=Case(When(severity="critical", then=0), When(severity="high", then=1),
                                When(severity="medium", then=2), default=3, output_field=IntegerField()))
            .order_by("rank", "-created_at")[:5])
    events = (BugEvent.objects.filter(bug__team__memberships__user=user)
              .select_related("actor", "bug").order_by("-created_at")[:8])
    comments = (Comment.objects.filter(bug__team__memberships__user=user)
                .select_related("author", "bug").order_by("-created_at")[:8])
    feed = [{"who": e.actor.display_name, "text": e.text, "bug": e.bug, "at": e.created_at} for e in events]
    feed += [{"who": c.author.display_name, "text": "прокоментував", "bug": c.bug, "at": c.created_at} for c in comments]
    feed.sort(key=lambda i: i["at"], reverse=True)
    return {
        "total": sum(by_status.values()),
        "open": open_n,
        "resolved": sum(n for k, n in by_status.items() if k not in OPEN_STATUSES),
        "urgent": base.filter(status__in=OPEN_STATUSES, severity__in=("high", "critical")).count(),
        "statuses": [{"key": k, "label": label, "n": by_status.get(k, 0)} for k, label in STATUS],
        "mine": mine,
        "mine_total": mine_qs.count(),
        "feed": feed[:8],
    }

@login_required
def bug_list(request):
    teams = Team.objects.filter(memberships__user=request.user).distinct()
    bugs = visible_bugs(request.user).prefetch_related("tags")
    f = request.GET
    if f.get("team", "").isdigit(): bugs = bugs.filter(team_id=f["team"])
    if f.get("status"): bugs = bugs.filter(status=f["status"])
    if f.get("tag"): bugs = bugs.filter(tags__name=f["tag"])
    if f.get("scope") == "mine": bugs = bugs.filter(assignee=request.user)
    if f.get("scope") == "reported": bugs = bugs.filter(reporter=request.user)
    # пошук: кожне слово має зустрітися (AND), місце — будь-де: назва, кроки, коментарі, теги, номер
    for term in f.get("q", "").split()[:8]:
        word = term.lower().lstrip("#")
        if not word:
            continue
        cond = Q(search_text__contains=word)
        m = re.fullmatch(r"(?:bug-?)?0*(\d{1,9})", word)
        if m:
            cond |= Q(pk=int(m.group(1)))
        bugs = bugs.filter(cond)
    params = f.copy()
    params.pop("tag", None)
    members = {m.team_id: m for m in Membership.objects.filter(user=request.user).select_related("team")}
    bugs = list(bugs)
    for b in bugs:
        m = members.get(b.team_id)
        b.can_delete = bool(m and can_delete_bug(request.user, b, m))
    return render(request, "bugs/list.html", {
        "bugs": bugs, "f": f, "statuses": STATUS, "teams": teams, "panel": panel_context(request.user),
        "all_tags": Tag.objects.filter(team__in=teams).values_list("name", flat=True).distinct().order_by("name"),
        "base_qs": params.urlencode(),
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
        set_tags(bug, form.cleaned_data["tags"])
        bug.rebuild_search_text()
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
    member = Membership.objects.select_related("team").get(team=bug.team, user=request.user)
    can_close = member.perm_close
    can_delete = can_delete_bug(request.user, bug, member)
    form = BugUpdateForm(instance=bug, can_close=can_close)
    cform = CommentForm()
    if request.method == "POST" and "comment" in request.POST:
        cform = CommentForm(request.POST)
        if cform.is_valid():
            c = cform.save(commit=False)
            c.bug, c.author = bug, request.user
            c.save()
            bug.rebuild_search_text()
            for u in {bug.reporter, bug.assignee} - {None}:
                notify(u, bug, f"{request.user.display_name} прокоментував {bug.code}: {c.text[:100]}", request.user)
            return redirect(bug)
    elif request.method == "POST" and "upload" in request.POST:
        save_attachments(request, bug)
        return redirect(bug)
    elif request.method == "POST":
        form = BugUpdateForm(request.POST, instance=bug, can_close=can_close)
        if form.is_valid():
            old_assignee, old_status = Bug.objects.values_list("assignee_id", "status").get(pk=pk)
            old_tags = set(bug.tags.values_list("name", flat=True))
            bug = form.save()
            new_tags = form.cleaned_data["tags"]
            if set(new_tags) != old_tags:
                set_tags(bug, new_tags)
                bug.rebuild_search_text()
                BugEvent.objects.create(bug=bug, actor=request.user,
                    text="змінив теги: " + (", ".join("#" + t for t in new_tags) or "—"))
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
    return render(request, "bugs/detail.html", {"bug": bug, "form": form, "cform": cform, "timeline": timeline,
        "can_close": can_close, "can_delete": can_delete})

@login_required
@require_POST
def bug_delete(request, pk):
    """Видалення бага. Для fetch-запиту (X-Requested-With) відповідаємо JSON — сторінка не перезавантажується."""
    bug = get_object_or_404(visible_bugs(request.user), pk=pk)
    member = Membership.objects.select_related("team").get(team=bug.team, user=request.user)
    if not can_delete_bug(request.user, bug, member):
        msg = "Видаляти баг може його автор, власник команди або той, кому дали право закривати баги"
        if is_ajax(request):
            return JsonResponse({"ok": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect(bug)
    code, team = bug.code, bug.team
    files = [a.file for a in bug.attachments.all()]
    with transaction.atomic():
        bug.delete()  # коментарі, історія, вкладення (записи) і сповіщення видаляються каскадом
        Tag.objects.filter(team=team, bugs__isnull=True).delete()  # теги, що лишилися без багів
    for f in files:  # самі файли з диска
        try:
            f.delete(save=False)
        except OSError:
            pass
    message = f"Баг {code} видалено"
    if is_ajax(request):
        return JsonResponse({"ok": True, "message": message, "id": pk})
    messages.success(request, message)
    return redirect("bug_list")

@login_required
def bug_panel(request):
    """Лише HTML правої панелі — сторінка підміняє ним вміст без перезавантаження."""
    return render(request, "bugs/_panel.html", {"panel": panel_context(request.user)})

@login_required
def suggest_assignee(request):
    m = Membership.objects.filter(team_id=request.GET.get("team"), area=request.GET.get("area"),
                                  team__memberships__user=request.user).first()
    return JsonResponse({"user_id": m.user_id if m else None})

@login_required
def tag_suggest(request):
    tid = request.GET.get("team", "")
    if not tid.isdigit():
        return JsonResponse({"tags": []})
    names = (Tag.objects.filter(team_id=tid, team__memberships__user=request.user)
             .annotate(n=Count("bugs")).order_by("-n", "name").values_list("name", flat=True)[:30])
    return JsonResponse({"tags": list(names)})

@login_required
def notifications_poll(request):
    """Нові непрочитані сповіщення з id більшим за `after` + загальна кількість непрочитаних."""
    try:
        after = int(request.GET.get("after", 0))
    except ValueError:
        after = 0
    qs = request.user.notifications
    fresh = qs.filter(id__gt=after, is_read=False).select_related("bug").order_by("id")[:20]
    return JsonResponse({
        "unread": qs.filter(is_read=False).count(),
        "items": [{
            "id": n.id, "code": n.bug.code, "text": n.text,
            "url": reverse("notification_open", args=[n.pk]),
            "time": timezone.localtime(n.created_at).strftime("%d.%m %H:%M"),
        } for n in fresh],
    })

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
