-- schema.sql — สร้างตารางทั้งหมดของ Granite Design Advisor (MySQL 8) สำหรับติดตั้งใหม่
-- สร้างอัตโนมัติจาก backend/models.py (รวม role, chat_messages, favorites แล้ว)
-- ติดตั้งใหม่: import ไฟล์นี้ก่อน แล้วค่อย import ข้อมูลหิน (seed) — ไม่ต้องรัน 06/07/08 อีก
-- รันใน phpMyAdmin (localhost:8080) > granite_db > แท็บ Import หรือ SQL

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(50) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	full_name VARCHAR(100), 
	is_active BOOL NOT NULL, 
	`role` VARCHAR(20) NOT NULL DEFAULT 'user', 
	created_at TIMESTAMP NULL DEFAULT now(), 
	updated_at TIMESTAMP NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (username), 
	UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS projects (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	created_at TIMESTAMP NULL DEFAULT now(), 
	updated_at TIMESTAMP NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_items (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	project_id INTEGER NOT NULL, 
	kind ENUM('granite','price','advisor','inspiration') NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	detail JSON, 
	created_at TIMESTAMP NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS granite_products (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	product_title VARCHAR(255) NOT NULL, 
	product_description TEXT, 
	product_price DECIMAL(10, 2) NOT NULL, 
	image_url VARCHAR(500), 
	product_url VARCHAR(500), 
	color VARCHAR(30), 
	material VARCHAR(20), 
	styles JSON, 
	areas JSON, 
	indoor VARCHAR(10), 
	rating JSON, 
	created_at TIMESTAMP NULL DEFAULT now(), 
	updated_at TIMESTAMP NULL DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	`role` VARCHAR(10) NOT NULL, 
	content TEXT NOT NULL, 
	has_image BOOL NOT NULL, 
	products JSON, 
	created_at TIMESTAMP NULL DEFAULT now(), 
	PRIMARY KEY (id)
)CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS favorites (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	created_at TIMESTAMP NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_favorite_user_product UNIQUE (user_id, product_id)
)CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ค้นหาแบบ FULLTEXT (ภาษาอังกฤษ) ที่ /granite-products?q=...
ALTER TABLE granite_products ADD FULLTEXT INDEX idx_fulltext_search (product_title, product_description);

CREATE INDEX ix_chat_messages_user_id ON chat_messages (user_id);
CREATE INDEX ix_favorites_user_id ON favorites (user_id);
CREATE INDEX ix_favorites_product_id ON favorites (product_id);
