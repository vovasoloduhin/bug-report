from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import RegisterForm

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
