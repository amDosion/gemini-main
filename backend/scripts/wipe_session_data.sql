-- Sprint 3 / Phase C-1 — 一次性 wipe 脚本
--
-- 背景: 切换到 per-mode 完全独立 session(方案 1)后, 旧数据中存在
-- "1 个 chat_sessions.id 跨多个 mode 的 message_index" 的混合状态。用户
-- 明确授权"数据库中的会话记录直接删除, 无需迁移", 故此脚本清空全部
-- session 相关数据, 让用户从 0 开始。
--
-- 用法:
--   docker compose exec backend psql -U <user> -d <db> -f /app/scripts/wipe_session_data.sql
-- 或:
--   PGPASSWORD=*** psql -h <host> -U <user> -d <db> -f backend/scripts/wipe_session_data.sql
--
-- 删除顺序按外键依赖逆序: 子表先于父表清空, 避免 FK violation。
-- 包裹在事务中, 失败可整体回滚。

BEGIN;

-- 1. message_attachments(复合 PK: id+message_id, 关联 messages_* / message_index)
DELETE FROM message_attachments;

-- 2. upload_tasks(关联 attachment_id; 清空避免孤儿)
DELETE FROM upload_tasks;

-- 3. message_history_states + session_history_preferences(关联 session/message)
DELETE FROM message_history_states;
DELETE FROM session_history_preferences;

-- 4. message_index(消息路由表, 关联 chat_sessions)
DELETE FROM message_index;

-- 5. 9 张 mode 分表(按 v3 schema)
DELETE FROM messages_chat;
DELETE FROM messages_image_gen;
DELETE FROM messages_video_gen;
DELETE FROM messages_image_chat_edit;
DELETE FROM messages_image_mask_edit;
DELETE FROM messages_image_inpainting;
DELETE FROM messages_image_background_edit;
DELETE FROM messages_image_recontext;
DELETE FROM messages_generic;

-- 6. chat_sessions 元数据
DELETE FROM chat_sessions;

COMMIT;

-- 验证 row count = 0(取消注释以输出):
-- SELECT 'chat_sessions' AS tbl, COUNT(*) FROM chat_sessions
-- UNION ALL SELECT 'message_index', COUNT(*) FROM message_index
-- UNION ALL SELECT 'messages_chat', COUNT(*) FROM messages_chat
-- UNION ALL SELECT 'messages_image_gen', COUNT(*) FROM messages_image_gen
-- UNION ALL SELECT 'messages_video_gen', COUNT(*) FROM messages_video_gen
-- UNION ALL SELECT 'messages_image_chat_edit', COUNT(*) FROM messages_image_chat_edit
-- UNION ALL SELECT 'messages_image_mask_edit', COUNT(*) FROM messages_image_mask_edit
-- UNION ALL SELECT 'messages_image_inpainting', COUNT(*) FROM messages_image_inpainting
-- UNION ALL SELECT 'messages_image_background_edit', COUNT(*) FROM messages_image_background_edit
-- UNION ALL SELECT 'messages_image_recontext', COUNT(*) FROM messages_image_recontext
-- UNION ALL SELECT 'messages_generic', COUNT(*) FROM messages_generic
-- UNION ALL SELECT 'message_attachments', COUNT(*) FROM message_attachments
-- UNION ALL SELECT 'message_history_states', COUNT(*) FROM message_history_states
-- UNION ALL SELECT 'session_history_preferences', COUNT(*) FROM session_history_preferences
-- UNION ALL SELECT 'upload_tasks', COUNT(*) FROM upload_tasks;
