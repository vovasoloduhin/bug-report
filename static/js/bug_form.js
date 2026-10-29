
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

  // Підказки тегів: клік по чіпу додає тег у поле
  const tagsInput = form.querySelector("[name=tags]");
  const box = document.createElement("div");
  box.className = "tag-suggest";
  tagsInput.parentElement.appendChild(box);
  async function loadTags() {
    box.textContent = "";
    if (!team.value) return;
    const r = await fetch(`${form.dataset.tags}?team=${team.value}`);
    const { tags } = await r.json();
    tags.forEach((name) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = "#" + name;
      b.addEventListener("click", () => {
        const cur = tagsInput.value.split(",").map((s) => s.trim()).filter(Boolean);
        if (!cur.includes(name)) cur.push(name);
        tagsInput.value = cur.join(", ");
      });
      box.appendChild(b);
    });
  }
  team.addEventListener("change", loadTags);
  loadTags();
})();

//Підставляє відповідального за обрану зону, поки користувач не обрав його вручну
