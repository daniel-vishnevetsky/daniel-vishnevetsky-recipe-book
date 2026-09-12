const body = document.getElementById("recipesBody");
const search = document.getElementById("search");
let allRecipes = [];

function recipeRow(r) {
  const image = r.image
    ? `<img class="thumb" src="${r.image}" alt="${r.name}" loading="lazy">`
    : `<div class="placeholder" aria-label="placeholder image">${r.emoji || "🍽️"}</div>`;

  const madeClass = r.made ? "" : " no";
  const madeIcon = r.made ? "👨‍🍳" : "👨‍🍳";
  const madeText = r.made ? "הוכן" : "טרם הוכן";

  return `
    <tr>
      <td>
        <a class="recipe-link" href="${r.url}" target="_blank" rel="noopener noreferrer">
          ${r.name}
        </a>
        ${r.subtitle ? `<div class="recipe-subtitle">${r.subtitle}</div>` : ""}
      </td>
      <td>
        <div class="source-badge">${r.source}</div>
      </td>
      <td>${image}</td>
      <td>
        <div class="made-icon${madeClass}">${madeIcon}</div>
        <div class="made-text">${madeText}</div>
      </td>
    </tr>
  `;
}

function render(items) {
  body.innerHTML = items.map(recipeRow).join("");
}

fetch("recipes.json")
  .then(r => r.json())
  .then(data => {
    allRecipes = data;
    render(allRecipes);
  });

search.addEventListener("input", () => {
  const q = search.value.trim().toLowerCase();

  const filtered = allRecipes.filter(r =>
    [r.name, r.subtitle, r.source].join(" ").toLowerCase().includes(q)
  );

  render(filtered);
});
