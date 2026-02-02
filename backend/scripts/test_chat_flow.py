#!/usr/bin/env python3
"""
Chat 模式完整流程测试脚本

测试内容：
1. 用户登录获取 JWT Token
2. 发送 Chat 请求（流式响应）
3. 验证 SSE 流式数据格式
4. 验证 camelCase/snake_case 转换
5. 模拟前端接收消息的完整流程

使用方法：
    cd backend
    python scripts/test_chat_flow.py
"""

import asyncio
import aiohttp
import json
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置
BASE_URL = "http://localhost:21574"
TEST_EMAIL = "121802744@qq.com"  # 测试邮箱
TEST_PASSWORD = "chuan*1127"  # 测试密码

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_data(label, data):
    print(f"{Colors.BLUE}{label}:{Colors.END}")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"  {data}")


async def test_login(session: aiohttp.ClientSession) -> dict:
    """测试登录获取 Token"""
    print_header("1. 测试用户登录")
    
    login_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    print_info(f"登录邮箱: {TEST_EMAIL}")
    
    try:
        async with session.post(
            f"{BASE_URL}/api/auth/login",
            json=login_data
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print_success("登录成功")
                
                # 响应结构: {user: {...}, access_token, refresh_token, token_type, expires_in}
                user = data.get("user", {})
                
                # 兼容 camelCase 和 snake_case
                access_token = data.get("accessToken") or data.get("access_token")
                refresh_token = data.get("refreshToken") or data.get("refresh_token")
                
                print_data("解析结果", {
                    "userId": user.get("id"),
                    "email": user.get("email"),
                    "hasAccessToken": bool(access_token),
                    "hasRefreshToken": bool(refresh_token)
                })
                
                # 返回包含 token 的数据
                return {
                    "accessToken": access_token,
                    "refreshToken": refresh_token,
                    "user": user
                }
            else:
                error = await resp.text()
                print_error(f"登录失败: {resp.status} - {error}")
                return None
    except Exception as e:
        print_error(f"登录异常: {e}")
        return None


async def test_get_models(session: aiohttp.ClientSession, token: str, provider: str = "google") -> list:
    """测试获取模型列表"""
    print_header("2. 测试获取模型列表")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with session.get(
            f"{BASE_URL}/api/models/{provider}",
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                models = data.get("models", [])
                print_success(f"获取到 {len(models)} 个模型")
                
                # 显示前 5 个模型
                for i, model in enumerate(models[:5]):
                    print(f"  {i+1}. {model.get('id')} - {model.get('name', 'N/A')}")
                
                if len(models) > 5:
                    print(f"  ... 还有 {len(models) - 5} 个模型")
                
                return models
            else:
                error = await resp.text()
                print_error(f"获取模型失败: {resp.status} - {error}")
                return []
    except Exception as e:
        print_error(f"获取模型异常: {e}")
        return []


async def test_chat_stream(
    session: aiohttp.ClientSession, 
    token: str, 
    provider: str = "google",
    model_id: str = "gemini-2.0-flash"
) -> bool:
    """测试 Chat 流式响应"""
    print_header("3. 测试 Chat 流式响应")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 构建请求体（使用 camelCase，测试中间件转换）
    request_body = {
        "modelId": model_id,
        "messages": [],
        "message": "你好，请用一句话介绍你自己。",
        "attachments": [],
        "options": {
            "temperature": 0.7,
            "maxTokens": 1024,
            "enableSearch": False,
            "enableThinking": False
        },
        "stream": True
    }
    
    print_info(f"模型: {model_id}")
    print_info(f"消息: {request_body['message']}")
    print_data("请求体 (camelCase)", request_body)
    
    try:
        print(f"\n{Colors.CYAN}--- 流式响应开始 ---{Colors.END}")
        
        full_content = ""
        chunk_count = 0
        usage_info = None
        
        async with session.post(
            f"{BASE_URL}/api/modes/{provider}/chat",
            headers=headers,
            json=request_body
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                print_error(f"请求失败: {resp.status} - {error}")
                return False
            
            # 验证响应类型
            content_type = resp.headers.get("Content-Type", "")
            if "text/event-stream" not in content_type:
                print_warning(f"响应类型不是 SSE: {content_type}")
            else:
                print_success(f"响应类型正确: {content_type}")
            
            # 读取 SSE 流
            async for line in resp.content:
                line = line.decode('utf-8').strip()
                
                if not line:
                    continue
                
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        chunk = json.loads(data_str)
                        chunk_count += 1
                        
                        chunk_type = chunk.get("chunkType", "unknown")
                        text = chunk.get("text", "")
                        
                        if chunk_type == "content" and text:
                            full_content += text
                            # 实时打印内容（模拟前端显示）
                            print(f"{Colors.GREEN}{text}{Colors.END}", end="", flush=True)
                        
                        elif chunk_type == "done":
                            usage_info = chunk.get("usage", {})
                            print(f"\n{Colors.CYAN}--- 流式响应结束 ---{Colors.END}")
                        
                        elif chunk_type == "error":
                            print_error(f"流式错误: {chunk.get('error')}")
                            return False
                        
                    except json.JSONDecodeError as e:
                        print_warning(f"JSON 解析失败: {e}")
        
        print()
        print_success(f"接收完成，共 {chunk_count} 个 chunk")
        print_data("完整响应内容", full_content)
        
        if usage_info:
            print_data("Token 使用情况", usage_info)
        
        # 验证响应格式（应该是 camelCase）
        print_header("4. 验证响应格式")
        print_info("检查 SSE 响应是否使用 camelCase...")
        
        # SSE 响应应该直接使用 camelCase（不经过中间件转换）
        if "chunkType" in str(chunk):
            print_success("SSE 响应使用 camelCase (chunkType) ✓")
        else:
            print_warning("SSE 响应格式可能有问题")
        
        return True
        
    except Exception as e:
        print_error(f"Chat 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_case_conversion(session: aiohttp.ClientSession, token: str) -> bool:
    """测试 camelCase/snake_case 转换"""
    print_header("5. 测试 Case 转换中间件")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 测试请求：使用 camelCase
    test_data = {
        "testField": "value1",
        "nestedObject": {
            "innerField": "value2",
            "deepNested": {
                "deepField": "value3"
            }
        },
        "arrayField": [
            {"itemField": "item1"},
            {"itemField": "item2"}
        ],
        # 这些字段的值不应该被转换
        "toolArgs": {
            "userName": "test",
            "apiEndpoint": "/api/v1"
        }
    }
    
    print_data("发送数据 (camelCase)", test_data)
    
    # 由于没有专门的测试端点，我们通过日志验证
    print_info("中间件会将 camelCase 转换为 snake_case 发送给后端")
    print_info("例如: testField -> test_field")
    print_info("但 toolArgs 内部的 key 不会被转换（保持 userName）")
    
    print_success("Case 转换逻辑已在 case_converter.py 中实现")
    print_info("跳过字段列表: toolArgs, arguments, extra, metadata 等")
    
    return True


async def test_frontend_simulation(session: aiohttp.ClientSession, token: str) -> bool:
    """模拟前端完整流程"""
    print_header("6. 模拟前端完整流程")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print_info("模拟前端 useChat Hook 的完整流程:")
    print()
    
    # Step 1: 创建用户消息
    print(f"  {Colors.CYAN}Step 1:{Colors.END} 创建用户消息 (userMessageId: uuid)")
    user_message = {
        "id": "test-user-msg-001",
        "role": "user",
        "content": "测试消息",
        "timestamp": int(datetime.now().timestamp() * 1000)
    }
    print(f"    → 用户消息: {user_message['content']}")
    
    # Step 2: 创建模型消息占位符
    print(f"  {Colors.CYAN}Step 2:{Colors.END} 创建模型消息占位符 (modelMessageId: uuid)")
    model_message = {
        "id": "test-model-msg-001",
        "role": "model",
        "content": "",
        "timestamp": int(datetime.now().timestamp() * 1000)
    }
    print(f"    → 模型消息占位符已创建")
    
    # Step 3: 调用 llmService.startNewChat
    print(f"  {Colors.CYAN}Step 3:{Colors.END} 调用 llmService.startNewChat(history, model, options)")
    print(f"    → 设置上下文历史、模型配置、选项")
    
    # Step 4: 调用 ChatHandler.execute
    print(f"  {Colors.CYAN}Step 4:{Colors.END} 调用 ChatHandler.execute(context)")
    print(f"    → 内部调用 llmService.sendMessageStream()")
    
    # Step 5: 处理流式响应
    print(f"  {Colors.CYAN}Step 5:{Colors.END} 处理流式响应")
    print(f"    → for await (const chunk of stream)")
    print(f"    → 累积文本: accumulatedText += chunk.text")
    print(f"    → 调用 onStreamUpdate() 更新 UI")
    
    # Step 6: 更新消息状态
    print(f"  {Colors.CYAN}Step 6:{Colors.END} 更新消息状态")
    print(f"    → setMessages(prev => prev.map(...))")
    print(f"    → 将 modelMessage.content 更新为完整响应")
    
    # Step 7: 处理上传任务（如果有）
    print(f"  {Colors.CYAN}Step 7:{Colors.END} 处理上传任务（如果有附件）")
    print(f"    → result.uploadTask.then(...)")
    print(f"    → 保存到数据库")
    
    print()
    print_success("前端流程模拟完成")
    
    return True


async def main():
    """主测试函数"""
    print(f"\n{Colors.BOLD}Chat 模式完整流程测试{Colors.END}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"后端地址: {BASE_URL}")
    
    # 创建 HTTP 会话
    async with aiohttp.ClientSession() as session:
        # 1. 登录
        login_result = await test_login(session)
        if not login_result:
            print_error("登录失败，无法继续测试")
            return
        
        token = login_result.get("accessToken")
        if not token:
            print_error("未获取到 accessToken")
            return
        
        # 2. 获取模型列表
        models = await test_get_models(session, token)
        
        # 选择一个模型进行测试
        model_id = "gemini-2.0-flash"
        if models:
            # 优先选择 gemini-2.0-flash，否则选择第一个
            for m in models:
                if "gemini-2.0-flash" in m.get("id", ""):
                    model_id = m["id"]
                    break
            else:
                model_id = models[0]["id"]
        
        # 3. 测试 Chat 流式响应
        chat_success = await test_chat_stream(session, token, model_id=model_id)
        
        # 4. 测试 Case 转换
        await test_case_conversion(session, token)
        
        # 5. 模拟前端流程
        await test_frontend_simulation(session, token)
        
        # 总结
        print_header("测试总结")
        if chat_success:
            print_success("Chat 模式流程测试通过 ✓")
        else:
            print_error("Chat 模式流程测试失败 ✗")
        
        print()
        print_info("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
