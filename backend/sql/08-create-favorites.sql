-- ตารางรายการโปรด (ปกติ backend สร้างให้เองตอนเริ่มทำงาน — ใช้ไฟล์นี้เฉพาะเมื่อสร้างอัตโนมัติไม่สำเร็จ)
-- รันใน phpMyAdmin (localhost:8080) > granite_db > แท็บ SQL
CREATE TABLE IF NOT EXISTS favorites (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  product_id INT NOT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_favorite_user_product (user_id, product_id),
  KEY ix_favorites_user_id (user_id),
  KEY ix_favorites_product_id (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
