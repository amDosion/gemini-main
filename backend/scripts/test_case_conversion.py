"""
测试 CaseConversionMiddleware 是否正确转换 data 字段内部的键

这个测试不需要调用 AI，只测试中间件的转换逻辑
"""
import sys
sys.path.insert(0, 'backend')

from app.utils.case_converter import to_camel_case, SKIP_VALUE_CONVERSION_FIELDS, snake_to_camel

# ========== 测试1：当前行为（'data' 在 SKIP_VALUE_CONVERSION_FIELDS 中）==========

# 模拟后端返回的响应（snake_case）
backend_response = {
    "success": True,
    "data": {
        "images": [
            {
                "url": "data:image/png;base64,xxx",
                "attachment_id": "test-attachment-id-123",
                "message_id": "test-message-id-456",
                "session_id": "test-session-id-789",
                "user_id": "test-user-id",
                "upload_status": "pending",
                "task_id": "test-task-id",
                "mime_type": "image/png",
                "filename": "edited-test.png",
                "cloud_url": "",
                "created_at": 1234567890
            }
        ],
        "text": "Some text response",
        "thoughts": [{"type": "thinking", "content": "..."}]
    },
    "provider": "google",
    "mode": "image-chat-edit"
}

print("=" * 60)
print("  测试 CaseConversionMiddleware 转换逻辑")
print("=" * 60)

print("\n1. 检查 SKIP_VALUE_CONVERSION_FIELDS 是否包含 'data':")
print(f"   'data' in SKIP_VALUE_CONVERSION_FIELDS: {'data' in SKIP_VALUE_CONVERSION_FIELDS}")

print("\n2. 原始后端响应（snake_case）:")
print(f"   data.images[0] 字段: {list(backend_response['data']['images'][0].keys())}")

print("\n3. 转换后的响应:")
converted = to_camel_case(backend_response)
print(f"   data.images[0] 字段: {list(converted['data']['images'][0].keys())}")

print("\n4. 关键字段检查:")
img = converted['data']['images'][0]

# 检查 camelCase 字段
camel_fields = ['attachmentId', 'messageId', 'sessionId', 'userId', 'uploadStatus', 'taskId', 'mimeType', 'cloudUrl', 'createdAt']
print("\n   camelCase 字段:")
for field in camel_fields:
    value = img.get(field)
    if value is not None:
        print(f"   ✅ {field}: {value}")
    else:
        print(f"   ❌ {field}: 不存在")

# 检查 snake_case 字段
snake_fields = ['attachment_id', 'message_id', 'session_id', 'user_id', 'upload_status', 'task_id', 'mime_type', 'cloud_url', 'created_at']
print("\n   snake_case 字段:")
for field in snake_fields:
    value = img.get(field)
    if value is not None:
        print(f"   ⚠️ {field}: {value} (未转换)")
    else:
        print(f"   ✅ {field}: 不存在 (已转换)")

print("\n" + "=" * 60)
print("  结论")
print("=" * 60)

# 判断结果
has_camel = 'attachmentId' in img
has_snake = 'attachment_id' in img

if has_camel and not has_snake:
    print("\n✅ CaseConversionMiddleware 正确转换了 data 字段内部的键")
    print("   后端返回 snake_case，中间件转换为 camelCase")
elif has_snake and not has_camel:
    print("\n⚠️ CaseConversionMiddleware 未转换 data 字段内部的键")
    print("   原因: 'data' 在 SKIP_VALUE_CONVERSION_FIELDS 中")
    print("   解决方案: 从 SKIP_VALUE_CONVERSION_FIELDS 中移除 'data'")
elif has_camel and has_snake:
    print("\n⚠️ 同时存在两种格式（异常情况）")
else:
    print("\n❌ 两种格式都不存在（异常情况）")

print()

# ========== 测试2：模拟移除 'data' 后的行为 ==========
print("\n" + "=" * 60)
print("  测试2：模拟移除 'data' 后的转换效果")
print("=" * 60)

# 创建一个不包含 'data' 的跳过字段集合
skip_fields_without_data = SKIP_VALUE_CONVERSION_FIELDS - {'data'}

def to_camel_case_without_data_skip(data_obj, skip_fields=None, _current_key=None):
    """模拟移除 'data' 后的转换函数"""
    all_skip_fields = skip_fields_without_data
    if skip_fields:
        all_skip_fields = all_skip_fields | skip_fields
    
    if isinstance(data_obj, dict):
        result = {}
        for k, v in data_obj.items():
            new_key = snake_to_camel(k)
            if k in all_skip_fields or new_key in all_skip_fields:
                result[new_key] = v
            else:
                result[new_key] = to_camel_case_without_data_skip(v, skip_fields, k)
        return result
    elif isinstance(data_obj, list):
        return [to_camel_case_without_data_skip(item, skip_fields, _current_key) for item in data_obj]
    else:
        return data_obj

converted_v2 = to_camel_case_without_data_skip(backend_response)
print(f"\n转换后 data.images[0] 字段: {list(converted_v2['data']['images'][0].keys())}")

img_v2 = converted_v2['data']['images'][0]

# 检查 camelCase 字段
print("\n   camelCase 字段:")
for field in camel_fields:
    value = img_v2.get(field)
    if value is not None:
        print(f"   ✅ {field}: {value}")
    else:
        print(f"   ❌ {field}: 不存在")

# 检查 snake_case 字段
print("\n   snake_case 字段:")
for field in snake_fields:
    value = img_v2.get(field)
    if value is not None:
        print(f"   ⚠️ {field}: {value} (未转换)")
    else:
        print(f"   ✅ {field}: 不存在 (已转换)")

print("\n" + "=" * 60)
print("  结论")
print("=" * 60)
if 'attachmentId' in img_v2 and 'attachment_id' not in img_v2:
    print("\n✅ 移除 'data' 后，所有字段都正确转换为 camelCase")
    print("   建议：从 SKIP_VALUE_CONVERSION_FIELDS 中移除 'data'")
else:
    print("\n❌ 仍有问题，需要进一步调查")

print()
