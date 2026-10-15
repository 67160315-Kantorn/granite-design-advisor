-- เพิ่มคอลัมน์ role ให้ตาราง users แล้วตั้งแอดมินคนแรก
-- รันใน phpMyAdmin (localhost:8080) > granite_db > แท็บ SQL
ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user';
UPDATE users SET role = 'admin' WHERE username = 'test22';  -- เปลี่ยนเป็น username ของคุณได้
