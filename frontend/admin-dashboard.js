/* ==========================================================
   admin-dashboard.js — แดชบอร์ดสถิติสำหรับแอดมิน (ปุ่ม "แดชบอร์ด" ข้างปุ่มออกจากระบบ)

   ดึงข้อมูลจาก GET /admin/stats (backend ตรวจ role = admin อีกชั้น ปุ่มนี้แค่ซ่อน/แสดง UI)
   แสดง: จำนวนสมาชิก/โปรเจกต์/แชต/หิน, สมัครใหม่ 7 วัน, หินยอดนิยม 3 มุมมอง, สัดส่วนแคตตาล็อก
   ========================================================== */
(function () {
  const _API_BASE = (typeof API_BASE !== "undefined") ? API_BASE : "";
  const KIND_LABELS = { granite: "หินที่บันทึก", price: "ผลคำนวณราคา", advisor: "ผล AI Advisor", inspiration: "แรงบันดาลใจ" };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function fmt(n) { return Number(n || 0).toLocaleString(); }

  const style = document.createElement("style");
  style.textContent = `
    .gda-ad-overlay{position:fixed; inset:0; background:rgba(0,0,0,0.65); z-index:1000; display:none; align-items:center; justify-content:center;}
    .gda-ad-overlay.open{display:flex;}
    .gda-ad-modal{background:var(--stone-charcoal,#211d17); border:1px solid var(--rule,#444); width:960px; max-width:95vw;
      max-height:90vh; overflow-y:auto; padding:1.8rem; position:relative; color:var(--marble-white,#eee);}
    .gda-ad-modal h3{font-family:'Noto Serif Thai',serif; font-size:1.25rem; margin-bottom:1.2rem;}
    .gda-ad-modal h4{font-size:0.8rem; letter-spacing:0.06em; color:var(--stone-gray,#998); margin:1.4rem 0 0.6rem; font-weight:600;}
    .gda-ad-close{position:absolute; top:0.8rem; right:1rem; background:none; border:none; color:var(--stone-gray,#998); font-size:1.3rem; cursor:pointer;}
    .gda-ad-tiles{display:grid; grid-template-columns:repeat(4,1fr); gap:0.8rem;}
    .gda-ad-tile{background:var(--stone-charcoal-2,#2a251d); border:1px solid var(--rule,#444); padding:0.9rem 1rem;}
    .gda-ad-tile b{display:block; font-family:'IBM Plex Mono',monospace; font-size:1.7rem; color:var(--vein-gold-bright,#d9ad5c); line-height:1.2;}
    .gda-ad-tile span{font-size:0.78rem; color:var(--stone-gray,#998);}
    .gda-ad-cols{display:grid; grid-template-columns:repeat(3,1fr); gap:1.2rem;}
    .gda-ad-bars{display:flex; align-items:flex-end; gap:0.6rem; height:120px; padding-top:0.5rem;}
    .gda-ad-bar{flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; font-size:0.72rem; color:var(--stone-gray,#998);}
    .gda-ad-bar i{display:block; width:100%; background:var(--vein-gold-bright,#d9ad5c); min-height:2px;}
    .gda-ad-bar em{font-style:normal; color:var(--marble-white,#eee); font-family:'IBM Plex Mono',monospace; margin-bottom:2px;}
    .gda-ad-rank{list-style:none; padding:0; margin:0; font-size:0.85rem;}
    .gda-ad-rank li{display:flex; align-items:center; gap:0.6rem; padding:0.35rem 0; border-bottom:1px solid var(--rule,#333);}
    .gda-ad-rank .n{flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
    .gda-ad-rank .c{font-family:'IBM Plex Mono',monospace; color:var(--vein-gold-bright,#d9ad5c);}
    .gda-ad-empty{color:var(--stone-gray,#998); font-size:0.82rem;}
    .gda-ad-chips span{display:inline-block; border:1px solid var(--rule,#444); padding:0.2rem 0.6rem; margin:0 0.4rem 0.4rem 0; font-size:0.8rem;}
    @media (max-width:760px){ .gda-ad-tiles{grid-template-columns:repeat(2,1fr);} .gda-ad-cols{grid-template-columns:1fr;} }
  `;
  document.head.appendChild(style);

  const overlay = document.createElement("div");
  overlay.className = "gda-ad-overlay";
  overlay.innerHTML = `<div class="gda-ad-modal">
    <button type="button" class="gda-ad-close" id="gda-ad-close" aria-label="ปิด">&times;</button>
    <h3>📊 แดชบอร์ดแอดมิน</h3>
    <div id="gda-ad-body">กำลังโหลด...</div>
  </div>`;
  document.body.appendChild(overlay);
  const bodyEl = overlay.querySelector("#gda-ad-body");
  const close = () => overlay.classList.remove("open");
  overlay.querySelector("#gda-ad-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });

  async function apiGet(path) {
    const res = await fetch(_API_BASE + path, { headers: { "Authorization": "Bearer " + window.GDA_AUTH.getToken() } });
    let body = null;
    try { body = await res.json(); } catch (e) {}
    if (!res.ok) throw new Error((body && body.detail) || `เกิดข้อผิดพลาด (${res.status})`);
    return body;
  }

  function rank(title, list) {
    return `<div><h4>${title}</h4>${list && list.length
      ? `<ol class="gda-ad-rank">${list.map((r) => `<li><span class="n">${esc(r.name)}</span><span class="c">${fmt(r.count)}</span></li>`).join("")}</ol>`
      : `<p class="gda-ad-empty">ยังไม่มีข้อมูล</p>`}</div>`;
  }

  function chips(obj, labels) {
    const entries = Object.entries(obj || {}).sort((a, b) => b[1] - a[1]);
    return entries.length
      ? `<div class="gda-ad-chips">${entries.map(([k, v]) => `<span>${esc((labels && labels[k]) || k)} · ${fmt(v)}</span>`).join("")}</div>`
      : `<p class="gda-ad-empty">ไม่มีข้อมูล</p>`;
  }

  function render(d) {
    const colorLabels = (typeof COLOR_LABELS !== "undefined") ? COLOR_LABELS : {};
    const maxSignup = Math.max(1, ...d.users.signups_7d.map((x) => x.count));
    const itemsTotal = Object.values(d.projects.items_by_kind).reduce((a, b) => a + b, 0);
    bodyEl.innerHTML = `
      <div class="gda-ad-tiles">
        <div class="gda-ad-tile"><b>${fmt(d.users.total)}</b><span>สมาชิกทั้งหมด (แอดมิน ${fmt(d.users.admins)})</span></div>
        <div class="gda-ad-tile"><b>${fmt(d.users.new_7d)}</b><span>สมัครใหม่ 7 วันล่าสุด</span></div>
        <div class="gda-ad-tile"><b>${fmt(d.projects.total)}</b><span>โปรเจกต์ (${fmt(itemsTotal)} รายการ)</span></div>
        <div class="gda-ad-tile"><b>${fmt(d.catalog.total)}</b><span>หินในแคตตาล็อก (เฉลี่ย ฿${fmt(d.catalog.avg_price)})</span></div>
        <div class="gda-ad-tile"><b>${fmt(d.chat.questions)}</b><span>คำถามถึง AI (7 วัน: ${fmt(d.chat.questions_7d)})</span></div>
        <div class="gda-ad-tile"><b>${fmt(d.chat.users)}</b><span>สมาชิกที่เคยคุยกับ AI</span></div>
        <div class="gda-ad-tile"><b>${fmt(d.favorites_total)}</b><span>รายการโปรดทั้งหมด</span></div>
        <div class="gda-ad-tile"><b>${fmt(d.chat.messages)}</b><span>ข้อความแชทที่เก็บไว้</span></div>
      </div>

      <h4>สมาชิกสมัครใหม่ รายวัน (7 วัน)</h4>
      <div class="gda-ad-bars">
        ${d.users.signups_7d.map((x) => `<div class="gda-ad-bar" title="${esc(x.date)}">
          <em>${fmt(x.count)}</em><i style="height:${Math.round((x.count / maxSignup) * 80)}px"></i>${esc(x.date.slice(5))}</div>`).join("")}
      </div>

      <div class="gda-ad-cols">
        ${rank("♥ หินที่ถูกกดโปรดมากสุด", d.top.favorited)}
        ${rank("🤖 หินที่ AI แนะนำบ่อยสุด", d.top.ai_recommended)}
        ${rank("📁 หินที่ถูกบันทึกลงโปรเจกต์มากสุด", d.top.in_projects)}
      </div>

      <div class="gda-ad-cols">
        <div><h4>แคตตาล็อกแยกตามประเภท</h4>${chips(d.catalog.by_material, { granite: "หินแกรนิต", marble: "หินอ่อน" })}</div>
        <div><h4>แยกตามสี</h4>${chips(d.catalog.by_color, colorLabels)}</div>
        <div><h4>รายการในโปรเจกต์แยกชนิด</h4>${chips(d.projects.items_by_kind, KIND_LABELS)}</div>
      </div>`;
  }

  async function open() {
    overlay.classList.add("open");
    bodyEl.textContent = "กำลังโหลด...";
    try { render(await apiGet("/admin/stats")); }
    catch (err) { bodyEl.innerHTML = `<p class="gda-ad-empty">โหลดสถิติไม่สำเร็จ: ${esc(err.message)}</p>`; }
  }

  // ---------- ปุ่มใน widget (เฉพาะแอดมิน) ----------
  let checkedToken = null, isAdmin = false;
  async function injectButton() {
    if (!window.GDA_AUTH || !window.GDA_AUTH.isLoggedIn()) return;
    const logoutBtn = document.getElementById("gda-logout-btn");
    if (!logoutBtn || document.getElementById("gda-admin-dash-btn")) return;
    const token = window.GDA_AUTH.getToken();
    if (checkedToken !== token) {
      checkedToken = token; isAdmin = false;
      try { isAdmin = (await apiGet("/me")).role === "admin"; } catch (e) {}
    }
    if (!isAdmin) return;
    const lb = document.getElementById("gda-logout-btn");
    if (!lb || document.getElementById("gda-admin-dash-btn")) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "gda-admin-dash-btn";
    btn.className = "gda-auth-btn";
    btn.textContent = "แดชบอร์ด";
    btn.addEventListener("click", open);
    lb.parentNode.insertBefore(btn, lb);
  }
  const widget = document.getElementById("gda-auth-widget");
  if (widget) new MutationObserver(injectButton).observe(widget, { childList: true, subtree: true });
  injectButton();
})();
