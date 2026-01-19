-- 迁移脚本：为 upload_tasks 表添加新的 source 字段
-- 日期: 2026-01-18
-- 说明: 支持 AI 返回 URL 和附件复用功能

-- 添加新 source 字段
ALTER TABLE upload_tasks ADD COLUMN IF NOT EXISTS source_ai_url TEXT;
ALTER TABLE upload_tasks ADD COLUMN IF NOT EXISTS source_attachment_id VARCHAR(255);

-- 添加索引（提高查询性能）
CREATE INDEX IF NOT EXISTS idx_upload_tasks_source_ai_url ON upload_tasks(source_ai_url);
CREATE INDEX IF NOT EXISTS idx_upload_tasks_source_attachment_id ON upload_tasks(source_attachment_id);

-- 验证迁移
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'upload_tasks' 
-- AND column_name IN ('source_ai_url', 'source_attachment_id');
