# ใช้ Python 3.13 แบบ slim (เบากว่า image เต็ม เหมาะกับ production)
FROM python:3.13-slim

WORKDIR /app

# copy แค่ requirements.txt ก่อน แล้ว install — เทคนิคนี้ทำให้ Docker cache layer นี้ไว้
# ครั้งต่อไปที่ build ถ้าไม่ได้แก้ requirements.txt จะไม่ต้อง pip install ใหม่ทุกครั้ง (build เร็วขึ้นมาก)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# copy โค้ดจริงทีหลัง (โค้ดเปลี่ยนบ่อยกว่า dependencies)
COPY backend/ backend/
COPY frontend/ frontend/

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
