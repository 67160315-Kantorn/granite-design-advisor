# Granite Design Advisor — Full-Stack (Docker + MySQL + JWT Auth + Gemini AI)

เว็บช่วยเลือกและออกแบบการตกแต่งบ้านด้วยหินแกรนิต/หินอ่อน — ไม่ใช่แค่บอกว่าหินดีหรือไม่ดี
แต่ช่วยจับคู่หินที่ใช่กับพื้นที่ งบประมาณ และสไตล์ของผู้ใช้ พร้อมระบบสมาชิกและบันทึกโปรเจกต์จริง

## Tech Stack

| ชั้น | เทคโนโลยี |
|---|---|
| Frontend | HTML5, CSS3, JavaScript (ES6+, ไม่ใช้ framework) |
| Backend | Python 3.13, FastAPI, Uvicorn |
| Database | MySQL 8 + phpMyAdmin |
| Auth | JWT (python-jose) + bcrypt (password hashing) |
| AI | Google Gemini API ผ่าน `google-genai` SDK (native) |
| Infra | Docker + Docker Compose |

## โครงสร้างโปรเจกต์

```
granite-design-advisor/
├── docker-compose.yml            ← สั่งรัน backend + MySQL + phpMyAdmin พร้อมกัน
├── .env.example                  ← template รหัสผ่าน MySQL (คัดลอกเป็น .env)
├── .gitignore
├── sql/
│   ├── schema.sql                     ← ตาราง users, projects, project_items, granite_products
│   ├── migration_add_catalog_fields.sql  ← เพิ่มคอลัมน์ styles/areas/indoor/rating
│   └── seed_catalog.sql               ← ข้อมูลหิน 24 ชนิดจาก siamtak.com
├── backend/
│   ├── Dockerfile
│   ├── main.py                   ← จุดเริ่มต้น รวม router ทั้งหมด + serve frontend
│   ├── database.py                ← เชื่อมต่อ MySQL ผ่าน SQLAlchemy
│   ├── models.py                  ← ORM models (User, Project, ProjectItem, GraniteProduct)
│   ├── auth_utils.py              ← เข้ารหัสรหัสผ่าน (bcrypt) + JWT token
│   ├── scrape_granite.py          ← scraper ดิบจาก siamtak.com (เขียนลง CSV staging)
│   ├── data/siamtak_granite.csv   ← ข้อมูลดิบสำรอง (ไม่ใช่แหล่งข้อมูลหลักอีกต่อไป)
│   ├── requirements.txt
│   ├── .env.example               ← template GEMINI_API_KEY, JWT_SECRET_KEY
│   └── routers/
│       ├── Auth.py                ← register / login / logout / change-password
│       ├── Users.py               ← /me, /users/{id}, /users, /check-username/{name}
│       ├── Projects.py            ← CRUD โปรเจกต์ + รายการในโปรเจกต์ (ผูกกับผู้ใช้)
│       ├── Catalog.py             ← GET /granite-products (อ่านจาก MySQL)
│       ├── Chat.py                ← AI Chat (Gemini) อ้างอิงข้อมูลหินจาก MySQL
│       └── Estimate.py            ← คำนวณราคา + scrape (ตาม flow เดิม)
└── frontend/
    ├── index.html
    ├── style.css
    ├── app.js                     ← ตรรกะหลักของเว็บ (แคตตาล็อก, compare, AI advisor)
    ├── auth.js                    ← ปลั๊กอิน login/register (inject UI เอง ไม่แก้ HTML)
    ├── projects-api.js            ← ย้าย "โปรเจกต์ของฉัน" จาก localStorage → API จริง
    ├── catalog-api.js             ← โหลดแคตตาล็อกจาก backend แทนข้อมูลฝังในโค้ด
    └── assets/theme-song.mp3
```

## วิธีรัน (ครั้งแรก)

ต้องติดตั้ง **[Docker Desktop](https://www.docker.com/products/docker-desktop)** ก่อน (บน Windows ต้องเปิด WSL2 ก่อนด้วย — รัน `wsl --install` ใน PowerShell ถ้ายังไม่เคยเปิด)

### 1) ตั้งค่า environment variables (2 ไฟล์)

```powershell
copy .env.example .env
copy backend\.env.example backend\.env
```

เปิด **`.env`** (ที่ root) ใส่รหัสผ่าน MySQL เอง (ห้ามเว้นค่า default):
```
MYSQL_ROOT_PASSWORD=<ตั้งเอง>
MYSQL_DATABASE=granite_db
MYSQL_USER=granite_user
MYSQL_PASSWORD=<ตั้งเอง>
```

เปิด **`backend/.env`** ใส่:
```
GEMINI_API_KEY=<คีย์จริงจาก https://aistudio.google.com/apikey>
JWT_SECRET_KEY=<สุ่มด้วย: python -c "import secrets; print(secrets.token_hex(32))">
```

### 2) รัน

```powershell
docker compose up --build
```

รอจนเห็น `Uvicorn running on http://0.0.0.0:8000`

### 3) สร้างตารางฐานข้อมูล (ทำครั้งเดียวตอนติดตั้งใหม่)

เปิด **http://localhost:8080** (phpMyAdmin) → login ด้วย `root` + รหัสผ่านจาก `MYSQL_ROOT_PASSWORD`
→ เลือกฐานข้อมูล `granite_db` → แท็บ **Import** → เลือกไฟล์ทีละไฟล์ตามลำดับนี้ **ห้ามสลับลำดับ**:

1. `sql/schema.sql`
2. `sql/migration_add_catalog_fields.sql`
3. `sql/seed_catalog.sql`

### 4) เปิดเว็บ

**http://localhost:8000**

## ตรวจสอบว่าทำงานถูกต้อง

- มุมขวาบน: จุดสถานะ backend (เขียว = เชื่อมต่อสำเร็จ) และปุ่ม **เข้าสู่ระบบ**
- สมัครสมาชิก → login → แท็บ **AI Chat**: คุยกับ Gemini จริง อ้างอิงหินจาก MySQL พร้อมรูปประกอบคำตอบ
- แท็บ **คำนวณราคา**: ราคาต่อ ตร.ม. ดึงจาก MySQL จริง
- แท็บ **โปรเจกต์ของฉัน**: สร้างโปรเจกต์ บันทึกหิน — ข้อมูลผูกกับบัญชี ไม่ใช่เบราว์เซอร์เครื่องเดียวอีกต่อไป
- Swagger UI (ดู/ทดสอบ API ทั้งหมด): **http://localhost:8000/docs**
- phpMyAdmin (ดูข้อมูลดิบในตาราง): **http://localhost:8080**

## API Endpoints ทั้งหมด

| กลุ่ม | Endpoint | ต้อง Login? |
|---|---|---|
| Auth | `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/change-password` | เฉพาะ logout/change-password |
| Users | `GET /me`, `GET /users/{id}`, `GET /users`, `PUT /users/{id}`, `DELETE /users/{id}` | ✅ ทุกตัว |
| Users | `GET /check-username/{name}` | ❌ |
| Projects | `POST /projects`, `GET /projects`, `GET/DELETE /projects/{id}` | ✅ ทุกตัว |
| Projects | `POST/DELETE /projects/{id}/items[/{item_id}]` | ✅ |
| Catalog | `GET /granite-products` (กรองด้วย `?color=&style=&area=&material=`), `GET /granite-products/{id}` | ❌ |
| Chat | `POST /chat/completions`, `POST /chat/completions/stream` | ❌ |
| Estimate | `POST /estimate/calculate`, `GET /estimate/products`, `GET /estimate/csv`, `POST /estimate/refresh` | ❌ |
| System | `GET /health` | ❌ |

## ครั้งต่อไปที่จะรัน (ไม่ใช่ครั้งแรกแล้ว)

ไม่ต้องทำซ้ำขั้นตอน import SQL หรือสร้าง `.env` ใหม่ — แค่:

```powershell
docker compose up
```

(ไม่ต้อง `--build` ถ้าไม่ได้แก้โค้ด backend/Dockerfile — จะเร็วกว่าเดิมมาก)

## ถ้าจะย้ายไปรันเครื่องอื่น

1. ติดตั้ง Docker Desktop บนเครื่องใหม่
2. `git clone` repo (ไฟล์ `.env` จะไม่ติดไปด้วยเพราะอยู่ใน `.gitignore` — ต้องสร้างใหม่ตามขั้นตอนที่ 1 ด้านบน)
3. รัน `docker compose up --build` แล้ว import SQL 3 ไฟล์ตามลำดับเหมือนเดิม (ข้อมูลในฐานข้อมูลไม่ได้ติดไปกับโค้ดอัตโนมัติ)

## ปัญหาที่เคยเจอระหว่างพัฒนา (กันเจอซ้ำ)

| อาการ | สาเหตุ | วิธีแก้ |
|---|---|---|
| `API key not valid` ทั้งที่คีย์ถูก | คีย์รูปแบบใหม่ `AQ...` ใช้กับ OpenAI-compatible endpoint ไม่ได้ | ใช้ `google-genai` SDK โดยตรง (แก้ไว้แล้วในโค้ด) |
| `Both GOOGLE_API_KEY and GEMINI_API_KEY are set` | มี env var เก่าค้างในเครื่อง | โค้ดลบ `GOOGLE_API_KEY` ทิ้งอัตโนมัติก่อนสร้าง client แล้ว |
| แก้ `.env` แล้วไม่มีผล | มี environment variable ชื่อเดียวกันค้างอยู่ใน Windows/OS | โค้ดใช้ `load_dotenv(override=True)` บังคับให้ `.env` ชนะเสมอ |
| `models/gemini-2.5-flash is no longer available` | Google ปิดรุ่นเก่าสำหรับผู้ใช้ใหม่ | ใช้ `gemini-3.6-flash` เป็นค่า default แล้ว |
| bcrypt error ตอนสมัครสมาชิก | bcrypt เวอร์ชันใหม่ชนกับ passlib | pin `bcrypt==4.0.1` ไว้ใน requirements.txt แล้ว |
| แชทขึ้น "network error" ห้วนๆ | error จริงเกิดหลัง HTTP headers ส่งไปแล้ว (SSE streaming) | โค้ดจับ error ในนี้แล้วส่งเป็น SSE event แทน |

## หมายเหตุเรื่อง scraper

`scrape_granite.py` มีโครง scraper จริง (requests + BeautifulSoup) แต่ CSS selector เป็นค่าเดา
ต้องปรับให้ตรงกับ HTML จริงของ siamtak.com ก่อนใช้งานจริง — ตอนนี้ scraper เขียนผลลัพธ์ลง CSV
เป็น "staging" เท่านั้น **ไม่ได้อัปเดตตาราง `granite_products` อัตโนมัติ** ต้องคัดกรองและรัน
seed script ใหม่เองถ้าต้องการข้อมูลชุดใหม่เข้า MySQL จริง

## สิ่งที่ยังไม่ได้ทำ (สำหรับใครมาต่อ)

- แก้ CSS selector ใน scraper ให้ scrape จริงได้ (ตอนนี้เป็นแค่โครง)
- Role/Admin สำหรับ User Management (ตอนนี้แก้ไข/ลบได้แค่บัญชีตัวเอง)
- Export PDF ของโปรเจกต์ (มีในเวอร์ชัน localStorage เดิม ยังไม่ได้ย้ายมาเวอร์ชัน API)
- Retry อัตโนมัติเมื่อ Gemini API ตอบ 503 (high demand)

รายละเอียดเปอร์เซ็นต์ความคืบหน้าและแผนงานเต็ม ดูที่ `docs/self-assessment.md`
