from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.utils import timezone
from .forms import ProfileForm, RegisterForm, TokenForm, UserEditForm
from .models import ApiToken, Profile, User
from .stats import can_view_profile, profile_stats

def register(request):
    # ?next= потрібен, щоб після реєстрації за посиланням-запрошенням повернутися на запрошення
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    form = RegisterForm(request.POST or None)
    if form.is_valid():
        login(request, form.save())
        if nxt and url_has_allowed_host_and_scheme(
                nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(nxt)
        return redirect("bug_list")
    return render(request, "registration/register.html", {"form": form, "next": nxt})

@login_required
def my_profile(request):
    return redirect("profile", pk=request.user.pk)

@login_required
def profile(request, pk):
    target = get_object_or_404(User, pk=pk)
    if not can_view_profile(request.user, target):
        raise Http404
    prof, _ = Profile.objects.get_or_create(user=target)
    return render(request, "accounts/profile.html", {
        "target": target, "prof": prof, "is_me": target.pk == request.user.pk,
        "s": profile_stats(request.user, target),
    })

@login_required
def profile_edit(request):
    prof, _ = Profile.objects.get_or_create(user=request.user)
    uform = UserEditForm(request.POST or None, instance=request.user)
    pform = ProfileForm(request.POST or None, request.FILES or None, instance=prof)
    if request.method == "POST" and uform.is_valid() and pform.is_valid():
        uform.save()
        pform.save()
        messages.success(request, "Профіль оновлено")
        return redirect("profile", pk=request.user.pk)
    return render(request, "accounts/profile_edit.html", {"uform": uform, "pform": pform, "prof": prof})

@login_required
def avatar(request, pk):
    """Віддає аватарку лише авторизованим користувачам (папка media/ назовні не відкрита)."""
    prof = get_object_or_404(Profile, user_id=pk)
    if not prof.avatar:
        raise Http404
    try:
        fh = prof.avatar.open("rb")
    except (FileNotFoundError, ValueError):
        raise Http404
    resp = FileResponse(fh, content_type="image/webp")
    resp["Cache-Control"] = "private, max-age=604800"   # адреса містить ?v=..., тож нова аватарка підтягнеться
    return resp

@login_required
def tokens(request):
    """Токени для API/MCP. Сам токен показуємо лише одразу після створення."""
    form = TokenForm(request.POST or None)
    new_token = None
    active = request.user.api_tokens.filter(revoked_at__isnull=True)
    if request.method == "POST" and form.is_valid():
        if sum(t.is_active for t in active) >= ApiToken.MAX_ACTIVE:
            form.add_error(None, f"Не більше {ApiToken.MAX_ACTIVE} активних токенів. Відкличте непотрібні.")
        else:
            _, new_token = ApiToken.issue(request.user, form.cleaned_data["name"],
                                          form.cleaned_data["scope"], int(form.cleaned_data["days"]))
            form = TokenForm()
    return render(request, "accounts/tokens.html", {
        "form": form, "new_token": new_token, "items": request.user.api_tokens.all()})

@login_required
@require_POST
def token_revoke(request, pk):
    tok = get_object_or_404(ApiToken, pk=pk, user=request.user)
    if not tok.revoked_at:
        tok.revoked_at = timezone.now()
        tok.save(update_fields=["revoked_at"])
    messages.success(request, f"Токен «{tok.name}» відкликано")
    return redirect("tokens")
