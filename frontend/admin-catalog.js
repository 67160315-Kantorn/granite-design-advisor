/* ==========================================================
   admin-catalog.js — หน้า "จัดการหิน" สำหรับแอดมิน (เพิ่ม / แก้ไข / ลบหิน)

   ปลั๊กอินแยก เหมือน profile.js: คอยดู widget ของ auth.js แล้วแปะปุ่ม "จัดการหิน"
   ให้เฉพาะบัญชีที่ role = admin (เช็คจาก GET /me) — ฝั่ง backend ตรวจสิทธิ์ซ้ำอีกชั้น
   ด้วย require_admin เสมอ ปุ่มนี้แค่ซ่อน/แสดง UI ไม่ใช่ตัวป้องกันความปลอดภัย

   วิธีใช้: <script src="admin-catalog.js"></script> ต่อท้าย catalog-api.js ใน index.html
   ========================================================== */
(function () {
  const _API_BASE = (typeof API_BASE !== "undefined") ? API_BASE : "";

  const COLOR_OPTIONS = ["black", "white", "grey", "brown", "red", "blue", "green", "gold", "beige"];
  const STYLE_OPTIONS = ["Luxury", "Modern", "Minimal", "Classic"];
  const AREA_OPTIONS = [
    ["kitchen", "ห้องครัว"], ["bathroom", "ห้องน้ำ"], ["livingroom", "Living Room"], ["counter", "Counter"],
    ["table", "โต๊ะ"], ["wall", "ผนัง"], ["floor", "พื้น"], ["outdoor", "Outdoor"],
  ];
  const RATING_OPTIONS = [
    ["price", "คุ้มราคา"], ["durability", "ความทนทาน"], ["maintenance", "ดูแลรักษาง่าย"],
    ["modern", "Modern"], ["luxury", "Luxury"],
  ];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ---------- CSS ----------
  const style = document.createElement("style");
  style.textContent = `
    .gda-ac-overlay{position:fixed; inset:0; background:rgba(0,0,0,0.65); z-index:1000;
      display:none; align-items:center; justify-content:center;}
    .gda-ac-overlay.open{display:flex;}
    .gda-ac-modal{background:var(--stone-charcoal,#211d17); border:1px solid var(--rule,#444);
      width:760px; max-width:94vw; max-height:88vh; overflow-y:auto; padding:1.8rem; position:relative;
      color:var(--marble-white,#eee);}
    .gda-ac-modal h3{font-family:'Noto Serif Thai',serif; margin-bottom:1rem; font-size:1.2rem;}
    .gda-ac-close{position:absolute; top:0.8rem; right:1rem; background:none; border:none;
      color:var(--stone-gray,#998); font-size:1.3rem; cursor:pointer; line-height:1;}
    .gda-ac-msg-err{color:var(--warn,#d99a7c); font-size:0.82rem; min-height:1.2em; margin:0.4rem 0;}
    .gda-ac-msg-ok{color:#9ed99a; font-size:0.82rem; min-height:1.2em; margin:0.4rem 0;}
    .gda-ac-toolbar{display:flex; justify-content:space-between; align-items:center; margin-bottom:0.8rem;}
    .gda-ac-btn{background:none; border:1px solid var(--rule,#444); color:var(--marble-white-dim,#ccc);
      font-family:inherit; font-size:0.82rem; padding:0.45rem 0.9rem; cursor:pointer;}
    .gda-ac-btn:hover{border-color:var(--vein-gold-bright,#d9ad5c); color:var(--vein-gold-bright,#d9ad5c);}
    .gda-ac-btn.primary{background:var(--vein-gold-bright,#d9ad5c); color:#171207; border-color:transparent; font-weight:600;}
    .gda-ac-btn.danger{border-color:var(--warn,#d99a7c); color:var(--warn,#d99a7c);}
    .gda-ac-btn.danger:hover{background:var(--warn,#d99a7c); color:#171207;}
    .gda-ac-list{list-style:none; padding:0; margin:0;}
    .gda-ac-list li{display:flex; align-items:center; gap:0.8rem; padding:0.55rem 0; border-bottom:1px solid var(--rule,#333);}
    .gda-ac-list img{width:48px; height:36px; object-fit:cover; background:#111; flex:none;}
    .gda-ac-list .name{flex:1; font-weight:600; font-size:0.9rem;}
    .gda-ac-list .meta{color:var(--stone-gray,#998); font-size:0.8rem; width:110px; text-align:right;}
    .gda-ac-form{display:grid; grid-template-columns:1fr 1fr; gap:0.2rem 1rem;}
    .gda-ac-form .full{grid-column:1 / -1;}
    .gda-ac-form label{font-size:0.78rem; color:var(--stone-gray,#998); display:block; margin:0.7rem 0 0.25rem;}
    .gda-ac-form input[type=text], .gda-ac-form input[type=number], .gda-ac-form select, .gda-ac-form textarea{
      width:100%; background:var(--stone-black,#111); border:1px solid var(--rule,#444);
      color:var(--marble-white,#eee); font-family:inherit; font-size:0.88rem; padding:0.55rem 0.7rem;}
    .gda-ac-form textarea{min-height:90px; resize:vertical;}
    .gda-ac-checks{display:flex; flex-wrap:wrap; gap:0.3rem 1rem; font-size:0.85rem;}
    .gda-ac-checks label{display:inline-flex; align-items:center; gap:0.35rem; margin:0; color:var(--marble-white-dim,#ccc);}
    .gda-ac-ratings{display:grid; grid-template-columns:repeat(5,1fr); gap:0.6rem;}
    .gda-ac-actions{display:flex; justify-content:flex-end; gap:0.6rem; margin-top:1.4rem;}
    @media (max-width:640px){ .gda-ac-form{grid-template-columns:1fr;} .gda-ac-ratings{grid-template-columns:repeat(2,1fr);} }
  `;
  document.head.appendChild(style);

  // ---------- โครง modal ----------
  const overlay = document.createElement("div");
  overlay.className = "gda-ac-overlay";
  overlay.innerHTML = `
    <div class="gda-ac-modal">
      <button type="button" class="gda-ac-close" id="gda-ac-close">&times;</button>
      <h3 id="gda-ac-title">จัดการหิน</h3>
      <div class="gda-ac-msg-err" id="gda-ac-err"></div>
      <div class="gda-ac-msg-ok" id="gda-ac-ok"></div>
      <div id="gda-ac-body"></div>
    </div>`;
  document.body.appendChild(overlay);

  const $ = (id) => document.getElementById(id);
  $("gda-ac-close").addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });

  function openModal() { overlay.classList.add("open"); showList(); }
  function closeModal() { overlay.classList.remove("open"); }
  function setErr(m) { $("gda-ac-err").textContent = m || ""; }
  function setOk(m) { $("gda-ac-ok").textContent = m || ""; }

  async function apiRequest(path, options) {
    options = options || {};
    const token = (window.GDA_AUTH && window.GDA_AUTH.getToken()) || null;
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (token) headers["Authorization"] = "Bearer " + token;
    const res = await fetch(_API_BASE + path, Object.assign({}, options, { headers }));
    if (res.status === 204) return null;
    let body = null;
    try { body = await res.json(); } catch (e) {}
    if (!res.ok) {
      let msg = `เกิดข้อผิดพลาด (${res.status})`;
      if (body && typeof body.detail === "string") msg = body.detail;
      else if (body && Array.isArray(body.detail) && body.detail[0]) {
        msg = (body.detail[0].loc || []).slice(1).join(".") + ": " + body.detail[0].msg;
      }
      throw new Error(msg);
    }
    return body;
  }

  // ---------- รายการหิน ----------
  async function showList() {
    setErr(""); 
    $("gda-ac-title").textContent = "จัดการหิน";
    $("gda-ac-body").innerHTML = `<p style="color:var(--stone-gray,#998)">กำลังโหลด...</p>`;
    let items;
    try {
      items = await apiRequest("/granite-products");
    } catch (err) {
      $("gda-ac-body").innerHTML = "";
      return setErr("โหลดรายการไม่สำเร็จ: " + err.message);
    }
    $("gda-ac-body").innerHTML = `
      <div class="gda-ac-toolbar">
        <span style="font-size:0.85rem;color:var(--stone-gray,#998)">ทั้งหมด ${items.length} ชนิด</span>
        <button type="button" class="gda-ac-btn primary" id="gda-ac-add">+ เพิ่มหินใหม่</button>
      </div>
      <ul class="gda-ac-list">
        ${items.map((p) => `
          <li>
            ${p.image_url ? `<img src="${esc(p.image_url)}" alt="">` : `<img alt="">`}
            <span class="name">${esc(p.product_title)}</span>
            <span class="meta">฿${Number(p.product_price).toLocaleString()}/ตร.ม.</span>
            <button type="button" class="gda-ac-btn" data-edit="${p.id}">แก้ไข</button>
            <button type="button" class="gda-ac-btn danger" data-del="${p.id}" data-name="${esc(p.product_title)}">ลบ</button>
          </li>`).join("")}
      </ul>`;
    $("gda-ac-add").addEventListener("click", () => showForm(null));
    $("gda-ac-body").querySelectorAll("[data-edit]").forEach((btn) =>
      btn.addEventListener("click", () => showForm(items.find((p) => String(p.id) === btn.dataset.edit))));
    $("gda-ac-body").querySelectorAll("[data-del]").forEach((btn) =>
      btn.addEventListener("click", () => deleteProduct(btn.dataset.del, btn.dataset.name)));
  }

  async function deleteProduct(id, name) {
    if (!confirm(`ลบหิน "${name}" ออกจากแคตตาล็อก? ย้อนกลับไม่ได้`)) return;
    setErr(""); setOk("");
    try {
      await apiRequest(`/granite-products/${id}`, { method: "DELETE" });
      setOk(`ลบ "${name}" แล้ว`);
      refreshCatalog();
      showList();
    } catch (err) {
      setErr("ลบไม่สำเร็จ: " + err.message);
    }
  }

  // ---------- ฟอร์มเพิ่ม/แก้ไข ----------
  function showForm(p) {
    setErr(""); setOk("");
    const isEdit = !!p;
    p = p || { styles: [], areas: [], rating: {}, material: "granite", indoor: "indoor", product_price: "" };
    const rating = p.rating || {};
    $("gda-ac-title").textContent = isEdit ? `แก้ไขหิน: ${p.product_title}` : "เพิ่มหินใหม่";
    $("gda-ac-body").innerHTML = `
      <form id="gda-ac-form" class="gda-ac-form" autocomplete="off">
        <div class="full"><label>ชื่อหิน *</label>
          <input type="text" name="product_title" required maxlength="255" value="${esc(p.product_title || "")}"></div>
        <div><label>ราคา (บาท/ตร.ม.) *</label>
          <input type="number" name="product_price" required min="0" step="1" value="${esc(p.product_price)}"></div>
        <div><label>วัสดุ</label>
          <select name="material">
            <option value="granite" ${p.material === "granite" ? "selected" : ""}>หินแกรนิต</option>
            <option value="marble" ${p.material === "marble" ? "selected" : ""}>หินอ่อน</option>
          </select></div>
        <div><label>สี</label>
          <input type="text" name="color" list="gda-ac-colors" value="${esc(p.color || "")}">
          <datalist id="gda-ac-colors">${COLOR_OPTIONS.map((c) => `<option value="${c}">`).join("")}</datalist></div>
        <div><label>การใช้งาน</label>
          <select name="indoor">
            ${["indoor", "outdoor", "both"].map((v) => `<option value="${v}" ${p.indoor === v ? "selected" : ""}>${v}</option>`).join("")}
          </select></div>
        <div class="full"><label>รายละเอียด</label>
          <textarea name="product_description">${esc(p.product_description || "")}</textarea></div>
        <div class="full"><label>ลิงก์รูปภาพ</label>
          <input type="text" name="image_url" maxlength="500" value="${esc(p.image_url || "")}"></div>
        <div class="full"><label>ลิงก์หน้าสินค้า</label>
          <input type="text" name="product_url" maxlength="500" value="${esc(p.product_url || "")}"></div>
        <div class="full"><label>สไตล์</label>
          <div class="gda-ac-checks">${STYLE_OPTIONS.map((s) => `
            <label><input type="checkbox" name="styles" value="${s}" ${(p.styles || []).includes(s) ? "checked" : ""}> ${s}</label>`).join("")}</div></div>
        <div class="full"><label>เหมาะกับพื้นที่</label>
          <div class="gda-ac-checks">${AREA_OPTIONS.map(([v, t]) => `
            <label><input type="checkbox" name="areas" value="${v}" ${(p.areas || []).includes(v) ? "checked" : ""}> ${t}</label>`).join("")}</div></div>
        <div class="full"><label>คะแนน (1-5)</label>
          <div class="gda-ac-ratings">${RATING_OPTIONS.map(([k, t]) => `
            <div><span style="font-size:0.75rem;color:var(--stone-gray,#998)">${t}</span>
            <input type="number" name="rating_${k}" min="1" max="5" step="1" value="${esc(rating[k] || 3)}"></div>`).join("")}</div></div>
        <div class="full gda-ac-actions">
          <button type="button" class="gda-ac-btn" id="gda-ac-cancel">ยกเลิก</button>
          <button type="submit" class="gda-ac-btn primary">${isEdit ? "บันทึกการแก้ไข" : "เพิ่มหิน"}</button>
        </div>
      </form>`;
    $("gda-ac-cancel").addEventListener("click", showList);
    $("gda-ac-form").addEventListener("submit", (e) => { e.preventDefault(); saveProduct(isEdit ? p.id : null, e.target); });
  }

  async function saveProduct(id, form) {
    setErr(""); setOk("");
    const fd = new FormData(form);
    const rating = {};
    RATING_OPTIONS.forEach(([k]) => { rating[k] = parseInt(fd.get("rating_" + k), 10) || 3; });
    const payload = {
      product_title: (fd.get("product_title") || "").trim(),
      product_price: parseFloat(fd.get("product_price")),
      product_description: fd.get("product_description") || null,
      image_url: (fd.get("image_url") || "").trim() || null,
      product_url: (fd.get("product_url") || "").trim() || null,
      color: (fd.get("color") || "").trim().toLowerCase() || null,
      material: fd.get("material"),
      indoor: fd.get("indoor"),
      styles: fd.getAll("styles"),
      areas: fd.getAll("areas"),
      rating,
    };
    try {
      if (id) await apiRequest(`/granite-products/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      else await apiRequest("/granite-products", { method: "POST", body: JSON.stringify(payload) });
      refreshCatalog();
      await showList();
      setOk(id ? "บันทึกการแก้ไขแล้ว" : "เพิ่มหินใหม่แล้ว");
    } catch (err) {
      setErr("บันทึกไม่สำเร็จ: " + err.message);
    }
  }

  function refreshCatalog() {
    if (typeof window.GDA_CATALOG_RELOAD === "function") window.GDA_CATALOG_RELOAD();
  }

  // ---------- ปุ่ม "จัดการหิน" ใน widget (เฉพาะแอดมิน) ----------
  let checkedToken = null;
  let isAdmin = false;

  async function injectButton() {
    if (!window.GDA_AUTH || !window.GDA_AUTH.isLoggedIn()) return;
    if (!document.getElementById("gda-logout-btn")) return;
    if (document.getElementById("gda-admin-catalog-btn")) return;

    const token = window.GDA_AUTH.getToken();
    if (checkedToken !== token) {
      checkedToken = token;
      isAdmin = false;
      try { isAdmin = (await apiRequest("/me")).role === "admin"; } catch (e) {}
    }
    if (!isAdmin) return;

    const logoutBtn = document.getElementById("gda-logout-btn");
    if (!logoutBtn || document.getElementById("gda-admin-catalog-btn")) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "gda-admin-catalog-btn";
    btn.className = "gda-auth-btn";
    btn.textContent = "จัดการหิน";
    btn.addEventListener("click", openModal);
    logoutBtn.parentNode.insertBefore(btn, logoutBtn);
  }

  const widget = document.getElementById("gda-auth-widget");
  if (widget) new MutationObserver(injectButton).observe(widget, { childList: true, subtree: true });
  injectButton();
})();
