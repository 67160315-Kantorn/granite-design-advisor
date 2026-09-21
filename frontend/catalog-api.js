/* ==========================================================
   catalog-api.js — โหลดแคตตาล็อกหินจาก backend (MySQL) แทนที่ข้อมูลฝังในเว็บ

   วิธีใช้: เพิ่ม <script src="catalog-api.js"></script> ต่อท้าย <script src="app.js"></script>
   ใน index.html (ลำดับก่อน/หลัง auth.js กับ projects-api.js ไม่สำคัญ)

   หลักการ: GRANITE_CATALOG ใน app.js ประกาศด้วย const เปลี่ยนทั้งตัวแปรไม่ได้ แต่ "เนื้อหา"
   ข้างในอาร์เรย์แก้ไขได้ปกติ — ไฟล์นี้จะดึงข้อมูลจริงจาก /granite-products มาแทนที่เนื้อหา
   เดิมทั้งหมด แล้วสั่ง render ใหม่ให้ตรงกับข้อมูลจาก backend ทันที

   ถ้าเชื่อมต่อ backend ไม่ได้ (เช่น server ยังไม่รัน) จะ "ไม่ทำอะไรเลย" ปล่อยให้เว็บใช้ข้อมูล
   สำรองที่ฝังไว้ใน app.js ต่อไปตามปกติ ไม่ทำให้เว็บพังหรือแคตตาล็อกว่างเปล่า
   ========================================================== */
(function () {
  // หมายเหตุสำคัญ: API_BASE ใน app.js ประกาศด้วย const ที่ top-level ของ <script> tag
  // ค่าแบบนี้ "ไม่" กลายเป็น window.API_BASE หรือ globalThis.API_BASE โดยอัตโนมัติ
  // (ต่างจาก var/function declaration) แต่เบราว์เซอร์แชร์ scope นี้ข้าม <script> tag ให้เอง
  // เลยต้องอ้างอิงด้วยชื่อตัวแปรเปล่าๆ (bare identifier) ถึงจะมองเห็นค่าจริงจาก app.js —
  // ใช้ typeof เช็คก่อนเสมอ เพราะอ้างอิงตัวแปรที่ไม่มีอยู่จริงตรงๆ จะทำให้ error ทันที
  // ตั้งชื่อตัวแปรของไฟล์นี้เป็น _API_BASE (ไม่ใช่ API_BASE) เพื่อไม่ให้ชื่อชนกับของ app.js
  const _API_BASE = (typeof API_BASE !== "undefined") ? API_BASE : "";

  async function loadCatalogFromAPI() {
    let data;
    try {
      const res = await fetch(_API_BASE + "/granite-products");
      if (!res.ok) throw new Error("status " + res.status);
      data = await res.json();
    } catch (err) {
      console.warn("โหลดแคตตาล็อกจาก backend ไม่สำเร็จ ใช้ข้อมูลสำรองที่ฝังไว้ในเว็บแทน:", err.message);
      return;
    }

    // สำคัญ: GRANITE_CATALOG ใน app.js ประกาศด้วย const ที่ top-level ของ <script> tag —
    // ค่าแบบนี้ "ไม่" กลายเป็น window.GRANITE_CATALOG โดยอัตโนมัติ (ต่างจาก var หรือ function
    // declaration) แต่เบราว์เซอร์แชร์ scope นี้ข้าม <script> tag ให้อัตโนมัติ เลยอ้างอิงถึงมัน
    // ได้ตรงๆ ด้วยชื่อตัวแปรเฉยๆ (ไม่ต้องมี window. นำหน้า) ตราบใดที่ catalog-api.js ถูกโหลด
    // เป็น <script src="..."> ทีหลัง app.js ใน index.html จริง — ใช้ typeof เช็คก่อนเพราะ
    // การอ้างอิงตัวแปรที่ไม่มีอยู่จริงตรงๆ (ไม่ผ่าน typeof) จะทำให้ error ทันที
    if (typeof GRANITE_CATALOG === "undefined" || !Array.isArray(GRANITE_CATALOG)) {
      console.warn("ไม่พบตัวแปร GRANITE_CATALOG ใน app.js — ข้ามการอัปเดตแคตตาล็อก");
      return;
    }

    const mapped = data.map((p) => ({
      id: String(p.id),
      name: p.product_title,
      material: p.material,
      color: p.color,
      styles: p.styles || [],
      price: p.product_price,
      areas: p.areas || [],
      indoor: p.indoor || "indoor",
      desc: p.product_description || "",
      rating: p.rating || { price: 3, durability: 3, maintenance: 3, modern: 3, luxury: 3 },
      image: p.image_url,
    }));

    // เคลียร์เนื้อหาเก่าทิ้งแล้วใส่ของใหม่จาก backend แทน (ไม่ได้ reassign ตัวแปร แค่แก้เนื้อหาข้างใน
    // ของอาร์เรย์เดิม ซึ่งทำได้ปกติแม้ตัวแปรจะประกาศด้วย const ก็ตาม)
    GRANITE_CATALOG.length = 0;
    mapped.forEach((item) => GRANITE_CATALOG.push(item));

    if (typeof renderCatalog === "function") renderCatalog();

    const priceSelect = document.getElementById("price-stone-select");
    if (priceSelect) {
      priceSelect.innerHTML = GRANITE_CATALOG
        .map((s) => `<option value="${s.id}">${s.name} (฿${s.price.toLocaleString()}/ตร.ม.)</option>`)
        .join("");
    }

    console.log("โหลดแคตตาล็อกจาก backend สำเร็จ:", mapped.length, "ชนิด");
  }

  loadCatalogFromAPI();
})();
