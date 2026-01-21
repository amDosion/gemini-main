-- 迁移脚本：将 personas 表重命名为 user_ai_personas
-- 日期: 2026-01-18
-- 说明: 重构表名以更清晰地表示用户AI角色配置

-- 1. 重命名表（如果存在）
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'personas') THEN
        ALTER TABLE personas RENAME TO user_ai_personas;
        RAISE NOTICE '表 personas 已重命名为 user_ai_personas';
    ELSE
        RAISE NOTICE '表 personas 不存在，跳过重命名';
    END IF;
END $$;

-- 2. 重命名主键约束（如果存在）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'personas_pkey' 
        AND conrelid = 'user_ai_personas'::regclass
    ) THEN
        ALTER TABLE user_ai_personas RENAME CONSTRAINT personas_pkey TO user_ai_personas_pkey;
        RAISE NOTICE '主键约束 personas_pkey 已重命名为 user_ai_personas_pkey';
    END IF;
END $$;

-- 3. 重命名索引（如果存在旧的索引名）
-- 注意：SQLAlchemy 自动生成的索引名格式为 ix_<tablename>_<columnname>
DO $$
DECLARE
    idx_record RECORD;
BEGIN
    -- 查找所有以 'ix_personas_' 开头的索引并重命名
    FOR idx_record IN 
        SELECT indexname 
        FROM pg_indexes 
        WHERE schemaname = 'public' 
        AND indexname LIKE 'ix_personas_%'
    LOOP
        EXECUTE format('ALTER INDEX %I RENAME TO %I', 
            idx_record.indexname, 
            replace(idx_record.indexname, 'ix_personas_', 'ix_user_ai_personas_'));
        RAISE NOTICE '索引 % 已重命名为 %', 
            idx_record.indexname, 
            replace(idx_record.indexname, 'ix_personas_', 'ix_user_ai_personas_');
    END LOOP;
    
    -- 检查并更新分类索引（如果存在，需要删除后重新创建以更新表名引用）
    IF EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE schemaname = 'public'
        AND indexname = 'idx_persona_user_category'
        AND tablename = 'user_ai_personas'
    ) THEN
        RAISE NOTICE '分类索引 idx_persona_user_category 已存在且表名已更新';
    ELSIF EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE schemaname = 'public'
        AND indexname = 'idx_persona_user_category'
        AND tablename = 'personas'
    ) THEN
        -- 如果索引还在旧表上，删除后会在 optimize_database_indexes.sql 中重新创建
        DROP INDEX IF EXISTS idx_persona_user_category;
        RAISE NOTICE '已删除旧的分类索引，将在 optimize_database_indexes.sql 中重新创建';
    END IF;
END $$;

-- 4. 验证迁移结果
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_ai_personas') THEN
        RAISE NOTICE '✅ 迁移成功：表 user_ai_personas 已存在';
    ELSE
        RAISE WARNING '⚠️ 迁移后表 user_ai_personas 不存在，可能需要手动创建';
    END IF;
END $$;

-- 验证查询（可选，取消注释以执行）
-- SELECT table_name, column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'user_ai_personas' 
-- ORDER BY ordinal_position;
