-- สร้างตารางเก็บประวัติ AI Chat (ถ้ายังไม่มี) — รันใน phpMyAdmin > granite_db > แท็บ SQL
CREATE TABLE IF NOT EXISTS chat_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  role VARCHAR(10) NOT NULL,
  content TEXT NOT NULL,
  has_image TINYINT(1) NOT NULL DEFAULT 0,
  products JSON NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_chat_messages_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
