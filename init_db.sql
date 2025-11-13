-- Create database
CREATE DATABASE IF NOT EXISTS apas CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE apas;

-- =========================
-- USERS TABLE
-- =========================
DROP TABLE IF EXISTS users;
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  role ENUM('student','instructor','admin') NOT NULL
);

-- =========================
-- RECORDS TABLE
-- =========================
DROP TABLE IF EXISTS records;
CREATE TABLE records (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_name VARCHAR(50) NOT NULL,
  marks INT,
  attendance INT,
  risk_score FLOAT,
  course VARCHAR(50),
  instructor_name VARCHAR(50),
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- DEMO USERS
-- =========================
-- Admins
INSERT INTO users (username, password, role) VALUES
('admin', 'adminpass', 'admin');

-- Instructors
INSERT INTO users (username, password, role) VALUES
('instructor1', 'instructorpass', 'instructor'),
('instructor2', 'instructorpass', 'instructor');

-- Students (for both instructors)
INSERT INTO users (username, password, role) VALUES
('student1', 'studentpass', 'student'),
('student2', 'studentpass', 'student'),
('student3', 'studentpass', 'student'),
('student4', 'studentpass', 'student'),
('student5', 'studentpass', 'student'),
('student6', 'studentpass', 'student'),
('student7', 'studentpass', 'student'),
('student8', 'studentpass', 'student');
