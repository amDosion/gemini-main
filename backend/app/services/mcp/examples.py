"""
MCP 服务使用示例

展示如何使用 MCP 客户端和管理器
"""

import asyncio
from .types import MCPServerConfig, MCPServerType
from .client import MCPClient
from ..mcp_manager import MCPManager


async def example_basic_usage():
    """示例 1：基本用法（直接使用客户端）"""
    print("\n=== 示例 1：基本用法 ===\n")

    # 配置 MCP 服务器（stdio 模式）
    config = MCPServerConfig(
        server_type=MCPServerType.STDIO,
        command="node",  # 或 "python"
        args=["path/to/mcp-server.js"],  # 或 ["mcp_server.py"]
        timeout=30.0
    )

    # 使用上下文管理器自动管理连接
    async with MCPClient(config) as client:
        # 1. 列出所有可用工具
        tools = await client.list_tools()
        print(f"可用工具数量: {len(tools)}")

        for tool in tools:
            print(f"\n工具名称: {tool.name}")
            print(f"描述: {tool.description}")
            print(f"参数 Schema: {tool.input_schema}")

        # 2. 调用工具
        if tools:
            result = await client.call_tool(
                tool_name=tools[0].name,
                arguments={"param1": "value1"}
            )

            if result.success:
                print(f"\n工具调用成功！")
                print(f"结果: {result.result}")
            else:
                print(f"\n工具调用失败: {result.error}")


async def example_manager_usage():
    """示例 2：使用 MCPManager（推荐）"""
    print("\n=== 示例 2：使用 MCPManager ===\n")

    manager = MCPManager()

    # 配置
    config = MCPServerConfig(
        server_type=MCPServerType.STDIO,
        command="node",
        args=["weather-server.js"]
    )

    try:
        # 1. 创建会话
        await manager.create_session("weather-session", config)
        print("会话已创建")

        # 2. 获取工具列表
        tools = await manager.list_tools("weather-session")
        print(f"\n可用工具: {[t.name for t in tools]}")

        # 3. 调用工具
        result = await manager.call_tool(
            session_id="weather-session",
            tool_name="get_weather",
            arguments={"location": "Beijing"}
        )

        if result.success:
            print(f"\n天气信息: {result.result}")
        else:
            print(f"\n错误: {result.error}")

    finally:
        # 4. 关闭会话
        await manager.close_session("weather-session")
        print("\n会话已关闭")


async def example_gemini_integration():
    """示例 3：Gemini 集成"""
    print("\n=== 示例 3：Gemini 集成 ===\n")

    manager = MCPManager()

    config = MCPServerConfig(
        server_type=MCPServerType.STDIO,
        command="node",
        args=["tools-server.js"]
    )

    try:
        # 创建会话
        await manager.create_session("gemini-tools", config)

        # 获取 Gemini 格式的工具
        gemini_tools = await manager.get_gemini_tools("gemini-tools")

        print(f"Gemini 工具格式:")
        import json
        print(json.dumps(gemini_tools, indent=2, ensure_ascii=False))

        # 在 Gemini API 中使用
        # model = genai.GenerativeModel(
        #     model_name="gemini-2.0-flash-exp",
        #     tools=gemini_tools
        # )

    finally:
        await manager.close_session("gemini-tools")


async def example_openai_integration():
    """示例 4：OpenAI 集成"""
    print("\n=== 示例 4：OpenAI 集成 ===\n")

    manager = MCPManager()

    config = MCPServerConfig(
        server_type=MCPServerType.STDIO,
        command="python",
        args=["calculator_server.py"]
    )

    try:
        await manager.create_session("openai-tools", config)

        # 获取 OpenAI 格式的工具
        openai_tools = await manager.get_openai_tools("openai-tools")

        print(f"OpenAI 工具格式:")
        import json
        print(json.dumps(openai_tools, indent=2, ensure_ascii=False))

        # 在 OpenAI API 中使用
        # response = openai.ChatCompletion.create(
        #     model="gpt-4",
        #     tools=openai_tools
        # )

    finally:
        await manager.close_session("openai-tools")


async def example_session_pool():
    """示例 5：会话池管理"""
    print("\n=== 示例 5：会话池管理 ===\n")

    manager = MCPManager()

    # 创建多个会话
    configs = [
        ("weather", MCPServerConfig(
            server_type=MCPServerType.STDIO,
            command="node",
            args=["weather-server.js"]
        )),
        ("calculator", MCPServerConfig(
            server_type=MCPServerType.STDIO,
            command="python",
            args=["calculator_server.py"]
        )),
    ]

    try:
        # 批量创建
        for session_id, config in configs:
            await manager.create_session(session_id, config)
            print(f"已创建会话: {session_id}")

        # 列出所有会话
        sessions = manager.list_sessions()
        print(f"\n活跃会话: {sessions}")

        # 分别使用
        weather_tools = await manager.list_tools("weather")
        calc_tools = await manager.list_tools("calculator")

        print(f"\nWeather 工具: {[t.name for t in weather_tools]}")
        print(f"Calculator 工具: {[t.name for t in calc_tools]}")

    finally:
        # 关闭所有会话
        await manager.close_all()
        print("\n所有会话已关闭")


async def example_context_manager():
    """示例 6：使用上下文管理器"""
    print("\n=== 示例 6：上下文管理器 ===\n")

    manager = MCPManager()

    config = MCPServerConfig(
        server_type=MCPServerType.STDIO,
        command="node",
        args=["server.js"]
    )

    # 自动创建和清理
    async with manager.session("auto-session", config) as client:
        tools = await client.list_tools()
        print(f"工具列表: {[t.name for t in tools]}")

        result = await client.call_tool("echo", {"message": "Hello MCP!"})
        print(f"结果: {result.result}")

    # 会话自动关闭
    print("会话已自动关闭")


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("MCP 服务使用示例")
    print("=" * 60)

    try:
        # await example_basic_usage()
        # await example_manager_usage()
        # await example_gemini_integration()
        # await example_openai_integration()
        # await example_session_pool()
        await example_context_manager()

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
