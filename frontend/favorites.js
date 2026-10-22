/* ==========================================================
   favorites.js — รายการโปรด (หัวใจ ♡/♥ บนการ์ดหิน + ตัวกรอง "เฉพาะรายการโปรด")

   ต้องล็อกอิน: เก็บที่ backend ตาราง favorites ต่อผู้ใช้ (GET/PUT/DELETE /favorites)
   เปิดให้ส่วนอื่นเรียกผ่าน window.GDA_FAV = { has(id), toggle(id), count() }
   ========================================================== */
(function () {
  const _API_BASE = (typeof API_BASE !== "undefined") ? API_BASE : "";
  let ids = new Set();         // id หิน (string) ที่ผู้ใช้กดหัวใจไว้
  let loadedToken = null;

  function token() { return (window.GDA_AUTH && window.GDA_AUTH.getToken()) || null; }
  function isLoggedIn() { return !!(window.GDA_AUTH && window.GDA_AUTH.isLoggedIn()); }
  function say(msg) { if (typeof toast === "function") toast(msg); }

  async function api(path, method) {
    const res = await fetch(_API_BASE + path, {
      method: method || "GET",
      headers: { "Authorization": "Bearer " + token() },
    });
    let body = null;
    try { body = await res.json(); } catch (e) {}
    if (!res.ok) throw new Error((body && body.detail) || `เกิดข้อผิดพลาด (${res.status})`);
    return body;
  }

  function apply(body) { ids = new Set((body.product_ids || []).map(String)); }
  function redraw() { if (typeof renderCatalog === "function") renderCatalog(); }

  async function toggle(id) {
    id = String(id);
    if (!isLoggedIn()) {
      say("เข้าสู่ระบบก่อนเพื่อเก็บรายการโปรด");
      if (window.GDA_AUTH) window.GDA_AUTH.openLoginModal();
      return;
    }
    const was = ids.has(id);
    // อัปเดตหน้าจอทันที แล้วค่อยยืนยันกับ backend (ถ้าพลาดจะย้อนกลับ)
    if (was) ids.delete(id); else ids.add(id);
    redraw();
    try {
      apply(await api("/favorites/" + encodeURIComponent(id), was ? "DELETE" : "PUT"));
      say(was ? "เอาออกจากรายการโปรดแล้ว" : "เพิ่มเข้ารายการโปรดแล้ว ♥");
    } catch (err) {
      if (was) ids.add(id); else ids.delete(id);
      say("บันทึกรายการโปรดไม่สำเร็จ: " + err.message);
    }
    redraw();
  }

  window.GDA_FAV = { has: (id) => ids.has(String(id)), toggle, count: () => ids.size };

  async function sync() {
    const t = token();
    if (!isLoggedIn()) {
      if (loadedToken !== null || ids.size) {
        ids = new Set(); loadedToken = null;
        const f = document.getElementById("f-fav");
        if (f) f.checked = false;
        redraw();
      }
      return;
    }
    if (loadedToken === t) return;
    loadedToken = t;
    try { apply(await api("/favorites")); redraw(); }
    catch (err) { console.warn("โหลดรายการโปรดไม่สำเร็จ:", err.message); loadedToken = null; }
  }

  const widget = document.getElementById("gda-auth-widget");
  if (widget) new MutationObserver(sync).observe(widget, { childList: true, subtree: true });
  sync();
})();
