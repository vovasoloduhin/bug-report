// Кнопка «Копіювати» для посилань-запрошень
document.querySelectorAll("[data-copy]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const input = document.getElementById(btn.dataset.copy);
    try {
      await navigator.clipboard.writeText(input.value);
    } catch {
      input.select();
      document.execCommand("copy"); // запасний варіант для http без clipboard API
    }
    const old = btn.textContent;
    btn.textContent = "Скопійовано";
    if (window.BT) window.BT.toast({ text: "Посилання скопійовано в буфер обміну", kind: "success", timeout: 3000 });
    setTimeout(() => (btn.textContent = old), 1800);
  });
});
