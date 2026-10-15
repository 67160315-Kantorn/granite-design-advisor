/* ==========================================================
   chat-history.js — แสดงประวัติ AI Chat ของผู้ใช้ที่ล็อกอิน (บันทึกที่ backend ตาราง chat_messages)

   - ล็อกอินแล้ว: โหลดบทสนทนาเดิมมาแสดงใน #chat-log และใส่เข้า chatHistory (ใน app.js) เพื่อให้
     AI จำบริบทเดิมต่อได้ด้วย (รูปที่เคยแนบไม่ถูกเก็บ — จะเห็นแค่ข้อความ)
   - ออกจากระบบ: ล้างหน้าแชทกลับเป็นข้อความทักทาย
   - ปุ่ม "ล้างประวัติการสนทนา" ใต้กล่องแชท (เฉพาะตอนล็อกอิน)
   การบันทึกเกิดฝั่ง backend อัตโนมัติ (app.js แค่แนบ token มากับ request แชท)
   ========================================================== */
(function () {
  const _API_BASE = (typeof API_BASE !== "undefined") ? API_BASE : "";
  const chatLogEl = document.getElementById("chat-log");
  const chatBoxEl = document.querySelector(".chat-box");
  if (!chatLogEl || !chatBoxEl) return;

  const greetingText = chatLogEl.firstElementChild ? chatLogEl.firstElementChild.textContent : "";

  // ---------- แถบใต้กล่องแชท ----------
  const bar = document.createElement("div");
  bar.style.cssText = "display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-top:0.6rem; font-size:0.78rem; color:var(--stone-gray,#998);";
  bar.innerHTML = `<span id="gda-chat-note"></span>
    <button type="button" id="gda-chat-clear" class="btn-small" style="display:none">ล้างประวัติการสนทนา</button>`;
  chatBoxEl.parentNode.insertBefore(bar, chatBoxEl.nextSibling);
  const noteEl = document.getElementById("gda-chat-note");
  const clearBtn = document.getElementById("gda-chat-clear");

  async function apiRequest(path, options) {
    const token = (window.GDA_AUTH && window.GDA_AUTH.getToken()) || null;
    const headers = Object.assign({ "Content-Type": "application/json" }, (options || {}).headers || {});
    if (token) headers["Authorization"] = "Bearer " + token;
    const res = await fetch(_API_BASE + path, Object.assign({}, options || {}, { headers }));
    if (res.status === 204) return null;
    let body = null;
    try { body = await res.json(); } catch (e) {}
    if (!res.ok) throw new Error((body && body.detail) || `เกิดข้อผิดพลาด (${res.status})`);
    return body;
  }

  function isLoggedIn() { return !!(window.GDA_AUTH && window.GDA_AUTH.isLoggedIn()); }

  function renderProducts(botEl, products) {
    if (!products || !products.length) return;
    const wrap = document.createElement("div");
    wrap.className = "msg-products";
    products.forEach((p) => {
      const card = document.createElement("div");
      card.className = "msg-product-card";
      const img = document.createElement("img");
      img.src = p.image_url;
      img.alt = p.name;
      img.loading = "lazy";
      const label = document.createElement("span");
      label.textContent = String(p.name || "").replace(/\s*\(.*?\)\s*$/, "");
      card.appendChild(img);
      card.appendChild(label);
      wrap.appendChild(card);
    });
    botEl.appendChild(wrap);
  }

  function resetToGreeting() {
    chatLogEl.innerHTML = "";
    if (typeof addMsg === "function" && greetingText) addMsg(greetingText, "bot");
    if (typeof chatHistory !== "undefined") chatHistory = [];
  }

  let loadedToken = null;   // token ที่โหลดประวัติไปแล้ว (กันโหลดซ้ำเมื่อ widget re-render)
  let wasLoggedIn = false;

  async function sync() {
    const token = (window.GDA_AUTH && window.GDA_AUTH.getToken()) || null;
    if (!isLoggedIn()) {
      clearBtn.style.display = "none";
      noteEl.textContent = "ล็อกอินเพื่อบันทึกประวัติการสนทนาไว้ในบัญชีของคุณ";
      if (wasLoggedIn) resetToGreeting();
      wasLoggedIn = false;
      loadedToken = null;
      return;
    }
    wasLoggedIn = true;
    clearBtn.style.display = "";
    noteEl.textContent = "บันทึกประวัติการสนทนาในบัญชีของคุณอัตโนมัติ";
    if (loadedToken === token) return;
    loadedToken = token;

    let items;
    try {
      items = await apiRequest("/chat/history?limit=60");
    } catch (err) {
      console.warn("โหลดประวัติแชทไม่สำเร็จ:", err.message);
      return;
    }
    if (!items.length) return;

    chatLogEl.innerHTML = "";
    if (typeof addMsg !== "function") return;
    addMsg(greetingText, "bot");
    const seeded = [];
    items.forEach((m) => {
      if (m.role === "user") {
        addMsg((m.has_image ? "📷 " : "") + (m.content || "(ส่งรูปภาพ)"), "user");
        seeded.push({ role: "user", content: m.content || "(ผู้ใช้ส่งรูปภาพ)" });
      } else {
        const el = addMsg(m.content, "bot");
        renderProducts(el, m.products);
        seeded.push({ role: "assistant", content: m.content });
      }
    });
    if (typeof chatHistory !== "undefined") chatHistory = seeded;
    chatLogEl.scrollTop = chatLogEl.scrollHeight;
  }

  clearBtn.addEventListener("click", async () => {
    if (!confirm("ล้างประวัติการสนทนากับ AI ทั้งหมดของคุณ? ย้อนกลับไม่ได้")) return;
    try {
      await apiRequest("/chat/history", { method: "DELETE" });
      resetToGreeting();
    } catch (err) {
      alert("ล้างประวัติไม่สำเร็จ: " + err.message);
    }
  });

  const widget = document.getElementById("gda-auth-widget");
  if (widget) new MutationObserver(sync).observe(widget, { childList: true, subtree: true });
  sync();
})();
