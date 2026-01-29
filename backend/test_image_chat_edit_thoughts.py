#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证 image-chat-edit 模式的 thoughts 功能

测试流程：
1. 使用 image-gen 模式生成图片
2. 使用 image-chat-edit 模式编辑图片，启用 enableThinking
3. 检查响应中是否包含 thoughts 数据

运行方式：
    python test_image_chat_edit_thoughts.py

需要先启动后端服务：
    cd backend && python main.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import asyncio
import aiohttp
import json
import sys
import uuid
from datetime import datetime

# 配置
BASE_URL = "http://localhost:8000"
PROVIDER = "google"

# 测试使用的模型
IMAGE_GEN_MODEL = "imagen-3.0-generate-001"  # 图片生成模型
# IMAGE_CHAT_EDIT_MODEL = "gemini-3-imagen"    # Chat Edit 模型（需要支持 thinking）
IMAGE_CHAT_EDIT_MODEL = "gemini-3-flash-preview-001"  # 使用 Gemini 3 模型


async def get_auth_token(session: aiohttp.ClientSession) -> str:
    """获取认证 token（假设使用测试用户）"""
    # 这里需要根据实际的认证方式获取 token
    # 如果服务没有开启认证，可以返回空字符串
    return ""


async def test_image_gen(session: aiohttp.ClientSession, token: str) -> dict:
    """测试图片生成"""
    print("\n" + "=" * 60)
    print("步骤 1: 测试 image-gen 模式生成图片")
    print("=" * 60)

    # 生成唯一 ID
    session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    request_data = {
        "modelId": IMAGE_GEN_MODEL,
        "prompt": "A cute cat wearing a hat, digital art style",
        "options": {
            "numberOfImages": 1,
            "aspectRatio": "1:1",
            "sessionId": session_id,
            "message_id": message_id
        }
    }

    print(f"请求数据: {json.dumps(request_data, indent=2, ensure_ascii=False)}")

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with session.post(
            f"{BASE_URL}/api/modes/{PROVIDER}/image-gen",
            json=request_data,
            headers=headers
        ) as response:
            result = await response.json()

            print(f"\n响应状态码: {response.status}")

            if response.status == 200 and result.get("success"):
                print("✅ 图片生成成功!")
                data = result.get("data", {})

                # 提取图片信息
                images = data if isinstance(data, list) else data.get("images", [])
                if images:
                    first_image = images[0]
                    print(f"  - attachmentId: {first_image.get('attachmentId', 'N/A')}")
                    print(f"  - url 类型: {'Base64' if first_image.get('url', '').startswith('data:') else 'HTTP URL'}")
                    print(f"  - mimeType: {first_image.get('mimeType', 'N/A')}")

                    return {
                        "success": True,
                        "image_url": first_image.get("url"),
                        "attachment_id": first_image.get("attachmentId"),
                        "session_id": session_id,
                        "message_id": message_id
                    }
            else:
                print(f"❌ 图片生成失败: {result}")
                return {"success": False, "error": result}

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return {"success": False, "error": str(e)}


async def test_image_chat_edit(
    session: aiohttp.ClientSession,
    token: str,
    image_url: str,
    attachment_id: str = None,
    session_id: str = None
) -> dict:
    """测试 image-chat-edit 模式（启用 thinking）"""
    print("\n" + "=" * 60)
    print("步骤 2: 测试 image-chat-edit 模式（启用 enableThinking）")
    print("=" * 60)

    # 使用新的 message_id
    message_id = str(uuid.uuid4())
    session_id = session_id or str(uuid.uuid4())

    # 构建附件
    attachments = []
    if image_url:
        attachments.append({
            "id": attachment_id or str(uuid.uuid4()),
            "mimeType": "image/png",
            "name": "generated_image.png",
            "url": image_url,
        })

    request_data = {
        "modelId": IMAGE_CHAT_EDIT_MODEL,
        "prompt": "请给这只猫加上一副太阳眼镜",
        "attachments": attachments,
        "options": {
            "enableThinking": True,  # ✅ 关键：启用思考过程
            "numberOfImages": 1,
            "sessionId": session_id,
            "message_id": message_id,
            "editMode": "EDIT_MODE_DEFAULT"
        }
    }

    print(f"请求数据:")
    print(f"  - modelId: {request_data['modelId']}")
    print(f"  - prompt: {request_data['prompt']}")
    print(f"  - enableThinking: {request_data['options']['enableThinking']}")
    print(f"  - attachments: {len(attachments)} 个")

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with session.post(
            f"{BASE_URL}/api/modes/{PROVIDER}/image-chat-edit",
            json=request_data,
            headers=headers
        ) as response:
            result = await response.json()

            print(f"\n响应状态码: {response.status}")

            if response.status == 200 and result.get("success"):
                print("✅ 图片编辑成功!")
                data = result.get("data", {})

                # 检查是否包含 thoughts
                print("\n检查响应中的 thoughts 字段:")

                # 检查顶层 thoughts
                if "thoughts" in data:
                    thoughts = data["thoughts"]
                    print(f"  ✅ 找到顶层 thoughts: {len(thoughts) if isinstance(thoughts, list) else 'N/A'} 条")
                    if thoughts:
                        print(f"  思考内容预览: {str(thoughts)[:200]}...")
                else:
                    print("  ❌ 未找到顶层 thoughts")

                # 检查 images 中的 thoughts
                images = data if isinstance(data, list) else data.get("images", [])
                if images:
                    for idx, img in enumerate(images):
                        if isinstance(img, dict):
                            if "thoughts" in img:
                                print(f"  ✅ 图片 {idx+1} 包含 thoughts: {img['thoughts'][:100] if img['thoughts'] else 'empty'}...")
                            else:
                                print(f"  ❌ 图片 {idx+1} 未包含 thoughts")

                            if "text" in img:
                                print(f"  ✅ 图片 {idx+1} 包含 text: {img['text'][:100] if img['text'] else 'empty'}...")

                # 打印完整响应（调试用）
                print("\n完整响应数据:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])

                return {"success": True, "data": data}
            else:
                print(f"❌ 图片编辑失败: {result}")
                return {"success": False, "error": result}

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


async def test_with_sample_image(session: aiohttp.ClientSession, token: str) -> dict:
    """使用示例图片直接测试 image-chat-edit"""
    print("\n" + "=" * 60)
    print("备选测试: 使用 Base64 示例图片测试 image-chat-edit")
    print("=" * 60)

    # 使用一个最小的测试图片（1x1 红色像素 PNG）
    # 这是一个有效的 PNG 图片
    sample_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

    return await test_image_chat_edit(
        session=session,
        token=token,
        image_url=sample_base64,
        attachment_id=str(uuid.uuid4())
    )


async def main():
    """主测试流程"""
    print("=" * 60)
    print("Image Chat Edit Thoughts 功能测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"后端地址: {BASE_URL}")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        # 获取认证 token
        token = await get_auth_token(session)

        # 方式 1：先生成图片，再编辑
        print("\n>>> 方式 1：生成图片后编辑 <<<")
        gen_result = await test_image_gen(session, token)

        if gen_result.get("success"):
            # 使用生成的图片进行 chat edit
            await test_image_chat_edit(
                session=session,
                token=token,
                image_url=gen_result["image_url"],
                attachment_id=gen_result.get("attachment_id"),
                session_id=gen_result.get("session_id")
            )
        else:
            print("\n⚠️ 图片生成失败，尝试使用示例图片...")
            await test_with_sample_image(session, token)

        # 方式 2：直接使用示例图片测试（可选）
        # print("\n>>> 方式 2：使用示例图片直接测试 <<<")
        # await test_with_sample_image(session, token)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
