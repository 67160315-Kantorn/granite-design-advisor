/* ==========================================================
   projects-api.js — ย้าย "โปรเจกต์ของฉัน" จาก localStorage ไปเป็น API จริง

   ไฟล์นี้ประกาศฟังก์ชันชื่อเดียวกับที่ app.js เคยประกาศไว้ (renderProjects,
   addToActiveProject, deleteProject, deleteProjectItem, setActiveProjectId)
   ผลคือ "ทับ" เวอร์ชันเดิมที่ผูกกับ localStorage ไปเลย โดยไม่ต้องแก้ไฟล์ app.js
   หรือ index.html เดิมแม้แต่บรรทัดเดียว

   วิธีใช้: เพิ่ม <script src="projects-api.js"></script> ต่อท้าย
   <script src="auth.js"></script> ใน index.html (ต้องมาหลังสุด)

   ข้อจำกัดที่ตั้งใจตัดออกไปก่อน (ยังไม่ได้ย้ายมาในเวอร์ชันนี้):
   - ปุ่ม "Export PDF" ของแต่ละโปรเจกต์ที่เคยมี — เพราะโครงสร้างข้อมูลจาก API
     ต่างจาก localStorage เดิมเล็กน้อย รอทำเป็นขั้นถัดไปได้ถ้าต้องการ
   ========================================================== */
(function () {
  // หมายเหตุสำคัญ: API_BASE ใน app.js ประกาศด้วย const ที่ top-level ของ <script> tag
  // ค่าแบบนี้ "ไม่" กลายเป็น window.API_BASE หรือ globalThis.API_BASE โดยอัตโนมัติ
  // (ต่างจาก var/function declaration) แต่เบราว์เซอร์แชร์ scope นี้ข้าม <script> tag ให้เอง
  // เลยต้องอ้างอิงด้วยชื่อตัวแปรเปล่าๆ (bare identifier) ถึงจะมองเห็นค่าจริงจาก app.js —
  // ใช้ typeof เช็คก่อนเสมอ เพราะอ้างอิงตัวแปรที่ไม่มีอยู่จริงตรงๆ จะทำให้ error ทันที
  // ตั้งชื่อตัวแปรของไฟล์นี้เป็น _API_BASE (ไม่ใช่ API_BASE) เพื่อไม่ให้ชื่อชนกับของ app.js
  const _API_BASE = (typeof API_BASE !== "undefined") ? API_BASE : "";
  const ACTIVE_PROJECT_ID_KEY = "gda_active_project_id"; // เก็บแค่ "ตัวชี้" ว่ากำลังใช้โปรเจกต์ไหนอยู่ (ไม่ใช่ข้อมูลจริง)

  const KIND_LABEL = { granite: "หิน", price: "ราคา", advisor: "AI แนะนำ", inspiration: "Inspiration" };

  function getActiveProjectId() {
    const v = localStorage.getItem(ACTIVE_PROJECT_ID_KEY);
    return v ? parseInt(v, 10) : null;
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

  function setActiveProjectId(id) {
    localStorage.setItem(ACTIVE_PROJECT_ID_KEY, String(id));
    renderProjects();
  }
  window.setActiveProjectId = setActiveProjectId;

  async function addToActiveProject(kind, title, detail) {
    if (!window.GDA_AUTH || !window.GDA_AUTH.isLoggedIn()) {
      alert("กรุณาเข้าสู่ระบบก่อนบันทึกลงโปรเจกต์");
      if (window.GDA_AUTH) window.GDA_AUTH.openLoginModal();
      return;
    }
    const activeId = getActiveProjectId();
    if (!activeId) {
      alert('ยังไม่ได้เลือกโปรเจกต์ครับ — ไปที่เมนู "โปรเจกต์ของฉัน" เพื่อสร้างหรือเลือกโปรเจกต์ก่อน');
      if (typeof window.goto === "function") window.goto("projects");
      return;
    }
    try {
      await apiRequest(`/projects/${activeId}/items`, {
        method: "POST",
        body: JSON.stringify({ kind: kind, title: title, detail: detail }),
      });
      if (typeof window.toast === "function") window.toast("บันทึกลงโปรเจกต์แล้ว");
      renderProjects();
    } catch (err) {
      if (String(err.message).includes("ไม่พบโปรเจกต์")) {
        // โปรเจกต์ที่เคยตั้ง active ไว้ถูกลบไปแล้วจากที่อื่น (เช่นอีกแท็บ) — เคลียร์ pointer ทิ้ง
        localStorage.removeItem(ACTIVE_PROJECT_ID_KEY);
      }
      alert("บันทึกไม่สำเร็จ: " + err.message);
    }
  }
  window.addToActiveProject = addToActiveProject;

  async function deleteProject(id) {
    if (!confirm("ต้องการลบโปรเจกต์นี้หรือไม่? รายการทั้งหมดในโปรเจกต์จะถูกลบไปด้วย")) return;
    try {
      await apiRequest(`/projects/${id}`, { method: "DELETE" });
      if (getActiveProjectId() === id) localStorage.removeItem(ACTIVE_PROJECT_ID_KEY);
      renderProjects();
    } catch (err) {
      alert("ลบไม่สำเร็จ: " + err.message);
    }
  }
  window.deleteProject = deleteProject;

  async function deleteProjectItem(projectId, itemId) {
    try {
      await apiRequest(`/projects/${projectId}/items/${itemId}`, { method: "DELETE" });
      renderProjects();
    } catch (err) {
      alert("ลบไม่สำเร็จ: " + err.message);
    }
  }
  window.deleteProjectItem = deleteProjectItem;

  async function renderProjects() {
    const listEl = document.getElementById("project-list");
    const note = document.getElementById("active-project-note");
    if (!listEl || !note) return; // ยังไม่อยู่ในหน้าที่มี element พวกนี้ (เช่นยังโหลดไม่เสร็จ) ข้ามไปเงียบๆ

    if (!window.GDA_AUTH || !window.GDA_AUTH.isLoggedIn()) {
      note.innerHTML = 'กรุณา <a href="#" id="gda-projects-login-link">เข้าสู่ระบบ</a> ก่อนใช้งานโปรเจกต์ — ข้อมูลผูกกับบัญชีผู้ใช้ ไม่ใช่เบราว์เซอร์เครื่องนี้อีกต่อไป';
      listEl.innerHTML = "";
      const link = document.getElementById("gda-projects-login-link");
      if (link) link.addEventListener("click", (e) => { e.preventDefault(); window.GDA_AUTH.openLoginModal(); });
      return;
    }

    let projects;
    try {
      projects = await apiRequest("/projects");
    } catch (err) {
      note.textContent = "โหลดโปรเจกต์ไม่สำเร็จ: " + err.message;
      listEl.innerHTML = "";
      return;
    }

    const activeId = getActiveProjectId();

    if (projects.length === 0) {
      note.innerHTML = "ยังไม่มีโปรเจกต์ — สร้างโปรเจกต์แรกของคุณด้านบนได้เลยครับ";
    } else {
      const active = projects.find((p) => p.id === activeId);
      note.innerHTML = active
        ? `โปรเจกต์ปัจจุบัน: <b>${active.name}</b> — ปุ่ม "+ โปรเจกต์" ทั่วเว็บจะบันทึกเข้าที่นี่`
        : `ยังไม่ได้เลือกโปรเจกต์ปัจจุบัน — กด "ตั้งเป็นโปรเจกต์ปัจจุบัน" ที่การ์ดด้านล่างก่อนเริ่มบันทึกรายการ`;
    }

    // GET /projects คืนแค่สรุป (item_count) ต้องขอรายละเอียดแต่ละโปรเจกต์แยกเพื่อโชว์รายการข้างใน
    const details = await Promise.all(
      projects.map((p) => apiRequest(`/projects/${p.id}`).catch(() => null))
    );

    listEl.innerHTML = projects
      .map((p, i) => {
        const detail = details[i];
        const items = detail ? detail.items : [];
        return `
      <div class="project-card ${p.id === activeId ? "active" : ""}">
        <div class="project-head">
          <div>
            <h3>${p.name} ${p.id === activeId ? "⭐" : ""}</h3>
            <div class="meta">${items.length} รายการ</div>
          </div>
          <div class="project-actions">
            ${p.id !== activeId ? `<button class="btn-small" onclick="setActiveProjectId(${p.id})">ตั้งเป็นโปรเจกต์ปัจจุบัน</button>` : ""}
            <button class="btn-small" onclick="deleteProject(${p.id})">ลบโปรเจกต์</button>
          </div>
        </div>
        <div class="project-items">
          ${
            items.length === 0
              ? '<p class="project-empty">ยังไม่มีรายการ — ลองกด "+ โปรเจกต์" จากแคตตาล็อกหรือ AI Advisor</p>'
              : items
                  .map(
                    (item) => `
            <div class="project-item">
              <div><span class="kind">${KIND_LABEL[item.kind] || item.kind}</span>${item.title}</div>
              <button class="btn-small" onclick="deleteProjectItem(${p.id},${item.id})">ลบ</button>
            </div>
          `
                  )
                  .join("")
          }
        </div>
      </div>
    `;
      })
      .join("");
  }
  window.renderProjects = renderProjects;

  // ---------- ผูกฟอร์ม "สร้างโปรเจกต์ใหม่" ใหม่ทับของเดิม ----------
  // clone + replace โหนดฟอร์มเดิมทิ้งก่อน เพื่อลบ event listener เก่า (ที่ผูกกับ localStorage) ออกให้หมด
  const oldForm = document.getElementById("new-project-form");
  if (oldForm) {
    const freshForm = oldForm.cloneNode(true);
    oldForm.parentNode.replaceChild(freshForm, oldForm);

    freshForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!window.GDA_AUTH || !window.GDA_AUTH.isLoggedIn()) {
        alert("กรุณาเข้าสู่ระบบก่อนสร้างโปรเจกต์");
        if (window.GDA_AUTH) window.GDA_AUTH.openLoginModal();
        return;
      }
      const input = document.getElementById("new-project-name");
      const name = input.value.trim();
      if (!name) return;
      try {
        const project = await apiRequest("/projects", {
          method: "POST",
          body: JSON.stringify({ name: name }),
        });
        setActiveProjectId(project.id);
        input.value = "";
      } catch (err) {
        alert("สร้างโปรเจกต์ไม่สำเร็จ: " + err.message);
      }
    });
  }

  // เรียก render ทันทีตอนสคริปต์นี้โหลดเสร็จ (เผื่อ refresh หน้าเว็บระหว่างอยู่ที่แท็บ Projects)
  renderProjects();
})();
