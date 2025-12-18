-- ================================================================
-- 手动数据库迁移脚本
-- 日期: 2025-12-17
-- 说明: 为 upload_tasks 表添加 priority 和 retry_count 字段
-- ================================================================

-- 步骤 1: 添加 priority 字段
ALTER TABLE upload_tasks ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'normal';

-- 步骤 2: 添加 retry_count 字段
ALTER TABLE upload_tasks ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- 步骤 3: 为现有记录设置默认值
UPDATE upload_tasks SET priority = 'normal' WHERE priority IS NULL;
UPDATE upload_tasks SET retry_count = 0 WHERE retry_count IS NULL;

-- 步骤 4: 添加索引（可选，提升查询性能）
CREATE INDEX IF NOT EXISTS idx_upload_tasks_priority ON upload_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_upload_tasks_status ON upload_tasks(status);

-- 步骤 5: 验证迁移
SELECT
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'upload_tasks'
  AND column_name IN ('priority', 'retry_count')
ORDER BY column_name;
