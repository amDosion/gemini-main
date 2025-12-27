-- Migration: Create research_tasks table
-- Date: 2025-12-26
-- Description: 创建 research_tasks 表以支持 Deep Research Agent 功能

-- 创建 research_tasks 表
CREATE TABLE IF NOT EXISTS research_tasks (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    prompt TEXT NOT NULL,
    prompt_hash VARCHAR(64) NOT NULL,
    agent VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    result TEXT,
    error TEXT,
    usage TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 添加索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_research_tasks_user_id ON research_tasks(user_id);

CREATE INDEX IF NOT EXISTS idx_research_tasks_status ON research_tasks(status);

CREATE INDEX IF NOT EXISTS idx_research_tasks_prompt_hash ON research_tasks(prompt_hash);

CREATE INDEX IF NOT EXISTS idx_research_tasks_created_at ON research_tasks(created_at);
