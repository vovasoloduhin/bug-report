(() => {
  const body = document.body;
  const pollUrl = body.dataset.poll;
  if (!pollUrl) return;

  const FAST = 5000;
  const SLOW = 15000;
  const baseTitle = document.title.replace(/^\(\d+\)\s*/, "");
  let lastId = parseInt(body.dataset.lastId || "0", 10) || 0;

  const store = {
    get() { try { return localStorage.getItem("bt_sound"); } catch { return null; } },
    set(v) { try { localStorage.setItem("bt_sound", v); } catch { } },
  };
  let soundOn = store.get() !== "off";
  let ctx = null;
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) ctx = new AC();
  } catch { }

  function unlock() {
    if (ctx && ctx.state === "suspended") return ctx.resume().catch(() => {});
    return Promise.resolve();
  }
  ["pointerdown", "pointerup", "click", "keydown", "touchend"]
    .forEach((e) => window.addEventListener(e, unlock, { passive: true }));

  function beep() {
    if (!soundOn || !ctx || ctx.state !== "running") return;
    const t0 = ctx.currentTime;
    [[880, 0], [1318, 0.14]].forEach(([freq, delay]) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, t0 + delay);
      gain.gain.exponentialRampToValueAtTime(0.25, t0 + delay + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + delay + 0.35);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t0 + delay);
      osc.stop(t0 + delay + 0.4);
    });
  }

  const toggle = document.getElementById("sound-toggle");
  const toggleLabel = document.getElementById("sound-label");
  function renderToggle() {
    if (!toggle) return;
    if (toggleLabel) toggleLabel.textContent = soundOn ? "Звук: увімкнено" : "Звук: вимкнено";
    toggle.setAttribute("aria-pressed", String(soundOn));
  }
  if (toggle) {
    renderToggle();
    toggle.addEventListener("click", () => {
      soundOn = !soundOn;
      store.set(soundOn ? "on" : "off");
      renderToggle();
      if (soundOn) unlock().then(beep);
    });
  }

  const countEl = document.getElementById("notif-count");
  function setUnread(n) {
    if (countEl) { countEl.textContent = n; countEl.hidden = n <= 0; }
    document.title = (n > 0 ? `(${n}) ` : "") + baseTitle;
  }
  setUnread(parseInt(countEl ? countEl.textContent : "0", 10) || 0);

  function showToast(item) {
    if (window.BT) window.BT.toast({ code: item.code, text: item.text, url: item.url, kind: "notify", timeout: 10000 });
  }

  function prependToList(item) {
    const list = document.getElementById("notif-list");
    if (!list) return;
    const empty = document.getElementById("notif-empty");
    if (empty) empty.remove();
    const a = document.createElement("a");
    a.className = "notif unread";
    a.href = item.url;
    const code = document.createElement("span");
    code.className = "code";
    code.textContent = item.code;
    const text = document.createElement("span");
    text.className = "notif-text";
    text.textContent = item.text;
    const time = document.createElement("span");
    time.className = "muted small notif-time";
    time.textContent = item.time;
    a.append(code, text, time);
    list.prepend(a);
  }

  let timer = null;
  let busy = false;
  let stopped = false;

  function schedule() {
    clearTimeout(timer);
    if (!stopped) timer = setTimeout(poll, document.hidden ? SLOW : FAST);
  }

  async function poll() {
    if (busy || stopped) return;
    busy = true;
    try {
      const r = await fetch(`${pollUrl}?after=${lastId}`, {
        credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" },
      });
      if (r.redirected) { stopped = true; return; }
      if (!r.ok) throw new Error(r.status);
      const data = await r.json();
      data.items.forEach((it) => {
        lastId = Math.max(lastId, it.id);
        showToast(it);
        prependToList(it);
      });
      if (data.items.length) {
        beep();
        document.dispatchEvent(new CustomEvent("bt:notifications", { detail: data.items }));
      }
      setUnread(data.unread);
    } catch {
    finally { busy = false; schedule(); }
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) { clearTimeout(timer); poll(); }
  });
  schedule();
})();
