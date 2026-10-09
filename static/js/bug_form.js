// Підставляє відповідального за обрану зону, поки користувач не обрав його вручну
(() => {
  const form = document.getElementById("bug-form");
  const team = form.querySelector("[name=team]");
  const area = form.querySelector("[name=area]");
  const who = form.querySelector("[name=assignee]");
  let manual = false;
  who.addEventListener("change", () => (manual = true));
  async function suggest() {
    if (manual || !team.value || !area.value) return;
    const r = await fetch(`${form.dataset.suggest}?team=${team.value}&area=${area.value}`);
    const { user_id } = await r.json();
    who.value = user_id || "";
  }
  team.addEventListener("change", suggest);
  area.addEventListener("change", suggest);
})();
