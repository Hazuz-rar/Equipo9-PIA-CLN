"use strict";
/* Funciones puras: comprobaciones previas a peticiones REST; no reemplazan validación del servidor. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.HotelForms = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  function validUUID(value) { return uuidRegex.test(String(value || "").trim()); }
  function requireUUID(value, label = "Identificador") {
    const v = String(value || "").trim();
    if (!validUUID(v)) throw new Error(`${label}: introduce un UUID válido.`);
    return v;
  }
  function dates(checkIn, checkOut) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(checkIn) || !/^\d{4}-\d{2}-\d{2}$/.test(checkOut) ||
        !Number.isFinite(Date.parse(checkIn)) || !Number.isFinite(Date.parse(checkOut)) || checkOut <= checkIn) {
      throw new Error("La salida debe ser una fecha válida posterior a la entrada.");
    }
    return {check_in:checkIn, check_out:checkOut};
  }
  function roomIds(text, minimum = 10) {
    const values = String(text || "").split(/[\s,;]+/).map(v=>v.trim()).filter(Boolean);
    if (values.length < minimum) throw new Error(`Se requieren al menos ${minimum} habitaciones distintas.`);
    if (values.some(v=>!validUUID(v))) throw new Error("Todos los identificadores de habitación deben ser UUID válidos.");
    if (new Set(values.map(v=>v.toLowerCase())).size !== values.length) throw new Error("No se permiten habitaciones duplicadas.");
    return values;
  }
  function amount(value, label = "Importe", allowZero = false) {
    const n=Number(value);
    if (String(value).trim()==="" || !Number.isFinite(n) || (allowZero ? n < 0 : n <= 0))
      throw new Error(`${label} debe ser un número ${allowZero ? "no negativo" : "mayor que cero"}.`);
    if (!/^\d+(?:\.\d{1,2})?$/.test(String(value).trim()))
      throw new Error(`${label} debe tener máximo dos decimales y sin signos.`);
    return String(value).trim();
  }
  function localDateTimeISO(value) {
    if(!/^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(String(value)))throw new Error("Introduce fecha y hora válidas.");
    const d=new Date(value);
    if (!Number.isFinite(d.getTime()))throw new Error("Fecha y hora inválidas.");
    // Zona horaria incluida para respetar la interfaz de la API.
    return d.toISOString();
  }
  function objectJSON(text) {
    let data;
    try { data=JSON.parse(text); } catch { throw new Error("El JSON de tarifas no es válido."); }
    if(!data || Array.isArray(data) || typeof data!=="object") throw new Error("La configuración debe ser un objeto JSON.");
    for (const field of ["bar_by_room_and_season", "weekend_multiplier", "channel_multipliers", "customer_multipliers", "seasons"])
      if (!(field in data))throw new Error(`Falta el campo ${field} en la configuración.`);
    if(data.currency && data.currency!=="MXN")throw new Error("El backend admite MXN en esta implementación.");
    if(!Array.isArray(data.seasons) || !data.seasons.length)throw new Error("Define al menos una temporada aprobada.");
    if (!(Number(data.weekend_multiplier)>1))throw new Error("El multiplicador de fin de semana debe ser mayor que uno.");
    return data;
  }
  return {validUUID,requireUUID,dates,roomIds,amount,localDateTimeISO,objectJSON};
});
