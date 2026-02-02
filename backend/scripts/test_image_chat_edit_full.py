"""
端到端测试 image-chat-edit 模式

严格按照前端流程测试：
1. 登录获取 JWT token (模拟 useAuth)
2. 使用 Authorization Bearer header (模拟 UnifiedProviderClient)
3. 使用 camelCase 参数 (中间件自动转换为 snake_case)
4. 包含完整的高级参数 (模拟 ChatEditInputArea + useControlsState)
5. 正确的附件格式 (模拟 ImageEditHandlerClass)
6. 支持 enhancePrompt 提示词增强功能

测试流程：
- ImageEditView.tsx → ChatEditInputArea.tsx → ImageEditHandlerClass.ts
- → llmService.editImage() → UnifiedProviderClient.editImage()
- → /api/modes/google/image-chat-edit

使用方法：
    python backend/scripts/test_image_chat_edit_full.py
    python backend/scripts/test_image_chat_edit_full.py --enhance  # 测试提示词增强
"""
import requests
import json
import base64
import uuid
import time
import sys
import argparse

# ==================== 配置 ====================
BASE_URL = "http://localhost:21574"
LOGIN_EMAIL = "121802744@qq.com"
LOGIN_PASSWORD = "chuan*1127"

# 必须使用这个模型进行 image-chat-edit 测试
MODEL_ID = "gemini-3-pro-image-preview"

# 测试图片 URL（使用一个稳定的公开图片）
TEST_IMAGE_URL = "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"


def log_step(step: str, message: str):
    """打印步骤日志"""
    print(f"\n{'='*60}")
    print(f"[{step}] {message}")
    print('='*60)


def log_info(message: str):
    """打印信息日志"""
    print(f"  ℹ️  {message}")


def log_success(message: str):
    """打印成功日志"""
    print(f"  ✅ {message}")


def log_error(message: str):
    """打印错误日志"""
    print(f"  ❌ {message}")


def log_warning(message: str):
    """打印警告日志"""
    print(f"  ⚠️  {message}")


def log_debug(key: str, value):
    """打印调试信息"""
    if isinstance(value, str) and len(value) > 100:
        # 截断长字符串
        if value.startswith('data:'):
            print(f"      {key}: [Base64 Data URL, 长度: {len(value)} 字符]")
        else:
            print(f"      {key}: {value[:100]}...")
    else:
        print(f"      {key}: {value}")


# ==================== Step 1: 登录 ====================
def step1_login() -> str:
    """
    模拟前端登录流程 (useAuth.ts → auth.ts)
    
    前端调用: POST /api/auth/login
    请求体: { email, password }
    响应: { accessToken, user }
    """
    log_step("Step 1", "登录获取 JWT Token")
    
    login_url = f"{BASE_URL}/api/auth/login"
    login_payload = {
        "email": LOGIN_EMAIL,
        "password": LOGIN_PASSWORD
    }
    
    log_info(f"请求 URL: {login_url}")
    log_info(f"请求体: {json.dumps(login_payload, indent=2)}")
    
    try:
        response = requests.post(
            login_url,
            json=login_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        log_info(f"响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            log_error(f"登录失败: {response.text}")
            sys.exit(1)
        
        data = response.json()
        token = data.get("accessToken")
        user = data.get("user", {})
        
        if not token:
            log_error("响应中没有 accessToken")
            sys.exit(1)
        
        log_success(f"登录成功!")
        log_debug("accessToken", token[:50] + "...")
        log_debug("user.id", user.get("id", "N/A"))
        log_debug("user.email", user.get("email", "N/A"))
        
        return token
        
    except Exception as e:
        log_error(f"登录异常: {e}")
        sys.exit(1)


# ==================== Step 2: 下载测试图片 ====================
def step2_download_test_image() -> tuple:
    """
    下载测试图片并转换为 Base64
    
    模拟前端用户上传图片后的处理流程
    """
    log_step("Step 2", "下载测试图片并转换为 Base64")
    
    log_info(f"图片 URL: {TEST_IMAGE_URL}")
    
    try:
        response = requests.get(TEST_IMAGE_URL, timeout=30)
        
        if response.status_code != 200:
            log_error(f"下载失败: {response.status_code}")
            sys.exit(1)
        
        image_bytes = response.content
        content_type = response.headers.get("Content-Type", "image/jpeg")
        
        # 转换为 Base64 Data URL（模拟前端 FileReader.readAsDataURL）
        base64_str = base64.b64encode(image_bytes).decode('utf-8')
        data_url = f"data:{content_type};base64,{base64_str}"
        
        log_success(f"下载成功!")
        log_debug("图片大小", f"{len(image_bytes)} bytes")
        log_debug("Content-Type", content_type)
        log_debug("Base64 长度", f"{len(base64_str)} 字符")
        log_debug("Data URL 长度", f"{len(data_url)} 字符")
        
        return data_url, content_type
        
    except Exception as e:
        log_error(f"下载异常: {e}")
        sys.exit(1)


# ==================== Step 3: 构建请求 ====================
def step3_build_request(image_data_url: str, mime_type: str, enhance_prompt: bool = False) -> dict:
    """
    构建 image-chat-edit 请求
    
    严格按照前端流程：
    1. ChatEditInputArea.handleGenerate() 构建 ChatOptions
    2. ImageEditHandlerClass.doExecute() 构建 referenceImages
    3. llmService.editImage() 调用 UnifiedProviderClient
    4. UnifiedProviderClient.editImage() 构建最终请求体
    
    注意：使用 camelCase（中间件会自动转换为 snake_case）
    
    Args:
        image_data_url: Base64 图片数据 URL
        mime_type: 图片 MIME 类型
        enhance_prompt: 是否启用提示词增强
    """
    log_step("Step 3", "构建请求体（模拟前端完整流程）")
    
    # 生成 IDs（模拟前端生成的 UUID）
    attachment_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    
    log_info("生成的 IDs:")
    log_debug("attachmentId", attachment_id)
    log_debug("sessionId", session_id)
    log_debug("messageId", message_id)
    
    # ==================== 构建附件 ====================
    # 模拟 ImageEditHandlerClass.doExecute() 中的附件处理
    # 前端传递完整的 Attachment 对象
    attachment = {
        "id": attachment_id,
        "name": "test-image.jpg",
        "mimeType": mime_type,
        "url": image_data_url,  # Base64 Data URL
    }
    
    log_info("附件结构:")
    log_debug("id", attachment["id"])
    log_debug("name", attachment["name"])
    log_debug("mimeType", attachment["mimeType"])
    log_debug("url", attachment["url"])
    
    # ==================== 构建 Options ====================
    # 模拟 ChatEditInputArea.handleGenerate() 中的 ChatOptions 构建
    # 参考 useControlsState.ts 和 frontend/controls/constants/defaults.ts
    options = {
        # 基础选项
        "enableSearch": False,
        "enableThinking": False,  # image-chat-edit 模式通常不需要
        "enableCodeExecution": False,
        
        # 图片生成参数（来自 useControlsState）
        "imageAspectRatio": "1:1",      # DEFAULT_CONTROLS.aspectRatio
        "imageResolution": "1K",         # DEFAULT_CONTROLS.resolution
        "numberOfImages": 1,             # DEFAULT_CONTROLS.numberOfImages
        
        # 高级参数
        "outputMimeType": "image/png",   # DEFAULT_CONTROLS.outputMimeType
        # "outputCompressionQuality": 80,  # 仅 JPEG 时传递
        
        # ✅ 提示词增强功能（来自 ImageEditControls.tsx）
        "enhancePrompt": enhance_prompt,          # DEFAULT_CONTROLS.enhancePrompt
        # "enhancePromptModel": "gemini-2.0-flash",  # 可选：指定增强模型
        
        # 会话和消息 ID（用于附件关联）
        "frontendSessionId": session_id,
        "sessionId": session_id,         # 向后兼容
        "messageId": message_id,
    }
    
    # 如果启用提示词增强，可以指定增强模型
    if enhance_prompt:
        options["enhancePromptModel"] = "gemini-2.0-flash"  # 使用快速模型进行增强
    
    log_info("Options 结构:")
    for key, value in options.items():
        log_debug(key, value)
    
    # ==================== 构建最终请求体 ====================
    # 模拟 UnifiedProviderClient.executeMode() 中的 requestBody
    # ✅ 使用更独特的提示词来减少 IMAGE_RECITATION 错误
    # 参考: https://discuss.ai.google.dev/t/no-response-due-to-recitation-finishreason/3957
    unique_prompt = (
        "Transform this image by adding a vibrant, hand-painted watercolor border "
        "with soft pink and blue gradients. Make the border look artistic and organic, "
        "as if painted by a skilled artist. Keep the original image content intact."
    )
    
    request_body = {
        "modelId": MODEL_ID,
        "prompt": unique_prompt,  # 使用更独特的提示词
        "attachments": [attachment],
        "options": options,
    }
    
    log_info("最终请求体结构:")
    log_debug("modelId", request_body["modelId"])
    log_debug("prompt", request_body["prompt"][:80] + "...")  # 截断长提示词
    log_debug("attachments 数量", len(request_body["attachments"]))
    log_debug("options 字段数", len(request_body["options"]))
    log_debug("enhancePrompt", options["enhancePrompt"])
    
    return request_body


# ==================== Step 4: 发送请求 ====================
def step4_send_request(token: str, request_body: dict) -> dict:
    """
    发送 image-chat-edit 请求
    
    模拟 UnifiedProviderClient.executeMode() 的请求发送
    """
    log_step("Step 4", "发送 image-chat-edit 请求")
    
    url = f"{BASE_URL}/api/modes/google/image-chat-edit"
    
    # 构建请求头（模拟 UnifiedProviderClient 中的 headers）
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    log_info(f"请求 URL: {url}")
    log_info("请求头:")
    log_debug("Content-Type", headers["Content-Type"])
    log_debug("Authorization", f"Bearer {token[:30]}...")
    
    log_info("发送请求中... (可能需要 30-60 秒)")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            url,
            json=request_body,
            headers=headers,
            timeout=180  # 图片编辑可能需要较长时间，增加到 3 分钟
        )
        
        elapsed_time = time.time() - start_time
        
        log_info(f"响应状态码: {response.status_code}")
        log_info(f"耗时: {elapsed_time:.2f} 秒")
        
        # 尝试解析响应
        try:
            response_data = response.json()
        except:
            response_data = {"raw_text": response.text[:500]}
        
        if response.status_code == 200:
            log_success("请求成功!")
            return {"success": True, "data": response_data, "elapsed": elapsed_time}
        else:
            log_error(f"请求失败!")
            return {"success": False, "data": response_data, "elapsed": elapsed_time, "status": response.status_code}
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        log_error(f"请求超时 (耗时: {elapsed_time:.2f} 秒)")
        return {"success": False, "error": "timeout", "elapsed": elapsed_time}
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        log_error(f"请求异常: {e}")
        return {"success": False, "error": str(e), "elapsed": elapsed_time}


# ==================== Step 5: 分析响应 ====================
def step5_analyze_response(result: dict, enhance_prompt: bool = False):
    """
    分析响应结果
    
    检查返回的图片数据是否正确
    """
    log_step("Step 5", "分析响应结果")
    
    if not result.get("success"):
        log_error("请求失败，无法分析响应")
        log_info("错误详情:")
        if "error" in result:
            log_debug("error", result["error"])
        if "data" in result:
            error_data = result["data"]
            if isinstance(error_data, dict):
                detail = error_data.get("detail", "")
                if isinstance(detail, str) and len(detail) > 200:
                    log_debug("detail", detail[:200] + "...")
                else:
                    log_debug("detail", detail)
            else:
                log_debug("data", json.dumps(error_data, indent=2, ensure_ascii=False)[:500])
        if "status" in result:
            log_debug("status_code", result["status"])
        return False
    
    data = result.get("data", {})
    
    log_info("响应数据结构:")
    log_debug("类型", type(data).__name__)
    
    if isinstance(data, dict):
        log_debug("字段", list(data.keys()))
        
        # 检查是否有 success 字段（统一响应格式）
        if "success" in data:
            log_debug("success", data["success"])
        
        # 检查是否有 data 字段（嵌套数据）
        if "data" in data:
            inner_data = data["data"]
            log_info("内部数据结构:")
            log_debug("类型", type(inner_data).__name__)
            
            if isinstance(inner_data, dict) and "images" in inner_data:
                images = inner_data["images"]
                log_success(f"找到 {len(images)} 张图片!")
                
                for i, img in enumerate(images):
                    log_info(f"图片 {i+1}:")
                    
                    # 基本信息
                    url = img.get("url", "N/A")
                    if url and url.startswith("data:"):
                        log_debug("url", f"[Base64 Data URL, 长度: {len(url)} 字符]")
                    else:
                        log_debug("url", url)
                    log_debug("mimeType", img.get("mimeType", "N/A"))
                    log_debug("attachmentId", img.get("attachmentId", "N/A"))
                    log_debug("uploadStatus", img.get("uploadStatus", "N/A"))
                    
                    # 检查是否有 thoughts（思考过程）
                    if img.get("thoughts"):
                        log_debug("thoughts", f"{len(img['thoughts'])} 个思考步骤")
                        for j, thought in enumerate(img['thoughts'][:3]):  # 只显示前3个
                            thought_type = thought.get('type', 'unknown')
                            thought_content = thought.get('content', '')
                            if len(thought_content) > 100:
                                thought_content = thought_content[:100] + "..."
                            log_debug(f"  thought[{j}]", f"[{thought_type}] {thought_content}")
                    
                    # 检查是否有 text（文本响应）
                    if img.get("text"):
                        text = img["text"]
                        log_debug("text", text[:150] + "..." if len(text) > 150 else text)
                    
                    # ✅ 检查是否有 enhancedPrompt（增强后的提示词）
                    if img.get("enhancedPrompt"):
                        enhanced = img["enhancedPrompt"]
                        log_success(f"提示词增强成功!")
                        log_debug("enhancedPrompt", enhanced[:200] + "..." if len(enhanced) > 200 else enhanced)
                    elif enhance_prompt:
                        log_warning("启用了提示词增强，但响应中没有 enhancedPrompt")
                
                return True
            
            elif isinstance(inner_data, list):
                log_success(f"找到 {len(inner_data)} 个结果!")
                for i, item in enumerate(inner_data):
                    log_info(f"结果 {i+1}:")
                    if isinstance(item, dict):
                        log_debug("url", item.get("url", "N/A"))
                        log_debug("mimeType", item.get("mimeType", "N/A"))
                return True
    
    elif isinstance(data, list):
        log_success(f"找到 {len(data)} 个结果!")
        for i, item in enumerate(data):
            log_info(f"结果 {i+1}:")
            if isinstance(item, dict):
                log_debug("url", item.get("url", "N/A"))
                log_debug("mimeType", item.get("mimeType", "N/A"))
        return True
    
    log_error("无法解析响应数据结构")
    log_debug("原始数据", json.dumps(data, indent=2, ensure_ascii=False)[:500])
    return False


# ==================== 主函数 ====================
def main():
    """
    运行完整的端到端测试
    """
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='image-chat-edit 端到端测试')
    parser.add_argument('--enhance', action='store_true', help='启用提示词增强功能测试')
    parser.add_argument('--prompt', type=str, default="Add a simple red border around this image", 
                        help='自定义提示词')
    args = parser.parse_args()
    
    enhance_prompt = args.enhance
    
    print("\n" + "="*60)
    print("  image-chat-edit 端到端测试")
    print("  模拟前端完整流程")
    if enhance_prompt:
        print("  ✨ 提示词增强: 已启用")
    print("="*60)
    
    # Step 1: 登录
    token = step1_login()
    
    # Step 2: 下载测试图片
    image_data_url, mime_type = step2_download_test_image()
    
    # Step 3: 构建请求
    request_body = step3_build_request(image_data_url, mime_type, enhance_prompt)
    
    # 如果指定了自定义提示词
    if args.prompt != "Add a simple red border around this image":
        request_body["prompt"] = args.prompt
        log_info(f"使用自定义提示词: {args.prompt}")
    
    # Step 4: 发送请求
    result = step4_send_request(token, request_body)
    
    # Step 5: 分析响应
    success = step5_analyze_response(result, enhance_prompt)
    
    # 总结
    print("\n" + "="*60)
    print("  测试总结")
    print("="*60)
    
    if success:
        log_success("端到端测试通过!")
        if enhance_prompt:
            log_info("提示词增强功能测试完成")
    else:
        log_error("端到端测试失败!")
        log_info("请检查后端日志获取更多信息")
        log_info("常见问题:")
        log_info("  1. IMAGE_RECITATION 错误 - 这是版权保护机制，不是安全过滤器")
        log_info("     解决方案: 使用流式响应、更高的 temperature、更独特的提示词")
        log_info("  2. 图片未提取 - 检查 inline_data 处理逻辑")
        log_info("  3. 超时 - 增加请求超时时间")
    
    print("\n")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
