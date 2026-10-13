import test from "node:test";
import assert from "node:assert/strict";

import {
  filterProducts,
  formatMeasurements,
  sanitizeProductsForCache,
} from "../logic.js";

test("busca sin depender de tildes y por varias palabras", () => {
  const products = [{
    nombre: "Protección auditiva",
    categoria: "EPP",
    ubicacion: "B1-A-E003",
    estado: "Activo",
  }];
  const result = filterProducts(products, {
    query: "proteccion epp",
    category: "Todos",
    status: "todos",
  });
  assert.equal(result.length, 1);
});

test("formatea las medidas estructuradas de un tubo", () => {
  const product = {
    tipo_medicion: "Largo",
    "tamaño_dimensiones": `MEDIDAS_V1:${JSON.stringify({
      formato: "Tubo cuadrado / rectangular",
      principal: 6,
      secundaria: 100,
      adicional: 50,
      espesor: 3,
      unidad_principal: "m",
      unidad_secundaria: "mm",
    })}`,
  };
  assert.equal(
    formatMeasurements(product),
    "Tubo cuadrado / rectangular · Largo: 6 m · Ancho: 100 mm · Alto: 50 mm · Espesor: 3 mm"
  );
});

test("no muestra medidas inexistentes como cero", () => {
  assert.equal(formatMeasurements({
    tipo_medicion: "No aplica",
    medida_largo: null,
    medida_ancho: null,
    "tamaño_dimensiones": "",
  }), "No aplica");
});

test("la copia local no conserva precio, mínimo ni códigos", () => {
  const cached = sanitizeProductsForCache([{
    id: 1,
    nombre: "Casco",
    categoria: "EPP",
    stock: 4,
    precio_unitario: 9999,
    stock_minimo: 2,
    codigo_barras: "SECRETO",
  }])[0];
  assert.equal(cached.nombre, "Casco");
  assert.equal("precio_unitario" in cached, false);
  assert.equal("stock_minimo" in cached, false);
  assert.equal("codigo_barras" in cached, false);
});

test("filtra estado y categoría", () => {
  const products = [
    { nombre: "Casco", categoria: "EPP", estado: "Activo" },
    { nombre: "Guante", categoria: "EPP", estado: "Inactivo" },
    { nombre: "Café", categoria: "Cafetería", estado: "Activo" },
  ];
  const result = filterProducts(products, {
    category: "EPP",
    status: "activo",
  });
  assert.deepEqual(result.map((product) => product.nombre), ["Casco"]);
});
