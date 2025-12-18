-- ================================================================
-- 删除并重建 upload_tasks 表（开发环境用）
-- 警告：此操作会删除 upload_tasks 表中的所有数据！
-- 日期: 2025-12-17
-- ================================================================

-- 步骤 1: 删除旧表（包括所有数据）
DROP TABLE IF EXISTS upload_tasks CASCADE;

-- 步骤 2: 重新创建表（带新字段）
CREATE TABLE upload_tasks (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR,
    message_id VARCHAR,
    attachment_id VARCHAR,
    source_url VARCHAR,
    source_file_path VARCHAR,
    target_url VARCHAR,
    filename VARCHAR NOT NULL,
    storage_id VARCHAR,
    priority VARCHAR(20) DEFAULT 'normal',
    retry_count INTEGER DEFAULT 0,
    status VARCHAR NOT NULL DEFAULT 'pending',
    error_message VARCHAR,
    created_at BIGINT NOT NULL,
    completed_at BIGINT
);

-- 步骤 3: 创建索引
CREATE INDEX IF NOT EXISTS idx_upload_tasks_status ON upload_tasks(status);
CREATE INDEX IF NOT EXISTS idx_upload_tasks_priority ON upload_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_upload_tasks_session_id ON upload_tasks(session_id);

-- 步骤 4: 验证表结构
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'upload_tasks'
ORDER BY ordinal_position;
