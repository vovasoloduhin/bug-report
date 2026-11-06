"""Уся бізнес-логіка багів в одному місці. Нею користуються і сторінки сайту (views.py), і REST API (api.py),
а значить і MCP-сервер: права та сповіщення поводяться однаково, звідки б не прийшов запит."""
import re

from django.db.models import Q

from teams.models import Membership
from .models import Bug, BugEvent, Comment, Notification
from .tags import set_tags


def notify(user, bug, text, actor):
    if user and user != actor:
        Notification.objects.create(user=user, bug=bug, text=text[:300])


def apply_filters(bugs, user, f):
    """Фільтри списку багів. `f` — QueryDict або dict зі строковими значеннями."""
    if str(f.get("team", "")).isdigit():
        bugs = bugs.filter(team_id=f["team"])
    if f.get("status"):
        bugs = bugs.filter(status=f["status"])
    if f.get("tag"):
        bugs = bugs.filter(tags__name=f["tag"])
    if f.get("scope") == "mine":
        bugs = bugs.filter(assignee=user)
    if f.get("scope") == "reported":
        bugs = bugs.filter(reporter=user)
    # пошук: кожне слово має зустрітися (AND), місце — будь-де: назва, кроки, коментарі, теги, номер
    for term in str(f.get("q", "")).split()[:8]:
        word = term.lower().lstrip("#")
        if not word:
            continue
        cond = Q(search_text__contains=word)
        m = re.fullmatch(r"(?:bug-?)?0*(\d{1,9})", word)
        if m:
            cond |= Q(pk=int(m.group(1)))
        bugs = bugs.filter(cond)
    return bugs


def create_bug(user, form):
    """`form` — валідна BugForm. Створює баг, теги, історію й сповіщення відповідальному."""
    bug = form.save(commit=False)
    bug.reporter = user
    if not bug.assignee:
        m = Membership.objects.filter(team=bug.team, area=bug.area).first()
        bug.assignee = m.user if m else None
    bug.save()
    set_tags(bug, form.cleaned_data["tags"])
    bug.rebuild_search_text()
    BugEvent.objects.create(bug=bug, actor=user, text="створив баг" + (
        f" і призначив {bug.assignee.display_name}" if bug.assignee else ""))
    steps = bug.steps if len(bug.steps) < 120 else bug.steps[:120] + "…"
    notify(bug.assignee, bug,
           f"{user.display_name} знайшов {bug.code} у вашій зоні ({bug.get_area_display()}). Дії: {steps}", user)
    return bug


def add_comment(user, bug, text):
    c = Comment.objects.create(bug=bug, author=user, text=text)
    bug.rebuild_search_text()
    for u in {bug.reporter, bug.assignee} - {None}:
        notify(u, bug, f"{user.display_name} прокоментував {bug.code}: {c.text[:100]}", user)
    return c


def status_changed(bug, actor):
    """Викликати після збереження нового статусу: запис в історії + сповіщення автору."""
    BugEvent.objects.create(bug=bug, actor=actor, text=f"змінив статус на «{bug.get_status_display()}»")
    notify(bug.reporter, bug, f"Статус {bug.code} змінено на «{bug.get_status_display()}»", actor)
