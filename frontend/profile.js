/* ==========================================================
   profile.js — หน้า "โปรไฟล์ของฉัน" และ "รายชื่อสมาชิก" สำหรับ Granite Design Advisor

   ไฟล์นี้เป็นปลั๊กอินแยก ไม่ต้องแก้ index.html หรือ app.js เลย — จะคอยสังเกต widget
   ที่ auth.js สร้างไว้ (มุมขวาบน) แล้วแปะปุ่ม "โปรไฟล์" / "สมาชิกทั้งหมด" เพิ่มเข้าไปเอง
   ทุกครั้งที่สถานะ login เปลี่ยน (ใช้ MutationObserver เฝ้าดู ไม่ต้องแก้ auth.js เลยสักบรรทัด)

   วิธีใช้: เพิ่ม <script src="profile.js"></script> ต่อท้าย <script src="auth.js"></script>
   ใน index.html (ต้องโหลดหลัง auth.js เสมอ เพราะใช้ window.GDA_AUTH)
   ========================================================== */
(function () {
  const API_BASE = (typeof window.API_BASE !== "undefined") ? window.API_BASE : "";
  // หมายเหตุเดียวกับไฟล์ปลั๊กอินอื่นๆ ในโปรเจกต์นี้: API_BASE ใน app.js ประกาศด้วย const
  // ที่ top-level ของ <script> tag ไม่กลายเป็น window.API_BASE อัตโนมัติ แต่เบราว์เซอร์แชร์
  // scope นี้ข้าม <script> tag ให้เอง เลยอ้างอิงตรงๆ ด้วยชื่อเปล่าได้
  const _API_BASE = (typeof API_BASE !== "undefined") ? API_BASE : "";

  // ---------- inject CSS (ใช้ CSS variable เดิมจาก style.css ให้สีตรงกันทั้งเว็บ) ----------
  const style = document.createElement("style");
  style.textContent = `
    .gda-profile-overlay{position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:1000;
      display:none; align-items:center; justify-content:center;}
    .gda-profile-overlay.open{display:flex;}
    .gda-profile-modal{background:var(--stone-charcoal,#211d17); border:1px solid var(--rule,#444);
      width:420px; max-width:92vw; max-height:85vh; overflow-y:auto; padding:1.8rem; position:relative;}
    .gda-profile-modal h3{font-family:'Noto Serif Thai',serif; color:var(--marble-white,#eee);
      margin-bottom:1.2rem; font-size:1.2rem;}
    .gda-profile-modal label{font-size:0.8rem; color:var(--stone-gray,#998); display:block; margin:0.8rem 0 0.3rem;}
    .gda-profile-modal input{width:100%; background:var(--stone-black,#111); border:1px solid var(--rule,#444);
      color:var(--marble-white,#eee); font-family:inherit; font-size:0.9rem; padding:0.65rem 0.8rem;}
    .gda-profile-modal input:disabled{opacity:0.5;}
    .gda-profile-modal .gda-error{color:var(--warn,#d99a7c); font-size:0.82rem; margin-top:0.8rem; min-height:1.2em;}
    .gda-profile-modal .gda-success{color:#9ed99a; font-size:0.82rem; margin-top:0.8rem; min-height:1.2em;}
    .gda-profile-modal .gda-actions{display:flex; justify-content:space-between; align-items:center; margin-top:1.4rem;}
    .gda-profile-modal-close{position:absolute; top:0.8rem; right:1rem; background:none; border:none;
      color:var(--stone-gray,#998); font-size:1.3rem; cursor:pointer; line-height:1;}
    .gda-danger-zone{margin-top:2rem; padding-top:1.2rem; border-top:1px dashed var(--warn,#d99a7c);}
    .gda-danger-zone p{font-size:0.78rem; color:var(--stone-gray,#998); margin-bottom:0.6rem;}
    .gda-btn-danger{background:none; border:1px solid var(--warn,#d99a7c); color:var(--warn,#d99a7c);
      font-family:inherit; font-size:0.8rem; padding:0.5rem 1rem; cursor:pointer;}
    .gda-btn-danger:hover{background:var(--warn,#d99a7c); color:#171207;}

    .gda-member-list{list-style:none; padding:0; margin:0.6rem 0;}
    .gda-member-list li{padding:0.6rem 0; border-bottom:1px solid var(--rule,#333); font-size:0.88rem;
      color:var(--marble-white,#eee); display:flex; justify-content:space-between;}
    .gda-member-list .uname{font-weight:600;}
    .gda-member-list .fname{color:var(--stone-gray,#998); font-size:0.8rem;}
    .gda-pagination{display:flex; justify-content:space-between; align-items:center; margin-top:1rem; font-size:0.82rem;}
    .gda-pagination button{background:none; border:1px solid var(--rule,#444); color:var(--marble-white-dim,#ccc);
      font-family:inherit; padding:0.4rem 0.8rem; cursor:pointer;}
    .gda-pagination button:disabled{opacity:0.35; cursor:not-allowed;}
  `;
  document.head.appendChild(style);

  // ============================================================
  // Profile modal
  // ============================================================
  const profileOverlay = document.createElement("div");
  profileOverlay.className = "gda-profile-overlay";
  profileOverlay.id = "gda-profile-overlay";
  profileOverlay.innerHTML = `
    <div class="gda-profile-modal">
      <button type="button" class="gda-profile-modal-close" id="gda-profile-close">&times;</button>
      <h3>โปรไฟล์ของฉัน</h3>

      <form id="gda-profile-form">
        <label>Username (แก้ไขไม่ได้)</label>
        <input type="text" id="gda-profile-username" disabled>
        <label>Email</label>
        <input type="email" id="gda-profile-email" required>
        <label>ชื่อ-นามสกุล</label>
        <input type="text" id="gda-profile-fullname">
        <div class="gda-error" id="gda-profile-error"></div>
        <div class="gda-success" id="gda-profile-success"></div>
        <div class="gda-actions">
          <span></span>
          <button type="submit" class="gda-auth-btn primary">บันทึกการแก้ไข</button>
        </div>
      </form>

      <div class="gda-danger-zone">
        <p>⚠️ ลบบัญชีแล้วกู้คืนไม่ได้ โปรเจกต์และรายการทั้งหมดของคุณจะถูกลบไปด้วย</p>
        <button type="button" class="gda-btn-danger" id="gda-delete-account-btn">ลบบัญชีของฉัน</button>
      </div>
    </div>
  `;
  document.body.appendChild(profileOverlay);

  document.getElementById("gda-profile-close").addEventListener("click", closeProfileModal);
  profileOverlay.addEventListener("click", (e) => { if (e.target === profileOverlay) closeProfileModal(); });

  function openProfileModal() {
    profileOverlay.classList.add("open");
    loadProfile();
  }
  function closeProfileModal() {
    profileOverlay.classList.remove("open");
  }

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
      const msg = (body && body.detail) ? body.detail : `เกิดข้อผิดพลาด (${res.status})`;
      throw new Error(msg);
    }
    return body;
  }

  let currentProfileUser = null;

  async function loadProfile() {
    const errorEl = document.getElementById("gda-profile-error");
    const successEl = document.getElementById("gda-profile-success");
    errorEl.textContent = "";
    successEl.textContent = "";
    try {
      const me = await apiRequest("/me");
      currentProfileUser = me;
      document.getElementById("gda-profile-username").value = me.username;
      document.getElementById("gda-profile-email").value = me.email;
      document.getElementById("gda-profile-fullname").value = me.full_name || "";
    } catch (err) {
      errorEl.textContent = "โหลดข้อมูลไม่สำเร็จ: " + err.message;
    }
  }

  document.getElementById("gda-profile-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = document.getElementById("gda-profile-error");
    const successEl = document.getElementById("gda-profile-success");
    errorEl.textContent = "";
    successEl.textContent = "";
    if (!currentProfileUser) return;
    const email = document.getElementById("gda-profile-email").value.trim();
    const full_name = document.getElementById("gda-profile-fullname").value.trim() || null;
    try {
      const updated = await apiRequest(`/users/${currentProfileUser.id}`, {
        method: "PUT",
        body: JSON.stringify({ email, full_name }),
      });
      currentProfileUser = updated;
      successEl.textContent = "บันทึกสำเร็จ";
    } catch (err) {
      errorEl.textContent = "บันทึกไม่สำเร็จ: " + err.message;
    }
  });

  document.getElementById("gda-delete-account-btn").addEventListener("click", async () => {
    if (!currentProfileUser) return;
    if (!confirm("ยืนยันลบบัญชีของคุณ? การกระทำนี้ย้อนกลับไม่ได้")) return;
    if (!confirm("ยืนยันอีกครั้ง — ลบบัญชี \"" + currentProfileUser.username + "\" จริงหรือไม่?")) return;
    try {
      await apiRequest(`/users/${currentProfileUser.id}`, { method: "DELETE" });
      closeProfileModal();
      alert("ลบบัญชีสำเร็จ");
      if (window.GDA_AUTH) await window.GDA_AUTH.logout();
    } catch (err) {
      document.getElementById("gda-profile-error").textContent = "ลบบัญชีไม่สำเร็จ: " + err.message;
    }
  });

  // ============================================================
  // Member list modal
  // ============================================================
  const membersOverlay = document.createElement("div");
  membersOverlay.className = "gda-profile-overlay";
  membersOverlay.id = "gda-members-overlay";
  membersOverlay.innerHTML = `
    <div class="gda-profile-modal">
      <button type="button" class="gda-profile-modal-close" id="gda-members-close">&times;</button>
      <h3>สมาชิกทั้งหมด</h3>
      <div class="gda-error" id="gda-members-error"></div>
      <ul class="gda-member-list" id="gda-member-list"></ul>
      <div class="gda-pagination">
        <button type="button" id="gda-members-prev">← ก่อนหน้า</button>
        <span id="gda-members-page-label"></span>
        <button type="button" id="gda-members-next">ถัดไป →</button>
      </div>
    </div>
  `;
  document.body.appendChild(membersOverlay);

  document.getElementById("gda-members-close").addEventListener("click", closeMembersModal);
  membersOverlay.addEventListener("click", (e) => { if (e.target === membersOverlay) closeMembersModal(); });

  let membersPage = 1;
  const MEMBERS_PAGE_SIZE = 10;

  function openMembersModal() {
    membersOverlay.classList.add("open");
    membersPage = 1;
    loadMembers();
  }
  function closeMembersModal() {
    membersOverlay.classList.remove("open");
  }

  async function loadMembers() {
    const errorEl = document.getElementById("gda-members-error");
    const listEl = document.getElementById("gda-member-list");
    const pageLabel = document.getElementById("gda-members-page-label");
    const prevBtn = document.getElementById("gda-members-prev");
    const nextBtn = document.getElementById("gda-members-next");
    errorEl.textContent = "";
    try {
      const data = await apiRequest(`/users?page=${membersPage}&page_size=${MEMBERS_PAGE_SIZE}`);
      listEl.innerHTML = data.items.map((u) => `
        <li><span class="uname">${u.username}</span><span class="fname">${u.full_name || ""}</span></li>
      `).join("");
      const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
      pageLabel.textContent = `หน้า ${data.page} / ${totalPages} (ทั้งหมด ${data.total} คน)`;
      prevBtn.disabled = data.page <= 1;
      nextBtn.disabled = data.page >= totalPages;
    } catch (err) {
      errorEl.textContent = "โหลดรายชื่อไม่สำเร็จ: " + err.message;
      listEl.innerHTML = "";
    }
  }

  document.getElementById("gda-members-prev").addEventListener("click", () => {
    if (membersPage > 1) { membersPage--; loadMembers(); }
  });
  document.getElementById("gda-members-next").addEventListener("click", () => {
    membersPage++; loadMembers();
  });

  // ============================================================
  // ฝังปุ่ม "โปรไฟล์" / "สมาชิกทั้งหมด" เข้าไปใน auth widget ของ auth.js
  // ใช้ MutationObserver เฝ้าดู เพราะ auth.js re-render widget ทุกครั้งที่ login/logout
  // โดยไม่ต้องแก้โค้ดใน auth.js เลยแม้แต่บรรทัดเดียว
  // ============================================================
  function injectButtons() {
    if (!window.GDA_AUTH || !window.GDA_AUTH.isLoggedIn()) return;
    const logoutBtn = document.getElementById("gda-logout-btn");
    if (!logoutBtn) return; // widget ยังไม่ได้ render แบบ logged-in

    if (!document.getElementById("gda-profile-btn")) {
      const profileBtn = document.createElement("button");
      profileBtn.type = "button";
      profileBtn.id = "gda-profile-btn";
      profileBtn.className = "gda-auth-btn";
      profileBtn.textContent = "โปรไฟล์";
      profileBtn.addEventListener("click", openProfileModal);
      logoutBtn.parentNode.insertBefore(profileBtn, logoutBtn);
    }

    if (!document.getElementById("gda-members-btn")) {
      const membersBtn = document.createElement("button");
      membersBtn.type = "button";
      membersBtn.id = "gda-members-btn";
      membersBtn.className = "gda-auth-btn";
      membersBtn.textContent = "สมาชิกทั้งหมด";
      membersBtn.addEventListener("click", openMembersModal);
      logoutBtn.parentNode.insertBefore(membersBtn, logoutBtn);
    }
  }

  const widget = document.getElementById("gda-auth-widget");
  if (widget) {
    const observer = new MutationObserver(injectButtons);
    observer.observe(widget, { childList: true, subtree: true });
  }
  injectButtons(); // เผื่อโหลดมาตอนที่ widget เป็นสถานะ logged-in อยู่แล้ว (เช่น refresh หน้า)
})();
