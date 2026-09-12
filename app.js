const body = document.getElementById("recipesBody");
const search = document.getElementById("search");

const backdrop = document.getElementById("modalBackdrop");
const closeModalButton = document.getElementById("closeModal");

const modalImage = document.getElementById("modalImage");
const modalSource = document.getElementById("modalSource");
const modalTitle = document.getElementById("modalTitle");
const modalSubtitle = document.getElementById("modalSubtitle");
const modalYield = document.getElementById("modalYield");
const modalPrep = document.getElementById("modalPrep");
const modalCook = document.getElementById("modalCook");
const modalIngredients = document.getElementById("modalIngredients");
const modalInstructions = document.getElementById("modalInstructions");
const originalLink = document.getElementById("originalLink");

let recipes = [];

function esc(s = "") {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function row(r, index) {
  return `
    <tr>
      <td>
        <button class="recipe-button" data-index="${index}">${esc(r.name)}</button>
        ${r.subtitle ? `<div class="recipe-subtitle">${esc(r.subtitle)}</div>` : ""}
      </td>
      <td><div class="source">${esc(r.source)}</div></td>
      <td>
        <img class="thumb" src="${esc(r.image)}" alt="${esc(r.name)}" loading="lazy"
             onerror="this.style.display='none'; this.insertAdjacentHTML('afterend','<div>לא ניתן לטעון תמונה</div>')">
      </td>
      <td>
        <div class="made">${r.made ? "✅" : "⬜"}</div>
        <div class="made-label">${r.made ? "הוכן" : "טרם הוכן"}</div>
      </td>
    </tr>`;
}

function render(list) {
  body.innerHTML = list.map(({recipe, originalIndex}) => row(recipe, originalIndex)).join("");
}

function showModal(recipe) {
  modalImage.src = recipe.image || "";
  modalImage.alt = recipe.name || "";
  modalSource.textContent = recipe.source || "";
  modalTitle.textContent = recipe.name || "";
  modalSubtitle.textContent = recipe.subtitle || "";

  modalYield.textContent = recipe.yield ? `🍽️ ${recipe.yield}` : "";
  modalPrep.textContent = recipe.prepTime ? `⏱️ הכנה: ${recipe.prepTime}` : "";
  modalCook.textContent = recipe.cookTime ? `🔥 בישול/אפייה: ${recipe.cookTime}` : "";

  modalIngredients.innerHTML = (recipe.ingredients || [])
    .map(x => `<li>${esc(x)}</li>`)
    .join("");

  modalInstructions.innerHTML = (recipe.instructions || [])
    .map(x => `<li>${esc(x)}</li>`)
    .join("");

  originalLink.href = recipe.url || "#";

  backdrop.classList.remove("hidden");
  backdrop.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function hideModal() {
  backdrop.classList.add("hidden");
  backdrop.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

body.addEventListener("click", (event) => {
  const button = event.target.closest(".recipe-button");
  if (!button) return;

  const index = Number(button.dataset.index);
  if (recipes[index]) showModal(recipes[index]);
});

closeModalButton.addEventListener("click", hideModal);

backdrop.addEventListener("click", (event) => {
  if (event.target === backdrop) hideModal();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") hideModal();
});

fetch("recipes.json")
  .then(r => r.json())
  .then(data => {
    recipes = data;
    render(recipes.map((recipe, originalIndex) => ({recipe, originalIndex})));
  });

search.addEventListener("input", () => {
  const q = search.value.trim().toLowerCase();

  const filtered = recipes
    .map((recipe, originalIndex) => ({recipe, originalIndex}))
    .filter(({recipe}) =>
      `${recipe.name} ${recipe.subtitle || ""} ${recipe.source || ""}`
        .toLowerCase()
        .includes(q)
    );

  render(filtered);
});
