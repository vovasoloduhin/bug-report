from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from bugs.models import Bug
from .forms import TeamForm, AddMemberForm, MemberForm, InviteForm
from .models import Team, Membership, TeamInvite


def _team_and_me(request, pk):
    """Команда + членство поточного користувача. 404, якщо він не в команді."""
    team = get_object_or_404(Team, pk=pk, memberships__user=request.user)
    me = team.memberships.select_related("team", "user").get(user=request.user)
    return team, me


def _require_manage(me):
    if not me.perm_manage:
        raise PermissionDenied


def _can_manage(me, target):
    """Керувати можна лише тими, хто не має права керування (крім власника — він може всіма)."""
    return me.perm_manage and (me.is_owner or not target.perm_manage)


def _can_edit(me, target):
    return _can_manage(me, target)


def _can_remove(me, target):
    return not target.is_owner and (_can_manage(me, target) or target.pk == me.pk)


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
        Membership.objects.create(team=team, user=request.user, area="other",
                                  can_close_bugs=True, can_manage_members=True)
        return redirect("team_detail", pk=team.pk)
    return render(request, "teams/form.html", {"form": form})

@login_required
def team_detail(request, pk):
    team, me = _team_and_me(request, pk)
    rows = []
    for m in team.memberships.select_related("user__profile", "team"):
        can_edit = _can_edit(me, m)
        rows.append({
            "m": m,
            "found": Bug.objects.filter(team=team, reporter=m.user).count(),
            "open": Bug.objects.filter(team=team, assignee=m.user).exclude(status__in=["fixed", "closed"]).count(),
            "can_edit": can_edit,
            "can_remove": _can_remove(me, m),
            "form": MemberForm(instance=m, actor_is_owner=me.is_owner, auto_id=False) if can_edit else None,
        })
    invites = []
    if me.perm_manage:
        for inv in team.invites.filter(is_active=True).select_related("created_by"):
            if inv.is_valid:
                invites.append({"obj": inv,
                                "url": request.build_absolute_uri(reverse("team_join", args=[inv.token]))})
    return render(request, "teams/detail.html", {
        "team": team, "rows": rows, "me": me, "invites": invites,
        "form": AddMemberForm(), "invite_form": InviteForm(),
    })

@login_required
@require_POST
def add_member(request, pk):
    team, me = _team_and_me(request, pk)
    _require_manage(me)
    form = AddMemberForm(request.POST)
    if form.is_valid():
        user = form.cleaned_data["username"]
        existing = team.memberships.select_related("team", "user").filter(user=user).first()
        if existing and not _can_manage(me, existing):
            raise PermissionDenied
        _, created = Membership.objects.update_or_create(
            team=team, user=user, defaults={"area": form.cleaned_data["area"]})
        messages.success(request, "Учасника додано" if created else "Відповідальність оновлено")
    else:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("team_detail", pk=pk)

@login_required
@require_POST
def member_update(request, pk, member_pk):
    team, me = _team_and_me(request, pk)
    target = get_object_or_404(team.memberships.select_related("team", "user"), pk=member_pk)
    if not _can_edit(me, target):
        raise PermissionDenied
    form = MemberForm(request.POST, instance=target, actor_is_owner=me.is_owner)
    if form.is_valid():
        form.save()
        messages.success(request, f"Збережено: {target.user.display_name}")
    else:
        messages.error(request, "Не вдалося зберегти зміни")
    return redirect("team_detail", pk=pk)

@login_required
@require_POST
def member_remove(request, pk, member_pk):
    team, me = _team_and_me(request, pk)
    target = get_object_or_404(team.memberships.select_related("team", "user"), pk=member_pk)
    if not _can_remove(me, target):
        raise PermissionDenied
    # баги, призначені на того, хто йде, лишаються без відповідального
    Bug.objects.filter(team=team, assignee=target.user).update(assignee=None)
    left_self = target.pk == me.pk
    target.delete()
    if left_self:
        messages.success(request, f"Ви вийшли з команди «{team.name}»")
        return redirect("team_list")
    messages.success(request, "Учасника видалено з команди")
    return redirect("team_detail", pk=pk)

@login_required
@require_POST
def invite_create(request, pk):
    team, me = _team_and_me(request, pk)
    _require_manage(me)
    form = InviteForm(request.POST)
    if form.is_valid():
        inv = form.save(commit=False)
        inv.team, inv.created_by = team, request.user
        days = int(form.cleaned_data["ttl"])
        inv.expires_at = timezone.now() + timedelta(days=days) if days else None
        inv.save()
        messages.success(request, "Посилання-запрошення створено — скопіюйте його нижче")
    else:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("team_detail", pk=pk)

@login_required
@require_POST
def invite_revoke(request, pk, invite_pk):
    team, me = _team_and_me(request, pk)
    _require_manage(me)
    inv = get_object_or_404(TeamInvite, pk=invite_pk, team=team)
    inv.is_active = False
    inv.save(update_fields=["is_active"])
    messages.success(request, "Посилання скасовано")
    return redirect("team_detail", pk=pk)

@login_required
def team_join(request, token):
    """Сторінка підтвердження + вступ у команду за посиланням."""
    invite = get_object_or_404(TeamInvite.objects.select_related("team", "created_by"), token=token)
    team = invite.team
    if team.memberships.filter(user=request.user).exists():
        messages.info(request, "Ви вже в цій команді")
        return redirect("team_detail", pk=team.pk)
    if not invite.is_valid:
        return render(request, "teams/join.html", {"invite": invite, "invalid": True}, status=410)
    if request.method == "POST":
        now = timezone.now()
        with transaction.atomic():
            # атомарно «займаємо» використання, щоб ліміт не обійшли два одночасні кліки
            taken = (TeamInvite.objects
                     .filter(pk=invite.pk, is_active=True)
                     .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
                     .filter(Q(max_uses__isnull=True) | Q(uses__lt=F("max_uses")))
                     .update(uses=F("uses") + 1))
            if not taken:
                return render(request, "teams/join.html", {"invite": invite, "invalid": True}, status=410)
            Membership.objects.get_or_create(team=team, user=request.user, defaults={"area": invite.area})
        messages.success(request, f"Ви приєдналися до команди «{team.name}»")
        return redirect("team_detail", pk=team.pk)
    return render(request, "teams/join.html", {"invite": invite})
