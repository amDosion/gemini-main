-- Migration: Add priority and retry_count fields to upload_tasks table
-- Date: 2025-12-17
-- Description: 为 upload_tasks 表添加 priority 和 retry_count 字段以支持 Redis 队列

-- 添加 priority 字段（优先级：high/normal/low）
ALTER TABLE upload_tasks ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'normal';

-- 添加 retry_count 字段（重试次数）
ALTER TABLE upload_tasks ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- 为现有记录设置默认值（priority）
UPDATE upload_tasks SET priority = 'normal' WHERE priority IS NULL;

-- 为现有记录设置默认值（retry_count）
UPDATE upload_tasks SET retry_count = 0 WHERE retry_count IS NULL;

-- 添加索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_upload_tasks_priority ON upload_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_upload_tasks_status ON upload_tasks(status);
