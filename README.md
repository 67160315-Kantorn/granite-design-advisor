# Granite Design Advisor — Full-Stack (พร้อมรัน local)

โครงสร้างโปรเจกต์:

```
granite-design-advisor/
├── backend/
│   ├── main.py              ← จุดเริ่มต้น รันด้วย uvicorn
│   ├── routers/
│   │   ├── Chat.py          ← chatbot (Gemini ผ่าน OpenAI-compatible endpoint)
│   │   └── Estimate.py      ← คำนวณราคา + scrape ข้อมูลหิน
│   ├── scrape_granite.py    ← ดึง/จัดการข้อมูลหินจาก siamtak.com
│   ├── data/siamtak_granite.csv   ← ข้อมูลตั้งต้น (ใช้ได้ทันทีไม่ต้อง scrape)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html
    ├── style.css
    ├── app.js
    └── assets/theme-song.mp3
```

## วิธีรัน (ครั้งแรก)

### 1) ติดตั้ง Python dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2) ตั้งค่า API key

```bash
cp .env.example .env
```

เปิดไฟล์ `.env` แล้วใส่ `GEMINI_API_KEY` ของคุณ (ขอฟรีที่ https://aistudio.google.com/apikey)

### 3) รัน server

```bash
uvicorn main:app --reload
```

เปิดเบราว์เซอร์ไปที่ **http://127.0.0.1:8000**

จบ — คำสั่งเดียวรันทั้งเว็บและ API พร้อมกัน (ไม่ต้องเปิด Live Server แยก เพราะ `main.py`
serve ไฟล์ frontend ให้อัตโนมัติ และ frontend เรียก API แบบ path สัมพัทธ์ที่ origin เดียวกัน
เลยไม่มีปัญหาเรื่อง CORS ตอน dev)

## ตรวจสอบว่าทำงานถูกต้อง

- มุมขวาบนของเว็บจะมีจุดสถานะ backend — สีเขียว = เชื่อมต่อสำเร็จ, สีส้ม = เชื่อมต่อไม่ได้
- แท็บ **AI Chat**: คุยกับ Gemini จริง อ้างอิงราคาจากไฟล์ CSV
- แท็บ **คำนวณราคา**: ราคาต่อ ตร.ม. ดึงจาก backend จริง (ไม่ใช่ค่า hardcode ใน JS อีกต่อไป)
- ดู API docs อัตโนมัติได้ที่ **http://127.0.0.1:8000/docs** (Swagger UI ของ FastAPI)

## คำสั่งที่มีประโยชน์

| ทำอะไร | คำสั่ง / endpoint |
|---|---|
| ดึงข้อมูลหินใหม่จาก siamtak.com | `POST /estimate/refresh` (ปรับ selector ใน `scrape_granite.py` ก่อนใช้จริง) |
| ดูรายการหินทั้งหมดที่ backend มี | `GET /estimate/products` |
| ดาวน์โหลด CSV ดิบ | `GET /estimate/csv` |
| ทดสอบ chat แบบเต็ม (ไม่ stream) | `POST /chat/completions` |
| เช็คว่า server ยังทำงานอยู่ | `GET /health` |

## ถ้าจะแยก deploy frontend/backend คนละที่ในอนาคต

1. Deploy `backend/` ขึ้น Railway / Render / Fly.io — ตั้ง env vars (`GEMINI_API_KEY`,
   `CORS_ALLOWED_ORIGINS=https://โดเมนของ-frontend`) ในหน้า dashboard ของ host
2. Deploy `frontend/` ขึ้น Vercel / Netlify / GitHub Pages
3. แก้ `const API_BASE = "";` ใน `app.js` ให้เป็น URL เต็มของ backend ที่ deploy ไว้
4. ลบส่วน mount `StaticFiles` ใน `main.py` ออกได้ (ไม่จำเป็นแล้วเพราะ frontend แยกไปอยู่คนละที่)

## หมายเหตุเรื่อง scraper

`scrape_granite.py` มีโครง scraper จริงให้ (requests + BeautifulSoup) แต่ CSS selector
(`.product-card` ฯลฯ) เป็นค่าเดา — ต้องเปิด view-source ของหน้า siamtak.com จริงแล้วปรับให้ตรง
ก่อนใช้งาน ถ้ายังไม่ปรับ ระบบจะยังใช้ข้อมูลใน `data/siamtak_granite.csv` (ชุดที่แนบมาให้) ต่อไป
ได้ตามปกติ ไม่กระทบการใช้งาน chat/คำนวณราคา
