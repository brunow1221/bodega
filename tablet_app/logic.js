const DIMENSION_PREFIX = "MEDIDAS_V1:";

export function normalizeText(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLocaleLowerCase("es");
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  return new Intl.NumberFormat("es-CL", {
    maximumFractionDigits: 3,
  }).format(numeric);
}

function measurement(value, unit) {
  const number = formatNumber(value);
  return number ? `${number} ${unit || ""}`.trim() : "";
}

export function decodeDimensions(product) {
  const raw = String(product?.["tamaño_dimensiones"] ?? "").trim();
  const fallback = {
    format: product?.tipo_medicion || "No aplica",
    primary: product?.medida_largo ?? null,
    secondary: product?.medida_ancho ?? null,
    additional: null,
    thickness: null,
    primaryUnit: product?.unidad_medida || "",
    secondaryUnit: product?.unidad_medida || "",
    legacyText: raw.startsWith(DIMENSION_PREFIX) ? "" : raw,
  };

  if (!raw.startsWith(DIMENSION_PREFIX)) return fallback;

  try {
    const parsed = JSON.parse(raw.slice(DIMENSION_PREFIX.length));
    return {
      format: parsed.formato || fallback.format,
      primary: parsed.principal ?? fallback.primary,
      secondary: parsed.secundaria ?? fallback.secondary,
      additional: parsed.adicional ?? null,
      thickness: parsed.espesor ?? null,
      primaryUnit: parsed.unidad_principal || fallback.primaryUnit,
      secondaryUnit: parsed.unidad_secundaria || fallback.secondaryUnit,
      legacyText: "",
    };
  } catch {
    return fallback;
  }
}

export function formatMeasurements(product) {
  const dimensions = decodeDimensions(product);
  if (dimensions.legacyText) return dimensions.legacyText;

  const primary = measurement(dimensions.primary, dimensions.primaryUnit);
  const secondary = measurement(dimensions.secondary, dimensions.secondaryUnit);
  const additional = measurement(dimensions.additional, dimensions.secondaryUnit);
  const thickness = measurement(dimensions.thickness, dimensions.secondaryUnit);
  const parts = [];

  const labelsByFormat = {
    "Plancha / Malla": ["Largo", "Ancho", "", "Espesor"],
    "Tubo redondo": ["Largo", "Diámetro", "", "Espesor"],
    "Tubo cuadrado / rectangular": ["Largo", "Ancho", "Alto", "Espesor"],
    "Perfil / Barra": ["Largo", "Ancho/diámetro", "Alto", "Espesor"],
    Rollo: ["Largo", "Ancho", "", "Espesor"],
    "Otro material": ["Medida", "Medida 2", "Medida 3", "Espesor"],
  };
  const labels = labelsByFormat[dimensions.format] || ["Medida", "Medida 2", "Medida 3", "Espesor"];

  for (const [label, value] of [
    [labels[0], primary],
    [labels[1], secondary],
    [labels[2], additional],
    [labels[3], thickness],
  ]) {
    if (label && value) parts.push(`${label}: ${value}`);
  }

  if (!parts.length) return "No aplica";
  const format = dimensions.format && dimensions.format !== "No aplica"
    ? `${dimensions.format} · `
    : "";
  return `${format}${parts.join(" · ")}`;
}

export function isActive(product) {
  return normalizeText(product?.estado || "Activo") !== "inactivo";
}

export function filterProducts(products, filters = {}) {
  const queryWords = normalizeText(filters.query).split(/\s+/).filter(Boolean);
  const selectedCategory = normalizeText(filters.category || "todos");
  const selectedStatus = normalizeText(filters.status || "todos");

  return products.filter((product) => {
    if (
      selectedCategory !== "todos"
      && normalizeText(product.categoria || "Sin categoría") !== selectedCategory
    ) return false;

    if (selectedStatus === "activo" && !isActive(product)) return false;
    if (selectedStatus === "inactivo" && isActive(product)) return false;

    const searchable = normalizeText([
      product.nombre,
      product.categoria,
      product.ubicacion,
      formatMeasurements(product),
      product.estado,
    ].join(" "));

    return queryWords.every((word) => searchable.includes(word));
  });
}

export function sanitizeProductsForCache(products) {
  return products.map((product) => ({
    id: product.id,
    nombre: product.nombre,
    categoria: product.categoria,
    stock: product.stock,
    ubicacion_id: product.ubicacion_id,
    ubicacion: product.ubicacion,
    estado: product.estado,
    "tamaño_dimensiones": product["tamaño_dimensiones"],
    tipo_medicion: product.tipo_medicion,
    medida_largo: product.medida_largo,
    medida_ancho: product.medida_ancho,
    unidad_medida: product.unidad_medida,
  }));
}
