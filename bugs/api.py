"""REST API v1 (JSON). Авторизація: `Authorization: Bearer bt_...` (токен із «Мій профіль → API-токени»).
Запити виконуються від імені власника токена й підпорядковуються тим самим правилам, що й сайт:
бачити можна лише баги своїх команд, закривати («Закрито», «Не буде виправлено») лише з правом команди.
Видалення багів через API навмисно відсутнє."""
import functools
import json

from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from accounts.models import ApiToken
from accounts.stats import profile_stats
from teams.models import Membership, Team
from .forms import RESTRICTED_STATUSES, BugForm, CommentForm
from .models import Bug, STATUS
from .services import add_comment, apply_filters, create_bug, status_changed
from .views import visible_bugs

RATE_LIMIT_PER_MIN = 120
MAX_BODY = 100 * 1024


class ApiError(Exception):
    def __init__(self, status, message, extra=None):
        self.status, self.message, self.extra = status, message, extra or {}


def err(status, message, **extra):
    return JsonResponse({"error": message, **extra}, status=status, json_dumps_params={"ensure_ascii": False})


def ok(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})


def api(scope="read", methods=("GET",)):
    def deco(view):
        @csrf_exempt
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return err(405, "Метод не підтримується", allowed=list(methods))
            header = request.headers.get("Authorization", "")
            if not header.lower().startswith("bearer "):
                return err(401, "Потрібен заголовок Authorization: Bearer <токен>")
            token = ApiToken.authenticate(header[7:].strip())
            if not token:
                return err(401, "Недійсний, прострочений або відкликаний токен")
            if scope == "write" and token.scope != "write":
                return err(403, "Цей токен лише для читання. Створіть токен із доступом «Читання й запис».")
            key = f"api-rate:{token.pk}:{int(timezone.now().timestamp() // 60)}"
            cache.add(key, 0, 90)
            if cache.incr(key) > RATE_LIMIT_PER_MIN:
                return err(429, f"Забагато запитів (ліміт {RATE_LIMIT_PER_MIN} на хвилину)")
            request.user, request.api_token = token.user, token
            try:
                return view(request, *args, **kwargs)
            except ApiError as e:
                return err(e.status, e.message, **e.extra)
        return wrapper
    return deco


def body(request):
    if int(request.META.get("CONTENT_LENGTH") or 0) > MAX_BODY:
        raise ApiError(413, "Тіло запиту завелике")
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        raise ApiError(400, "Очікується JSON")
    if not isinstance(data, dict):
        raise ApiError(400, "Очікується JSON-об'єкт")
    return data


def form_errors(form):
    return {k: [str(e) for e in v] for k, v in form.errors.items()}


def person(u):
    return {"id": u.pk, "name": u.display_name} if u else None


def bug_dict(request, b, full=False):
    d = {
        "id": b.pk, "code": b.code, "title": b.title,
        "team": {"id": b.team_id, "name": b.team.name},
        "area": b.area, "area_label": b.get_area_display(),
        "severity": b.severity, "severity_label": b.get_severity_display(),
        "status": b.status, "status_label": b.get_status_display(),
        "reporter": person(b.reporter), "assignee": person(b.assignee),
        "tags": [t.name for t in b.tags.all()],
        "created_at": b.created_at.isoformat(), "updated_at": b.updated_at.isoformat(),
        "url": request.build_absolute_uri(b.get_absolute_url()),
    }
    if full:
        d.update({
            "steps": b.steps, "expected": b.expected, "actual": b.actual,
            "attachments": [a.filename for a in b.attachments.all()],
            "comments": [{"author": person(c.author), "text": c.text, "created_at": c.created_at.isoformat()}
                         for c in b.comments.select_related("author")],
            "history": [{"actor": person(e.actor), "text": e.text, "created_at": e.created_at.isoformat()}
                        for e in b.events.select_related("actor")],
        })
    return d


def get_visible(request, pk):
    bug = visible_bugs(request.user).prefetch_related("tags").filter(pk=pk).first()
    if not bug:
        raise ApiError(404, "Баг не знайдено")
    return bug


@api()
def me(request):
    u = request.user
    s = profile_stats(u, u)
    return ok({
        "id": u.pk, "username": u.username, "name": u.display_name,
        "token_scope": request.api_token.scope,
        "stats": {k: s[k] for k in ("found", "fixed", "working", "comments", "fix_rate")},
    })


@api()
def teams(request):
    out = []
    for m in Membership.objects.filter(user=request.user).select_related("team"):
        members = Membership.objects.filter(team=m.team).select_related("user")
        out.append({
            "id": m.team_id, "name": m.team.name, "my_area": m.area,
            "can_close_bugs": m.perm_close,
            "members": [{"id": x.user_id, "name": x.user.display_name, "area": x.area} for x in members],
        })
    return ok({"results": out})


@api(scope="read", methods=("GET", "POST"))
def bugs(request):
    if request.method == "POST":
        return create(request)
    try:
        limit = min(max(int(request.GET.get("limit", 20)), 1), 100)
    except ValueError:
        limit = 20
    qs = apply_filters(visible_bugs(request.user).prefetch_related("tags"), request.user, request.GET)
    total = qs.count()
    return ok({"count": total, "results": [bug_dict(request, b) for b in qs.order_by("-created_at")[:limit]]})


def create(request):
    if request.api_token.scope != "write":
        raise ApiError(403, "Цей токен лише для читання. Створіть токен із доступом «Читання й запис».")
    data = body(request)
    if isinstance(data.get("tags"), list):
        data["tags"] = ", ".join(str(t) for t in data["tags"])
    form = BugForm(data, user=request.user)
    if not form.is_valid():
        raise ApiError(400, "Некоректні дані", {"fields": form_errors(form)})
    bug = create_bug(request.user, form)
    return ok(bug_dict(request, get_visible(request, bug.pk), full=True), status=201)


@api()
def bug_detail(request, pk):
    return ok(bug_dict(request, get_visible(request, pk), full=True))


@api(scope="write", methods=("POST",))
def comment(request, pk):
    bug = get_visible(request, pk)
    form = CommentForm(body(request))
    if not form.is_valid():
        raise ApiError(400, "Некоректні дані", {"fields": form_errors(form)})
    c = add_comment(request.user, bug, form.cleaned_data["text"])
    return ok({"id": c.pk, "bug": bug.code, "created_at": c.created_at.isoformat()}, status=201)


@api(scope="write", methods=("POST",))
def set_status(request, pk):
    bug = get_visible(request, pk)
    new = body(request).get("status")
    if new not in dict(STATUS):
        raise ApiError(400, "Невідомий статус", {"allowed": [k for k, _ in STATUS]})
    member = Membership.objects.select_related("team").get(team=bug.team, user=request.user)
    # ті самі правила, що в BugUpdateForm: «Закрито» / «Не буде виправлено» лише з правом закривати баги
    if not member.perm_close and (new in RESTRICTED_STATUSES or bug.status in RESTRICTED_STATUSES):
        raise ApiError(403, "Закривати баги (і знімати закриття) може лише той, кому команда дала це право")
    if new != bug.status:
        bug.status = new
        bug.save(update_fields=["status", "updated_at"])
        status_changed(bug, request.user)
    return ok(bug_dict(request, get_visible(request, pk)))
