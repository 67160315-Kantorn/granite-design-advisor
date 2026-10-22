/* ==========================================================
   product-detail.js — หน้าต่าง "รายละเอียดหิน" (กดที่รูป / ชื่อ / ปุ่ม "รายละเอียด" บนการ์ด)

   ปลั๊กอินแยก: ใช้ข้อมูลจาก GRANITE_CATALOG ใน app.js (มี image, desc, rating, url ครบแล้ว)
   เปิดผ่าน window.openStoneDetail(id) ที่การ์ดในแคตตาล็อกเรียกใช้
   ========================================================== */
(function () {
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  const RATING_LABELS = [
    ["price", "คุ้มราคา"], ["durability", "ความทนทาน"], ["maintenance", "ดูแลรักษาง่าย"],
    ["modern", "Modern"], ["luxury", "Luxury"],
  ];

  const style = document.createElement("style");
  style.textContent = `
    .gda-pd-overlay{position:fixed; inset:0; background:rgba(0,0,0,0.7); z-index:1000;
      display:none; align-items:center; justify-content:center;}
    .gda-pd-overlay.open{display:flex;}
    .gda-pd-modal{background:var(--stone-charcoal,#211d17); border:1px solid var(--rule,#444);
      width:880px; max-width:94vw; max-height:90vh; overflow-y:auto; position:relative;
      color:var(--marble-white,#eee); display:grid; grid-template-columns:1fr 1fr;}
    .gda-pd-img{min-height:340px; background-size:cover; background-position:center; background-color:#111;}
    .gda-pd-body{padding:1.8rem;}
    .gda-pd-close{position:absolute; top:0.6rem; right:0.9rem; background:rgba(0,0,0,0.45); border:none;
      color:#fff; font-size:1.4rem; cursor:pointer; line-height:1; width:34px; height:34px; border-radius:50%;}
    .gda-pd-body h3{font-family:'Noto Serif Thai',serif; font-size:1.5rem; margin:0.5rem 0 0.8rem;}
    .gda-pd-desc{color:var(--stone-gray,#998); font-size:0.88rem; line-height:1.7; margin-bottom:1rem;}
    .gda-pd-rate{display:grid; grid-template-columns:120px 1fr; gap:0.3rem 0.8rem; font-size:0.82rem;
      color:var(--marble-white-dim,#ccc); margin-bottom:1rem; align-items:center;}
    .gda-pd-price{font-family:'IBM Plex Mono',monospace; font-size:1.2rem; margin:0.4rem 0 1rem;}
    .gda-pd-actions{display:flex; gap:0.6rem; flex-wrap:wrap;}
    .gda-pd-actions a{text-decoration:none; display:inline-block;}
    @media (max-width:720px){ .gda-pd-modal{grid-template-columns:1fr;} .gda-pd-img{min-height:220px;} }
  `;
  document.head.appendChild(style);

  const overlay = document.createElement("div");
  overlay.className = "gda-pd-overlay";
  overlay.innerHTML = `<div class="gda-pd-modal" role="dialog" aria-modal="true">
    <button type="button" class="gda-pd-close" id="gda-pd-close" aria-label="ปิด">&times;</button>
    <div class="gda-pd-img" id="gda-pd-img"></div>
    <div class="gda-pd-body" id="gda-pd-body"></div>
  </div>`;
  document.body.appendChild(overlay);

  function close() { overlay.classList.remove("open"); }
  document.getElementById("gda-pd-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });

  window.openStoneDetail = function (id) {
    if (typeof GRANITE_CATALOG === "undefined") return;
    const s = GRANITE_CATALOG.find((x) => String(x.id) === String(id));
    if (!s) return;

    const colorLabel = (typeof COLOR_LABELS !== "undefined" && COLOR_LABELS[s.color]) || s.color || "";
    const areas = (s.areas || []).map((a) => (typeof AREA_LABELS !== "undefined" && AREA_LABELS[a]) || a).join(", ");
    const stars = (n) => (typeof renderStars === "function" ? renderStars(n || 0) : "★".repeat(n || 0));

    document.getElementById("gda-pd-img").style.backgroundImage = s.image ? `url('${String(s.image).replace(/'/g, "%27")}')` : "none";
    document.getElementById("gda-pd-body").innerHTML = `
      <div>
        <span class="stone-tag">${esc(colorLabel)}</span>
        <span class="stone-tag">${s.material === "marble" ? "หินอ่อน" : "หินแกรนิต"}</span>
        ${(s.styles || []).map((st) => `<span class="stone-tag">${esc(st)}</span>`).join("")}
      </div>
      <h3>${esc(s.name)}</h3>
      <p class="gda-pd-desc">${esc(s.desc)}</p>
      <div class="gda-pd-rate">
        ${RATING_LABELS.map(([k, t]) => `<span>${t}</span><span>${stars((s.rating || {})[k])}</span>`).join("")}
      </div>
      <div class="stone-meta"><b>เหมาะกับ:</b> ${esc(areas)}</div>
      <div class="stone-meta"><b>การใช้งาน:</b> ${s.indoor === "indoor" ? "ภายในอาคาร" : "ภายใน/ภายนอกอาคาร"}</div>
      <div class="gda-pd-price">฿${Number(s.price).toLocaleString()} / ตร.ม.</div>
      <div class="gda-pd-actions">
        <button type="button" class="btn-small" id="gda-pd-price-btn">คำนวณราคา</button>
        <button type="button" class="btn-small" id="gda-pd-project-btn">+ โปรเจกต์</button>
        <button type="button" class="btn-small" id="gda-pd-fav-btn"></button>
        ${/^https?:\/\//.test(s.url || "") ? `<a class="btn-small" href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">ดูสินค้าจริง ↗</a>` : ""}
      </div>`;

    document.getElementById("gda-pd-price-btn").addEventListener("click", () => {
      close();
      if (typeof window.goPriceWithStone === "function") window.goPriceWithStone(s.id);
    });
    document.getElementById("gda-pd-project-btn").addEventListener("click", () => {
      if (typeof window.addToActiveProject === "function") {
        window.addToActiveProject("granite", s.name, { stoneId: s.id, price: s.price });
      }
    });
    const favBtn = document.getElementById("gda-pd-fav-btn");
    const paintFav = () => {
      const on = !!(window.GDA_FAV && window.GDA_FAV.has(s.id));
      favBtn.textContent = on ? "♥ ในรายการโปรด" : "♡ เพิ่มรายการโปรด";
      favBtn.style.color = on ? "var(--vein-gold-bright,#d9ad5c)" : "";
    };
    paintFav();
    favBtn.addEventListener("click", async () => {
      if (window.GDA_FAV) { await window.GDA_FAV.toggle(s.id); paintFav(); }
    });
    overlay.classList.add("open");
  };
})();
