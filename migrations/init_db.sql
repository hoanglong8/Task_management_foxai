-- FOXAI Task Management Platform — Initial Schema
-- Run: psql -U foxai -d foxai_tasks -f migrations/init_db.sql

-- Users
CREATE TYPE user_role AS ENUM ('admin', 'manager', 'member');

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    role            user_role NOT NULL DEFAULT 'member',
    telegram_id     VARCHAR(50) UNIQUE,
    zalo_id         VARCHAR(50) UNIQUE,
    facebook_id     VARCHAR(50) UNIQUE,
    whatsapp_phone  VARCHAR(20) UNIQUE,
    department      VARCHAR(50),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_telegram ON users(telegram_id);
CREATE INDEX idx_users_zalo ON users(zalo_id);

-- Tasks
CREATE TYPE task_status AS ENUM ('pending', 'in_progress', 'completed');

CREATE TABLE IF NOT EXISTS tasks (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    project     VARCHAR(100),
    notes       TEXT,
    owner_id    INTEGER REFERENCES users(id),
    owner_name  VARCHAR(100),
    created_by  INTEGER REFERENCES users(id),
    deadline    DATE,
    status      task_status NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_owner ON tasks(owner_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_deadline ON tasks(deadline);
CREATE INDEX idx_tasks_project ON tasks(project);

-- Task History (audit log)
CREATE TABLE IF NOT EXISTS task_history (
    id              SERIAL PRIMARY KEY,
    task_id         INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    changed_by      INTEGER REFERENCES users(id),
    changed_by_name VARCHAR(100),
    field_name      VARCHAR(50) NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    changed_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_task_history_task ON task_history(task_id);

-- Platform Notifications
CREATE TABLE IF NOT EXISTS platform_notifications (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    task_id      INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    platform     VARCHAR(20) NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    sent_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    status       VARCHAR(20) NOT NULL DEFAULT 'sent'
);

CREATE INDEX idx_notifications_user ON platform_notifications(user_id);
