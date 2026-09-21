/* ==========================================================
   auth.js — ระบบ Login/Register/Logout สำหรับ Granite Design Advisor

   ไฟล์นี้ตั้งใจให้เป็น "ปลั๊กอิน" แยกต่างหาก ไม่ต้องแก้ index.html หรือ app.js เลย —
   จะสร้าง UI (ปุ่ม login มุมขวาบน + หน้าต่าง login/register) ขึ้นมาเองด้วย JavaScript
   วิธีใช้: เพิ่ม <script src="auth.js"></script> ต่อท้าย <script src="app.js"></script>
   ใน index.html (ต้องมาหลัง app.js เสมอ เพราะจะอ้างอิงตัวแปร API_BASE จากไฟล์นั้น)
   ========================================================== */
(function () {
  // หมายเหตุสำคัญ: API_BASE ใน app.js ประกาศด้วย const ที่ top-level ของ <script> tag
  // ค่าแบบนี้ "ไม่" กลายเป็น window.API_BASE หรือ globalThis.API_BASE โดยอัตโนมัติ
  // (ต่างจาก var/function declaration) แต่เบราว์เซอร์แชร์ scope นี้ข้าม <script> tag ให้เอง
  // เลยต้องอ้างอิงด้วยชื่อตัวแปรเปล่าๆ (bare identifier) ถึงจะมองเห็นค่าจริงจาก app.js —
  // ใช้ typeof เช็คก่อนเสมอ เพราะอ้างอิงตัวแปรที่ไม่มีอยู่จริงตรงๆ จะทำให้ error ทันที
  // ตั้งชื่อตัวแปรของไฟล์นี้เป็น _API_BASE (ไม่ใช่ API_BASE) เพื่อไม่ให้ชื่อชนกับของ app.js
  const _API_BASE = (typeof API_BASE !== "undefined") ? API_BASE : "";
  const TOKEN_KEY = "gda_token";

  // ---------- token storage ----------
  function getToken() { return localStorage.getItem(TOKEN_KEY); }
  function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
  function clearToken() { localStorage.removeItem(TOKEN_KEY); }
  function isLoggedIn() { return !!getToken(); }

  let currentUser = null; // { id, username, email, full_name } | null

  // ---------- inject CSS (ใช้ CSS variable เดิมจาก style.css เพื่อให้สีตรงกันทั้งเว็บ) ----------
  const style = document.createElement("style");
  style.textContent = `
    .gda-auth-widget{display:flex; align-items:center; gap:0.6rem; font-family:'IBM Plex Mono',monospace; font-size:0.8rem;}
    .gda-auth-btn{background:none; border:1px solid var(--rule, #444); color:var(--marble-white-dim,#ccc);
      font-family:inherit; font-size:0.78rem; padding:0.45rem 0.9rem; cursor:pointer;}
    .gda-auth-btn:hover{border-color:var(--vein-gold-bright,#d9ad5c); color:var(--vein-gold-bright,#d9ad5c);}
    .gda-auth-btn.primary{background:var(--vein-gold-bright,#d9ad5c); color:#171207; border-color:transparent; font-weight:600;}
    .gda-user-chip{color:var(--marble-white,#eee); font-size:0.8rem;}

    .gda-modal-overlay{position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:1000;
      display:none; align-items:center; justify-content:center;}
    .gda-modal-overlay.open{display:flex;}
    .gda-modal{background:var(--stone-charcoal,#211d17); border:1px solid var(--rule,#444);
      width:360px; max-width:92vw; padding:1.8rem; position:relative;}
    .gda-modal h3{font-family:'Noto Serif Thai',serif; color:var(--marble-white,#eee); margin-bottom:1.2rem; font-size:1.2rem;}
    .gda-modal label{font-size:0.8rem; color:var(--stone-gray,#998); display:block; margin:0.8rem 0 0.3rem;}
    .gda-modal input{width:100%; background:var(--stone-black,#111); border:1px solid var(--rule,#444);
      color:var(--marble-white,#eee); font-family:inherit; font-size:0.9rem; padding:0.65rem 0.8rem;}
    .gda-modal .gda-error{color:var(--warn,#d99a7c); font-size:0.82rem; margin-top:0.8rem; min-height:1.2em;}
    .gda-modal .gda-actions{display:flex; justify-content:space-between; align-items:center; margin-top:1.4rem;}
    .gda-modal-close{position:absolute; top:0.8rem; right:1rem; background:none; border:none;
      color:var(--stone-gray,#998); font-size:1.3rem; cursor:pointer; line-height:1;}
    .gda-switch-link{color:var(--vein-gold-bright,#d9ad5c); font-size:0.82rem; cursor:pointer; text-decoration:underline; background:none; border:none; font-family:inherit;}
  `;
  document.head.appendChild(style);

  // ---------- inject widget into topbar ----------
  const widget = document.createElement("div");
  widget.className = "gda-auth-widget";
  widget.id = "gda-auth-widget";

  const topbar = document.querySelector(".topbar");
  if (topbar) {
    topbar.appendChild(widget);
  } else {
    // เผื่อ .topbar หาไม่เจอ (โครงสร้างเปลี่ยนไป) — แปะไว้มุมขวาบนสุดของหน้าแทน ไม่ให้ฟีเจอร์หายไปเงียบๆ
    widget.style.position = "fixed";
    widget.style.top = "12px";
    widget.style.right = "16px";
    widget.style.zIndex = "999";
    document.body.appendChild(widget);
  }

  // ---------- inject modal ----------
  const overlay = document.createElement("div");
  overlay.className = "gda-modal-overlay";
  overlay.id = "gda-auth-overlay";
  overlay.innerHTML = `
    <div class="gda-modal">
      <button type="button" class="gda-modal-close" id="gda-modal-close">&times;</button>
      <h3 id="gda-modal-title">เข้าสู่ระบบ</h3>

      <form id="gda-login-form">
        <label>Username</label>
        <input type="text" id="gda-login-username" required autocomplete="username">
        <label>Password</label>
        <input type="password" id="gda-login-password" required autocomplete="current-password">
        <div class="gda-error" id="gda-login-error"></div>
        <div class="gda-actions">
          <button type="button" class="gda-switch-link" id="gda-go-register">ยังไม่มีบัญชี? สมัครสมาชิก</button>
          <button type="submit" class="gda-auth-btn primary">เข้าสู่ระบบ</button>
        </div>
      </form>

      <form id="gda-register-form" style="display:none;">
        <label>Username (3-50 ตัว, a-z A-Z 0-9 _ เท่านั้น)</label>
        <input type="text" id="gda-reg-username" required minlength="3" maxlength="50" pattern="[a-zA-Z0-9_]+">
        <label>Email</label>
        <input type="email" id="gda-reg-email" required>
        <label>ชื่อ-นามสกุล (ไม่บังคับ)</label>
        <input type="text" id="gda-reg-fullname">
        <label>Password (อย่างน้อย 8 ตัวอักษร)</label>
        <input type="password" id="gda-reg-password" required minlength="8">
        <div class="gda-error" id="gda-reg-error"></div>
        <div class="gda-actions">
          <button type="button" class="gda-switch-link" id="gda-go-login">มีบัญชีแล้ว? เข้าสู่ระบบ</button>
          <button type="submit" class="gda-auth-btn primary">สมัครสมาชิก</button>
        </div>
      </form>
    </div>
  `;
  document.body.appendChild(overlay);

  const loginForm = document.getElementById("gda-login-form");
  const registerForm = document.getElementById("gda-register-form");
  const modalTitle = document.getElementById("gda-modal-title");

  function showLoginForm() {
    loginForm.style.display = "block";
    registerForm.style.display = "none";
    modalTitle.textContent = "เข้าสู่ระบบ";
    document.getElementById("gda-login-error").textContent = "";
  }
  function showRegisterForm() {
    loginForm.style.display = "none";
    registerForm.style.display = "block";
    modalTitle.textContent = "สมัครสมาชิก";
    document.getElementById("gda-reg-error").textContent = "";
  }
  function openModal() {
    overlay.classList.add("open");
    showLoginForm();
  }
  function closeModal() {
    overlay.classList.remove("open");
  }

  document.getElementById("gda-modal-close").addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
  document.getElementById("gda-go-register").addEventListener("click", showRegisterForm);
  document.getElementById("gda-go-login").addEventListener("click", showLoginForm);

  // ---------- API calls ----------
  async function apiPost(path, body, token) {
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;
    const res = await fetch(_API_BASE + path, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    let data = null;
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      throw new Error((data && data.detail) ? data.detail : `เกิดข้อผิดพลาด (${res.status})`);
    }
    return data;
  }

  async function fetchMe() {
    const token = getToken();
    if (!token) { currentUser = null; return null; }
    try {
      const res = await fetch(_API_BASE + "/me", { headers: { "Authorization": "Bearer " + token } });
      if (!res.ok) { clearToken(); currentUser = null; return null; }
      currentUser = await res.json();
      return currentUser;
    } catch (e) {
      currentUser = null;
      return null;
    }
  }

  // ---------- render widget based on login state ----------
  function renderWidget() {
    if (currentUser) {
      widget.innerHTML = `
        <span class="gda-user-chip">👤 ${currentUser.username}</span>
        <button type="button" class="gda-auth-btn" id="gda-logout-btn">ออกจากระบบ</button>
      `;
      document.getElementById("gda-logout-btn").addEventListener("click", doLogout);
    } else {
      widget.innerHTML = `<button type="button" class="gda-auth-btn primary" id="gda-login-btn">เข้าสู่ระบบ</button>`;
      document.getElementById("gda-login-btn").addEventListener("click", openModal);
    }
  }

  async function doLogout() {
    const token = getToken();
    clearToken();
    currentUser = null;
    renderWidget();
    if (typeof window.renderProjects === "function") window.renderProjects();
    // เรียก /auth/logout แบบ best-effort เฉยๆ (ไม่ต้องรอผล เพราะ logout จริงคือลบ token ฝั่งนี้ไปแล้ว)
    if (token) {
      fetch(_API_BASE + "/auth/logout", { method: "POST", headers: { "Authorization": "Bearer " + token } }).catch(() => {});
    }
  }

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("gda-login-username").value.trim();
    const password = document.getElementById("gda-login-password").value;
    const errorEl = document.getElementById("gda-login-error");
    errorEl.textContent = "";
    try {
      const data = await apiPost("/auth/login", { username, password });
      setToken(data.access_token);
      await fetchMe();
      renderWidget();
      closeModal();
      if (typeof window.renderProjects === "function") window.renderProjects();
    } catch (err) {
      errorEl.textContent = err.message;
    }
  });

  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("gda-reg-username").value.trim();
    const email = document.getElementById("gda-reg-email").value.trim();
    const full_name = document.getElementById("gda-reg-fullname").value.trim() || null;
    const password = document.getElementById("gda-reg-password").value;
    const errorEl = document.getElementById("gda-reg-error");
    errorEl.textContent = "";
    try {
      await apiPost("/auth/register", { username, email, password, full_name });
      // สมัครสำเร็จแล้ว ล็อกอินให้อัตโนมัติต่อเลย ไม่ต้องให้กรอกซ้ำ
      const data = await apiPost("/auth/login", { username, password });
      setToken(data.access_token);
      await fetchMe();
      renderWidget();
      closeModal();
      if (typeof window.renderProjects === "function") window.renderProjects();
    } catch (err) {
      errorEl.textContent = err.message;
    }
  });

  // ---------- public API ----------
  window.GDA_AUTH = {
    getToken,
    isLoggedIn,
    getCurrentUser: () => currentUser,
    openLoginModal: openModal,
    logout: doLogout,
  };

  // ---------- init: ถ้ามี token ค้างอยู่ ให้เช็คว่ายังใช้ได้ไหมตอนเปิดหน้าเว็บ ----------
  renderWidget();
  fetchMe().then(renderWidget);
})();
