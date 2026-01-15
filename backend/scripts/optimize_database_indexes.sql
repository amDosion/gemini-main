-- ============================================================================
-- 数据库索引优化脚本
-- ============================================================================
-- 
-- 用途：创建缺失的复合索引，优化查询性能
-- 执行方式：在 PostgreSQL 中直接执行此脚本
-- 
-- 注意：这些索引会占用额外存储空间，但能显著提升查询性能
-- ============================================================================

-- ============================================================================
-- 1. MessageIndex 表索引优化
-- ============================================================================

-- 主排序索引：按会话+顺序查询（最常用）
-- 用于：获取会话的所有消息（按顺序）
CREATE INDEX IF NOT EXISTS idx_message_index_session_seq 
ON message_index(session_id, seq);

-- 用户+会话索引：优化用户范围内的会话查询
CREATE INDEX IF NOT EXISTS idx_message_index_user_session 
ON message_index(user_id, session_id, seq);

-- 模式过滤索引：按会话+模式+顺序查询
-- 用于：获取特定模式的消息（如只获取 chat 模式的消息）
CREATE INDEX IF NOT EXISTS idx_message_index_session_mode_seq 
ON message_index(session_id, mode, seq);

-- ============================================================================
-- 2. ChatSession 表索引优化
-- ============================================================================

-- 用户+创建时间索引：优化会话列表查询（按时间倒序）
-- 用于：获取用户的所有会话，按最新优先排序
CREATE INDEX IF NOT EXISTS idx_chat_session_user_created 
ON chat_sessions(user_id, created_at DESC);

-- 用户+模式索引：优化按模式筛选会话
CREATE INDEX IF NOT EXISTS idx_chat_session_user_mode 
ON chat_sessions(user_id, mode);

-- ============================================================================
-- 3. MessagesChat 表索引优化
-- ============================================================================

-- 用户+会话+时间索引：优化消息历史查询
CREATE INDEX IF NOT EXISTS idx_messages_chat_user_session_created 
ON messages_chat(user_id, session_id, created_at DESC);

-- ============================================================================
-- 4. MessageAttachment 表索引优化
-- ============================================================================

-- 消息+用户索引：优化附件查询
CREATE INDEX IF NOT EXISTS idx_message_attachment_message_user 
ON message_attachments(message_id, user_id);

-- 会话+用户索引：优化会话附件查询
CREATE INDEX IF NOT EXISTS idx_message_attachment_session_user 
ON message_attachments(session_id, user_id);

-- ============================================================================
-- 5. Persona 表索引优化
-- ============================================================================

-- 用户+分类索引：优化 Persona 分类查询
CREATE INDEX IF NOT EXISTS idx_persona_user_category 
ON personas(user_id, category);

-- ============================================================================
-- 6. ConfigProfile 表索引优化
-- ============================================================================

-- 用户+激活状态索引：优化激活配置查询
CREATE INDEX IF NOT EXISTS idx_config_profile_user_active 
ON config_profiles(user_id, is_active);

-- ============================================================================
-- 7. StorageConfig 表索引优化
-- ============================================================================

-- 用户索引：优化存储配置查询（已有 user_id 索引，但可以添加复合索引）
-- 注意：如果已有 user_id 索引，此索引可能冗余

-- ============================================================================
-- 8. LoginAttempt 表索引优化（防暴力破解）
-- ============================================================================

-- IP+时间索引：优化 IP 级别失败次数查询
CREATE INDEX IF NOT EXISTS idx_login_attempt_ip_created 
ON login_attempts(ip_address, created_at DESC);

-- 邮箱+时间索引：优化邮箱级别失败次数查询
CREATE INDEX IF NOT EXISTS idx_login_attempt_email_created 
ON login_attempts(email, created_at DESC) 
WHERE email IS NOT NULL;

-- ============================================================================
-- 9. IPLoginHistory 表索引优化
-- ============================================================================

-- 用户+时间索引：优化用户登录历史查询
CREATE INDEX IF NOT EXISTS idx_ip_login_history_user_created 
ON ip_login_history(user_id, created_at DESC);

-- IP+时间索引：优化 IP 登录历史查询
CREATE INDEX IF NOT EXISTS idx_ip_login_history_ip_created 
ON ip_login_history(ip_address, created_at DESC);

-- ============================================================================
-- 索引使用说明
-- ============================================================================
-- 
-- 1. 查看索引使用情况：
--    SELECT * FROM pg_stat_user_indexes WHERE schemaname = 'public';
-- 
-- 2. 分析查询计划：
--    EXPLAIN ANALYZE SELECT * FROM message_index WHERE session_id = 'xxx' ORDER BY seq;
-- 
-- 3. 删除未使用的索引（谨慎操作）：
--    DROP INDEX IF EXISTS index_name;
-- 
-- ============================================================================
