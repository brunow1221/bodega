import {
  filterProducts,
  formatMeasurements,
  isActive,
  normalizeText,
  sanitizeProductsForCache,
} from "./logic.js";

const CACHE_KEY = "bodega-tablet-inventario-v1";
const CACHE_DATE_KEY = "bodega-tablet-fecha-v1";
const ZOOM_KEY = "bodega-tablet-zoom-v1";
const PAGE_SIZE = 1000;

const state = {
  products: [],
  category: "Todos",
  status: "todos",
  query: "",
  loading: false,
  installPrompt: null,
};

const elements = {
  categoryFilters: document.querySelector("#category-filters"),
  clearSearch: document.querySelector("#clear-search"),
  connectionStatus: document.querySelector("#connection-status"),
  emptyState: document.querySelector("#empty-state"),
  grid: document.querySelector("#item-grid"),
  installButton: document.querySelector("#install-button"),
  lastUpdate: document.querySelector("#last-update"),
  loadingGrid: document.querySelector("#loading-grid"),
  messagePanel: document.querySelector("#message-panel"),
  messageText: document.querySelector("#message-text"),
  messageTitle: document.querySelector("#message-title"),
  refreshButton: document.querySelector("#refresh-button"),
  resetFilters: document.querySelector("#reset-filters"),
  resultCount: document.querySelector("#result-count"),
  resultLabel: document.querySelector("#result-label"),
  resultTitle: document.querySelector("#result-title"),
  searchInput: document.querySelector("#search-input"),
  statusSelect: document.querySelector("#status-select"),
  template: document.querySelector("#item-template"),
  zoomIn: document.querySelector("#zoom-in"),
  zoomOut: document.querySelector("#zoom-out"),
  zoomReset: document.querySelector("#zoom-reset"),
};

function getConfig() {
  const config = window.BODEGA_CONFIG || {};
  return {
    url: String(config.supabaseUrl || "").replace(/\/$/, ""),
    key: String(config.supabaseKey || ""),
  };
}

function configIsValid(config) {
  return /^https:\/\/.+\.supabase\.co$/i.test(config.url)
    && config.key.length > 20
    && !config.key.includes("tu_clave");
}

async function fetchAllRows(table, select, order = "") {
  const config = getConfig();
  const rows = [];
  let start = 0;

  while (true) {
    const params = new URLSearchParams({ select });
    if (order) params.set("order", order);
    const response = await fetch(`${config.url}/rest/v1/${table}?${params}`, {
      headers: {
        apikey: config.key,
        Authorization: `Bearer ${config.key}`,
        Range: `${start}-${start + PAGE_SIZE - 1}`,
        "Range-Unit": "items",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      const details = await response.text();
      throw new Error(`Supabase respondió ${response.status}: ${details}`);
    }

    const page = await response.json();
    rows.push(...page);
    if (page.length < PAGE_SIZE) break;
    start += PAGE_SIZE;
  }

  return rows;
}

async function loadInventory() {
  const config = getConfig();
  if (!configIsValid(config)) {
    showMessage(
      "Falta configurar la conexión",
      "Ejecuta preparar_configuracion.ps1 o completa config.js con la URL y la clave pública de Supabase."
    );
    setLoading(false);
    return;
  }

  setLoading(true);
  hideMessage();

  try {
    const [products, locations] = await Promise.all([
      fetchAllRows(
        "productos",
        "id,nombre,categoria,stock,ubicacion_id,estado,tamaño_dimensiones,tipo_medicion,medida_largo,medida_ancho,unidad_medida",
        "nombre.asc"
      ),
      fetchAllRows("ubicaciones", "id,codigo_ubicacion,descripcion", "codigo_ubicacion.asc"),
    ]);

    const locationsById = new Map(locations.map((location) => [
      String(location.id),
      location.codigo_ubicacion || location.descripcion || "Sin ubicación",
    ]));

    state.products = products.map((product) => ({
      ...product,
      ubicacion: locationsById.get(String(product.ubicacion_id)) || "Sin ubicación",
    }));

    const now = new Date().toISOString();
    localStorage.setItem(CACHE_KEY, JSON.stringify(sanitizeProductsForCache(state.products)));
    localStorage.setItem(CACHE_DATE_KEY, now);
    updateLastUpdate(now, false);
    buildCategoryFilters();
    render();
  } catch (error) {
    console.error(error);
    const cacheLoaded = loadCachedInventory();
    showMessage(
      cacheLoaded ? "Mostrando la última copia disponible" : "No se pudo cargar el inventario",
      cacheLoaded
        ? "No fue posible conectarse. Los datos pueden no estar actualizados."
        : "Revisa la conexión a internet y la configuración de Supabase."
    );
  } finally {
    setLoading(false);
  }
}

function loadCachedInventory() {
  try {
    const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || "[]");
    if (!Array.isArray(cached) || !cached.length) return false;
    state.products = cached;
    buildCategoryFilters();
    updateLastUpdate(localStorage.getItem(CACHE_DATE_KEY), true);
    render();
    return true;
  } catch {
    return false;
  }
}

function setLoading(isLoading) {
  state.loading = isLoading;
  elements.refreshButton.disabled = isLoading;
  elements.refreshButton.classList.toggle("is-refreshing", isLoading);
  elements.loadingGrid.hidden = !isLoading || state.products.length > 0;
  if (isLoading && !state.products.length) elements.grid.hidden = true;
}

function showMessage(title, text) {
  elements.messageTitle.textContent = title;
  elements.messageText.textContent = text;
  elements.messagePanel.hidden = false;
}

function hideMessage() {
  elements.messagePanel.hidden = true;
}

function updateLastUpdate(isoDate, fromCache) {
  if (!isoDate) return;
  const date = new Date(isoDate);
  const formatted = new Intl.DateTimeFormat("es-CL", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
  elements.lastUpdate.textContent = `${fromCache ? "Copia guardada" : "Actualizado"}: ${formatted}`;
}

function buildCategoryFilters() {
  const categories = [...new Set(
    state.products.map((product) => product.categoria || "Sin categoría")
  )].sort((a, b) => a.localeCompare(b, "es", { sensitivity: "base" }));

  if (
    state.category !== "Todos"
    && !categories.some((category) => normalizeText(category) === normalizeText(state.category))
  ) state.category = "Todos";

  elements.categoryFilters.replaceChildren();
  for (const category of ["Todos", ...categories]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "category-chip";
    button.textContent = category;
    button.classList.toggle(
      "active",
      normalizeText(category) === normalizeText(state.category)
    );
    button.setAttribute(
      "aria-pressed",
      normalizeText(category) === normalizeText(state.category) ? "true" : "false"
    );
    button.addEventListener("click", () => {
      state.category = category;
      buildCategoryFilters();
      render();
    });
    elements.categoryFilters.append(button);
  }
}

function render() {
  const filtered = filterProducts(state.products, {
    query: state.query,
    category: state.category,
    status: state.status,
  });

  elements.grid.replaceChildren();
  const fragment = document.createDocumentFragment();
  for (const product of filtered) fragment.append(createProductCard(product));
  elements.grid.append(fragment);

  elements.grid.hidden = filtered.length === 0;
  elements.emptyState.hidden = filtered.length !== 0 || state.loading;
  elements.resultCount.textContent = new Intl.NumberFormat("es-CL").format(filtered.length);
  elements.resultLabel.textContent = filtered.length === 1 ? "artículo" : "artículos";
  elements.resultTitle.textContent = state.category === "Todos"
    ? "Todos los artículos"
    : state.category;
}

function createProductCard(product) {
  const card = elements.template.content.firstElementChild.cloneNode(true);
  const active = isActive(product);
  const stock = Number(product.stock || 0);
  const measurementText = formatMeasurements(product);

  card.querySelector(".category-badge").textContent = product.categoria || "Sin categoría";
  const stateBadge = card.querySelector(".state-badge");
  stateBadge.textContent = active ? "Activo" : "Inactivo";
  stateBadge.classList.add(active ? "active" : "inactive");
  card.querySelector(".item-name").textContent = product.nombre || "Artículo sin nombre";
  card.querySelector(".stock-value").textContent = new Intl.NumberFormat("es-CL").format(stock);
  card.querySelector(".stock-block").classList.toggle("no-stock", stock <= 0);
  card.querySelector(".location-value").textContent = product.ubicacion || "Sin ubicación";
  card.querySelector(".measurement-value").textContent = measurementText;
  card.querySelector(".measurement-row").hidden = measurementText === "No aplica";
  return card;
}

function resetFilters() {
  state.query = "";
  state.category = "Todos";
  state.status = "todos";
  elements.searchInput.value = "";
  elements.statusSelect.value = "todos";
  elements.clearSearch.hidden = true;
  buildCategoryFilters();
  render();
}

function updateConnectionStatus() {
  const online = navigator.onLine;
  elements.connectionStatus.classList.toggle("online", online);
  elements.connectionStatus.classList.toggle("offline", !online);
  elements.connectionStatus.querySelector("span:last-child").textContent = online
    ? "En línea"
    : "Sin conexión";
}

function applyZoom(value) {
  const zoom = Math.min(140, Math.max(90, Math.round(value / 10) * 10));
  document.documentElement.style.setProperty("--scale", String(zoom / 100));
  elements.zoomReset.textContent = `${zoom}%`;
  localStorage.setItem(ZOOM_KEY, String(zoom));
}

function currentZoom() {
  return Number(localStorage.getItem(ZOOM_KEY) || 100);
}

elements.searchInput.addEventListener("input", (event) => {
  state.query = event.target.value;
  elements.clearSearch.hidden = !state.query;
  render();
});

elements.clearSearch.addEventListener("click", () => {
  state.query = "";
  elements.searchInput.value = "";
  elements.clearSearch.hidden = true;
  elements.searchInput.focus();
  render();
});

elements.statusSelect.addEventListener("change", (event) => {
  state.status = event.target.value;
  render();
});

elements.refreshButton.addEventListener("click", loadInventory);
elements.resetFilters.addEventListener("click", resetFilters);
elements.zoomOut.addEventListener("click", () => applyZoom(currentZoom() - 10));
elements.zoomIn.addEventListener("click", () => applyZoom(currentZoom() + 10));
elements.zoomReset.addEventListener("click", () => applyZoom(100));

window.addEventListener("online", () => {
  updateConnectionStatus();
  loadInventory();
});
window.addEventListener("offline", updateConnectionStatus);

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  state.installPrompt = event;
  elements.installButton.hidden = false;
});

elements.installButton.addEventListener("click", async () => {
  if (!state.installPrompt) return;
  state.installPrompt.prompt();
  await state.installPrompt.userChoice;
  state.installPrompt = null;
  elements.installButton.hidden = true;
});

window.addEventListener("appinstalled", () => {
  elements.installButton.hidden = true;
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./service-worker.js").catch(console.error);
  });
}

applyZoom(currentZoom());
updateConnectionStatus();
loadCachedInventory();
loadInventory();
