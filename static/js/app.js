(() => {
  "use strict";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const csrfToken = () => { const m = $('meta[name="csrf-token"]'); return m ? m.content : ""; };

  function icon(id) {
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "ic");
    const use = document.createElementNS(NS, "use");
    use.setAttribute("href", "#" + id);
    svg.append(use);
    return svg;
  }

  function dismiss(box) {
    if (!box || box.classList.contains("leaving")) return;
    box.classList.add("leaving");
    box.addEventListener("animationend", () => box.remove(), { once: true });
    setTimeout(() => box.remove(), 500);
  }

  function toast({ text, code, url, kind = "info", timeout = 8000 }) {
    const host = document.getElementById("toasts");
    if (!host) return null;
    const box = document.createElement("div");
    box.className = "toast toast-" + kind;
    box.setAttribute("role", kind === "error" ? "alert" : "status");

    const body = document.createElement(url ? "a" : "div");
    body.className = "toast-body";
    if (url) body.href = url;
    if (code) {
      const c = document.createElement("span");
      c.className = "code";
      c.textContent = code;
      body.append(c, " ");
    }
    body.append(text);

    const close = document.createElement("button");
    close.type = "button";
    close.className = "x";
    close.setAttribute("aria-label", "Закрити");
    close.append(icon("i-x"));
    close.addEventListener("click", () => dismiss(box));

    box.append(body, close);
    host.append(box);

    const alive = () => Array.from(host.children).filter((c) => !c.classList.contains("leaving"));
    while (alive().length > 4) dismiss(alive()[0]);

    let timer;
    const arm = () => { clearTimeout(timer); if (timeout) timer = setTimeout(() => dismiss(box), timeout); };
    box.addEventListener("mouseenter", () => clearTimeout(timer)); // під курсором не зникає
    box.addEventListener("mouseleave", arm);
    arm();
    return box;
  }

  const dlg = document.getElementById("confirm");
  if (dlg) {
    dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close("cancel"); });
  }

  function confirmDialog({ title = "Підтвердьте дію", text = "", ok = "Підтвердити", danger = false } = {}) {
    if (!dlg || typeof dlg.showModal !== "function") return Promise.resolve(window.confirm(title + "\n" + text));
    $("#confirm-title", dlg).textContent = title;
    $("#confirm-text", dlg).textContent = text;
    const okBtn = $("#confirm-ok", dlg);
    okBtn.textContent = ok;
    okBtn.classList.toggle("danger", danger);
    dlg.classList.toggle("is-danger", danger);
    dlg.returnValue = "";
    return new Promise((resolve) => {
      dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true });
      dlg.showModal();
    });
  }

  async function post(url, body) {
    const r = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
      body: body || new FormData(),
    });
    if (r.redirected) throw new Error("Сесія завершилась — увійдіть знову");
    let data = null;
    try { data = await r.json(); } catch { }
    if (!r.ok || !data || data.ok === false) throw new Error((data && data.error) || "Помилка " + r.status);
    return data;
  }

  async function getHtml(url) {
    const r = await fetch(url, {
      credentials: "same-origin", cache: "no-store",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!r.ok || r.redirected) throw new Error(String(r.status));
    return r.text();
  }

  async function refreshPanel() {
    const rail = document.getElementById("rail");
    const body = document.getElementById("rail-body");
    if (!rail || !body) return;
    try { body.innerHTML = await getHtml(rail.dataset.url); } catch {}
  }

  function syncList() {
    const rows = $$("#bug-table tbody tr[data-bug]");
    const empty = $("#bug-table .empty-row");
    if (empty) empty.hidden = rows.length > 0;
    const counter = document.getElementById("list-count");
    if (counter) counter.textContent = rows.length;
  }

  async function refreshList() {
    const tbody = $("#bug-table tbody");
    if (!tbody || (dlg && dlg.open) || $(".is-deleting", tbody)) return;
    try {
      const doc = new DOMParser().parseFromString(await getHtml(location.href), "text/html");
      const fresh = doc.querySelector("#bug-table tbody");
      if (!fresh) return;
      tbody.replaceWith(document.importNode(fresh, true));
      const counter = document.getElementById("list-count");
      const freshCounter = doc.getElementById("list-count");
      if (counter && freshCounter) counter.textContent = freshCounter.textContent;
    } catch { /* мережа недоступна */ }
  }

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-delete-url]");
    if (!btn || btn.disabled) return;
    e.preventDefault();
    const row = btn.closest("tr");
    const yes = await confirmDialog({
      title: "Видалити " + btn.dataset.code + "?",
      text: "«" + btn.dataset.title + "» буде видалено разом із коментарями, історією та вкладеннями. Цю дію неможливо скасувати.",
      ok: "Видалити",
      danger: true,
    });
    if (!yes) return;

    btn.disabled = true;
    if (row) row.classList.add("is-deleting");
    try {
      const res = await post(btn.dataset.deleteUrl);
      if (row) { row.classList.add("gone"); await sleep(240); row.remove(); }
      syncList();
      toast({ text: res.message, kind: "success" });
      refreshPanel();
    } catch (err) {
      btn.disabled = false;
      if (row) row.classList.remove("is-deleting");
      toast({ text: err.message, kind: "error" });
    }
  });

  document.addEventListener("submit", async (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-confirm") || form.dataset.confirmed) return;
    e.preventDefault();
    const yes = await confirmDialog({
      title: form.dataset.confirmTitle || "Підтвердьте дію",
      text: form.dataset.confirm,
      ok: form.dataset.confirmOk || "Підтвердити",
      danger: form.hasAttribute("data-confirm-danger"),
    });
    if (yes) { form.dataset.confirmed = "1"; form.submit(); }
  });

  $$(".flash").forEach((el) => {
    const kind = el.classList.contains("error") ? "error" : el.classList.contains("success") ? "success" : "info";
    if (toast({ text: el.textContent.trim(), kind, timeout: 7000 })) el.remove();
  });

  document.addEventListener("bt:notifications", () => { refreshPanel(); refreshList(); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshPanel(); });

  window.BT = { toast, confirm: confirmDialog, post, refreshPanel, refreshList };
})();
