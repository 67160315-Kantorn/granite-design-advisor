# Technology Stack — Granite Design Advisor

![Technology Stack](./images/granite-technology-stack.png)

## ภาพรวม

Stack แบ่งเป็น 5 ชั้นตามหน้าที่ ตั้งแต่ส่วนที่ผู้ใช้เห็น (frontend) ลงไปถึงโครงสร้างพื้นฐาน (DevOps)

## รายละเอียดแต่ละชั้น

### 01 — Frontend / Client
| เทคโนโลยี | ใช้ทำอะไร |
|---|---|
| HTML5 / CSS3 | โครงสร้างและดีไซน์หน้าเว็บ |
| JavaScript (ES6+) | ตรรกะฝั่ง client ทั้งหมด ไม่ใช้ framework |
| Fetch API + SSE | เรียก backend API และรับ AI Chat แบบ streaming (Server-Sent Events) |
| jsPDF | สร้างไฟล์ PDF ใบประมาณราคาให้ดาวน์โหลด |

### 02 — Backend / Application
| เทคโนโลยี | ใช้ทำอะไร |
|---|---|
| Python 3.13 | ภาษาหลักฝั่ง backend |
| FastAPI | Web framework สำหรับสร้าง REST API |
| Uvicorn | ASGI server ที่รัน FastAPI |
| Pydantic | validate ข้อมูล request/response |
| APScheduler | ตั้งเวลารัน scraper อัตโนมัติทุกวัน |

### 03 — AI & Data Collection
| เทคโนโลยี | ใช้ทำอะไร |
|---|---|
| Google Gemini API | โมเดล AI ที่ขับเคลื่อนแชทบอทแนะนำหิน (`gemini-3.6-flash`) |
| google-genai SDK | เรียก Gemini API โดยตรง (native SDK ไม่ผ่าน OpenAI-compatible endpoint) |
| BeautifulSoup4 / Requests | เตรียมไว้สำหรับ scrape ข้อมูลหินจาก siamtak.com |

### 04 — Data Layer
| เทคโนโลยี | ใช้ทำอะไร | สถานะ |
|---|---|---|
| CSV | ข้อมูลหินตั้งต้น 24 ชนิด | ✅ ใช้งานจริงตอนนี้ |
| MySQL | ฐานข้อมูลเชิงสัมพันธ์ | 🔜 วางแผนไว้ ยังไม่ได้ implement |
| phpMyAdmin | เครื่องมือจัดการฐานข้อมูล | 🔜 วางแผนไว้ ยังไม่ได้ implement |

### 05 — DevOps & Infrastructure
| เทคโนโลยี | ใช้ทำอะไร |
|---|---|
| Git & GitHub | Version control และเก็บ source code |
| Docker / Docker Compose | 🔜 วางแผนไว้สำหรับ containerize backend + MySQL + phpMyAdmin |
| Render | Cloud hosting (free tier) — deploy backend และ frontend จาก server เดียวกัน |
| VS Code | Code editor หลักที่ใช้พัฒนา |

## เหตุผลที่เลือกใช้แต่ละเทคโนโลยี

- **FastAPI** แทนที่จะใช้ Flask หรือ Django — เพราะรองรับ async ในตัว, สร้าง API docs อัตโนมัติ (`/docs`), และ validate ข้อมูลด้วย Pydantic ได้ในตัว เหมาะกับโปรเจกต์ที่ต้องเรียก external API (Gemini) แบบ streaming
- **google-genai SDK** แทนที่จะใช้ `openai` library ยิงผ่าน OpenAI-compatible endpoint — เพราะ Gemini API key รูปแบบใหม่ (Auth key ขึ้นต้นด้วย `AQ.`) ใช้กับ OpenAI-compatible endpoint ไม่ได้ ต้องใช้ native SDK เท่านั้น
- **Render** แทนที่จะใช้ Railway หรือ Fly.io — เพราะเป็นเจ้าเดียวที่ยังมี free tier จริงโดยไม่ต้องผูกบัตรเครดิต (ข้อมูล ณ กลางปี 2026)
- **ไม่ใช้ frontend framework** (React/Vue) — เพราะขนาดโปรเจกต์ไม่ซับซ้อนพอที่จะคุ้มค่ากับ overhead ของ framework จึงเลือกใช้ vanilla JavaScript เพื่อให้ deploy ง่าย ไม่ต้อง build step
