from django.db.models import Count

from bugs.models import Bug, Comment, SEVERITY
from teams.models import Membership

OPEN = ("new", "in_progress")
DONE = ("fixed", "closed")
SEV_COLORS = {"low": "low", "medium": "medium", "high": "high", "critical": "critical"}


def can_view_profile(viewer, target):
    if viewer.pk == target.pk:
        return True
    return Membership.objects.filter(user=target, team__memberships__user=viewer).exists()


def profile_stats(viewer, target):
    visible = Bug.objects.filter(team__in=Membership.objects.filter(user=viewer).values("team"))
    found = visible.filter(reporter=target)
    fixed = visible.filter(assignee=target, status__in=DONE)
    working = visible.filter(assignee=target, status__in=OPEN)

    found_n, fixed_n, working_n = found.count(), fixed.count(), working.count()
    assigned_n = fixed_n + working_n
    by_sev = dict(found.order_by().values_list("severity").annotate(n=Count("pk")))
    top = max(by_sev.values(), default=0)

    return {
        "found": found_n,
        "fixed": fixed_n,
        "working": working_n,
        "comments": Comment.objects.filter(author=target, bug__in=visible).count(),
        "found_open": found.filter(status__in=OPEN).count(),
        "found_done": found.filter(status__in=DONE).count(),
        "fixed_critical": fixed.filter(severity__in=("high", "critical")).count(),
        "fix_rate": round(100 * fixed_n / assigned_n) if assigned_n else None,
        "severity": [{"key": k, "label": label, "n": by_sev.get(k, 0),
                      "pct": round(100 * by_sev.get(k, 0) / top) if top else 0} for k, label in SEVERITY],
        "recent_found": found.select_related("team").order_by("-created_at")[:5],
        "recent_fixed": fixed.select_related("team").order_by("-updated_at")[:5],
        "teams": Membership.objects.filter(user=target, team__in=Membership.objects.filter(user=viewer).values("team"))
                           .select_related("team"),
    }
