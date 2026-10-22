# Granite Design Advisor — Full-Stack (Docker + MySQL + JWT Auth + Gemini AI)

ผู้ทำ: 67160315 กันต์ธร ใจใหญ่ (sec 1) · 67160372 ศุภวิชญ์ จิตรดี (sec 1)

เว็บช่วยเลือกและออกแบบการตกแต่งบ้านด้วยหินแกรนิต/หินอ่อน — ไม่ใช่แค่บอกว่าหินดีหรือไม่ดี
แต่ช่วยจับคู่หินที่ใช่กับพื้นที่ งบประมาณ และสไตล์ของผู้ใช้ พร้อมระบบสมาชิกและบันทึกโปรเจกต์จริง

## ฟีเจอร์

**สำหรับทุกคน (ไม่ต้องล็อกอิน)**
- แคตตาล็อกหิน 24 ชนิด กรองตามสี สไตล์ พื้นที่ ประเภท เรียงตามราคา/ความทนทาน/ความง่ายในการดูแล
- ค้นหาแบบผสม: FULLTEXT (อังกฤษ) + LIKE (ไทย) ใช้ร่วมกับตัวกรองได้
- หน้ารายละเอียดหิน (รูปใหญ่ คะแนน ราคา ลิงก์สินค้าจริง)
- เปรียบเทียบหิน 2–3 ชนิดข้างกัน ไฮไลต์ค่าที่ดีที่สุดในแต่ละแถว
- AI Design Advisor: ตอบ 4 ข้อ ได้หินแนะนำ 3 อันดับพร้อมเหตุผล
- AI Chat (Gemini) อ้างอิงข้อมูลหินจากฐานข้อมูล พร้อมการ์ดรูปหินประกอบคำตอบ
  - แนบรูปห้องได้ (📷): AI วิเคราะห์โทนสี/สไตล์ของห้องแล้วแนะนำหินจากแคตตาล็อก
  - ลองใหม่อัตโนมัติเมื่อ Gemini ตอบ 503/429
- คำนวณราคาจากราคาจริงในฐานข้อมูล (ค่าวัสดุ ผิวสัมผัส ค่าติดตั้ง VAT 7%) และดาวน์โหลดใบประมาณราคา PDF ภาษาไทย

**สำหรับสมาชิก (ล็อกอิน)**
- โปรเจกต์ของฉัน: บันทึกหิน/ผลคำนวณ/ผล AI Advisor ผูกกับบัญชี และ Export สรุปโปรเจกต์เป็น PDF ภาษาไทย
- รายการโปรด ♥ (กดหัวใจที่การ์ดหิน + กรองเฉพาะรายการโปรด)
- ประวัติ AI Chat ต่อบัญชี (ล็อกอินกลับมาแล้วยังเห็นบทสนทนาเดิม, ล้างได้)
- โปรไฟล์: แก้ข้อมูล, เปลี่ยนรหัสผ่าน, ลบบัญชี

**สำหรับแอดมิน** (`role = admin`)
- จัดการสมาชิก: ดูรายชื่อ, ลบสมาชิกทั่วไป (ลบแอดมินอื่น/แอดมินคนสุดท้ายไม่ได้)
- จัดการหิน: เพิ่ม/แก้ไข/ลบหินในแคตตาล็อกผ่านหน้าเว็บ
- แดชบอร์ดสถิติ: สมาชิก โปรเจกต์ แชต หินยอดนิยม (โปรด / AI แนะนำ / อยู่ในโปรเจกต์)

## Tech Stack

| ชั้น | เทคโนโลยี |
|---|---|
| Frontend | HTML5, CSS3, JavaScript (ES6+, ไม่ใช้ framework) |
| Backend | Python 3.13, FastAPI, Uvicorn |
| Database | MySQL 8 + phpMyAdmin |
| Auth | JWT (python-jose) + bcrypt, role `user` / `admin` |
| AI | Google Gemini API ผ่าน `google-genai` SDK (streaming SSE) |
| PDF | fpdf2 + uharfbuzz (จัดสระ/วรรณยุกต์ไทย) + ฟอนต์ TLWG ใน Docker image |
| Infra | Docker + Docker Compose |

## โครงสร้างโปรเจกต์

```
granite-design-advisor/
├── docker-compose.yml            ← backend + MySQL + phpMyAdmin
├── .env.example                  ← รหัสผ่าน MySQL (คัดลอกเป็น .env)
├── backend/
│   ├── Dockerfile                ← ติดตั้งฟอนต์ไทยสำหรับ PDF ด้วย
│   ├── main.py                   ← รวม router + serve frontend + สร้างตารางที่เพิ่มทีหลังอัตโนมัติ
│   ├── database.py / models.py   ← SQLAlchemy (User, Project, ProjectItem, GraniteProduct, ChatMessage, Favorite)
│   ├── auth_utils.py             ← bcrypt + JWT
│   ├── pdf_export.py             ← สร้าง PDF โปรเจกต์และใบประมาณราคา (ภาษาไทย)
│   ├── scrape_granite.py         ← scraper ดิบ (เขียน CSV staging)
│   ├── .env.example              ← GEMINI_API_KEY, JWT_SECRET_KEY
│   ├── sql/                      ← 01-schema.sql และสคริปต์ migration (ดูหัวข้อติดตั้ง)
│   └── routers/
│       ├── Auth.py               ← register / login / logout / change-password, require_admin
│       ├── Users.py              ← /me, /users, role (แอดมิน), /check-username
│       ├── Projects.py           ← CRUD โปรเจกต์ + รายการ + export PDF
│       ├── Catalog.py            ← อ่านหิน (สาธารณะ) + เพิ่ม/แก้/ลบ (แอดมิน)
│       ├── Favorites.py          ← รายการโปรด
│       ├── Admin.py              ← สถิติแดชบอร์ด
│       ├── Chat.py               ← Gemini chat + ประวัติ + retry
│       └── Estimate.py           ← คำนวณราคา + PDF ใบประมาณราคา + scrape
└── frontend/
    ├── index.html, style.css
    ├── app.js                    ← แคตตาล็อก, เปรียบเทียบ, AI Advisor, แชต, คำนวณราคา
    ├── auth.js                   ← login/register (ปลั๊กอิน inject UI เอง)
    ├── profile.js                ← โปรไฟล์, เปลี่ยนรหัสผ่าน, รายชื่อสมาชิก
    ├── projects-api.js           ← โปรเจกต์ผ่าน API
    ├── catalog-api.js            ← โหลดแคตตาล็อกจาก backend
    ├── product-detail.js         ← หน้ารายละเอียดหิน
    ├── favorites.js              ← รายการโปรด
    ├── chat-history.js           ← ประวัติแชต
    ├── admin-catalog.js          ← จัดการหิน (แอดมิน)
    └── admin-dashboard.js        ← แดชบอร์ด (แอดมิน)
```

## วิธีรัน (ติดตั้งครั้งแรก)

ต้องติดตั้ง **[Docker Desktop](https://www.docker.com/products/docker-desktop)** ก่อน (บน Windows ต้องเปิด WSL2 — รัน `wsl --install` ใน PowerShell ถ้ายังไม่เคยเปิด)

### 1) ตั้งค่า environment variables (2 ไฟล์)

```powershell
copy .env.example .env
copy backend\.env.example backend\.env
```

**`.env`** (root) — รหัสผ่าน MySQL ตั้งเอง:
```
MYSQL_ROOT_PASSWORD=<ตั้งเอง>
MYSQL_DATABASE=granite_db
MYSQL_USER=granite_user
MYSQL_PASSWORD=<ตั้งเอง>
```

**`backend/.env`**:
```
GEMINI_API_KEY=<คีย์จริงจาก https://aistudio.google.com/apikey>
JWT_SECRET_KEY=<สุ่มด้วย: python -c "import secrets; print(secrets.token_hex(32))">
```

### 2) รัน

```powershell
docker compose up --build
```

รอจนเห็น `Uvicorn running on http://0.0.0.0:8000`

### 3) สร้างตารางและนำเข้าข้อมูลหิน (ครั้งเดียว)

เปิด **http://localhost:8080** (phpMyAdmin) → login `root` + `MYSQL_ROOT_PASSWORD` → เลือก `granite_db` → แท็บ **Import**

1. `backend/sql/01-schema.sql` — สร้างตารางทั้งหมด (รวม role, แชต, รายการโปรดแล้ว ไม่ต้องรัน 06–08)
2. ไฟล์ข้อมูลหิน 24 ชนิด (seed) — ดูหัวข้อ "ข้อมูลหิน (seed)" ด้านล่าง

> สร้างแอดมินคนแรก: สมัครสมาชิกบนเว็บก่อน แล้วรันใน tab SQL ของ phpMyAdmin
> `UPDATE users SET role='admin' WHERE username='<ชื่อผู้ใช้ของคุณ>';`

### 4) เปิดเว็บ

**http://localhost:8000** · Swagger UI: **http://localhost:8000/docs** · phpMyAdmin: **http://localhost:8080**

### ข้อมูลหิน (seed)

ข้อมูลหินอยู่ในตาราง `granite_products` (ไม่ได้อยู่ในโค้ด) ถ้าติดตั้งบนเครื่องอื่นต้องย้ายข้อมูลไปด้วย
export จากเครื่องที่มีข้อมูลอยู่แล้ว (รันใน PowerShell ที่โฟลเดอร์โปรเจกต์ ขณะที่ `docker compose up` ทำงานอยู่ ไม่ต้องพิมพ์รหัสผ่าน) แล้วเก็บไฟล์ไว้ที่ `backend/sql/02-seed-catalog.sql`:

```powershell
docker compose exec mysql sh -c 'mysqldump -uroot -p$MYSQL_ROOT_PASSWORD --no-create-info --skip-extended-insert --default-character-set=utf8mb4 --result-file=/tmp/seed.sql granite_db granite_products'
docker compose cp mysql:/tmp/seed.sql backend/sql/02-seed-catalog.sql
```

แล้ว import ไฟล์นั้นในขั้นตอนที่ 3 ข้อ 2 บนเครื่องใหม่

## รันครั้งต่อไป

```powershell
docker compose up
```

เพิ่ม `--build` เฉพาะเมื่อแก้โค้ด backend/frontend หรือ Dockerfile (container เก็บสำเนาโค้ดไว้ในตัว) แล้วกด **Ctrl+F5** ที่เบราว์เซอร์เพื่อล้าง cache

ตาราง `chat_messages` และ `favorites` ถูกสร้างอัตโนมัติตอน backend เริ่มทำงาน ถ้าไม่สำเร็จ (ดู `docker compose logs backend`) ให้ import `backend/sql/07-…` / `08-…` เอง

## ตรวจสอบว่าทำงานถูกต้อง

- มุมขวาบน: จุดสถานะ backend (เขียว = เชื่อมต่อสำเร็จ) และปุ่ม **เข้าสู่ระบบ**
- สมัคร → login → แท็บ **AI Chat**: คุยกับ Gemini ได้ ลองแนบรูปห้องด้วยปุ่ม 📷
- แท็บ **คำนวณราคา**: คำนวณแล้วกด Export PDF (ภาษาไทยต้องถูกต้อง)
- แคตตาล็อก: กด ♡ เก็บรายการโปรด, ติ๊ก "เลือกเปรียบเทียบ" 2–3 ชนิดแล้วกด "เปรียบเทียบเลย"
- บัญชีแอดมิน: เห็นปุ่ม "จัดการหิน" และ "แดชบอร์ด" ข้างปุ่มออกจากระบบ

## API Endpoints

| กลุ่ม | Endpoint | สิทธิ์ |
|---|---|---|
| Auth | `POST /auth/register`, `/auth/login` | ทุกคน |
| Auth | `POST /auth/logout`, `/auth/change-password` | ล็อกอิน |
| Users | `GET /me`, `GET /users`, `GET /users/{id}`, `PUT /users/{id}` | ล็อกอิน (แก้ได้แค่ของตัวเอง) |
| Users | `DELETE /users/{id}` | เจ้าของบัญชี หรือแอดมิน |
| Users | `PUT /users/{id}/role` | แอดมิน |
| Users | `GET /check-username/{name}` | ทุกคน |
| Projects | `POST/GET /projects`, `GET/DELETE /projects/{id}`, `POST/DELETE /projects/{id}/items[/{item_id}]` | ล็อกอิน (เจ้าของ) |
| Projects | `GET /projects/{id}/export` (PDF) | ล็อกอิน (เจ้าของ) |
| Catalog | `GET /granite-products` (`?q=&color=&style=&area=&material=&min_price=&max_price=`), `GET /granite-products/{id}` | ทุกคน |
| Catalog | `POST /granite-products`, `PUT/DELETE /granite-products/{id}` | แอดมิน |
| Favorites | `GET /favorites`, `PUT/DELETE /favorites/{product_id}` | ล็อกอิน |
| Chat | `POST /chat/completions`, `POST /chat/completions/stream` | ทุกคน (ล็อกอินแล้วบันทึกประวัติ) |
| Chat | `GET/DELETE /chat/history` | ล็อกอิน |
| Estimate | `POST /estimate/calculate`, `POST /estimate/pdf`, `GET /estimate/products` | ทุกคน |
| Estimate | `GET /estimate/csv`, `POST /estimate/refresh` | ทุกคน |
| Admin | `GET /admin/stats` | แอดมิน |
| System | `GET /health` | ทุกคน |

## ปัญหาที่เคยเจอระหว่างพัฒนา (กันเจอซ้ำ)

| อาการ | สาเหตุ | วิธีแก้ |
|---|---|---|
| `API key not valid` ทั้งที่คีย์ถูก | คีย์รูปแบบใหม่ `AQ...` ใช้กับ OpenAI-compatible endpoint ไม่ได้ | ใช้ `google-genai` SDK โดยตรง (แก้ไว้แล้ว) |
| `Both GOOGLE_API_KEY and GEMINI_API_KEY are set` | มี env var เก่าค้างในเครื่อง | โค้ดลบ `GOOGLE_API_KEY` ก่อนสร้าง client |
| แก้ `.env` แล้วไม่มีผล | มี environment variable ชื่อเดียวกันค้างใน OS | ใช้ `load_dotenv(override=True)` |
| `models/gemini-2.5-flash is no longer available` | Google ปิดรุ่นเก่าสำหรับผู้ใช้ใหม่ | ใช้ `gemini-3.6-flash` เป็นค่า default |
| bcrypt error ตอนสมัคร | bcrypt รุ่นใหม่ชนกับ passlib | pin `bcrypt==4.0.1` |
| แชทขึ้น "network error" ห้วนๆ | error เกิดหลังส่ง HTTP headers (SSE) | จับ error แล้วส่งเป็น SSE event |
| แชทแจ้งว่า Gemini ไม่ว่าง (503) | โมเดลคนใช้เยอะ | retry อัตโนมัติแบบ exponential backoff (ถ้ายังไม่มีข้อความออกมา) |
| แก้โค้ดแล้วหน้าเว็บไม่เปลี่ยน | container เก็บสำเนา frontend/backend ไว้ | `docker compose up --build` แล้ว Ctrl+F5 |
| PDF ภาษาไทยเป็น `?` | ไม่มีฟอนต์ไทย (รันนอก Docker) | ตั้ง `PDF_FONT_PATH` (และ `PDF_FONT_BOLD_PATH`) ใน `backend/.env` เป็นไฟล์ `.ttf` |
| ประวัติแชทหายหลังรีเฟรช | ตาราง `chat_messages` ยังไม่ถูกสร้าง | ดู log backend แล้ว import `backend/sql/07-create-chat-messages.sql` |

## หมายเหตุ

- **Scraper**: `scrape_granite.py` เป็นโครง (CSS selector เป็นค่าเดา) เขียนผลลง CSV staging เท่านั้น ไม่ได้อัปเดตตาราง `granite_products` อัตโนมัติ
- **Cloudflare Quick Tunnel** ไม่รองรับ SSE — แชทแบบ streaming อาจใช้งานไม่ได้ผ่านลิงก์ชั่วคราวแบบนี้
- **ก่อนเปิดเว็บสู่สาธารณะ**: เปลี่ยน `JWT_SECRET_KEY` และรหัสผ่าน MySQL ทั้งหมด, ปิดพอร์ต MySQL (3306) และ phpMyAdmin (8080) จากภายนอก, ใช้ HTTPS

## สิ่งที่ยังไม่ได้ทำ

- ลืมรหัสผ่านทางอีเมล (ต้องมี SMTP)
- กราฟแนวโน้มราคาหิน (ต้องเก็บประวัติราคาก่อน)
- จำกัดจำนวนครั้ง (rate limit) ของล็อกอินและแชต
- Deploy ขึ้นเซิร์ฟเวอร์สาธารณะ (แผน: VPS + Docker Compose + Caddy สำหรับ HTTPS)
- แก้ CSS selector ใน scraper ให้ scrape จริง

รายละเอียดความคืบหน้าเต็ม ดูที่ `self-assessment.md`
