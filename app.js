
const recipes = window.RECIPES || [];
const sources = window.SOURCES || [];
const categories = window.CATEGORIES || [];

const state = {
  view: "home",
  category: "",
  subcategory: "",
  status: "all",
  search: "",
  sourceSearch: "",
  sourceGroup: "הכול",
  languageFilter: ""
};

const $ = (q, root=document) => root.querySelector(q);
const $$ = (q, root=document) => [...root.querySelectorAll(q)];

function escapeHtml(v="") {
  return String(v).replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[ch]));
}

function showView(view) {
  state.view = view;
  $$(".view").forEach(v => v.classList.toggle("active", v.id === view));
  $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  if (view === "recipes") renderRecipes();
  if (view === "sources") renderSources();
  window.scrollTo({top:0, behavior:"smooth"});
}

function statusLabel(status) {
  if (status === "made") return "הוכן";
  if (status === "highly") return "Highly Recommended";
  if (status === "not_made") return "טרם הוכן";
  return "לא ידוע";
}

function statusCell(r) {
  if (r.status === "made") {
    return `<img class="chef" src="assets/icons/chef-green.png" alt="הוכן">`;
  }
  if (r.status === "not_made") {
    return `<img class="chef" src="assets/icons/chef-red.png" alt="טרם הוכן">`;
  }
  if (r.status === "highly") {
    return `<span class="highly-wrap"><img class="chef" src="assets/icons/chef-green.png" alt="הוכן ומומלץ"><span class="highly-pill">HIGHLY RECOMMENDED</span></span>`;
  }
  return `<span class="unknown-status">לא ידוע</span>`;
}

function sourceCount(sourceId) {
  return recipes.filter(r => r.sourceId === sourceId).length;
}

function sourceById(id) {
  return sources.find(s => s.id === id);
}

function renderHome() {
  const homeCats = categories.slice(0, 8);
  $("#homeCategories").innerHTML = homeCats.map(c => `
    <button class="cat-card" data-home-category="${escapeHtml(c.name)}">
      <span class="cat-icon">${c.icon || "🍴"}</span>
      <div class="cat-name">${escapeHtml(c.name)}</div>
      <div class="cat-count">${c.count} מתכונים</div>
    </button>
  `).join("");

  $$("[data-home-category]").forEach(btn => {
    btn.onclick = () => {
      state.category = btn.dataset.homeCategory;
      state.subcategory = "";
      state.search = "";
      state.status = "all";
      showView("recipes");
    };
  });
}

function renderSidebar() {
  const root = $("#categorySidebar");
  root.innerHTML = `
    <button class="side-item ${state.category ? "" : "active"}" data-cat="">
      <span>כל המתכונים</span><span class="side-count">${recipes.length}</span>
    </button>
  ` + categories.map(c => {
    const active = state.category === c.name;
    const subs = active && c.subcategories.length ? `
      <div class="subcat-list">
        <button class="subcat ${state.subcategory ? "" : "active"}" data-sub="">כל ${escapeHtml(c.name)}</button>
        ${c.subcategories.map(s => `<button class="subcat ${state.subcategory === s ? "active" : ""}" data-sub="${escapeHtml(s)}">${escapeHtml(s)}</button>`).join("")}
      </div>
    ` : "";
    return `
      <button class="side-item ${active ? "active" : ""}" data-cat="${escapeHtml(c.name)}">
        <span>${c.icon || "🍴"} ${escapeHtml(c.name)}</span><span class="side-count">${c.count}</span>
      </button>
      ${subs}
    `;
  }).join("");

  $$("[data-cat]", root).forEach(btn => {
    btn.onclick = () => {
      state.category = btn.dataset.cat;
      state.subcategory = "";
      renderRecipes();
    };
  });
  $$("[data-sub]", root).forEach(btn => {
    btn.onclick = () => {
      state.subcategory = btn.dataset.sub;
      renderRecipes();
    };
  });
}

function filteredRecipes() {
  const q = state.search.trim().toLowerCase();
  return recipes.filter(r => {
    if (state.category && r.category !== state.category) return false;
    if (state.subcategory && r.subcategory !== state.subcategory) return false;
    if (state.status !== "all") {
      if (state.status === "made" && !(r.status === "made" || r.status === "highly")) return false;
      if (state.status === "highly" && r.status !== "highly") return false;
      if (state.status === "not_made" && r.status !== "not_made") return false;
    }
    if (state.languageFilter) {
      const s = sourceById(r.sourceId);
      if (!s || s.language !== state.languageFilter) return false;
    }
    if (q) {
      const hay = [r.title,r.subtitle,r.source,r.category,r.subcategory].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function renderRecipes() {
  renderSidebar();
  const list = filteredRecipes();
  $("#recipeSearch").value = state.search;

  const title = state.subcategory || state.category || "כל המתכונים";
  $("#activeCategoryTitle").textContent = title;
  $("#resultCount").textContent = `${list.length} תוצאות`;
  $("#recipeContext").textContent = state.subcategory
    ? `${state.category} ← ${state.subcategory}`
    : state.category || "בחרו קטגוריה או חפשו מתכון.";

  $$("#statusFilters .filter").forEach(b => b.classList.toggle("active", b.dataset.status === state.status));

  if (!list.length) {
    $("#recipeRows").innerHTML = `<tr><td colspan="4"><div class="empty-state">לא נמצאו מתכונים שמתאימים לסינון.</div></td></tr>`;
    return;
  }

  $("#recipeRows").innerHTML = list.map(r => {
    const subtitle = r.subtitle ? `<div class="recipe-sub">${escapeHtml(r.subtitle)}</div>` : "";
    const image = r.image
      ? `<img class="thumb" loading="lazy" src="${r.image}" alt="${escapeHtml(r.title)}">`
      : `<div class="no-thumb">אין תמונה</div>`;
    const source = r.source ? escapeHtml(r.source) : "—";
    return `
      <tr>
        <td>
          <button class="recipe-link" data-recipe-id="${r.id}">${escapeHtml(r.title)}</button>
          ${subtitle}
          ${r.linkStatus === "broken" ? `<div class="recipe-sub"><span class="bad-link">קישור תקול</span></div>` : ""}
          ${r.linkStatus === "none" ? `<div class="recipe-sub"><span class="no-link">ללא קישור</span></div>` : ""}
        </td>
        <td><span class="source-name">${source}</span></td>
        <td>${image}</td>
        <td>${statusCell(r)}</td>
      </tr>
    `;
  }).join("");

  $$("[data-recipe-id]").forEach(btn => {
    btn.onclick = () => openRecipe(btn.dataset.recipeId);
  });
}

function extractionText(r) {
  const st = r.extractionStatus;
  if (st === "success") return ["success","✓ שליפת המצרכים ואופן ההכנה הצליחה"];
  if (st === "partial") return ["partial","! השליפה הצליחה חלקית"];
  if (st === "failed") return ["failed","× שליפת המצרכים ואופן ההכנה לא צלחה"];
  if (st === "no_source") return ["no_source","אין קישור למקור ולכן לא בוצעה שליפה"];
  return ["pending","שליפת המצרכים ואופן ההכנה טרם בוצעה"];
}

function renderList(items, ordered=false) {
  if (!items || !items.length) return "";
  const tag = ordered ? "ol" : "ul";
  return `<${tag}>${items.map(x => `<li>${escapeHtml(typeof x === "string" ? x : (x.text || ""))}</li>`).join("")}</${tag}>`;
}

function openRecipe(id) {
  const r = recipes.find(x => x.id === id);
  if (!r) return;

  $("#modalTitle").textContent = r.title;
  $("#modalSub").textContent = r.subtitle || "";
  $("#modalSource").textContent = r.source || "";

  const photo = $("#modalPhoto");
  const noPhoto = $("#modalNoPhoto");
  if (r.image) {
    photo.src = r.image;
    photo.alt = r.title;
    photo.style.display = "block";
    noPhoto.style.display = "none";
  } else {
    photo.removeAttribute("src");
    photo.style.display = "none";
    noPhoto.style.display = "grid";
  }

  const meta = [
    r.category,
    r.subcategory,
    statusLabel(r.status)
  ].filter(Boolean);
  $("#modalMeta").innerHTML = meta.map(x => `<span>${escapeHtml(x)}</span>`).join("");

  const [statusClass,statusText] = extractionText(r);
  const statusEl = $("#extractStatus");
  statusEl.className = `extract-status ${statusClass}`;
  statusEl.textContent = r.extractionMessage || statusText;

  if (r.ingredients && r.ingredients.length) {
    $("#ingredientsBlock").innerHTML = renderList(r.ingredients);
  } else {
    const msg = r.extractionStatus === "failed"
      ? "שליפת המצרכים לא צלחה."
      : r.extractionStatus === "no_source"
      ? "אין מצרכים שמורים למתכון זה."
      : "המצרכים עדיין לא נשמרו באתר.";
    $("#ingredientsBlock").innerHTML = `<p class="placeholder-copy">${msg}</p>`;
  }

  if (r.instructions && r.instructions.length) {
    $("#instructionsBlock").innerHTML = renderList(r.instructions, true);
  } else {
    const msg = r.extractionStatus === "failed"
      ? "שליפת אופן ההכנה לא צלחה. ניתן לצפות במתכון המלא בקישור המקורי."
      : r.extractionStatus === "no_source"
      ? "אין אופן הכנה שמור למתכון זה."
      : "אופן ההכנה עדיין לא נשמר באתר.";
    $("#instructionsBlock").innerHTML = `<p class="placeholder-copy">${msg}</p>`;
  }

  const linkArea = $("#modalLinkArea");
  if (r.linkStatus === "broken") {
    linkArea.innerHTML = `<div class="link-broken"><span class="bad-link">קישור תקול</span></div>`;
  } else if (r.url) {
    linkArea.innerHTML = `<a class="original" href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer">למתכון המקורי ↗</a>`;
  } else {
    linkArea.innerHTML = `<div class="link-broken"><span class="no-link">ללא קישור</span></div>`;
  }

  $("#modalNote").textContent = r.note || "";
  $("#modal").classList.add("open");
  history.replaceState(null, "", `#recipe=${r.id}`);
}

function closeModal() {
  $("#modal").classList.remove("open");
  if (location.hash.startsWith("#recipe=")) history.replaceState(null, "", location.pathname + location.search);
}

function renderSourceFilters() {
  const groups = ["הכול", ...new Set(sources.map(s => s.group).filter(Boolean))];
  $("#sourceFilters").innerHTML = groups.map(g => `<button class="chip ${state.sourceGroup === g ? "active" : ""}" data-source-group="${escapeHtml(g)}">${escapeHtml(g)}</button>`).join("");
  $$("[data-source-group]").forEach(b => {
    b.onclick = () => {
      state.sourceGroup = b.dataset.sourceGroup;
      renderSources();
    };
  });
}

function renderSources() {
  renderSourceFilters();
  $("#sourceSearch").value = state.sourceSearch;
  const q = state.sourceSearch.trim().toLowerCase();
  const list = sources.filter(s => {
    if (state.sourceGroup !== "הכול" && s.group !== state.sourceGroup) return false;
    if (q) {
      const hay = [s.name,s.language,s.cuisine,s.description,s.group].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  $("#sourceGrid").innerHTML = list.map(s => {
    const count = sourceCount(s.id);
    const tag = [s.language,s.cuisine].filter(Boolean).join(" · ") || s.group || "מקור";
    const logo = s.logo ? `<img class="source-logo" loading="lazy" src="${s.logo}" alt="${escapeHtml(s.name)}">` : "";
    const actions = (s.links || []).map(l => {
      const labels = {website:"אתר ↗",instagram:"Instagram",facebook:"Facebook",youtube:"YouTube",tiktok:"TikTok",pinterest:"Pinterest"};
      return `<a class="source-action" href="${escapeHtml(l.url)}" target="_blank" rel="noopener noreferrer">${labels[l.type] || "קישור"}</a>`;
    }).join("");
    return `
      <article class="source-card">
        <span class="source-count">${count} מתכונים</span>
        ${logo}
        <div class="source-tag">${escapeHtml(tag)}</div>
        <h3>${escapeHtml(s.name)}</h3>
        <p>${escapeHtml(s.description || "מקור מתכונים בספר.")}</p>
        ${actions ? `<div class="source-actions">${actions}</div>` : ""}
      </article>
    `;
  }).join("");
}

function clearRecipeFilters() {
  state.category = "";
  state.subcategory = "";
  state.status = "all";
  state.search = "";
  state.languageFilter = "";
  renderRecipes();
}

function init() {
  renderHome();

  $$(".nav-btn").forEach(b => b.onclick = () => showView(b.dataset.view));
  $$(".brand").forEach(b => b.onclick = () => showView("home"));
  $$("[data-go]").forEach(b => b.onclick = () => showView(b.dataset.go));

  $("#recipeSearch").addEventListener("input", e => {
    state.search = e.target.value;
    renderRecipes();
  });

  $("#globalSearch").addEventListener("keydown", e => {
    if (e.key === "Enter") {
      state.search = e.target.value;
      state.category = "";
      state.subcategory = "";
      state.status = "all";
      showView("recipes");
    }
  });

  $$("#statusFilters .filter").forEach(b => {
    b.onclick = () => {
      state.status = b.dataset.status;
      renderRecipes();
    };
  });

  $("#clearFilters").onclick = clearRecipeFilters;

  $("#sourceSearch").addEventListener("input", e => {
    state.sourceSearch = e.target.value;
    renderSources();
  });

  $$("[data-filter-status]").forEach(b => {
    b.onclick = () => {
      state.status = b.dataset.filterStatus;
      state.category = "";
      state.subcategory = "";
      state.search = "";
      showView("recipes");
    };
  });

  $$("[data-filter-source-language]").forEach(b => {
    b.onclick = () => {
      state.languageFilter = b.dataset.filterSourceLanguage;
      state.category = "";
      state.subcategory = "";
      state.search = "";
      state.status = "all";
      showView("recipes");
    };
  });

  $$("[data-filter-recent]").forEach(b => {
    b.onclick = () => {
      state.category = "";
      state.subcategory = "";
      state.status = "all";
      state.search = "";
      showView("recipes");
      // "Recent" isn't tracked yet; scrolls to list for now.
    };
  });

  $("#closeModal").onclick = closeModal;
  $("#modal").onclick = e => { if (e.target.id === "modal") closeModal(); };
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

  renderRecipes();
  renderSources();

  if (location.hash.startsWith("#recipe=")) {
    const id = location.hash.split("=")[1];
    if (recipes.some(r => r.id === id)) openRecipe(id);
  }
}

init();
