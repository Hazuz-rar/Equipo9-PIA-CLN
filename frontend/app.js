"use strict";

/* Interfaz del PIA Hotel Costa Azul. Solo utiliza rutas verificadas del backend.
 * Nunca guarda contraseñas ni documentación del huésped en almacenamiento.
 * El token se conserva en sessionStorage (se borra al cerrar la pestaña).
 */
const API = "http://127.0.0.1:8000/api/v1";
const KEY = "costa_azul_session_token";
const RECENT = "costa_azul_recent_reservations";
const app = document.getElementById("app");
const Forms = window.HotelForms;
const state = {
  token: sessionStorage.getItem(KEY) || "",
  staff: null,
  page: "dashboard",
  recent: loadRecent(),
  chosenRoom: null,
  currentReservation: null,
  lastFolioId: "",
  teacherGuestId: "",
};

// Migración única del almacenamiento antiguo: no deja tokens en localStorage.
const oldToken = localStorage.getItem("access_token");
if (!state.token && oldToken) {
  state.token = oldToken;
  sessionStorage.setItem(KEY, oldToken);
}
localStorage.removeItem("access_token");

const ROLE_NAMES = {
  MANAGER_OPERATIONS: "Gerencia de operaciones", MANAGER_RECEPTION: "Gerencia de recepción",
  RECEPTION: "Recepción", RESERVATIONS: "Reservaciones", FINANCE: "Finanzas",
  HOUSEKEEPING: "Limpieza", MAINTENANCE: "Mantenimiento",
};
const RIGHTS = {
  reservations: ["RECEPTION", "RESERVATIONS", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
  reception: ["RECEPTION", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
  housekeeping: ["HOUSEKEEPING"],
  folios: ["RECEPTION", "FINANCE", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
  reports: ["FINANCE", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
  maintenance: ["RECEPTION", "MAINTENANCE", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
  tariffs: ["RECEPTION", "RESERVATIONS", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
  groups: ["RESERVATIONS", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
  staychanges: ["RECEPTION", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
  walk: ["RECEPTION", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
  channels: ["RESERVATIONS", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
  teacherdata: ["RECEPTION", "RESERVATIONS", "FINANCE", "MANAGER_RECEPTION", "MANAGER_OPERATIONS"],
};
const MENU = [
  {id: "dashboard", name: "Resumen", symbol: "▦"},
  {id: "availability", name: "Disponibilidad", symbol: "▤"},
  {id: "reservations", name: "Reservaciones", symbol: "▣"},
  {id: "reception", name: "Recepción", symbol: "♧"},
  {id: "folios", name: "Folios y pagos", symbol: "◈"},
  {id: "housekeeping", name: "Limpieza", symbol: "✧"},
  {id: "maintenance", name: "Mantenimiento", symbol: "⚒"},
  {id: "tariffs", name: "Cotizaciones", symbol: "⌁"},
  {id: "groups", name: "Reservas grupales", symbol: "▦"},
  {id: "staychanges", name: "Cambios de estancia", symbol: "⇄"},
  {id: "walk", name: "Reubicaciones", symbol: "↗"},
  {id: "channels", name: "Eventos de canales", symbol: "⌁"},
  {id: "reports", name: "Reportes", symbol: "▥"},
  {id: "teacherdata", name: "Datos del profesor", symbol: "▤"},
];
function allowed(id) { return !RIGHTS[id] || RIGHTS[id].includes(state.staff?.role); }
function $(id) { return document.getElementById(id); }
function loadRecent() {
  try { return (JSON.parse(sessionStorage.getItem(RECENT) || "[]") || []).filter(v => /^[0-9a-f-]{36}$/i.test(v)).slice(0, 20); }
  catch { return []; }
}
function rememberId(id) {
  if (!/^[0-9a-f-]{36}$/i.test(String(id))) return;
  state.recent = [id, ...state.recent.filter(v => v !== id)].slice(0, 20);
  sessionStorage.setItem(RECENT, JSON.stringify(state.recent));
}
function todayISO(offset = 0) {
  const d = new Date(); d.setDate(d.getDate() + offset);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}
function displayMoney(value) {
  const n = Number(value);
  return Number.isFinite(n) ? new Intl.NumberFormat("es-MX", {style:"currency",currency:"MXN"}).format(n) : "No disponible";
}
function text(parent, value, className = "") {
  const n = document.createElement("span"); n.textContent = value == null ? "—" : String(value);
  if (className) n.className = className; parent.append(n); return n;
}
function message(id, content, type = "success") {
  const container = $(id); if (!container) return;
  container.className = `alert ${type}`;
  container.textContent = content;
  container.hidden = false;
}
let toastTimer = null;
function toast(messageText, type = "success") {
  let el = $("toast");
  if (!el) { el = document.createElement("div"); el.id = "toast"; document.body.append(el); }
  el.className = "toast " + type; el.textContent = String(messageText); el.hidden = false;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 5600);
}
function serializeError(data, status) {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(e => `${(e.loc || []).join(".")}: ${e.msg || "Campo inválido"}`).join("; ");
  return data?.message || `Error HTTP ${status}`;
}
async function request(path, {method="GET", body, auth=true}={}) {
  const headers = {Accept:"application/json"};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && state.token) headers.Authorization = `Bearer ${state.token}`;
  let response;
  try {
    response = await fetch(API + path, {method, headers, body:body === undefined ? undefined : JSON.stringify(body), cache:"no-store"});
  } catch {
    throw Error("No se pudo conectar con la API. Comprueba Docker y http://127.0.0.1:8000/api/v1/health.");
  }
  let data = null;
  try { data = await response.json(); } catch { /* Respuesta sin JSON */ }
  if (!response.ok) {
    if (response.status === 401 && auth) { signOut(true); throw Error("La sesión caducó o las credenciales ya no son válidas. Inicia sesión otra vez."); }
    throw Error(serializeError(data, response.status));
  }
  return data;
}
function signOut(expired = false) {
  state.token = ""; state.staff = null; state.currentReservation = null;
  sessionStorage.removeItem(KEY); sessionStorage.removeItem(RECENT);
  state.recent = [];
  renderLogin(expired ? "La sesión terminó. Vuelve a iniciar sesión." : "");
}
function start() {
  if (!state.token) {renderLogin(); return;}
  request("/auth/me").then(staff => {state.staff = staff; renderShell(); navigate("dashboard");})
    .catch(() => {if (!state.staff) renderLogin("Inicia sesión para continuar.");});
}
function renderLogin(notice = "") {
  app.innerHTML = `
    <div class="login-layout">
      <section class="login-brand">
        <div class="brand-mark"><span class="brand-icon">≋</span> HOTEL COSTA AZUL</div>
        <div class="login-slogan"><span class="eyebrow">PLATAFORMA OPERATIVA · PMS</span><h1>Tu hotel,<br>en un solo lugar.</h1><p>Gestiona reservaciones, recepción, habitaciones y operación hotelera desde un mismo panel.</p></div>
        <div class="login-bottom">Proyecto Integrador de Aprendizaje · Entorno local de demostración</div>
      </section>
      <section class="login-right"><div class="login-card">
        <span class="eyebrow">ACCESO PARA PERSONAL</span><h2>Bienvenido</h2>
        <p>Ingresa con las credenciales de tu cuenta de personal para abrir el sistema.</p>
        <form id="loginForm" class="form-stack">
          <div class="field"><label for="username">Usuario</label><input id="username" autocomplete="username" required placeholder="Ej. admin" maxlength="80"></div>
          <div class="field"><label for="password">Contraseña</label><input id="password" type="password" autocomplete="current-password" required placeholder="Tu contraseña"></div>
          <button id="loginSubmit" class="button wide" type="submit">Entrar al sistema →</button>
          <div id="loginMessage" class="alert error" hidden></div>
        </form>
        <p class="caption" style="margin-top:26px">El acceso se valida en FastAPI; no existe una contraseña predeterminada en la interfaz.</p>
      </div></section>
    </div>`;
  if (notice) message("loginMessage", notice, "warning");
  $("loginForm").addEventListener("submit", async e => {
    e.preventDefault();
    const btn = $("loginSubmit"); btn.disabled = true; btn.textContent = "Validando...";
    try {
      const data = await request("/auth/token", {method:"POST", auth:false, body:{username:$("username").value.trim(),password:$("password").value}});
      const token = data?.access_token; if (!token) throw Error("El servidor no devolvió un token válido.");
      state.token = token;
      state.staff = await request("/auth/me");
      sessionStorage.setItem(KEY, token); // La contraseña nunca se guarda.
      $("password").value = "";
      renderShell(); navigate("dashboard"); toast("Inicio de sesión correcto.");
    } catch(err) { message("loginMessage", err.message, "error"); }
    finally {if (btn.isConnected) {btn.disabled=false;btn.textContent="Entrar al sistema →";}}
  });
}
function renderShell() {
  app.innerHTML = `
    <div class="layout"><aside class="sidebar">
      <div class="brand-mark"><span class="brand-icon">≋</span> HOTEL COSTA AZUL</div>
      <div class="side-caption">OPERACIÓN</div><nav class="nav-list" id="nav" aria-label="Menú principal"></nav>
      <div class="sidebar-spacer"></div><div class="side-account"><strong id="sideUser"></strong><span id="sideRole"></span></div>
      <button class="side-logout" id="logoutBtn" type="button">Cerrar sesión</button>
    </aside><main class="main"><header class="topbar"><div><strong>Panel de gestión hotelera</strong><div class="subtle">Hotel Costa Azul · Sistema PMS</div></div><div class="top-right"><span class="status-indicator"><i></i> API local</span><span id="topAvatar" class="avatar"></span></div></header><div id="content" class="content"></div></main></div>`;
  const nav = $("nav");
  for (const item of MENU.filter(i => allowed(i.id))) {
    const button = document.createElement("button"); button.type="button"; button.className="nav-item"; button.dataset.page=item.id;
    const symbol = document.createElement("span"); symbol.className="nav-symbol";symbol.textContent=item.symbol;
    const name = document.createElement("span");name.className="nav-label";name.textContent=item.name;
    button.append(symbol,name);button.title=item.name;
    button.addEventListener("click", () => navigate(item.id));nav.append(button);
  }
  $("sideUser").textContent = state.staff.username;
  $("sideRole").textContent = ROLE_NAMES[state.staff.role] || state.staff.role;
  $("topAvatar").textContent = state.staff.username.slice(0,1).toUpperCase();
  $("logoutBtn").addEventListener("click", () => signOut());
}
function heading(title, subtitle) {
  const container = $("content");
  container.innerHTML = `<div class="page-heading"><h1></h1><p></p></div><div id="workspace" class="stack"></div>`;
  container.querySelector("h1").textContent=title;
  container.querySelector(".page-heading p").textContent=subtitle;
  return $("workspace");
}
function navigate(page) {
  if (!state.staff) return;
  if (!allowed(page)) { toast("Tu rol no tiene acceso a este apartado.","error"); return; }
  state.page = page;
  document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.page===page));
  const pages={dashboard:dashboardPage,availability:availabilityPage,reservations:reservationsPage,reception:receptionPage,folios:foliosPage,housekeeping:housekeepingPage,maintenance:maintenancePage,tariffs:tariffsPage,groups:groupsPage,staychanges:stayChangesPage,walk:walkPage,channels:channelsPage,reports:reportsPage,teacherdata:teacherDataPage};
  pages[page]?.();
}
function setWorking(button, working) {
  button.disabled = working;
  if (working) {button.dataset.original=button.textContent;button.textContent="Procesando...";}
  else {button.textContent=button.dataset.original||"Enviar";}
}
async function runForm(e, execute, messageId) {
  e.preventDefault();const btn=e.submitter || e.target.querySelector('button[type="submit"]');
  if (btn) setWorking(btn,true);
  try {const result=await execute(new FormData(e.target)); if (result !== undefined) {
    message(messageId,typeof result === "string"?result:"Operación realizada.","success");
  }}
  catch(err){message(messageId,err.message,"error");}
  finally{if(btn?.isConnected)setWorking(btn,false);}
}
function makeTable(container, columns, rows, {empty="No hay registros que mostrar."}={}) {
  container.replaceChildren(); container.classList.remove("empty");
  if (!Array.isArray(rows) || rows.length===0) { const e=document.createElement("div");e.className="empty";e.textContent=empty;container.append(e);return; }
  const wrapper=document.createElement("div");wrapper.className="table-scroll";
  const table=document.createElement("table");table.className="data-table";
  const header=table.createTHead().insertRow();
  for (const col of columns) {const th=document.createElement("th");th.textContent=col;header.append(th);}
  const body=table.createTBody();
  for(const row of rows){
    const tr=body.insertRow();
    for(const cell of row){
      const td=tr.insertCell();
      if(cell && typeof cell==="object" && typeof cell.action==="function") {
        const b=document.createElement("button");b.className="button small secondary";b.type="button";b.textContent=cell.label||"Ver";
        b.addEventListener("click",cell.action);td.append(b);
      } else if(cell && typeof cell==="object" && cell.pill) {
        const s=text(td,cell.pill,`pill ${cell.color||""}`);
      } else text(td,cell);
    }
  }
  wrapper.append(table);container.append(wrapper);
}
function badgeFor(status) {
  const s=String(status||"");
  const color=/CONFIRMADA|AVAILABLE|INSPECTED|CHECK_OUT|CERRADO/.test(s)?"green":/CANCELADA|OUT_OF_ORDER|NO_SHOW/.test(s)?"red":/SOLICITADA|DIRTY|OCCUPIED|CHECK_IN/.test(s)?"amber":"blue";
  return {pill:s,color};
}
function card(label, value, foot="") {
  const div=document.createElement("div");div.className="metric";
  const a=document.createElement("div");a.className="micro";a.textContent=label;
  const b=document.createElement("strong");b.textContent=value;
  const c=document.createElement("div");c.className="foot";c.textContent=foot;
  div.append(a,b,c);return div;
}
async function dashboardPage() {
  const root=heading("Resumen operativo","Consulta datos del backend y accede a los módulos permitidos para tu rol.");
  const banner=document.createElement("section");banner.className="info-banner";
  const h=document.createElement("h2");h.textContent=`Bienvenido, ${state.staff.username}`;
  const p=document.createElement("p");p.textContent=`Sesión activa como ${ROLE_NAMES[state.staff.role]||state.staff.role}. Los indicadores se consultan en tiempo real; no se muestran datos inventados.`;
  banner.append(h,p);root.append(banner);
  const cards=document.createElement("div");cards.className="cards";cards.id="dashboardCards";root.append(cards);
  cards.append(card("Reservas consultadas aquí",String(state.recent.length),"Historial de esta pestaña, no total del hotel"));
  cards.append(card("Fecha local",todayISO(),"Fecha del dispositivo"));
  cards.append(card("Integración", "API REST", "FastAPI + PostgreSQL"));
  const panel=document.createElement("section");panel.className="panel";
  panel.innerHTML=`<h2>Accesos rápidos</h2><p class="panel-desc">Elige una operación para trabajar con registros reales.</p><div id="quickActions" class="inline-actions"></div>`;
  root.append(panel);
  for (const [id,label] of [["availability","Buscar habitaciones"],["reservations","Gestionar reserva"],["reception","Check-in / check-out"],["folios","Consultar folio"],["reports","Ver reportes"]]) {
    if(!allowed(id))continue;const b=document.createElement("button");b.type="button";b.className="button secondary";b.textContent=label;b.addEventListener("click",()=>navigate(id));$("quickActions").append(b);
  }
  if(allowed("reports")) {
    const rp=document.createElement("section");rp.className="panel";rp.innerHTML=`<h2>Indicadores operativos del día</h2><p class="panel-desc">Estimaciones del endpoint de reportes, no contabilidad auditada.</p><div id="todayStats" class="cards"></div><div id="dashboardNote" class="caption"></div>`;root.append(rp);
    try{
      const r=await request(`/staff/reports/daily?target_date=${todayISO()}`);
      if(state.page!=="dashboard")return;
      $("todayStats").append(card("Habitaciones en inventario",r.rooms_total??"—","Total actual"));
      $("todayStats").append(card("Ocupación estimada",`${r.estimated_occupancy_percent??"—"}%`,"Estimación para hoy"));
      $("todayStats").append(card("Llegadas previstas",r.arrivals?.length??"—","Según reservas registradas"));
      $("dashboardNote").textContent=r.note||"";
    }catch(err){if(state.page==="dashboard")$("dashboardNote").textContent=err.message;}
  }
}
function availabilityPage(){
  const root=heading("Disponibilidad de habitaciones","Busca habitaciones por fecha, tipo y capacidad. Solo se muestran las que devuelve PostgreSQL.");
  root.innerHTML=`<section class="panel"><h2>Buscar habitaciones</h2><p class="panel-desc">La API evalúa reservas superpuestas y el estado operativo de las habitaciones.</p><form id="availForm" class="form-stack"><div class="fields">
    <div class="field"><label for="avIn">Entrada</label><input type="date" id="avIn" name="check_in" required></div>
    <div class="field"><label for="avOut">Salida</label><input type="date" id="avOut" name="check_out" required></div>
    <div class="field"><label for="avType">Tipo (opcional)</label><input id="avType" name="room_type" placeholder="Estándar"></div>
    <div class="field"><label for="avGuests">Personas</label><input id="avGuests" name="guests" type="number" min="1" max="30" value="2" required></div>
  </div><div class="row"><button class="button" type="submit">Consultar disponibilidad</button></div><div id="availMessage" hidden></div></form></section>
  <section class="panel"><h2>Habitaciones disponibles</h2><p class="panel-desc">La tarifa mostrada es la tarifa base, no una cotización final por temporada.</p><div id="availResults" class="empty">Realiza una búsqueda para ver resultados.</div></section>`;
  $("avIn").value=state.chosenRoom?.check_in||todayISO(1);
  $("avOut").value=state.chosenRoom?.check_out||todayISO(2);
  $("availForm").addEventListener("submit",e=>runForm(e,async f=>{
    const data=Object.fromEntries(f);
    if(data.check_out<=data.check_in)throw Error("La fecha de salida debe ser posterior a la entrada.");
    const params=new URLSearchParams({check_in:data.check_in,check_out:data.check_out,guests:data.guests});
    if(data.room_type.trim())params.set("room_type",data.room_type.trim());
    const rows=await request(`/rooms/available?${params}`);
    makeTable($("availResults"),["Habitación","Tipo","Capacidad","Tarifa base","Acción"],rows.map(r=>[
      r.number,r.room_type,`${r.capacity} personas`,displayMoney(r.base_rate),{label:"Seleccionar",action:()=>{
        state.chosenRoom={...r,check_in:data.check_in,check_out:data.check_out};
        if(allowed("reservations")){navigate("reservations");toast(`Habitación ${r.number} seleccionada.`);}
        else toast("La consulta es solo de lectura para tu rol.","warning");
      }}]),{empty:"No existen habitaciones disponibles con esos filtros."});
    return `${rows.length} habitación(es) encontradas.`;
  },"availMessage"));
}
function reservationDetail(record) {
  const target=$("reservationDetail");if(!target)return;
  target.replaceChildren();
  state.currentReservation=record;rememberId(record.id);
  const rows=[
    ["ID",record.id],["Estado",record.status],["Habitación UUID",record.room_id],
    ["Huésped UUID",record.guest_id],["Entrada",record.check_in],["Salida",record.check_out]
  ];
  const table=document.createElement("div");table.className="table-scroll";
  const t=document.createElement("table");t.className="data-table";const tb=t.createTBody();
  for(const [label,value] of rows){const tr=tb.insertRow();let td=tr.insertCell();td.textContent=label;td=tr.insertCell();td.textContent=value;td.className=label.includes("UUID")||label==="ID"?"mono":"";}
  table.append(t);target.append(table);
  const actions=document.createElement("div");actions.className="inline-actions";actions.style.marginTop="14px";
  function addAction(label, action, css="secondary"){
    const b=document.createElement("button");b.type="button";b.className=`button small ${css}`;b.textContent=label;
    b.addEventListener("click",action);actions.append(b);
  }
  if(record.status==="SOLICITADA"){
    if(allowed("tariffs")) addAction("Aceptar cotización",()=>{navigate("tariffs");if($("acceptRes"))$("acceptRes").value=record.id;});
    addAction("Confirmar",async()=>{if(!confirm("¿Confirmar esta reserva?"))return;try{const r=await request(`/reservations/${record.id}/confirm`,{method:"PATCH"});reservationDetail(r);toast("Reserva confirmada.");}catch(e){toast(e.message,"error");}},"");
    addAction("Cancelar solicitud",async()=>{if(!confirm("¿Cancelar esta solicitud?"))return;try{const r=await request(`/reservations/${record.id}/cancel`,{method:"PATCH"});reservationDetail(r);toast("Solicitud cancelada.");}catch(e){toast(e.message,"error");}},"danger");
  }
  if(record.status==="CONFIRMADA"){
    addAction("Cancelación según RN-04",async()=>{
      if(!confirm("¿Aplicar la política de cancelación? La penalización quedará pendiente de pasarela, no se realizará un cobro real."))return;
      try{const r=await request(`/staff/reservations/${record.id}/cancel-policy`,{method:"POST"});toast(`Cancelación registrada. Penalización: ${displayMoney(r.penalty)}; estado de liquidación: ${r.settlement_status}.`);await loadReservation(record.id);}catch(e){toast(e.message,"error");}
    },"danger");
  }
  if(allowed("reception") && ["CONFIRMADA","CHECK_IN"].includes(record.status))addAction("Ir a recepción",()=>{navigate("reception");$("rxReservation").value=record.id;});
  target.append(actions);
}
async function loadReservation(id) {
  const record=await request(`/reservations/${encodeURIComponent(id)}`);
  if(state.page==="reservations")reservationDetail(record);
  else {state.currentReservation=record;rememberId(record.id);}
  return record;
}
function reservationsPage(){
  const root=heading("Reservaciones","Crea solicitudes, consulta por UUID, confirma y cancela según el estado y las políticas del hotel.");
  root.innerHTML=`<div class="two-col"><section class="panel"><h2>Nueva solicitud</h2><p class="panel-desc">Primero selecciona una habitación desde Disponibilidad. Para pruebas puedes generar un UUID de huésped ficticio.</p>
    <form id="createResForm" class="form-stack"><div class="fields">
      <div class="field"><label for="newGuest">UUID del huésped</label><input id="newGuest" name="guest_id" required placeholder="xxxxxxxx-xxxx-..." autocomplete="off"></div>
      <div class="field"><label for="newRoom">UUID de habitación</label><input id="newRoom" name="room_id" required placeholder="UUID devuelto por disponibilidad" autocomplete="off"></div>
      <div class="field"><label for="resIn">Check-in</label><input type="date" id="resIn" name="check_in" required></div>
      <div class="field"><label for="resOut">Check-out</label><input type="date" id="resOut" name="check_out" required></div>
    </div><div class="inline-actions"><button class="button secondary" type="button" id="guestUUID">Generar UUID de prueba</button><button class="button" type="submit">Crear reservación</button></div><div id="createResMsg" hidden></div></form></section>
    <section class="panel"><h2>Buscar reservación</h2><p class="panel-desc">El backend todavía no expone un listado global. Busca mediante el identificador exacto.</p>
      <form id="searchResForm" class="form-stack"><div class="field"><label for="searchResId">UUID de reservación</label><input id="searchResId" required autocomplete="off" placeholder="Pega el UUID"></div><button class="button secondary" type="submit">Consultar por UUID</button><div id="searchResMsg" hidden></div></form>
      <div class="section-divider"></div><h3>Detalle</h3><div id="reservationDetail" class="empty">Selecciona una reserva o crea una nueva.</div></section></div>
      <section class="panel"><h2>Reservas recientes de esta pestaña</h2><p class="panel-desc">No es un listado global de PostgreSQL. Solo conserva los UUID consultados durante esta sesión.</p><div id="recentRes"></div></section>`;
  $("resIn").value=state.chosenRoom?.check_in||todayISO(1);
  $("resOut").value=state.chosenRoom?.check_out||todayISO(2);
  $("newRoom").value=state.chosenRoom?.id||"";
  $("newGuest").value=state.teacherGuestId||"";
  $("guestUUID").addEventListener("click",()=>{ $("newGuest").value=crypto.randomUUID();toast("UUID de huésped ficticio generado para demostración.","warning");});
  $("createResForm").addEventListener("submit",e=>runForm(e,async f=>{
    const body=Object.fromEntries(f);
    if(body.check_out<=body.check_in)throw Error("La salida debe ser posterior a la entrada.");
    const rec=await request("/reservations",{method:"POST",body});
    reservationDetail(rec);refreshRecent();$("searchResId").value=rec.id;
    return `Solicitud creada correctamente. UUID: ${rec.id}`;
  },"createResMsg"));
  $("searchResForm").addEventListener("submit",e=>runForm(e,async()=>{
    const rec=await loadReservation($("searchResId").value.trim());refreshRecent();
    return `Reservación localizada: ${rec.status}.`;
  },"searchResMsg"));
  if(state.currentReservation)reservationDetail(state.currentReservation);
  refreshRecent();
}
function refreshRecent(){
  const target=$("recentRes");if(!target)return;
  makeTable(target,["UUID consultado","Acción"],state.recent.map(id=>[
    id,{label:"Ver",action:async()=>{try{const r=await loadReservation(id);$("searchResId").value=r.id;}catch(e){toast(e.message,"error");}}}
  ]),{empty:"Todavía no has consultado reservaciones en esta pestaña."});
}
function receptionPage() {
  const root=heading("Recepción y estancias","Registra documentación protegida y ejecuta check-in y check-out en la fecha real del hotel.");
  root.innerHTML=`<div class="two-col">
    <section class="panel"><h2>Documentación de llegada</h2><p class="panel-desc">Datos personales: la API los cifra. No se almacenan en el navegador.</p>
      <form id="documentForm" class="form-stack"><div class="fields">
      <div class="field"><label for="docReservation">UUID de reserva confirmada</label><input id="docReservation" name="reservation_id" required></div>
      <div class="field"><label for="docName">Nombre completo</label><input id="docName" name="full_name" required autocomplete="off"></div>
      <div class="field"><label for="docId">Número de identificación oficial</label><input id="docId" name="official_id_number" required autocomplete="off"></div>
      <div class="field"><label for="docExpiry">Vigencia de identificación</label><input id="docExpiry" type="date" name="official_id_valid_until" required></div>
      <div class="field"><label for="docCountry">Nacionalidad</label><input id="docCountry" name="nationality" required></div>
      <div class="field"><label for="docContact">Contacto</label><input id="docContact" name="contact_details" required autocomplete="off"></div>
      <div class="field"><label for="docFiscal">Domicilio fiscal (si aplica)</label><input id="docFiscal" name="fiscal_address"></div>
      </div><label class="checkline"><input type="checkbox" name="invoice_requested"> Solicita factura</label>
      <label class="checkline"><input type="checkbox" name="guarantee_accepted"> Garantía válida aceptada y verificada</label>
      <button class="button" type="submit">Guardar documentación cifrada</button><div id="documentMsg" hidden></div></form>
    </section>
    <section class="stack"><div class="panel"><h2>Operación de estancia</h2><p class="panel-desc">Utiliza la hora actual del servidor. No permite simular horas fuera de desarrollo.</p>
      <div class="form-stack"><div class="field"><label for="rxReservation">UUID de reservación</label><input id="rxReservation" required placeholder="Pega la reserva confirmada"></div>
      <div class="inline-actions"><button type="button" class="button" id="checkInBtn">Registrar check-in</button><button type="button" class="button secondary" id="checkOutBtn">Registrar check-out</button></div><div id="operationMessage" hidden></div></div></div>
      <div class="panel"><h2>Consideraciones de recepción</h2><div class="kbd-note">El check-in exige una reserva confirmada, documentación y garantía. El check-out requiere folio abierto con saldo cero. Las reglas de fechas y horarios se validan en el backend.</div>
      <p class="caption" style="margin-top:13px">Las operaciones reales solo deben ejecutarse con datos de demostración mientras la configuración de producción no esté revisada.</p></div>
    </section></div>`;
  if(state.currentReservation){$("rxReservation").value=state.currentReservation.id;$("docReservation").value=state.currentReservation.id;}
  $("docExpiry").value=todayISO(365);
  $("documentForm").addEventListener("submit",e=>runForm(e,async f=>{
    const rid=String(f.get("reservation_id")).trim();f.delete("reservation_id");
    const body=Object.fromEntries(f);
    body.invoice_requested = f.get("invoice_requested")==="on";
    body.guarantee_accepted = f.get("guarantee_accepted")==="on";
    body.fiscal_address = body.fiscal_address?.trim()||null;
    const r=await request(`/staff/reservations/${encodeURIComponent(rid)}/check-in-documentation`,{method:"POST",body});
    $("docId").value="";$("docContact").value="";
    return r.missing_guarantee_risk?"Documentación registrada; falta garantía. El check-in estará restringido.":"Documentación registrada y cifrada.";
  },"documentMsg"));
  for(const [id,part,label] of [["checkInBtn","check-in","entrada"],["checkOutBtn","check-out","salida"]]){
    $(id).addEventListener("click",async()=>{
      const rid=$("rxReservation").value.trim();if(!rid){message("operationMessage","Introduce el UUID de reservación.","error");return;}
      if(!confirm(`¿Registrar ${label} ahora? Se actualizarán estados de reserva, habitación y folio.`))return;
      const btn=$(id);setWorking(btn,true);
      try{
        const result=await request(`/staff/reservations/${encodeURIComponent(rid)}/${part}`,{method:"POST",body:{}});
        if(result?.folio_id)state.lastFolioId=String(result.folio_id);
        message("operationMessage",`${label.toUpperCase()} registrado correctamente. ${result?.folio_id ? `Folio UUID: ${result.folio_id}`:""}`,"success");
        state.currentReservation=null;
      }catch(e){message("operationMessage",e.message,"error");}
      finally{if(btn.isConnected)setWorking(btn,false);}
    });
  }
}
function housekeepingPage(){
  const root=heading("Control de limpieza","Consulta habitaciones sucias y registra el fin de limpieza con tu cuenta de Housekeeping.");
  root.innerHTML=`<section class="panel"><div class="row between"><div><h2>Pendientes de limpieza</h2><p class="panel-desc">Las tareas provienen de la API. La operación queda auditada.</p></div><button class="button secondary" id="reloadDirty">Actualizar</button></div><div id="dirtyResult" class="empty">Consultando habitaciones...</div></section>`;
  $("reloadDirty").addEventListener("click",loadDirty);loadDirty();
}
async function loadDirty(){
  try{
    const rows=await request("/staff/rooms/dirty");if(state.page!=="housekeeping")return;
    makeTable($("dirtyResult"),["Número","Tipo","ID","Acción"],rows.map(r=>[
      r.number,r.room_type,r.id,{label:"Marcar como limpia",action:async()=>{
        if(!confirm(`¿Confirmar limpieza de ${r.number}?`))return;
        try{await request(`/staff/rooms/${r.id}/clean`,{method:"POST"});toast(`Habitación ${r.number} marcada como limpia.`);await loadDirty();}catch(e){toast(e.message,"error");}
      }}
    ]),{empty:"No hay habitaciones sucias registradas."});
  }catch(e){if(state.page==="housekeeping")message("dirtyResult",e.message,"error");}
}
function foliosPage(){
  const root=heading("Folios y movimientos","Consulta el saldo registrado y añade un pago manual; esto no procesa tarjetas ni pasarelas.");
  root.innerHTML=`<div class="two-col"><section class="panel"><h2>Consultar folio</h2><p class="panel-desc">Utiliza el UUID devuelto por el check-in o una consulta existente.</p>
    <form id="folioQuery" class="form-stack"><div class="field"><label for="folioId">UUID del folio</label><input id="folioId" required></div><button class="button" type="submit">Consultar folio</button><div id="folioMessage" hidden></div></form><div id="folioInfo" style="margin-top:20px"></div></section>
    <section class="panel"><h2>Registrar pago</h2><p class="panel-desc">Anota un pago que ya haya sido verificado externamente. No representa captura de dinero.</p>
      <form id="folioPayment" class="form-stack"><div class="field"><label for="paymentFolioId">UUID del folio</label><input id="paymentFolioId" required></div>
      <div class="field"><label for="paymentDesc">Descripción / referencia manual</label><input id="paymentDesc" required maxlength="500"></div>
      <div class="field"><label for="paymentAmount">Importe registrado (MXN)</label><input id="paymentAmount" type="number" min="0.01" step="0.01" required></div>
      <button class="button" type="submit">Registrar pago confirmado</button><div id="paymentMessage" hidden></div></form></section></div>`;
  $("folioId").value=state.lastFolioId;$("paymentFolioId").value=state.lastFolioId;
  $("folioQuery").addEventListener("submit",e=>runForm(e,async()=>{
    const id=$("folioId").value.trim();const f=await request(`/staff/folios/${encodeURIComponent(id)}`);
    state.lastFolioId=id;$("paymentFolioId").value=id;
    const target=$("folioInfo");target.replaceChildren();
    const metrics=document.createElement("div");metrics.className="cards";metrics.style.gridTemplateColumns="repeat(auto-fit,minmax(130px,1fr))";
    metrics.append(card("Cargos",displayMoney(f.total_charges)),card("Pagos",displayMoney(f.total_payments)),card("Saldo",displayMoney(f.balance)));
    target.append(metrics);const h=document.createElement("h3");h.style.marginTop="25px";h.textContent=`Movimientos del folio (${f.status})`;target.append(h);
    const table=document.createElement("div");target.append(table);
    makeTable(table,["Tipo","Descripción","Importe"],[...(f.charges||[]).map(c=>["Cargo",c.description,displayMoney(c.amount)]),...(f.payments||[]).map(p=>["Pago",p.description,displayMoney(p.amount)])],{empty:"Este folio no tiene movimientos."});
    return "Folio consultado correctamente.";
  },"folioMessage"));
  $("folioPayment").addEventListener("submit",e=>runForm(e,async()=>{
    const id=$("paymentFolioId").value.trim();if(!confirm("Confirma que el importe ya fue recibido y verificado fuera del sistema."))return;
    const r=await request(`/staff/folios/${encodeURIComponent(id)}/payments`,{method:"POST",body:{description:$("paymentDesc").value.trim(),amount:$("paymentAmount").value}});
    $("folioId").value=id;
    return `Pago anotado en el folio. Saldo: ${displayMoney(r.balance)}. No se ha ejecutado una transacción bancaria.`;
  },"paymentMessage"));
  addVoucherForm(root);
}
function maintenancePage(){
  const root=heading("Habitaciones y mantenimiento","Registra incidencias y solicita su resolución o reincorporación según el rol autorizado.");
  root.innerHTML=`<section class="panel"><h2>Administración de estado</h2><p class="panel-desc">Los permisos efectivos se comprueban en la API; no basta con ocultar botones.</p><form id="maintenanceForm" class="form-stack">
    <div class="field"><label for="maintRoom">UUID de habitación</label><input id="maintRoom" required placeholder="UUID de la habitación"></div>
    <div class="field"><label for="maintReason">Motivo de incidencia</label><textarea id="maintReason" minlength="5" maxlength="500" placeholder="Describir incidencia (mínimo 5 caracteres)"></textarea></div>
    <div class="inline-actions" id="maintActions"></div><div id="maintenanceMessage" hidden></div></form>
    <hr class="section-divider"><div class="field"><label for="incidentId">UUID de incidencia (para mantenimiento)</label><input id="incidentId" placeholder="Identificador que devuelve el reporte"></div>
    <div class="inline-actions" style="margin-top:14px"><button class="button secondary" type="button" id="resolveIncident">Marcar incidencia resuelta</button></div>
    <p class="caption" style="margin-top:16px">La reincorporación necesita incidencia resuelta y aprobación gerencial. La inspección es una operación distinta.</p></section>`;
  const actions=$("maintActions");
  for(const [label,path,getBody,permission] of [
    ["Reportar fuera de servicio",id=>`/staff/rooms/${id}/out-of-service`,()=>({reason:$("maintReason").value.trim()}),["RECEPTION","MAINTENANCE","MANAGER_RECEPTION","MANAGER_OPERATIONS"]],
    ["Reincorporar habitación",id=>`/staff/rooms/${id}/restore`,()=>({requires_cleaning:true}),["MANAGER_RECEPTION","MANAGER_OPERATIONS"]],
    ["Inspeccionar habitación",id=>`/staff/rooms/${id}/inspect`,()=>undefined,["HOUSEKEEPING","MANAGER_RECEPTION","MANAGER_OPERATIONS"]]
  ]){
    if(!permission.includes(state.staff.role))continue;
    const btn=document.createElement("button");btn.type="button";btn.className="button secondary";btn.textContent=label;
    btn.addEventListener("click",async()=>{
      const id=$("maintRoom").value.trim();if(!id){message("maintenanceMessage","Introduce el UUID de habitación.","error");return;}
      if(!confirm(`¿Confirmar operación: ${label}?`))return;
      const body=getBody();setWorking(btn,true);
      try{const response=await request(path(encodeURIComponent(id)),{method:"POST",body});
        if(response.incident_id)$("incidentId").value=response.incident_id;
        message("maintenanceMessage",JSON.stringify(response),"success");
      }catch(e){message("maintenanceMessage",e.message,"error");}
      finally{if(btn.isConnected)setWorking(btn,false);}
    });actions.append(btn);
  }
  if(state.staff.role!=="MAINTENANCE")$("resolveIncident").disabled=true;
  $("resolveIncident").addEventListener("click",async()=>{
    const id=$("incidentId").value.trim();if(!id)return message("maintenanceMessage","Introduce el UUID de incidencia.","error");
    try{const data=await request(`/staff/incidents/${encodeURIComponent(id)}/resolve`,{method:"POST"});message("maintenanceMessage",`Incidencia resuelta: ${data.incident_id}`,"success");}
    catch(e){message("maintenanceMessage",e.message,"error");}
  });
}
function tariffsPage(){
  const root=heading("Cotizaciones","Solicita una cotización con parámetros tarifarios configurados previamente por Gerencia.");
  root.innerHTML=`<section class="panel"><h2>Calcular tarifa</h2><p class="panel-desc">El cálculo toma las temporadas y multiplicadores autorizados del backend. No inventa tarifas.</p>
  <form id="quoteForm" class="form-stack"><div class="fields"><div class="field"><label for="quoteType">Tipo de habitación</label><input id="quoteType" name="room_type" value="Estándar" required></div>
    <div class="field"><label for="quoteIn">Check-in</label><input id="quoteIn" type="date" name="check_in" required></div>
    <div class="field"><label for="quoteOut">Check-out</label><input id="quoteOut" type="date" name="check_out" required></div>
    <div class="field"><label for="quoteChannel">Canal configurado</label><input id="quoteChannel" name="channel" required placeholder="Ej. directo"></div>
    <div class="field"><label for="quoteCustomer">Tipo de cliente configurado</label><input id="quoteCustomer" name="customer_type" required placeholder="Ej. individual"></div>
  </div><button class="button" type="submit">Cotizar estancia</button><div id="quoteMessage" hidden></div></form><div id="quoteResults" style="margin-top:20px"></div>
  <p class="caption">Si no existe una configuración tarifaria aprobada, la API devolverá un error. Gerencia puede crearla desde Swagger.</p></section>`;
  $("quoteIn").value=todayISO(1);$("quoteOut").value=todayISO(2);
  $("quoteForm").addEventListener("submit",e=>runForm(e,async f=>{
    const p=new URLSearchParams(Object.fromEntries(f));const q=await request(`/staff/tariffs/quote?${p}`);
    const target=$("quoteResults");target.replaceChildren();target.append(card("Cotización total",displayMoney(q.total),q.currency));
    const table=document.createElement("div");target.append(table);table.style.marginTop="15px";
    makeTable(table,["Fecha","Temporada","Tarifa de noche"],(q.nights||[]).map(n=>[n.day,n.season,displayMoney(n.amount)]));
    return "Cotización calculada con parámetros vigentes.";
  },"quoteMessage"));
  addTariffOperations(root);
}
function reportsPage(){
  const root=heading("Reportes y auditoría","Consultas operativas permitidas para Finanzas y Gerencia. Indicadores estimados, no contabilidad certificada.");
  root.innerHTML=`<div class="two-col"><section class="panel"><h2>Reporte diario</h2><form id="dailyForm" class="form-stack">
    <div class="field"><label for="dailyDate">Fecha</label><input type="date" id="dailyDate" required></div><button class="button" type="submit">Consultar día</button><div id="dailyMessage" hidden></div></form>
    <div id="dailyResults" style="margin-top:19px"></div></section>
    <section class="panel"><h2>Reporte semanal</h2><form id="weeklyForm" class="form-stack"><div class="field"><label for="weeklyStart">Inicio del periodo</label><input type="date" id="weeklyStart" required></div>
      <button class="button secondary" type="submit">Consultar semana</button><div id="weeklyMessage" hidden></div></form><div id="weeklyResults" style="margin-top:19px"></div></section></div>
    <section class="panel"><div class="row between"><div><h2>Auditoría</h2><p class="panel-desc">Últimas 30 operaciones registradas por el personal.</p></div><button id="auditReload" type="button" class="button secondary">Actualizar</button></div><div id="auditResults" class="empty">Presiona Actualizar.</div></section>`;
  $("dailyDate").value=todayISO();$("weeklyStart").value=todayISO(-6);
  $("dailyForm").addEventListener("submit",e=>runForm(e,async()=>{
    const r=await request(`/staff/reports/daily?target_date=${$("dailyDate").value}`);
    const target=$("dailyResults");target.replaceChildren();const cards=document.createElement("div");cards.className="cards";cards.style.gridTemplateColumns="repeat(auto-fit,minmax(130px,1fr))";
    cards.append(card("Habitaciones",r.rooms_total??"—"),card("Fuera de servicio",r.rooms_out_of_order_now??"—"),card("Ocupación estimada",`${r.estimated_occupancy_percent??"—"}%`));
    target.append(cards);const p=document.createElement("p");p.className="caption";p.textContent=r.note||"";target.append(p);
    const table=document.createElement("div");target.append(table);
    makeTable(table,["Llegadas previstas","Salidas previstas"],[[r.arrivals?.length??0,r.departures?.length??0]]);
    return "Reporte diario actualizado.";
  },"dailyMessage"));
  $("weeklyForm").addEventListener("submit",e=>runForm(e,async()=>{
    const r=await request(`/staff/reports/weekly?start_date=${$("weeklyStart").value}`);
    const target=$("weeklyResults");target.replaceChildren();const box=document.createElement("div");box.className="stack";
    box.append(card("Pagos anotados en el periodo",displayMoney(r.payments_recorded_in_period),"No equivale a ingresos por alojamiento"));
    box.append(card("Cancelaciones / no-show",`${r.cancelled_arrivals_in_period} / ${r.no_show_arrivals_in_period}`));
    target.append(box);const p=document.createElement("p");p.className="caption";p.textContent=r.note||"";target.append(p);
    return "Reporte semanal actualizado.";
  },"weeklyMessage"));
  $("auditReload").addEventListener("click",loadAudit);
}
async function loadAudit(){
  try{const rows=await request("/staff/audit?limit=30");if(state.page!=="reports")return;
    makeTable($("auditResults"),["Fecha","Operación","Entidad","Usuario (UUID)"],rows.map(r=>[
      r.occurred_at?.replace("T"," ").slice(0,19)||"—",r.action,`${r.entity_type} · ${r.entity_id}`,r.actor_id
    ]),{empty:"Sin eventos de auditoría registrados."});
  }catch(e){if(state.page==="reports")message("auditResults",e.message,"error");}
}

/* ETAPA 2. Los contratos de estos formularios corresponden a las rutas FastAPI U2/U3.
   Son formularios REST; no inventan listados ni pagos externos. */
function groupsPage() {
  const root=heading("Reservaciones grupales","US-22 / RN-07: bloqueo de diez o más habitaciones, contrato y depósito verificado manualmente.");
  root.innerHTML=`
    <section class="panel"><h2>Crear bloqueo grupal</h2><p class="panel-desc">Necesitas al menos diez UUID de habitaciones disponibles. Las tarifas y temporadas deben estar configuradas por Gerencia.</p>
      <form id="groupCreate" class="form-stack">
        <div class="fields"><div class="field"><label for="groupOrganizer">Organizador</label><input id="groupOrganizer" required minlength="2" maxlength="150"></div>
        <div class="field"><label for="groupContract">Referencia de contrato</label><input id="groupContract" required minlength="5" maxlength="150"></div>
        <div class="field"><label for="groupIn">Entrada</label><input type="date" id="groupIn" required></div>
        <div class="field"><label for="groupOut">Salida</label><input type="date" id="groupOut" required></div>
        <div class="field"><label for="groupDue">Vencimiento del depósito (hora de tu equipo)</label><input type="datetime-local" id="groupDue" required></div>
        <div class="field"><label for="groupChannel">Canal configurado</label><input id="groupChannel" required maxlength="40"></div>
        <div class="field"><label for="groupCustomer">Tipo de cliente configurado</label><input id="groupCustomer" required maxlength="40"></div></div>
        <div class="field"><label for="groupRooms">UUID de habitaciones (separa con comas o saltos de línea)</label><textarea id="groupRooms" rows="5" required placeholder="Pega al menos diez UUID diferentes"></textarea></div>
        <button class="button" type="submit">Crear bloqueo y calcular depósito</button><div id="groupCreateMsg" hidden></div>
      </form><div id="groupCreated" class="cards" style="margin-top:18px"></div>
    </section>
    <div class="two-col"><section class="panel"><h2>Confirmar depósito</h2><p class="panel-desc">Solo registra depósitos comprobados por el personal; no realiza cargos bancarios.</p>
      <form id="groupDeposit" class="form-stack"><div class="field"><label for="groupDepositId">UUID del grupo</label><input id="groupDepositId" required></div>
      <div class="field"><label for="groupDepositAmount">Importe verificado (MXN)</label><input id="groupDepositAmount" type="number" min="0.01" step="0.01" required></div>
      <div class="field"><label for="groupReceipt">Referencia del comprobante</label><input id="groupReceipt" required minlength="5" maxlength="150"></div>
      <button type="submit" class="button">Registrar depósito</button><div id="groupDepositMsg" hidden></div></form>
    </section><section class="panel"><h2>Cancelar grupo</h2><p class="panel-desc">RN-07: la API determina el reembolso según los siete días. La transferencia queda pendiente de gestión externa.</p>
      <form id="groupCancel" class="form-stack"><div class="field"><label for="groupCancelId">UUID del grupo</label><input id="groupCancelId" required></div>
      <button class="button danger" type="submit">Cancelar grupo</button><div id="groupCancelMsg" hidden></div></form>
    </section></div>`;
  $("groupIn").value=todayISO(7);$("groupOut").value=todayISO(9);
  const due=new Date(Date.now()+48*60*60*1000);$("groupDue").value=`${due.getFullYear()}-${String(due.getMonth()+1).padStart(2,"0")}-${String(due.getDate()).padStart(2,"0")}T${String(due.getHours()).padStart(2,"0")}:${String(due.getMinutes()).padStart(2,"0")}`;
  $("groupCreate").addEventListener("submit",e=>runForm(e,async()=>{
    const period=Forms.dates($("groupIn").value,$("groupOut").value);
    const room_ids=Forms.roomIds($("groupRooms").value);
    const result=await request("/staff/groups",{method:"POST",body:{
      organizer:$("groupOrganizer").value.trim(),contract_reference:$("groupContract").value.trim(),
      room_ids,...period,deposit_due_at:Forms.localDateTimeISO($("groupDue").value),
      channel:$("groupChannel").value.trim(),customer_type:$("groupCustomer").value.trim()
    }});
    $("groupDepositId").value=result.id;$("groupCancelId").value=result.id;
    const cards=$("groupCreated");cards.replaceChildren();cards.append(card("Grupo",result.id,"Copia este UUID para próximas operaciones"),card("Total presupuestado",displayMoney(result.total)),card("Depósito requerido",displayMoney(result.required_deposit),"30 % del total"));
    return `Grupo creado: ${result.id}. Estado: ${result.status}.`;
  },"groupCreateMsg"));
  $("groupDeposit").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("groupDepositId").value,"Grupo");
    const amount=Forms.amount($("groupDepositAmount").value,"Depósito");
    if(!confirm("¿El depósito fue recibido y su comprobante fue verificado? Este sistema no procesa pagos."))return;
    const r=await request(`/staff/groups/${id}/confirm-deposit`,{method:"POST",body:{amount,receipt_reference:$("groupReceipt").value.trim()}});
    return `Depósito registrado manualmente: ${displayMoney(r.deposit_recorded)}. Estado ${r.status}.`;
  },"groupDepositMsg"));
  $("groupCancel").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("groupCancelId").value,"Grupo");
    if(!confirm("¿Cancelar grupo? Esta operación es irreversible; el reembolso no se ejecuta automáticamente."))return;
    const r=await request(`/staff/groups/${id}/cancel`,{method:"POST"});
    return `Estado: ${r.status}. Reembolso estimado: ${displayMoney(r.refundable_deposit)}. ${r.notice||""}`;
  },"groupCancelMsg"));
}
function stayChangesPage(){
  const root=heading("Cambios de estancia","US-11, US-12 y RN-05: reasignaciones, ampliaciones y validaciones de reserva.");
  root.innerHTML=`<div class="two-col"><section class="panel"><h2>Cambiar habitación</h2>
    <p class="panel-desc">Solo durante una estancia activa. La habitación anterior queda sucia y la nueva debe estar libre.</p>
    <form id="changeRoomForm" class="form-stack"><div class="field"><label for="changeReservation">UUID de la reserva</label><input id="changeReservation" required></div>
    <div class="field"><label for="changeToRoom">UUID de la habitación de destino</label><input id="changeToRoom" required></div>
    <div class="field"><label for="changeReason">Motivo del cambio</label><textarea id="changeReason" required minlength="5" maxlength="500"></textarea></div>
    <button class="button" type="submit">Cambiar habitación</button><div id="changeRoomMsg" hidden></div></form></section>
    <section class="panel"><h2>Ampliar estancia</h2><p class="panel-desc">Requiere rol gerencial, tarifa original aceptada y conformidad del huésped.</p>
    <form id="extendForm" class="form-stack"><div class="field"><label for="extendReservation">UUID de reserva</label><input id="extendReservation" required></div>
    <div class="field"><label for="newCheckout">Nueva fecha de salida</label><input id="newCheckout" type="date" required></div>
    <div class="field"><label for="extendReason">Motivo</label><textarea id="extendReason" required minlength="5" maxlength="500"></textarea></div>
    <label class="checkline"><input id="extendAccepted" type="checkbox" required> El huésped aceptó la tarifa adicional</label>
    <button class="button" type="submit">Ampliar estancia</button><div id="extendMsg" hidden></div></form></section></div>
    <div class="two-col"><section class="panel"><h2>Posibles reservas duplicadas</h2><p class="panel-desc">Busca coincidencias por UUID de huésped y fechas, no por nombre o contacto.</p>
    <form id="duplicateForm" class="form-stack"><div class="field"><label for="duplicateReservation">UUID de reserva</label><input id="duplicateReservation" required></div>
    <button class="button secondary" type="submit">Buscar coincidencias</button><div id="duplicateMsg" hidden></div></form><div id="duplicateResults"></div></section>
    <section class="panel"><h2>Garantía tokenizada</h2><p class="panel-desc">Solo referencias externas. Nunca introduzcas número de tarjeta, CVV ni contraseñas.</p>
    <form id="guaranteeForm" class="form-stack"><div class="field"><label for="guaranteeReservation">UUID de reserva</label><input id="guaranteeReservation" required></div>
    <div class="field"><label for="guaranteeMethod">Método</label><input id="guaranteeMethod" required minlength="3" maxlength="80" placeholder="Referencia de garantía"></div>
    <div class="field"><label for="guaranteeRef">Token / referencia externa</label><input id="guaranteeRef" required minlength="3" maxlength="255" autocomplete="off"></div>
    <button class="button" type="submit">Registrar constancia</button><div id="guaranteeMsg" hidden></div></form></section></div>
    <section class="panel" id="noshowSection"><h2>Marcar no-show (RN-05)</h2><p class="panel-desc">Solo después de las 23:59 del día de llegada, con las condiciones del backend. Las penalizaciones se registran como pendientes; no son cobros reales.</p>
    <form id="noshowForm" class="form-stack"><div class="field"><label for="noshowReservation">UUID de reserva</label><input id="noshowReservation" required></div>
    <button type="submit" class="button danger">Registrar no-show</button><div id="noshowMsg" hidden></div></form></section>`;
  if(state.currentReservation){for(const id of ["changeReservation","extendReservation","duplicateReservation","guaranteeReservation","noshowReservation"])$(id).value=state.currentReservation.id;}
  $("newCheckout").value=todayISO(2);
  if(!["MANAGER_RECEPTION","MANAGER_OPERATIONS"].includes(state.staff.role))$("extendForm").querySelector('button[type="submit"]').disabled=true;
  if(!["FINANCE","MANAGER_RECEPTION","MANAGER_OPERATIONS"].includes(state.staff.role))$("noshowSection").hidden=true;
  $("changeRoomForm").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("changeReservation").value,"Reserva");
    const room=Forms.requireUUID($("changeToRoom").value,"Habitación nueva");
    if(!confirm("¿Cambiar habitación? La antigua pasará a sucia y la nueva a ocupada."))return;
    const r=await request(`/staff/reservations/${id}/change-room`,{method:"POST",body:{new_room_id:room,reason:$("changeReason").value.trim()}});
    return `Habitación reasignada. Anterior: ${r.old_room_id} (${r.old_room_status}); nueva: ${r.new_room_id} (${r.new_room_status}).`;
  },"changeRoomMsg"));
  $("extendForm").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("extendReservation").value,"Reserva");
    if(!$("extendAccepted").checked)throw Error("El huésped debe aceptar la tarifa adicional.");
    if(!confirm("¿Extender estancia con la cotización adicional vigente?"))return;
    const r=await request(`/staff/reservations/${id}/extend`,{method:"POST",body:{new_check_out:$("newCheckout").value,guest_accepted:true,reason:$("extendReason").value.trim()}});
    return `Nueva salida ${r.new_check_out}. Importe añadido ${displayMoney(r.added_total)}. Nuevo total ${displayMoney(r.updated_total)}.`;
  },"extendMsg"));
  $("duplicateForm").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("duplicateReservation").value,"Reserva");
    const r=await request(`/staff/reservations/${id}/possible-duplicates`);
    makeTable($("duplicateResults"),["Posible coincidencia"],(r.possible_duplicate_ids||[]).map(i=>[String(i)]),{empty:"No hay coincidencias por huésped y fechas."});
    return r.warning?`${r.possible_duplicate_ids.length} coincidencia(s) potencial(es).`:"Sin coincidencias potenciales.";
  },"duplicateMsg"));
  $("guaranteeForm").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("guaranteeReservation").value,"Reserva");
    const ref=$("guaranteeRef").value.trim();
    if(/\d{12,19}/.test(ref.replace(/[ -]/g,"")))throw Error("No introduzcas números de tarjeta; usa solo token externo.");
    await request(`/staff/reservations/${id}/guarantee`,{method:"POST",body:{method:$("guaranteeMethod").value.trim(),external_reference:ref}});
    $("guaranteeRef").value="";
    return "Se registró la constancia tokenizada; no se verificó ni cobró una tarjeta.";
  },"guaranteeMsg"));
  $("noshowForm").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("noshowReservation").value,"Reserva");
    if(!confirm("¿Registrar no-show? El backend comprobará horario y registrará la penalización pendiente."))return;
    const r=await request(`/staff/reservations/${id}/no-show`,{method:"POST"});
    return `Estado ${r.status}. Penalización ${displayMoney(r.penalty)}, liquidación ${r.settlement_status}. No es cargo bancario.`;
  },"noshowMsg"));
}
function walkPage(){
  const root=heading("Reubicaciones por sobreventa","RN-06 / US-23: registrar expediente walk y confirmación manual de hotel aliado.");
  root.innerHTML=`<div class="two-col"><section class="panel"><h2>Crear plan de reubicación</h2><p class="panel-desc">Requiere una reserva confirmada y una incidencia real de asignación.</p>
    <form id="walkCreate" class="form-stack"><div class="field"><label for="walkReservation">UUID de reserva</label><input id="walkReservation" required></div>
    <div class="field"><label for="walkHotel">Hotel aliado</label><input id="walkHotel" required minlength="3" maxlength="150"></div>
    <div class="field"><label for="walkTransport">Transporte acordado</label><textarea id="walkTransport" required minlength="3" maxlength="500"></textarea></div>
    <div class="field"><label for="walkFare">Diferencia tarifaria (MXN)</label><input id="walkFare" type="number" min="0" step="0.01" value="0" required></div>
    <div class="field"><label for="walkCourtesy">Cortesías ofrecidas</label><textarea id="walkCourtesy" required minlength="3" maxlength="500"></textarea></div>
    <button class="button" type="submit">Crear expediente</button><div id="walkCreateMsg" hidden></div></form>
    </section><section class="panel"><h2>Confirmar reserva en hotel aliado</h2><p class="panel-desc">Solo Gerencia puede confirmar que el hotel aliado aceptó la reserva y que la categoría es equivalente.</p>
    <form id="walkConfirm" class="form-stack"><div class="field"><label for="walkCaseId">UUID de expediente walk</label><input id="walkCaseId" required></div>
    <div class="field"><label for="walkExternalRef">Referencia confirmada por hotel aliado</label><input id="walkExternalRef" required minlength="5" maxlength="200"></div>
    <label class="checkline"><input id="walkVerified" type="checkbox" required> Confirmé directamente con el hotel aliado la categoría equivalente.</label>
    <button class="button" type="submit">Registrar confirmación externa</button><div id="walkConfirmMsg" hidden></div></form></section></div>`;
  if(state.currentReservation)$("walkReservation").value=state.currentReservation.id;
  if(!["MANAGER_RECEPTION","MANAGER_OPERATIONS"].includes(state.staff.role))$("walkConfirm").querySelector('button[type="submit"]').disabled=true;
  $("walkCreate").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("walkReservation").value,"Reserva");
    const r=await request(`/staff/reservations/${id}/walk-plan`,{method:"POST",body:{
      allied_hotel:$("walkHotel").value.trim(),transport_details:$("walkTransport").value.trim(),
      fare_difference:Forms.amount($("walkFare").value,"Diferencia tarifaria",true),courtesy_details:$("walkCourtesy").value.trim()
    }});
    $("walkCaseId").value=r.walk_id;
    return `Expediente creado: ${r.walk_id}. Estado ${r.state}. Aún no se ha confirmado el alojamiento aliado.`;
  },"walkCreateMsg"));
  $("walkConfirm").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("walkCaseId").value,"Expediente");
    if(!$("walkVerified").checked)throw Error("Confirma la categoría equivalente antes de continuar.");
    if(!confirm("¿El hotel aliado confirmó realmente la nueva reservación?"))return;
    const r=await request(`/staff/walk-cases/${id}/confirm-partner`,{method:"POST",body:{partner_booking_reference:$("walkExternalRef").value.trim(),similar_category_verified:true}});
    return `Caso ${r.walk_id}: reserva ${r.reservation_id}, estado ${r.status}. Confirmación externa anotada manualmente.`;
  },"walkConfirmMsg"));
}
function channelsPage(){
  const root=heading("Eventos para canales de venta","US-25: eventos pendientes del outbox; no equivalen a sincronización real con OTA.");
  root.innerHTML=`<section class="panel"><div class="row between"><div><h2>Eventos pendientes</h2><p class="panel-desc">Muestra hasta 100 eventos que requieren una integración externa para ser publicados. La interfaz no cambia su estado.</p></div>
    <button class="button secondary" type="button" id="channelsReload">Actualizar</button></div><div id="channelsMsg" hidden></div><div id="channelsResults" class="empty">Haz clic en Actualizar para leer la bandeja.</div></section>`;
  $("channelsReload").addEventListener("click",async()=>{
    const b=$("channelsReload");setWorking(b,true);
    try{const rows=await request("/staff/channels/pending");if(state.page!=="channels")return;
      makeTable($("channelsResults"),["Evento UUID","Reserva UUID","Acción","Publicado"],rows.map(r=>[r.id,r.reservation_id,r.action,r.published?"Sí":"No"]),{empty:"No hay eventos pendientes de publicación."});
      message("channelsMsg",`${rows.length} evento(s) pendientes. Estos registros NO son confirmaciones de una OTA.`,"success");
    }catch(e){message("channelsMsg",e.message,"error");}finally{if(b.isConnected)setWorking(b,false);}
  });
}
function addTariffOperations(root){
  const acceptance=document.createElement("section");acceptance.className="panel";
  acceptance.innerHTML=`<h2>Aceptar cotización de una reserva solicitada</h2><p class="panel-desc">Guarda tarifa por noche y consentimiento del huésped; indispensable para aplicar determinadas penalizaciones y extensiones.</p>
    <form id="acceptQuoteForm" class="form-stack"><div class="fields"><div class="field"><label for="acceptRes">UUID de reserva</label><input id="acceptRes" required></div>
    <div class="field"><label for="acceptChannel">Canal configurado</label><input id="acceptChannel" required maxlength="40"></div>
    <div class="field"><label for="acceptCustomer">Tipo de cliente configurado</label><input id="acceptCustomer" required maxlength="40"></div></div>
    <label class="checkline"><input id="acceptConsent" type="checkbox" required> El huésped aceptó la cotización y las condiciones aplicables.</label>
    <button class="button" type="submit">Registrar tarifa aceptada</button><div id="acceptQuoteMsg" hidden></div></form>`;
  root.append(acceptance);
  if(state.currentReservation?.status==="SOLICITADA")$("acceptRes").value=state.currentReservation.id;
  $("acceptQuoteForm").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("acceptRes").value,"Reserva");
    if(!$("acceptConsent").checked)throw Error("Se requiere aceptación del huésped.");
    const r=await request(`/staff/tariffs/reservations/${id}/accept-quote`,{method:"POST",body:{
      channel:$("acceptChannel").value.trim(),customer_type:$("acceptCustomer").value.trim(),guest_accepted:true
    }});
    return `Tarifa aceptada: ${displayMoney(r.total)}. Primera noche ${displayMoney(r.first_night)}.`;
  },"acceptQuoteMsg"));
  if(!["MANAGER_RECEPTION","MANAGER_OPERATIONS"].includes(state.staff.role))return;
  const config=document.createElement("section");config.className="panel";
  config.innerHTML=`<h2>Configuración tarifaria aprobada (Gerencia)</h2><p class="panel-desc">RN-13: no existen factores oficiales precargados. Copia el esquema JSON, reemplaza TODOS los marcadores por tarifas, fechas y multiplicadores aprobados y guarda.</p>
    <form id="tariffConfigForm" class="form-stack"><div class="field"><label for="tariffConfigJSON">JSON de temporadas y multiplicadores</label><textarea id="tariffConfigJSON" rows="15" spellcheck="false" class="mono" required></textarea></div>
    <label class="checkline"><input id="tariffConfirmed" type="checkbox" required> Confirmo que los valores son políticas aprobadas por el hotel y no ejemplos inventados.</label>
    <button class="button" type="submit">Guardar configuración autorizada</button><div id="tariffConfigMsg" hidden></div></form>`;
  root.append(config);
  $("tariffConfigJSON").value=JSON.stringify({currency:"MXN",bar_by_room_and_season:{"Estándar|baja":"REEMPLAZAR_TARIFA"},weekend_multiplier:"REEMPLAZAR_FACTOR",channel_multipliers:{"directo":"REEMPLAZAR_FACTOR"},customer_multipliers:{"individual":"REEMPLAZAR_FACTOR"},seasons:[{name:"baja",start:"AAAA-MM-DD",end:"AAAA-MM-DD"}]},null,2);
  $("tariffConfigForm").addEventListener("submit",e=>runForm(e,async()=>{
    if(!$("tariffConfirmed").checked)throw Error("Confirma que todos los valores fueron aprobados.");
    const body=Forms.objectJSON($("tariffConfigJSON").value);
    if($("tariffConfigJSON").value.includes("REEMPLAZAR") || $("tariffConfigJSON").value.includes("AAAA-MM-DD"))throw Error("Reemplaza todos los marcadores por valores aprobados antes de guardar.");
    if(!confirm("¿Guardar una nueva configuración tarifaria que afectará las cotizaciones futuras?"))return;
    const r=await request("/staff/tariffs/configuration",{method:"POST",body});
    return `Configuración guardada: ${r.configuration_id}. Divisa ${r.currency}.`;
  },"tariffConfigMsg"));
}
function addVoucherForm(root){
  const section=document.createElement("section");section.className="panel";
  section.innerHTML=`<h2>Registrar consumo respaldado por vale (RN-12)</h2><p class="panel-desc">Este formulario registra un cargo a un folio existente. Requiere vale con habitación, huésped, firma registrada, hora, punto de venta y número. No realiza cobro bancario.</p>
    <form id="voucherForm" class="form-stack"><div class="fields">
    <div class="field"><label for="voucherFolio">UUID del folio</label><input id="voucherFolio" required></div>
    <div class="field"><label for="voucherRoom">Número de habitación del vale</label><input id="voucherRoom" required maxlength="30"></div>
    <div class="field"><label for="voucherGuest">Nombre del huésped</label><input id="voucherGuest" required maxlength="200" autocomplete="off"></div>
    <div class="field"><label for="voucherSignature">Referencia de firma del vale</label><input id="voucherSignature" required maxlength="500" autocomplete="off"></div>
    <div class="field"><label for="voucherTime">Fecha y hora de consumo</label><input id="voucherTime" type="datetime-local" required></div>
    <div class="field"><label for="voucherPOS">Punto de venta</label><input id="voucherPOS" required maxlength="100"></div>
    <div class="field"><label for="voucherNumber">Número del vale</label><input id="voucherNumber" required maxlength="100"></div>
    <div class="field"><label for="voucherAmount">Importe (MXN)</label><input id="voucherAmount" type="number" min="0.01" step="0.01" required></div></div>
    <div class="field"><label for="voucherDetail">Detalle de consumo</label><textarea id="voucherDetail" required maxlength="500"></textarea></div>
    <button class="button" type="submit">Registrar cargo respaldado por vale</button><div id="voucherMsg" hidden></div></form>`;
  root.append(section);
  $("voucherFolio").value=state.lastFolioId;
  const now=new Date();$("voucherTime").value=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}T${String(now.getHours()).padStart(2,"0")}:${String(now.getMinutes()).padStart(2,"0")}`;
  $("voucherForm").addEventListener("submit",e=>runForm(e,async()=>{
    const id=Forms.requireUUID($("voucherFolio").value,"Folio");
    const body={room_number:$("voucherRoom").value.trim(),guest_name:$("voucherGuest").value.trim(),
      guest_signature:$("voucherSignature").value.trim(),issued_at:Forms.localDateTimeISO($("voucherTime").value),
      point_of_sale:$("voucherPOS").value.trim(),consumption_detail:$("voucherDetail").value.trim(),
      amount:Forms.amount($("voucherAmount").value,"Importe"),voucher_number:$("voucherNumber").value.trim()};
    if(!confirm("¿Registrar este cargo? Verifica que el vale físico/digital firmado exista y sea válido."))return;
    const r=await request(`/staff/folios/${id}/charges`,{method:"POST",body});
    $("voucherGuest").value="";$("voucherSignature").value="";
    $("folioId").value=id;
    return `Cargo registrado. Nuevo saldo del folio: ${displayMoney(r.balance)}. No se realizó una transacción bancaria.`;
  },"voucherMsg"));
}

function teacherDataPage(){
  const root=heading("Datos ficticios del profesor","Datos integrados a PostgreSQL: 40 huéspedes, 20 habitaciones y 60 escenarios, sin reservar automáticamente fechas ni cobrar importes.");
  root.innerHTML=`<section class="panel"><h2>Catálogos operativos de demostración</h2><p class="panel-desc">Los huéspedes pueden seleccionarse para una reserva nueva. Los 20 recursos se incorporaron como habitaciones P-001 a P-020 con aforos de demostración explícitos; la columna original capacidad_o_stock NO equivale a personas.</p><div class="inline-actions"><button class="button" id="teacherGuestsBtn">40 huéspedes</button><button class="button secondary" id="teacherRoomsBtn">20 habitaciones</button><button class="button secondary" id="teacherScenariosBtn">60 escenarios</button><button class="button secondary" id="teacherCasesBtn">120 casos</button><button class="button secondary" id="teacherTransitionsBtn">20 transiciones</button></div><div id="teacherMessage" class="caption"></div><div id="teacherDataResult"></div><div id="teacherDetail" class="stack"></div></section>`;
  const result=$("teacherDataResult"), detail=$("teacherDetail");
  async function perform(button,fn){
    setWorking(button,true);detail.replaceChildren();
    try{await fn();}catch(err){message("teacherMessage",err.message,"error");}
    finally{if(button.isConnected)setWorking(button,false);}
  }
  $("teacherGuestsBtn").addEventListener("click",e=>perform(e.currentTarget,async()=>{
    const rows=await request("/staff/demo-data/guests");if(state.page!=="teacherdata")return;
    makeTable(result,["Código","Nombre","Ciudad","Activo","VIP","Utilizar"],rows.map(r=>[r.source_actor_id,r.name,r.city,r.is_active?"Sí":"No",r.is_preferred?"Sí":"No",{label:"Usar UUID",action:()=>{
      if(!r.is_active){toast("El huésped de ejemplo está inactivo.","error");return;}
      state.teacherGuestId=r.id;navigate("reservations");toast(`Huésped ${r.source_actor_id} seleccionado para nueva reserva.`);
    }}]));
    $("teacherMessage").textContent=`${rows.length} huéspedes ficticios cargados en el catálogo operacional.`;
  }));
  $("teacherRoomsBtn").addEventListener("click",e=>perform(e.currentTarget,async()=>{
    const rows=await request("/staff/demo-data/rooms");if(state.page!=="teacherdata")return;
    makeTable(result,["Recurso CSV","Habitación","Tipo","Personas (demo)","Tarifa base MXN","Estado"],rows.map(r=>[r.source_resource_id,r.number,r.room_type,r.capacity,displayMoney(r.base_rate),r.status]));
    $("teacherMessage").textContent=`${rows.length} habitaciones añadidas a la tabla rooms. Una fuera de servicio en el CSV no se ofrece para reservar.`;
  }));
  $("teacherScenariosBtn").addEventListener("click",e=>perform(e.currentTarget,async()=>{
    const rows=await request("/staff/demo-data/scenarios");if(state.page!=="teacherdata")return;
    makeTable(result,["Operación","Huésped","Líneas","Importe ilustrativo","Precondiciones ilustrativas","Detalle"],rows.map(r=>[r.operation_id,r.guest_name,r.line_count,displayMoney(r.example_total_mxn),r.processability_example?"Sí":"No",{label:"Ver líneas",action:async()=>{
      try{const s=await request(`/staff/demo-data/scenarios/${encodeURIComponent(r.operation_id)}`);
        const h=document.createElement("h3");h.textContent=`Detalle ${r.operation_id}`;
        const p=document.createElement("p");p.textContent=s.date_note;
        detail.replaceChildren(h,p);const t=document.createElement("div");detail.append(t);
        makeTable(t,["Recurso","Habitación","Cantidad","Precio","Subtotal"],s.lines.map(x=>[x.source_resource_id,x.room_number,x.quantity,displayMoney(x.unit_price_mxn),displayMoney(x.line_total_mxn)]));
      }catch(err){toast(err.message,"error");}
    }}]));
    $("teacherMessage").textContent="Los escenarios NO son reservas del hotel. Debes seleccionar fechas en Reservaciones para crear una estancia real.";
  }));
  $("teacherCasesBtn").addEventListener("click",e=>perform(e.currentTarget,async()=>{
    const rows=await request("/staff/demo-data/test-cases");if(state.page!=="teacherdata")return;
    makeTable(result,["Caso","Operación","Tipo","Regla ilustrativa","Resultado del alumno"],rows.map(r=>[r.caso_id,r.operacion_id,r.tipo_prueba,r.regla_a_verificar,r.resultado_alumno]));
    $("teacherMessage").textContent="Pendiente significa no ejecutado: importación no equivale a evaluación automática.";
  }));
  $("teacherTransitionsBtn").addEventListener("click",e=>perform(e.currentTarget,async()=>{
    const rows=await request("/staff/demo-data/transitions");if(state.page!=="teacherdata")return;
    makeTable(result,["Caso","Operación","Acción propuesta","Estado inicial","Resultado"],rows.map(r=>[r.caso_id,r.operacion_id,r.accion_sugerida,r.estado_inicial,r.resultado_alumno]));
    $("teacherMessage").textContent="Las transiciones se muestran como escenarios de prueba; no se aplican automáticamente a reservaciones.";
  }));
  $("teacherGuestsBtn").click();
}

start();
