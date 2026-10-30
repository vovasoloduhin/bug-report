// Миттєвий попередній перегляд аватарки до збереження форми.
(() => {
  "use strict";
  const input = document.getElementById("id_avatar");
  const box = document.getElementById("avatar-preview");
  if (!input || !box) return;
  const MAX = 5 * 1024 * 1024;
  let url = null;

  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if (!file) return;
    const problem = !file.type.startsWith("image/") ? "Оберіть зображення (PNG, JPG, WEBP або GIF)."
                  : file.size > MAX ? "Файл більший за 5 МБ." : "";
    if (problem) {
      input.value = "";
      if (window.BT) BT.toast({ text: problem, kind: "error" }); else alert(problem);
      return;
    }
    if (url) URL.revokeObjectURL(url);
    url = URL.createObjectURL(file);
    box.textContent = "";
    const img = document.createElement("img");
    img.src = url; img.alt = "";
    box.append(img);
  });
})();
